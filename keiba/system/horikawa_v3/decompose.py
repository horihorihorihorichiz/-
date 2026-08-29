# -*- coding: utf-8 -*-
"""人気を固定して、システム評価だけを動かす。

「2番人気の複勝が88%」は市場を買っているだけで、システムを一切使っていない。
知りたいのはそこではなく、**同じ人気の馬の中で、システムが上と言った馬と
下と言った馬に差があるか**。差があるなら、システムは市場に情報を足している。
無いなら足していない。

やること:

  1 モデル順位ごとの成績（1位、2位、…）
  2 人気帯 × モデル評価 の2元表。人気を固定した各行で、
    システム上位と下位の3着内率・複勝回収率を比べる
  3 その差を検定する。これがシステムの正味の貢献

窓は explore.py と同じ。未知期間には触れない。

  python decompose.py
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

OUT = "weights/decompose.json"

POPS = [("1番人気", 1, 1), ("2番人気", 2, 2), ("3番人気", 3, 3),
        ("4-6番人気", 4, 6), ("7-9番人気", 7, 9), ("10番人気以下", 10, 99)]


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

    H = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay or "複勝" not in pay:
            continue
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        rank = {i: k + 1 for k, i in enumerate(o)}
        fuk = dict(pay.get("複勝", []))
        tan = dict(pay.get("単勝", []))
        n = len(sc)
        for i, h in enumerate(r["rows"]):
            if not h["pop"] or h["odds"] <= 0:
                continue
            f = _fin(h["fin"])
            H.append({
                "pop": int(h["pop"]), "rank": rank[i], "n": n,
                "pct": (rank[i] - 0.5) / n,               # レース内でのモデル順位（0が上位）
                "odds": h["odds"],
                "in3": bool(f is not None and f <= 3),
                "fuku": fuk.get(str(h["umaban"]), 0) / 100.0,
                "tan": tan.get(str(h["umaban"]), 0) / 100.0,
            })
    print(f"延べ {len(H)}頭\n", flush=True)

    # ── 1 モデル順位ごと
    print("── モデル順位ごと（人気は混ぜたまま）")
    print(f'  {"順位":<8}{"頭数":>7}{"3着内率":>9}{"複勝ROI":>9}{"単勝ROI":>9}{"平均人気":>9}')
    for k in range(1, 9):
        s = [h for h in H if h["rank"] == k]
        if len(s) < 50:
            continue
        print(f'  {k}位{"":<5}{len(s):>7}{np.mean([h["in3"] for h in s])*100:>8.1f}%'
              f'{np.mean([h["fuku"] for h in s])*100:>8.1f}%'
              f'{np.mean([h["tan"] for h in s])*100:>8.1f}%'
              f'{np.mean([h["pop"] for h in s]):>9.1f}')

    # ── 2 人気を固定して、システム評価で3分割
    print("\n── 人気を固定し、同じ人気の馬をシステム評価で3等分")
    print("   （システムが市場に情報を足しているなら、同じ行の中で上位と下位に差が出る）")
    print(f'  {"人気帯":<12}{"頭数":>7}   ' +
          "".join(f'{x:>22}' for x in ["システム上位1/3", "中位", "下位1/3"]) +
          f'{"上位-下位":>11}{"t":>7}')
    rowsout = []
    for lab, lo, hi in POPS:
        s = [h for h in H if lo <= h["pop"] <= hi]
        if len(s) < 150:
            continue
        q = np.quantile([h["pct"] for h in s], [1 / 3, 2 / 3])
        grp = [[h for h in s if h["pct"] <= q[0]],
               [h for h in s if q[0] < h["pct"] <= q[1]],
               [h for h in s if h["pct"] > q[1]]]
        cells = []
        for g in grp:
            if not g:
                cells.append((0, 0, 0))
                continue
            cells.append((len(g), np.mean([h["in3"] for h in g]) * 100,
                          np.mean([h["fuku"] for h in g]) * 100))
        a = np.array([h["fuku"] for h in grp[0]])
        c = np.array([h["fuku"] for h in grp[2]])
        d3a = np.array([h["in3"] for h in grp[0]], float)
        d3c = np.array([h["in3"] for h in grp[2]], float)
        se = np.sqrt(a.var(ddof=1) / len(a) + c.var(ddof=1) / len(c))
        t = (a.mean() - c.mean()) / se if se else 0.0
        se3 = np.sqrt(d3a.var(ddof=1) / len(d3a) + d3c.var(ddof=1) / len(d3c))
        t3 = (d3a.mean() - d3c.mean()) / se3 if se3 else 0.0
        txt = "".join(f'{n_:>6}頭 {i3:>5.1f}% {ro:>6.1f}%' for n_, i3, ro in cells)
        print(f'  {lab:<12}{len(s):>7}   {txt}'
              f'{(a.mean()-c.mean())*100:>+10.1f}%{t:>7.2f}')
        rowsout.append({"pop": lab, "n": len(s),
                        "top": {"n": cells[0][0], "in3": round(cells[0][1], 1), "roi": round(cells[0][2], 1)},
                        "mid": {"n": cells[1][0], "in3": round(cells[1][1], 1), "roi": round(cells[1][2], 1)},
                        "bot": {"n": cells[2][0], "in3": round(cells[2][1], 1), "roi": round(cells[2][2], 1)},
                        "roi_diff": round((a.mean() - c.mean()) * 100, 1), "t_roi": round(float(t), 2),
                        "in3_diff": round((d3a.mean() - d3c.mean()) * 100, 1), "t_in3": round(float(t3), 2)})

    print("\n── 3着内率で見た同じ表の差（システムが順位付けとして効いているか）")
    for r in rowsout:
        print(f'  {r["pop"]:<12} 上位 {r["top"]["in3"]:>5.1f}% / 下位 {r["bot"]["in3"]:>5.1f}%'
              f'  差 {r["in3_diff"]:>+6.1f}pt  t={r["t_in3"]:>6.2f}')

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "level": lv,
               "n_horses": len(H), "by_pop": rowsout},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
