# -*- coding: utf-8 -*-
"""理由のあるパターンを並べて測る。

mine_conditions.py は総当たりで、2,688通り引けば偶然でも150%台のマスが出ると
分かった。ここは逆で、**先に理由を書いてから測る**。数を絞るぶん、当たれば
偶然では説明しにくい。

パターンは3系統。

  A 市場だけ（モデルを使わない）
     人気順位ごとの回収率。市場そのものが歪んでいる場所があるなら、
     モデルの良し悪しと関係なくそこにエッジがある。
     A1/A2 は全馬が対象なので本数が桁違いに多く、いちばん信頼できる。

  B モデルと市場のズレ
     モデルが市場と食い違う馬に賭ける。モデルが独立の情報を持つなら、
     食い違うところでこそ勝てるはず。

  C 調教評価
     厩舎短評という、文章で出ていてオッズに集約されにくい情報。
     重みも77.5と大きい。市場が拾い切れていないなら、ここに残る。

窓は explore.py と同じ。未知期間には触れない。

  python patterns.py
"""
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, build, _fin  # noqa: E402

OUT = "weights/patterns.json"
RNG = np.random.default_rng(20260830)


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}

    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    names = list(features.BASE_NAMES) + [train_eval.NAME]
    nf = len(features.BASE_NAMES)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True, nf)
    lv, _ = F.choose_level(FIT, names)
    m = F.Model().fit(FIT, names, verbose=False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True, nf)
    print(f"学習 {len(FIT)}R / 探索 {len(EXP)}R / 段階 {lv}\n", flush=True)

    # ── 1レース1件に整える。馬ごとの情報も持っておく
    races = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay or "複勝" not in pay:
            continue
        Z = np.asarray(d["Z"], float)
        sc = Z @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        sd = float(np.std(sc)) or 1.0
        tan = dict(pay.get("単勝", []))
        fuk = dict(pay.get("複勝", []))
        hs = []
        for i, h in enumerate(r["rows"]):
            if not h["pop"] or h["odds"] <= 0:
                continue
            hs.append({
                "um": h["umaban"], "pop": int(h["pop"]), "odds": h["odds"],
                "rank": o.index(i) + 1,                 # モデルの順位
                "tev": float(Z[i][-1]),                 # 調教評価のZ
                "tan": tan.get(str(h["umaban"]), 0) / 100.0,
                "fuku": fuk.get(str(h["umaban"]), 0) / 100.0,
            })
        if len(hs) < 5:
            continue
        hs.sort(key=lambda x: x["rank"])
        races.append({"hs": hs, "n": len(hs),
                      "g12": float((sc[o[0]] - sc[o[1]]) / sd) if len(sc) > 1 else 0.0})
    print(f"測れたレース {len(races)}R / 延べ {sum(r['n'] for r in races)}頭\n", flush=True)

    # ── パターン。sel はレースを受けて (買う馬のリスト, 券種) を返す。買わないなら空。
    def by_pop(k):
        return lambda R: ([h for h in R["hs"] if h["pop"] == k], "tan")

    def by_pop_f(k):
        return lambda R: ([h for h in R["hs"] if h["pop"] == k], "fuku")

    def agree(R):
        h = R["hs"][0]
        return ([h], "fuku") if h["pop"] <= 3 else ([], "fuku")

    def diverge(R):
        h = R["hs"][0]
        return ([h], "fuku") if h["pop"] >= 4 else ([], "fuku")

    def diverge_deep(R):
        h = R["hs"][0]
        return ([h], "fuku") if h["pop"] >= 6 else ([], "fuku")

    def tev_top_unpop(R):
        c = max(R["hs"], key=lambda x: x["tev"])
        return ([c], "fuku") if (c["tev"] >= 1.0 and c["pop"] >= 4) else ([], "fuku")

    def tev_top(R):
        c = max(R["hs"], key=lambda x: x["tev"])
        return ([c], "fuku") if c["tev"] >= 1.0 else ([], "fuku")

    def tev_gap(R):
        """調教評価が突出、かつモデル順位も3位以内、なのに人気は5番手以下。"""
        c = max(R["hs"], key=lambda x: x["tev"])
        ok = c["tev"] >= 1.0 and c["rank"] <= 3 and c["pop"] >= 5
        return ([c], "fuku") if ok else ([], "fuku")

    def strong_fav(R):
        h = R["hs"][0]
        return ([h], "tan") if (R["g12"] >= 1.0 and h["pop"] == 1) else ([], "tan")

    PATTERNS = [
        ("A1 1番人気の単勝", "市場の歪みを直に見る。人気馬が過小評価なら100%を越える", by_pop(1)),
        ("A2 2番人気の単勝", "同上", by_pop(2)),
        ("A3 3番人気の単勝", "同上", by_pop(3)),
        ("A4 1番人気の複勝", "複勝は別プール。単勝と歪みの向きが違うことがある", by_pop_f(1)),
        ("A5 2番人気の複勝", "同上", by_pop_f(2)),
        ("A6 3番人気の複勝", "同上", by_pop_f(3)),
        ("B1 モデル1位が3番人気以内の複勝", "市場と合意した馬。合意が精度を上げるなら効く", agree),
        ("B2 モデル1位が4番人気以下の複勝", "市場と食い違う馬。独立情報があるなら効く", diverge),
        ("B3 モデル1位が6番人気以下の複勝", "食い違いをさらに深く", diverge_deep),
        ("C1 調教評価が突出した馬の複勝", "短評はオッズに集約されにくい", tev_top),
        ("C2 調教評価が突出 かつ 4番人気以下", "短評が良いのに人気が無い＝市場が拾えていない", tev_top_unpop),
        ("C3 調教評価が突出 かつ モデル3位以内 かつ 5番人気以下", "上の条件を厳しく", tev_gap),
        ("D1 1強かつ1位が1番人気の単勝", "形がはっきりしたときだけ単勝を持つ", strong_fav),
    ]

    print(f'{"パターン":<38}{"R":>6}{"点数":>6}{"回収率":>8}{"±1SE":>7}{"t vs 80%":>9}')
    out = []
    for label, why, sel in PATTERNS:
        pay = []
        nr = 0
        for R in races:
            picks, kind = sel(R)
            if not picks:
                continue
            nr += 1
            for h in picks:
                pay.append(h[kind])
        if len(pay) < 30:
            print(f"{label:<38}{nr:>6}{len(pay):>6}   （本数が足りない）")
            continue
        a = np.array(pay)
        roi = a.mean() * 100
        se = a.std(ddof=1) / np.sqrt(len(a)) * 100
        t = (a.mean() - 0.80) / (a.std(ddof=1) / np.sqrt(len(a)))
        print(f"{label:<38}{nr:>6}{len(pay):>6}{roi:>7.1f}%{se:>7.1f}{t:>9.2f}")
        out.append({"pattern": label, "why": why, "races": nr, "bets": len(pay),
                    "roi": round(roi, 1), "se": round(se, 1), "t_vs_80": round(float(t), 2)})

    print("\nt は「控除率どおりの80%と違うか」。プラス方向に大きいほど市場より良い。")
    print(f"パターンは{len(PATTERNS)}個しか試していないので、"
          f"多重比較の補正は Bonferroni で t>{2.6 + 0.4:.1f} 相当を見ておけば足りる。")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "n_races": len(races),
               "level": lv, "patterns": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")
    print("ここは探索窓。100%を越えたものだけを未知期間で一度だけ試すこと。")


if __name__ == "__main__":
    main()
