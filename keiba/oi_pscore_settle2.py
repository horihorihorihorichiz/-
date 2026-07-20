# -*- coding: utf-8 -*-
"""ラウンド2: 全馬垂れ流しでなく、EV最大馬1頭/レース と 二段構え条件で精算"""
import json
from collections import defaultdict

rows = json.load(open("oi_model_rows.json", encoding="utf-8"))
odds_db = json.load(open("oi_odds.json", encoding="utf-8"))
ps = json.load(open("oi_pscores.json", encoding="utf-8"))
meta = {r["rid"]: r for r in rows}

CELLS = defaultdict(lambda: {"dev": [0, 0, 0, 0], "conf": [0, 0, 0, 0]})  # cost,ret,nR,hits


def book(cell, phase, cost, ret, hit):
    c = CELLS[cell][phase]
    c[0] += cost; c[1] += ret; c[2] += 1; c[3] += hit


for rid, sc in ps.items():
    if not sc.get("p"):
        continue
    m = meta.get(rid)
    od = odds_db.get(rid)
    if not m or not od:
        continue
    phase = "dev" if m["month"] < "202601" else "conf"
    pay = m.get("pay", {})
    fuku = pay.get("複勝", {})
    tan_pay = pay.get("単勝", {})
    g12 = m["g12"]
    tier = m["tier"]
    cands = []
    for num, p in sc["p"].items():
        info = od.get(num)
        if not info or not info.get("odds"):
            continue
        o = info["odds"]
        cands.append((p * o, num, p, o, info))
    if not cands:
        continue
    cands.sort(reverse=True)

    def settle(num, o, info):
        win = info.get("rank") == 1
        t = int(tan_pay.get(num, 0)) if win else 0
        if win and t == 0:
            t = int(o * 100)
        f = int(fuku.get(num, 0))
        return t, f

    # A) EV最大馬1頭のみ（thr別、オッズ上限つき/なし）
    ev, num, p, o, info = cands[0]
    t, f = settle(num, o, info)
    for thr in (1.0, 1.3, 1.6, 2.0):
        if ev > thr:
            book(f"A:maxEV単勝 thr{thr}", phase, 100, t, t > 0)
            book(f"A:maxEV複勝 thr{thr}", phase, 100, f, f > 0)
            if o <= 30:
                book(f"A:maxEV単勝 thr{thr} o<=30", phase, 100, t, t > 0)
                book(f"A:maxEV複勝 thr{thr} o<=30", phase, 100, f, f > 0)
            if o <= 15:
                book(f"A:maxEV単勝 thr{thr} o<=15", phase, 100, t, t > 0)
                book(f"A:maxEV複勝 thr{thr} o<=15", phase, 100, f, f > 0)

    # B) 二段構え: p下限×オッズ帯 (全該当馬)
    for evv, num, p, o, info in cands:
        t, f = settle(num, o, info)
        for pmin in (0.10, 0.15):
            for lo, hi, tag in ((3, 7, "o3-7"), (7, 15, "o7-15"), (15, 30, "o15-30")):
                if p >= pmin and lo <= o < hi and evv > 1.0:
                    book(f"B:単勝 p>={pmin} {tag}", phase, 100, t, t > 0)
                    book(f"B:複勝 p>={pmin} {tag}", phase, 100, f, f > 0)
        # C) 既知生存の全馬拡張: o15+ × 混戦g12<0.15 × EV閾値
        if o >= 15 and g12 < 0.15:
            for thr in (1.3, 1.6, 2.0):
                if evv > thr:
                    book(f"C:単勝 o15+ g12<.15 thr{thr}", phase, 100, t, t > 0)
        # D) 上位クラス限定 (tier<=5) EV
        if tier <= 5:
            for thr in (1.3, 1.6):
                if evv > thr and o <= 30:
                    book(f"D:単勝 tier<=5 thr{thr} o<=30", phase, 100, t, t > 0)
                    book(f"D:複勝 tier<=5 thr{thr} o<=30", phase, 100, f, f > 0)

res = []
for cell, d in CELLS.items():
    dc, dr, dn, dh = d["dev"]
    cc, cr, cn, ch = d["conf"]
    droi = dr / dc * 100 if dc else 0
    croi = cr / cc * 100 if cc else 0
    tot = (dr + cr) / (dc + cc) * 100 if dc + cc else 0
    hits = dh + ch
    passed = droi >= 103 and dn >= 15 and croi >= 100 and cn >= 8 and hits >= 5
    res.append((passed, tot, cell, droi, dn, croi, cn, hits))
res.sort(key=lambda x: (-x[0], -x[1]))
print(f"round2 cells: {len(CELLS)}")
for passed, tot, cell, droi, dn, croi, cn, hits in res:
    flag = "PASS" if passed else "    "
    print(f"{flag} {cell:32s} dev {droi:6.1f}% ({dn:4d}) conf {croi:6.1f}% ({cn:3d}) tot {tot:6.1f}% hits {hits}")
