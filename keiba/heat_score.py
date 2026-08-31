# -*- coding: utf-8 -*-
"""ヒートスコア検証: 「確認済み条件がN個重なるほど本当に熱いのか」をWF2200Rで実測。
   乖離単勝ベース(モデル1位7倍+・未勝利除く)に対し、各条件の該当数でROIを層別。
   出力: 条件数別ROI + 各条件の単独寄与 + 推奨ヒート閾値"""
import ast, json, itertools

rows = []
for l in open("wf_preds.jsonl", encoding="utf-8"):
    d = json.loads(l)
    for k in ("order", "odds", "payout", "scores"):
        if isinstance(d.get(k), str):
            try: d[k] = ast.literal_eval(d[k])
            except Exception: d[k] = None
    for k in ("dist", "tier", "field"):
        try: d[k] = int(d.get(k))
        except (TypeError, ValueError): d[k] = None
    if d.get("order") and d.get("odds"):
        d["odds"] = {int(k): v for k, v in d["odds"].items() if v}
        rows.append(d)

def pwin_of(d):
    """scoresからsoftmax近似でモデル1位の確率(モデル価値の代用)"""
    s = d.get("scores") or {}
    if not s: return 0
    import math
    vals = {int(k): float(v) for k, v in s.items()}
    mx = max(vals.values())
    ex = {k: math.exp(v - mx) for k, v in vals.items()}
    tot = sum(ex.values())
    return ex.get(d["order"][0], 0) / tot if tot else 0

# 確認済み条件(全てWFでプラス実証済みのもの)
CONDS = {
    "上級(2勝+)": lambda d: bool(d["tier"] and d["tier"] >= 6),
    "ダート": lambda d: d["surface"] == "ダ",
    "中距離": lambda d: bool(d["dist"] and 1401 <= d["dist"] <= 1900),
    "多頭15+": lambda d: bool(d["field"] and d["field"] >= 15),
    "モデル価値1.6+": lambda d: pwin_of(d) * d["odds"][d["order"][0]] >= 1.6,
    "1人気モデル売り": lambda d: {n: i+1 for i, n in enumerate(d["order"])}.get(
        min(d["odds"], key=lambda x: d["odds"][x]), 99) >= 5,
    "軸10-30倍": lambda d: 10 <= d["odds"][d["order"][0]] <= 30,
}

fires = [d for d in rows if d["order"][0] in d["odds"] and d["odds"][d["order"][0]] >= 7.0
         and not (d["tier"] and d["tier"] >= 10)]
for d in fires:
    d["_hits"] = [k for k, f in CONDS.items() if f(d)]

def roi(sel):
    bet = len(sel) * 100; pays = []
    for d in sel:
        p = (d.get("payout") or {}).get("単勝") or {}
        v = 0
        for k, val in p.items():
            if int(k) == d["order"][0]: v = val
        pays.append(v)
    tot = sum(pays); mx = max(pays, default=0)
    return len(sel), sum(1 for p in pays if p), (100.0*tot/bet if bet else 0), \
        (100.0*(tot-mx)/(bet-100) if bet > 100 else 0)

print(f"乖離発火(未勝利除く) = {len(fires)}R\n")
print("=== 各条件の単独寄与(その条件を満たす発火レースの単勝ROI) ===")
for k, f in CONDS.items():
    n, h, r, _ = roi([d for d in fires if k in d["_hits"]])
    n0, h0, r0, _ = roi([d for d in fires if k not in d["_hits"]])
    print(f"  {k:<16} 該当 n={n:3d} hits={h:2d} ROI{r:6.1f}%  ／ 非該当 n={n0:3d} ROI{r0:6.1f}%  差{r-r0:+6.1f}pt")

print("\n=== ★重複数別ROI(ヒートスコア検証) ===")
for c in range(0, 6):
    sel = [d for d in fires if len(d["_hits"]) == c]
    if not sel: continue
    n, h, r, ex = roi(sel)
    dev = [d for d in sel if d["month"] <= "202603"]; cf = [d for d in sel if d["month"] >= "202604"]
    _, _, dr, _ = roi(dev); _, _, cr, _ = roi(cf)
    print(f"  {c}条件該当: n={n:3d} hits={h:2d} 通算ROI{r:7.1f}% (dev{dr:6.1f}%/{len(dev)} conf{cr:6.1f}%/{len(cf)}) 除外後{ex:6.1f}%")

print("\n=== 累積(N個以上該当) ===")
for c in range(0, 6):
    sel = [d for d in fires if len(d["_hits"]) >= c]
    if len(sel) < 10: continue
    n, h, r, ex = roi(sel)
    dev = [d for d in sel if d["month"] <= "202603"]; cf = [d for d in sel if d["month"] >= "202604"]
    _, _, dr, _ = roi(dev); _, _, cr, _ = roi(cf)
    print(f"  {c}個以上: n={n:3d} hits={h:2d} 通算{r:7.1f}% (dev{dr:6.1f}% conf{cr:6.1f}%) 除外後{ex:6.1f}%")

print("\n=== 頻出の組合せ(2個以上・n>=8) ===")
combo = {}
for d in fires:
    if len(d["_hits"]) >= 2:
        key = "+".join(sorted(d["_hits"]))
        combo.setdefault(key, []).append(d)
for key, sel in sorted(combo.items(), key=lambda kv: -len(kv[1])):
    if len(sel) < 8: continue
    n, h, r, ex = roi(sel)
    print(f"  {key:<52} n={n:3d} hits={h:2d} ROI{r:7.1f}% 除外{ex:6.1f}%")
