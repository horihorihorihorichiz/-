# -*- coding: utf-8 -*-
"""三連複ながし 3点の中身の再編テスト（7/19「人気並べるだけじゃない何か」探索）。
   対象: 発火レース(オッズ乖離ルール) × 軸10-30倍 × ≤1900m（凍結カタログの三連複ゾーン）。
   相手 = 市場人気1-4位。ペアの組み方を変えた5変種を2段階(dev<202605/conf≥202605)で比較。
   月別内訳・的中詳細つき。
"""
import json, itertools, collections

KAIRI = 7.0
recs = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]

def trio_pay(payout, a, b, c):
    key = "-".join(str(x) for x in sorted([a, b, c]))
    return payout.get("三連複", {}).get(key, 0)

variants = {
    "A.フル3点(現行=1-3人気)": lambda t1, fav: [(fav[0], fav[1]), (fav[0], fav[2]), (fav[1], fav[2])],
    "B.堅ペア(1x2)削り2点":    lambda t1, fav: [(fav[0], fav[2]), (fav[1], fav[2])],
    "C.4点(1-4人気から1軸含む)": lambda t1, fav: [(fav[0], fav[1]), (fav[0], fav[2]), (fav[0], fav[3]), (fav[1], fav[2])],
    "D.1人気外し(2-4人気)3点":  lambda t1, fav: [(fav[1], fav[2]), (fav[1], fav[3]), (fav[2], fav[3])],
    "E.1人気アンカー(1xN)3点":  lambda t1, fav: [(fav[0], fav[1]), (fav[0], fav[2]), (fav[0], fav[3])],
}

res = {k: {"dev": [0, 0], "conf": [0, 0], "mon": collections.defaultdict(lambda: [0, 0]), "hits": []}
       for k in variants}
n_races = {"dev": 0, "conf": 0}

for r in recs:
    odds = {int(k): v for k, v in r["odds"].items() if v}
    order = r["order"]
    if not order or len(odds) < 5:
        continue
    t1 = order[0]
    o1 = odds.get(t1, 0)
    scores = r.get("scores", {})
    # 発火ルール（本番watch_dayと同一思想: オッズ乖離）
    fire = o1 >= KAIRI
    if not fire or not (10 <= o1 <= 30):
        continue
    if r.get("dist") and r["dist"] > 1900:
        continue
    phase = "dev" if r["month"] < "202605" else "conf"
    fav = sorted((h for h in odds if h != t1), key=lambda h: odds[h])[:4]
    if len(fav) < 4:
        continue
    n_races[phase] += 1
    for name, fn in variants.items():
        pairs = fn(t1, fav)
        cost = len(pairs) * 100
        ret = sum(trio_pay(r["payout"], t1, a, b) for a, b in pairs)
        res[name][phase][0] += cost
        res[name][phase][1] += ret
        res[name]["mon"][r["month"]][0] += cost
        res[name]["mon"][r["month"]][1] += ret
        if ret:
            res[name]["hits"].append((r["month"], r["rid"], o1, ret))

print(f"対象レース: dev {n_races['dev']}R / conf {n_races['conf']}R")
print()
for name in variants:
    d, c = res[name]["dev"], res[name]["conf"]
    tc, tr = d[0] + c[0], d[1] + c[1]
    ok = (d[1] / d[0] >= 1.03 if d[0] else False) and (c[1] / c[0] >= 1.00 if c[0] else False)
    mark = "★" if ok else " "
    print(f"{mark}{name:28s} 発見{100*d[1]/d[0]:6.1f}%({d[0]//100:3d}点) "
          f"確認{100*c[1]/c[0]:6.1f}%({c[0]//100:3d}点) 通算{100*tr/tc:6.1f}% 的中{len(res[name]['hits'])}回")
print()
print("==== 月別 A(現行) vs D(1人気外し) ====")
months = sorted({m for r in recs for m in [r["month"]]})
for m in months:
    a = res["A.フル3点(現行=1-3人気)"]["mon"].get(m)
    d = res["D.1人気外し(2-4人気)3点"]["mon"].get(m)
    if not a or not a[0]:
        continue
    print(f"  {m}: A {100*a[1]/a[0]:6.1f}%  D {100*d[1]/d[0]:6.1f}%  ({a[0]//300}R)")
print()
print("==== D の的中内訳（月/レース/軸オッズ/払戻） ====")
for m, rid, o1, ret in res["D.1人気外し(2-4人気)3点"]["hits"]:
    print(f"  {m} {rid} 軸{o1}倍 → {ret}円")
print()
print("==== A の的中内訳 ====")
for m, rid, o1, ret in res["A.フル3点(現行=1-3人気)"]["hits"]:
    print(f"  {m} {rid} 軸{o1}倍 → {ret}円")
