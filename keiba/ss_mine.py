# -*- coding: utf-8 -*-
"""SS階級の再定義採掘（2026-08-15）。
   台帳2394Rを本番と同一のclassify/heat_ofで再生し、◎最良発火レースについて
   事前指定の候補セル(乖離ROI主張帯×ヒート×条件)のROIを測る。
   ゲート: n>=40, dev>=110, conf>=100。多重比較を抑えるため候補は事前指定の6個のみ。
   null: ヒート数をレース間でシャッフルして同じ最良セル選択を1000回→偽陽性率。
   usage: python3 ss_mine.py
"""
import glob, json, random
from collections import defaultdict

import sim_rank as SR

CANDS = [
    ("A: 主張200+×🔥5+",        lambda c, h, x: c >= 200 and h >= 5),
    ("B: 主張200+×🔥4+",        lambda c, h, x: c >= 200 and h >= 4),
    ("C: 主張230+×🔥4+",        lambda c, h, x: c >= 230 and h >= 4),
    ("D: 主張200+×🔥4+×中距離",  lambda c, h, x: c >= 200 and h >= 4 and x["mid"]),
    ("E: 主張200+×🔥4+×1勝",     lambda c, h, x: c >= 200 and h >= 4 and x["t6"]),
    ("F: 主張200+×🔥4+×単勝7倍+", lambda c, h, x: c >= 200 and h >= 4 and (x["o1"] or 0) >= 7.0),
]


def replay():
    rid_date = {}
    for f in glob.glob("hist/*.json"):
        try:
            rid_date[f.split("/")[-1][:12]] = json.load(open(f, encoding="utf-8")).get("date", "")
        except Exception:
            pass
    rows = SR.load("wf_preds_v3.jsonl")
    fires = []
    for r in rows:
        r["date"] = rid_date.get(r["rid"], "")
        buy, hc = SR.classify_race(r)
        if not buy:
            continue
        best = max(buy, key=lambda f: f[2])
        st = SR.settle_fire(r, best[0], best[3])
        if st is None:
            continue
        pts, pay100 = st
        fires.append(dict(m=r["m"], claim=best[2], heat=hc, inv=pts*100, ret=pay100,
                          x=dict(mid=1700 <= (r.get("dist") or 0) <= 2200,
                                 t6=(r.get("tier") == 6), o1=r["odds"].get(r["order"][0]))))
    return fires


def roi(fs):
    inv = sum(f["inv"] for f in fs)
    ret = sum(f["ret"] for f in fs)
    return (ret/inv*100 if inv else 0), len(fs), sum(1 for f in fs if f["ret"] > 0)


def main():
    fires = replay()
    print(f"◎最良発火: {len(fires)}レース")
    results = []
    for name, cond in CANDS:
        sel = [f for f in fires if cond(f["claim"], f["heat"], f["x"])]
        dev = [f for f in sel if f["m"] <= "202603"]
        conf = [f for f in sel if f["m"] > "202603"]
        r_all, n, hits = roi(sel)
        r_dev, nd, _ = roi(dev)
        r_conf, nc, _ = roi(conf)
        ok = n >= 40 and r_dev >= 110 and r_conf >= 100
        results.append((name, r_all, n, hits, r_dev, nd, r_conf, nc, ok, cond))
        print(f"  {name:<28s} ROI{r_all:6.1f}% n={n:3d} 的中{hits:2d} | dev{r_dev:6.1f}%/{nd} conf{r_conf:6.1f}%/{nc} | {'✅ゲート通過' if ok else '✕'}")
    passed = [r for r in results if r[8]]
    if not passed:
        print("\n結論: ゲート通過セルなし → SS再定義は見送り(正直報告)")
        return
    best = max(passed, key=lambda r: r[1])
    name, r_all, n = best[0], best[1], best[2]
    # null: ヒートをシャッフルして同条件セルのROIがr_allを超える割合
    random.seed(7)
    heats = [f["heat"] for f in fires]
    exceed = 0
    N = 1000
    for _ in range(N):
        random.shuffle(heats)
        sel = [f for f, h in zip(fires, heats) if best[9](f["claim"], h, f["x"])]
        rr, nn, _ = roi(sel)
        if nn >= 40 and rr >= r_all:
            exceed += 1
    print(f"\n最良セル: {name} ROI{r_all:.1f}%/{n}R  null超過率 p={exceed/N:.3f} ({N}回)")
    print("採用可否: " + ("✅ p<0.10 → SS再定義候補" if exceed/N < 0.10 else "✕ nullで再現→採用見送り"))


if __name__ == "__main__":
    main()
