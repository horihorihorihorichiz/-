# -*- coding: utf-8 -*-
"""NAR重賞へのシステム移植検証（7/19）。JRA製V3+パターンをそのまま適用し、
   結果ページの最終オッズ・実払戻で精算。「同じ運用でいけるか」の判定材料。
   usage: python3 eval_nar.py
"""
import glob, itertools, json
from collections import defaultdict

import calc, v2_live


def main():
    files = sorted(glob.glob("hist_nar/*.json"))
    n_ok = 0
    cap_h = cap_n = at1 = n_r = 0
    mkt_cap = mkt_at1 = 0
    P = defaultdict(lambda: [0, 0, 0])   # pattern -> [stake, ret, n]
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
            race = d["race"]
            res = calc.run(race)
            v2_live.rescore(race, res["rows"])
        except Exception:
            continue
        order_model = [r["num"] for r in res["rows"]]
        result = d["result"]
        om = {o["num"]: o["odds"] for o in result.get("order", []) if o.get("odds")}
        top3 = [o["num"] for o in result.get("order", []) if o.get("rank") in ("1", "2", "3")]
        if len(top3) < 3 or len(om) < 6:
            continue
        n_ok += 1
        payout = result.get("payout", {})
        # 捕捉KPI(モデル vs 市場)
        t5 = set(order_model[:5])
        cap_h += sum(1 for t in top3 if t in t5)
        cap_n += 3
        at1 += (order_model[0] == top3[0])
        msort = sorted(om, key=lambda h: om[h])
        m5 = set(msort[:5])
        mkt_cap += sum(1 for t in top3 if t in m5)
        mkt_at1 += (msort[0] == top3[0])
        n_r += 1
        # パターン(新定義: 1位オッズ7倍+)
        t1 = order_model[0]
        o1 = om.get(t1, 0)
        if o1 >= 7:
            ret = payout.get("単勝", {}).get(str(t1), 0)
            P["乖離単勝(7倍+)"][0] += 100; P["乖離単勝(7倍+)"][1] += ret; P["乖離単勝(7倍+)"][2] += 1
            dist = race.get("distance", 0)
            if race.get("surface") == "ダ":
                P["×ダ"][0] += 100; P["×ダ"][1] += ret; P["×ダ"][2] += 1
            if 1401 <= dist <= 1900:
                P["×中距離"][0] += 100; P["×中距離"][1] += ret; P["×中距離"][2] += 1
                mtop = [n for n in msort if n != t1][:3]
                if len(mtop) >= 3:
                    pts = ["-".join(map(str, sorted((t1,)+p)))
                           for p in itertools.combinations(mtop, 2)]
                    tret = sum(payout.get("三連複", {}).get(k, 0) for k in pts)
                    P["三連複ながし×中距離"][0] += 300; P["三連複ながし×中距離"][1] += tret
                    P["三連複ながし×中距離"][2] += 1
    print(f"評価対象: {n_ok}R (NAR重賞2年分)")
    print(f"捕捉5: モデル {cap_h/cap_n*100:.1f}% vs 市場 {mkt_cap/cap_n*100:.1f}%")
    print(f"勝ち馬=1位率: モデル {at1/n_r*100:.1f}% vs 市場 {mkt_at1/n_r*100:.1f}%")
    print("\nパターン別(最終オッズ・実払戻):")
    for k, (st, ret, n) in P.items():
        print(f"  {k:18s} ROI {ret/st*100 if st else 0:6.1f}% ({n}R 投{st})")


if __name__ == "__main__":
    main()
