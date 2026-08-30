# -*- coding: utf-8 -*-
"""市場を使わない木を、事実の成分だけで高める。

前走人気（市場由来）を抜いた47成分を土台に、残差検定で信号が確認済みの
事実成分を足す。すべて過去走・当日発表の事実で、市場（人気・オッズ）は使わない。

  F1 前走が道悪だったか        前走の馬場が良以外なら1。道悪の大敗を度外視する手掛かり
  F2 良馬場に限った近2走の着順比  道悪の大敗を除いた「素の近走」
  F3 道悪での通算3着内率        今回が道悪のとき、過去の道悪での実績
  F4 馬体重の増減            bwd。＋大幅増は減点・−大幅減は加点（残差 t で確認済み）
  F5 馬体重の増減の絶対値        変化の大きさ（符号と別に）

比較:
  木47（現状・市場なし）
  木47 + 上の事実成分
  参考: 市場（1番人気）

的中率だけでなく、月ごとの3着内率のばらつき（安定性）でも見る。

窓は explore.py と同じ。未知期間には触れない。

  python facts_boost.py
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
from boost import XPARAMS, to_matrix, build  # noqa: E402

OUT = "weights/facts_boost.json"
NAN = float("nan")
SEV = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
NEW = ["前走道悪", "良馬場近2走の着順比", "道悪3着内率", "馬体重増減", "増減の絶対値"]


def facts(book, ri, hi):
    r = book.races[ri]
    h = r["rows"][hi]
    P = book.past(ri, hi, 9)
    last = P[0] if P else None
    g = SEV.get(r["ground"], 3)

    f1 = NAN
    if last:
        f1 = 1.0 if SEV.get(last["r"]["ground"], 0) >= 1 else 0.0

    # 良馬場に限った近2走の着順比
    good2 = [q for q in P[:3] if SEV.get(q["r"]["ground"], 0) == 0 and q["pos"]][:2]
    f2 = float(np.mean([q["pos"] / q["r"]["n"] for q in good2])) if good2 else NAN

    # 今回が道悪のときだけ、過去の道悪3着内率
    if g >= 1:
        wet = [q for q in P if q["ago"] <= 365 and SEV.get(q["r"]["ground"], 0) >= 1 and q["pos"]]
        f3 = float(np.mean([q["pos"] <= 3 for q in wet])) if wet else NAN
    else:
        f3 = NAN

    f4 = float(h["bwd"]) if h["bw"] > 0 else NAN
    f5 = float(abs(h["bwd"])) if h["bw"] > 0 else NAN
    return [f1, f2, f3, f4, f5]


def build_ex(book, b, lo, hi, val, add):
    DS = []
    for ri, r in enumerate(book.races):
        if lo <= r["date"] < hi:
            d = b.build_wide(ri)
            Z = [list(x) for x in d["Z"]]
            mm = val.get(r["id"]) or {}
            col = train_eval.znorm_column(
                [mm.get(str(x["umaban"]), NAN) for x in r["rows"]])
            for row, x in zip(Z, col):
                row.append(x)
            if add:
                for k, row in enumerate(Z):
                    row.extend(facts(book, ri, k))
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS


def fit(TR, names):
    TRs = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=names); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=names); dv.set_group(gb)
    m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    n = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    d = xgb.DMatrix(X, label=y, feature_names=names); d.set_group(g)
    return xgb.train(XPARAMS, d, num_boost_round=n), n


def report(EXP, model, names, pays):
    by_month = defaultdict(lambda: [0, 0])
    win = i3 = n = 0
    tan, fuku = [], []
    for d in EXP:
        r = d["race"]
        s = model.predict(xgb.DMatrix(np.asarray(d["Z"], np.float32)[:, :len(names)],
                                      feature_names=names))
        i = int(np.argmax(s))
        h = r["rows"][i]
        f = _fin(h["fin"])
        n += 1
        win += (f == 1)
        i3 += (f is not None and f <= 3)
        mo = r["date"][4:6]
        by_month[mo][1] += 1
        by_month[mo][0] += (f is not None and f <= 3)
        p = pays.get(r["id"])
        if p:
            tan.append(dict(p.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0)
            fuku.append(dict(p.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0)
    rates = [c[0] / c[1] * 100 for c in by_month.values() if c[1] >= 30]
    return {"win": win / n * 100, "in3": i3 / n * 100,
            "tan": float(np.mean(tan) * 100), "fuku": float(np.mean(fuku) * 100),
            "m_sd": float(np.std(rates)), "m_min": float(min(rates))}


def main():
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)
    st = Store(config.DB_PATH)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    base = list(b.wide_names) + [train_eval.NAME]
    FIT = build_ex(book, b, config.CUT_HIST, CUT_EXPLORE, val, True)
    EXP = build_ex(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True)

    pop = base.index("前走人気")
    nopop = [i for i in range(len(base)) if i != pop]     # 市場由来を抜く
    full = base + NEW
    nopop_full = nopop + list(range(len(base), len(base) + len(NEW)))

    def cut_cols(DS, cols):
        return [dict(d, Z=np.asarray(d["Z"])[:, cols]) for d in DS]

    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R\n", flush=True)
    res = []

    # 木47（現状・市場なし）
    nm = [base[i] for i in nopop]
    m, r1 = fit(cut_cols(FIT, nopop), nm)
    res.append(("木47（現状・市場なし）", report(cut_cols(EXP, nopop), m, nm, pays), r1))

    # 木47 + 事実成分
    nm2 = [full[i] for i in nopop_full]
    m2, r2 = fit(cut_cols(FIT, nopop_full), nm2)
    rep2 = report(cut_cols(EXP, nopop_full), m2, nm2, pays)
    res.append((f"木47 + 事実{len(NEW)}成分", rep2, r2))

    print(f'{"":<24}{"1着":>8}{"3着内":>9}{"単勝":>8}{"複勝":>8}{"月SD":>7}{"最低月":>8}{"木":>6}')
    for lab, r, nb in res:
        print(f'{lab:<24}{r["win"]:>7.2f}%{r["in3"]:>8.2f}%{r["tan"]:>7.1f}%'
              f'{r["fuku"]:>7.1f}%{r["m_sd"]:>7.2f}{r["m_min"]:>7.1f}%{nb:>6}')
    print(f'{"市場（1番人気）":<24}{"—":>8}{"65.28%":>9}{"76.3%":>8}{"83.8%":>8}')

    imp = m2.get_score(importance_type="gain")
    tot = sum(imp.values()) or 1
    rank = {n: i + 1 for i, (n, _v) in enumerate(sorted(imp.items(), key=lambda x: -x[1]))}
    print(f"\n足した事実成分の順位（全{len(rank)}成分中）")
    for n in NEW:
        print(f"  {n:<20}" + (f"{rank[n]:>2}位  寄与 {imp[n]/tot*100:.2f}%"
                              if n in imp else "使われず"))

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "results": [{"label": l, **r, "rounds": nb} for l, r, nb in res],
               "importance": {n: round(imp.get(n, 0) / tot * 100, 2) for n in NEW}},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
