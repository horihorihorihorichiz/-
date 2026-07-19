# -*- coding: utf-8 -*-
"""大井 確定判定: 2年全量(2171R)×実オッズで乖離パターンを二段階検証。
   dev = 〜202512 / conf = 202601〜。ROI基準 dev>=103% & conf>=100%。
   券種: 単勝(帯別×条件) / 複勝 / 三連複軸ながし(紐=市場1-3)。"""
import json
from collections import defaultdict

rows = json.load(open("oi_model_rows.json", encoding="utf-8"))
odds_db = json.load(open("oi_odds.json", encoding="utf-8"))

cells = defaultdict(lambda: {"dev": [0, 0, 0], "conf": [0, 0, 0]})

def book(name, month, cost, ret):
    ph = "dev" if month < "202601" else "conf"
    c = cells[name][ph]
    c[0] += cost; c[1] += ret; c[2] += 1

n_fire = 0
for r in rows:
    od = odds_db.get(r["rid"])
    if not od:
        continue
    m1 = r["model1"]
    rec = od.get(str(m1)) or {}
    o1 = rec.get("odds")
    if not o1:
        continue
    mo, pay = r["month"], r["pay"]
    win = r["top3"][0]
    fld = r.get("field") or 0
    dist = r.get("dist") or 0
    g12 = r.get("g12") or 0
    if o1 < 7.0:
        continue
    n_fire += 1
    band = ("7-10" if o1 < 10 else "10-15" if o1 < 15 else
            "15-30" if o1 <= 30 else "30-50" if o1 <= 50 else "50+")
    tan_ret = int(o1*100) if m1 == win else 0
    fuku = pay.get("複勝", {})
    fuku_ret = int(fuku.get(str(m1), 0)) if m1 in r["top3"] else 0
    # --- 単勝: 帯のみ ---
    book(f"単勝 {band}", mo, 100, tan_ret)
    # --- 単勝: 帯×条件 ---
    conds = {
        "多頭数14+": fld >= 14, "中頭数11-13": 11 <= fld <= 13, "少頭数~10": fld <= 10,
        "短距離~1200": dist <= 1200, "マイル1400-1600": 1400 <= dist <= 1600, "中距離1700+": dist >= 1700,
        "首位確信g12>=0.3": g12 >= 0.3, "混戦g12<0.15": g12 < 0.15,
        "下級tier9+": (r.get("tier") or 0) >= 9, "上級tier<=8": 0 < (r.get("tier") or 9) <= 8,
    }
    for cn, on in conds.items():
        if on:
            book(f"単勝 {band}×{cn}", mo, 100, tan_ret)
    if o1 >= 15:
        for cn, on in conds.items():
            if on:
                book(f"単勝 15倍+×{cn}", mo, 100, tan_ret)
        book("単勝 15倍+", mo, 100, tan_ret)
        book(f"複勝 15倍+", mo, 100, fuku_ret)
    # --- 複勝: 帯別 ---
    book(f"複勝 {band}", mo, 100, fuku_ret)
    # --- 三連複軸ながし: 紐=市場1-3(軸除く) ---
    if 10 <= o1 <= 50:
        mkt = sorted((h for h in od if od[h].get("odds")), key=lambda h: od[h]["odds"])
        partners = [int(h) for h in mkt if int(h) != m1][:3]
        if len(partners) >= 3:
            combos = {tuple(sorted([m1, a, b]))
                      for i, a in enumerate(partners) for b in partners[i+1:]}
            tk = tuple(sorted(r["top3"]))
            tp = pay.get("三連複", {})
            ret3 = int(list(tp.values())[0]) if (tk in combos and tp) else 0
            tb = "10-30" if o1 <= 30 else "30-50"
            book(f"三連複 軸{tb}×紐市場1-3", mo, 300, ret3)
            if fld >= 14:
                book(f"三連複 軸{tb}×多頭数", mo, 300, ret3)
            m5 = set(r["order"][:5])
            if all(p in m5 for p in partners):
                book(f"三連複 軸{tb}×紐一致", mo, 300, ret3)

print(f"発火 {n_fire}R / {len(rows)}R = {100*n_fire/len(rows):.1f}%\n")
res = []
for name, d in cells.items():
    dv, cf = d["dev"], d["conf"]
    if dv[2] < 15 or cf[2] < 8:
        continue
    droi, croi = dv[1]/dv[0], cf[1]/cf[0]
    tot = (dv[1]+cf[1])/(dv[0]+cf[0])
    ok = droi >= 1.03 and croi >= 1.00
    res.append((ok, tot, name, droi, dv[2], croi, cf[2]))
res.sort(key=lambda x: (-x[0], -x[1]))
print("★=二段階通過(dev>=103% & conf>=100%)")
for ok, tot, name, droi, dn, croi, cn in res[:40]:
    print(f"{'★' if ok else ' '}{name:32s} 発見{100*droi:6.1f}%({dn:3d}R) 確認{100*croi:6.1f}%({cn:3d}R) 通算{100*tot:6.1f}%")
