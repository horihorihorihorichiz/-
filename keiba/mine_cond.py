# -*- coding: utf-8 -*-
"""距離×場×クラス条件マップ採掘（7/23・盛られた数字排除の独立版）。
   wf_preds.jsonl(JRA 2200R) を dev(202511-202603)/conf(202604-202607) に分割し、
   ベース=乖離単勝(モデル1位オッズ7倍+) の上に条件を1つずつ載せてROIを両期間で測る。
   合格ライン: dev>=110% & conf>=100% & n>=40 & hits>=5 & 最大的中除外でも>=95%。
   大井(oi_model_rows.json)も同様に単勝系を層別。"""
import json, itertools, collections

VEN = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京",
       "06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}

rows = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]
for r in rows:
    r["venue"] = VEN.get(r["rid"][4:6], "?")
    for k in ("order", "odds", "payout", "scores"):
        if isinstance(r.get(k), str):
            import ast
            try: r[k] = ast.literal_eval(r[k])
            except Exception: r[k] = None
    for k in ("dist", "tier", "field"):
        try: r[k] = int(r.get(k))
        except (TypeError, ValueError): r[k] = None

def dband(d):
    if not d: return "?"
    if d <= 1300: return "短距離"
    if d <= 1900: return "中距離"
    return "長距離"

def tband(t):
    if t is None: return "?"
    if t >= 10: return "未勝利新馬"
    if t >= 6: return "上級"
    return "条件"

def roi_of(rs):
    """乖離単勝: モデル1位、単勝オッズ>=7。payout['tan']で精算"""
    bet = hit = 0; pays = []
    for r in rs:
        m1 = r["order"][0]
        o1 = (r.get("odds") or {}).get(str(m1)) or (r.get("odds") or {}).get(m1)
        if not o1 or o1 < 7.0:
            continue
        bet += 100
        pay = 0
        tanpay = (r.get("payout") or {}).get("単勝") or {}
        for k, v in tanpay.items():
            if int(k) == m1:
                pay = v
        pays.append(pay)
        hit += 1 if pay else 0
    if not bet:
        return None
    tot = sum(pays)
    mx = max(pays) if pays else 0
    n = bet // 100
    return dict(n=n, hits=hit, roi=100.0*tot/bet,
                roi_ex=100.0*(tot-mx)/max(bet-100,1) if n > 1 else 0)

dev = [r for r in rows if r["month"] <= "202603"]
conf = [r for r in rows if r["month"] >= "202604"]

def sweep(name, pred):
    a, b = roi_of([r for r in dev if pred(r)]), roi_of([r for r in conf if pred(r)])
    if not a or not b: return None
    n = a["n"] + b["n"]; hits = a["hits"] + b["hits"]
    allr = roi_of([r for r in rows if pred(r)])
    ok = a["roi"] >= 110 and b["roi"] >= 100 and n >= 40 and hits >= 5 and allr["roi_ex"] >= 95
    return dict(name=name, dev=a, conf=b, all=allr, n=n, hits=hits, ok=ok)

conds = []
# 単軸: 場 / 距離帯 / surface / クラス / 頭数
for v in VEN.values():
    conds.append((f"場={v}", lambda r, v=v: r["venue"] == v))
for db in ["短距離","中距離","長距離"]:
    conds.append((f"距離={db}", lambda r, db=db: dband(r.get("dist")) == db))
for s in ["芝","ダ"]:
    conds.append((f"馬場={s}", lambda r, s=s: r.get("surface") == s))
for tb in ["上級","条件","未勝利新馬"]:
    conds.append((f"級={tb}", lambda r, tb=tb: tband(r.get("tier")) == tb))
conds.append(("多頭15+", lambda r: (r.get("field") or 0) >= 15))
conds.append(("少頭<=10", lambda r: (r.get("field") or 0) <= 10))
# 2軸: 場×距離帯 / 場×surface / 距離×級 / surface×距離
for v in VEN.values():
    for db in ["短距離","中距離","長距離"]:
        conds.append((f"{v}×{db}", lambda r, v=v, db=db: r["venue"] == v and dband(r.get("dist")) == db))
    for s in ["芝","ダ"]:
        conds.append((f"{v}×{s}", lambda r, v=v, s=s: r["venue"] == v and r.get("surface") == s))
for db in ["短距離","中距離","長距離"]:
    for tb in ["上級","条件"]:
        conds.append((f"{db}×{tb}", lambda r, db=db, tb=tb: dband(r.get("dist")) == db and tband(r.get("tier")) == tb))
    for s in ["芝","ダ"]:
        conds.append((f"{s}×{db}", lambda r, s=s, db=db: r.get("surface") == s and dband(r.get("dist")) == db))

res = [x for x in (sweep(n, p) for n, p in conds) if x]
res.sort(key=lambda x: -(x["all"]["roi"]))
print(f"=== JRA 乖離単勝(7倍+) 条件別 dev/conf ({len(res)}条件) ===")
print("合格 = dev>=110 & conf>=100 & n>=40 & hits>=5 & 最大的中除外>=95")
for x in res:
    m = "◎PASS" if x["ok"] else "  ----"
    print(f"{m} {x['name']:<14} 通算{x['all']['roi']:6.1f}% n={x['n']:3d} hits={x['hits']:2d} "
          f"dev{x['dev']['roi']:6.1f}%/{x['dev']['n']} conf{x['conf']['roi']:6.1f}%/{x['conf']['n']} "
          f"除外{x['all']['roi_ex']:6.1f}%")
json.dump(res, open("cond_map_20260723.json", "w", encoding="utf-8"), ensure_ascii=False)
print("WROTE cond_map_20260723.json")
