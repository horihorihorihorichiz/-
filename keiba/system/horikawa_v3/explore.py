# -*- coding: utf-8 -*-
"""オッズを切り口にして、買える条件の候補を探す。

`backtest.py` は未知期間（CUT_VAL 以降）で測るもので、あそこで思いついた条件を
足していくと未知期間が汚れる。ここは探索専用で、**未知期間には一切触れない**。

窓の切り方:

    CUT_HIST ────── CUT_EXPLORE ────── CUT_EMBARGO ─ CUT_VAL ──────
    │  配点を学習する  │  条件を探す      │            │  最終判定用   │
    │  3,213R        │  1,866R        │            │  （触らない） │

配点も調教評価も CUT_EXPLORE より前だけで作り直すので、探索窓は
重みにとって未知になる。ここで見つけた候補を、あとで一度だけ CUT_VAL 以降に
かけて採否を決める。それが plus_fires.json になる。

  python explore.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402

EVAL_RAW = "../../data/hk_train_raw.json"
CUT_EXPLORE = "20250801"
OUT = "weights/explore_odds.json"

# オッズを軸にした切り口。d は1レース1件の辞書。
# pick はそのレースで買う馬（無ければ見送り）。
CUTS = [
    ("モデル1位を買う（全体）", lambda d: True, "top"),
    ("　うち1位=1番人気", lambda d: d["pop1"] == 1, "top"),
    ("　うち1位≠1番人気", lambda d: d["pop1"] != 1, "top"),
    ("　1位が2〜3番人気", lambda d: 2 <= d["pop1"] <= 3, "top"),
    ("　1位が4〜6番人気", lambda d: 4 <= d["pop1"] <= 6, "top"),
    ("　1位が7番人気以下", lambda d: d["pop1"] >= 7, "top"),
    ("上位3頭の最人気薄が10倍超", lambda d: d["odds3"] >= 10, "long3"),
    ("1位が人気薄かつ1強", lambda d: d["pop1"] >= 4 and d["g12"] >= 1.0, "top"),
]


def _fin(x):
    try:
        return int(x)
    except Exception:
        return None


def build(book, b, lo, hi, val, use_tev, nf):
    """[lo, hi) のレースを成分つきで返す。b は呼び出し前の状態から進める。"""
    DS = []
    for ri, r in enumerate(book.races):
        if lo <= r["date"] < hi:
            d = b.build_wide(ri)
            Z = [list(x[:nf]) for x in d["Z"]]
            if use_tev:
                mm = (val.get(r["id"]) or {})
                col = train_eval.znorm_column(
                    [mm.get(str(h["umaban"]), float("nan")) for h in r["rows"]])
                for row, x in zip(Z, col):
                    row.append(x)
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS


def main():
    st = Store(config.DB_PATH)

    # 調教評価も探索窓より前だけで学ぶ（探索窓に漏らさない）
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, info = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)
    print(f"調教評価: {info['語数']}語 / 学習{info['レース数']}R (date<{CUT_EXPLORE})")

    names = list(features.BASE_NAMES) + [train_eval.NAME]
    nf = len(features.BASE_NAMES)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)

    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True, nf)
    print(f"配点の学習 {len(FIT)}R ({config.CUT_HIST}〜{CUT_EXPLORE})")
    lv, _tab = F.choose_level(FIT, names)
    m = F.Model().fit(FIT, names, verbose=False)
    print(f"内側検証が選んだ段階: {lv}")

    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True, nf)
    print(f"条件を探す窓 {len(EXP)}R ({CUT_EXPLORE}〜{config.CUT_EMBARGO})\n")

    rows = []
    for d in EXP:
        r = d["race"]
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        sd = float(np.std(sc)) or 1.0
        top = r["rows"][o[0]]
        if top["odds"] <= 0 or not top["pop"]:
            continue
        fav = min(r["rows"], key=lambda h: h["odds"] if h["odds"] > 0 else 1e9)
        # モデル上位3頭のうち、いちばん人気の無い馬
        cand = [r["rows"][i] for i in o[:3] if r["rows"][i]["odds"] > 0]
        long3 = max(cand, key=lambda h: h["odds"]) if cand else top
        rows.append({
            "top": (top["odds"], _fin(top["fin"]) == 1),
            "long3": (long3["odds"], _fin(long3["fin"]) == 1),
            "fav": (fav["odds"], _fin(fav["fin"]) == 1),
            "pop1": int(top["pop"]), "odds1": top["odds"], "odds3": long3["odds"],
            "g12": float((sc[o[0]] - sc[o[1]]) / sd) if len(sc) > 1 else 0.0,
        })

    print(f'{"切り口":<26}{"R":>6}{"的中":>7}{"回収率":>8}{"±1SE":>7}{"1番人気":>8}{"差":>7}{"t":>6}')
    out = []
    for label, f, key in CUTS:
        s = [d for d in rows if f(d)]
        if len(s) < 30:
            print(f"{label:<26}{len(s):>6}   （本数が足りないので測らない）")
            continue
        n = len(s)
        pay = np.array([(d[key][0] if d[key][1] else 0.0) for d in s])
        fpay = np.array([(d["fav"][0] if d["fav"][1] else 0.0) for d in s])
        diff = pay - fpay
        se = pay.std(ddof=1) / np.sqrt(n)
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(n)) if diff.std(ddof=1) else 0.0
        hit = float((pay > 0).mean())
        print(f"{label:<26}{n:>6}{hit*100:>6.1f}%{pay.mean()*100:>7.1f}%"
              f"{se*100:>6.1f}{fpay.mean()*100:>7.1f}%{(pay.mean()-fpay.mean())*100:>+7.1f}{t:>6.2f}")
        out.append({"cut": label.strip(), "bet": key, "n": n, "hit": round(hit * 100, 1),
                    "roi": round(pay.mean() * 100, 1), "se": round(se * 100, 1),
                    "fav_roi": round(fpay.mean() * 100, 1), "t_vs_fav": round(float(t), 2)})

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": {"fit": [config.CUT_HIST, CUT_EXPLORE],
                          "explore": [CUT_EXPLORE, config.CUT_EMBARGO],
                          "untouched": [config.CUT_VAL, "-"]},
               "level": lv, "n_fit": len(FIT), "n_explore": len(EXP), "cuts": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")
    print("控除率20%。回収率100%を越えない限り買う理由にならない。")
    print("ここは探索窓。採否は CUT_VAL 以降で一度だけ測って決めること。")


if __name__ == "__main__":
    main()
