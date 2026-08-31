# -*- coding: utf-8 -*-
"""全馬モデル価値スイープの精算。
   トリガー: p(モデル勝率) × 実単勝オッズ > 閾値 の全馬 (モデル1位に限らない)。
   券種: 単勝(100円) / 複勝(100円)。dev=month<202601 / conf>=202601 で二段階検証。"""
import json
from collections import defaultdict

rows = json.load(open("oi_model_rows.json", encoding="utf-8"))
odds_db = json.load(open("oi_odds.json", encoding="utf-8"))
ps = json.load(open("oi_pscores.json", encoding="utf-8"))

meta = {r["rid"]: r for r in rows}

# cell -> {phase -> [cost, ret, n_bets, races(set->count), hits]}
CELLS = defaultdict(lambda: {"dev": [0, 0, 0, set(), 0], "conf": [0, 0, 0, set(), 0]})


def book(cell, phase, rid, cost, ret, hit):
    c = CELLS[cell][phase]
    c[0] += cost
    c[1] += ret
    c[2] += 1
    c[3].add(rid)
    c[4] += hit


n_scored = 0
for rid, sc in ps.items():
    if sc.get("engine") == "FAIL" or not sc.get("p"):
        continue
    m = meta.get(rid)
    od = odds_db.get(rid)
    if not m or not od:
        continue
    n_scored += 1
    phase = "dev" if m["month"] < "202601" else "conf"
    pay = m.get("pay", {})
    fuku = pay.get("複勝", {})
    tan_pay = pay.get("単勝", {})
    model1 = str(m["model1"])
    tier = m["tier"]
    field = m["field"]
    g12 = m["g12"]
    for num, p in sc["p"].items():
        info = od.get(num)
        if not info or not info.get("odds"):
            continue
        o = info["odds"]
        ev = p * o
        rank = info.get("rank")
        win = rank == 1
        # 複勝的中は払戻dictに馬番があるか(同着含む)
        f_ret = int(fuku.get(num, 0))
        t_ret = int(tan_pay.get(num, 0)) if win else 0
        if win and t_ret == 0:
            t_ret = int(o * 100)
        for thr in (1.0, 1.3, 1.6, 2.0):
            if ev <= thr:
                continue
            tag = f"thr{thr}"
            book(f"単勝 {tag}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag}", phase, rid, 100, f_ret, f_ret > 0)
            # ---- サブスライス (thr別) ----
            ob = ("o<3" if o < 3 else "o3-7" if o < 7 else "o7-15" if o < 15
                  else "o15-30" if o < 30 else "o30+")
            book(f"単勝 {tag} {ob}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {ob}", phase, rid, 100, f_ret, f_ret > 0)
            pb = ("p>=.20" if p >= 0.20 else "p.10-.20" if p >= 0.10
                  else "p.05-.10" if p >= 0.05 else "p<.05")
            book(f"単勝 {tag} {pb}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {pb}", phase, rid, 100, f_ret, f_ret > 0)
            mr = "M1" if num == model1 else ("Mtop3" if int(num) in m["order"][:3] else "Mout")
            book(f"単勝 {tag} {mr}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {mr}", phase, rid, 100, f_ret, f_ret > 0)
            tb = "tier<=5" if tier <= 5 else "tier6-8" if tier <= 8 else "tier9+"
            book(f"単勝 {tag} {tb}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {tb}", phase, rid, 100, f_ret, f_ret > 0)
            fb = "field<=10" if field <= 10 else "field11+"
            book(f"単勝 {tag} {fb}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {fb}", phase, rid, 100, f_ret, f_ret > 0)
            gb = "g12<0.15" if g12 < 0.15 else "g12>=0.3" if g12 >= 0.3 else "g12mid"
            book(f"単勝 {tag} {gb}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {gb}", phase, rid, 100, f_ret, f_ret > 0)
            db = "d<=1200" if m["dist"] <= 1200 else "d1300-1600" if m["dist"] <= 1600 else "d1700+"
            book(f"単勝 {tag} {db}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {db}", phase, rid, 100, f_ret, f_ret > 0)
            popb = "pop1-3" if info.get("pop", 99) <= 3 else "pop4-6" if info.get("pop", 99) <= 6 else "pop7+"
            book(f"単勝 {tag} {popb}", phase, rid, 100, t_ret, win)
            book(f"複勝 {tag} {popb}", phase, rid, 100, f_ret, f_ret > 0)

print(f"scored races used: {n_scored}")
print(f"total cells: {len(CELLS)}")
print()
res = []
for cell, d in CELLS.items():
    dc, dr, dn, drs, dh = d["dev"]
    cc, cr, cn, crs, ch = d["conf"]
    droi = dr / dc * 100 if dc else 0
    croi = cr / cc * 100 if cc else 0
    tot = (dr + cr) / (dc + cc) * 100 if dc + cc else 0
    hits = dh + ch
    passed = (droi >= 103 and len(drs) >= 15 and croi >= 100 and len(crs) >= 8
              and hits >= 5)
    res.append((passed, tot, cell, droi, dn, len(drs), croi, cn, len(crs), hits))
res.sort(key=lambda x: (-x[0], -x[1]))
for passed, tot, cell, droi, dn, drr, croi, cn, crr, hits in res:
    flag = "PASS" if passed else "    "
    print(f"{flag} {cell:34s} dev {droi:6.1f}% ({dn:4d}bet/{drr:4d}R) "
          f"conf {croi:6.1f}% ({cn:3d}bet/{crr:3d}R) tot {tot:6.1f}% hits {hits}")
