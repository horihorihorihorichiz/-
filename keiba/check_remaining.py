# -*- coding: utf-8 -*-
"""残りレースを検証済み2層モデル(hori52_w.json)で採点（2026-08-22夕）。"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_rank as R
from verify_export import scorer_from_artifact

ART = json.load(open("hori52_w.json"))
wg = np.array(ART["wg"]); w6={k:np.array(v) for k,v in ART["w6"].items()}
w30={k:np.array(v) for k,v in ART["w30"].items()}; w52={k:np.array(v) for k,v in ART["w52"].items()}

def weight_for(surface, dist_cat, tier, venue):
    b = w30.get(f"{surface}{dist_cat}/t{tier}")
    if b is None: b = w6.get(f"{surface}{dist_cat}", wg)
    c = w52.get(f"{venue}{surface}{dist_cat}")
    return b if c is None else 0.5*c + 0.5*b

def latest_tan(rid):
    t={}
    for l in open('odds_timeline/20260822.jsonl'):
        r=json.loads(l)
        if r.get('rid')==rid and r.get('tan'): t=r['tan']
    return t

RIDS=[("202604030110","新潟10R","17:10"),("202607030110","中京10R","17:20"),
      ("202604030111","新潟11R","17:40"),("202607030111","中京11R","17:50"),
      ("202604030112","新潟12R","18:10"),("202607030112","中京12R","18:20")]
today="20260822"
for rid,label,post in RIDS:
    try:
        race,rdate,_=R.load_race(rid)
    except Exception as e:
        print(f"\n=== {label} {post} 読込失敗 {e}"); continue
    try:
        rows,Z=R.scores_for(race)
        Z16,nz0=R.z16_for(race,rows,Z,today)
    except Exception as e:
        print(f"\n=== {label} {post} 採点不能({e})"); continue
    dc = race.get("dist_cat") or ("S" if race["distance"]<=1400 else "M" if race["distance"]<=1700 else "L")
    w = weight_for(race["surface"], dc, race.get("today_tier"), race.get("venue"))
    s = Z16 @ w
    tan = latest_tan(rid)
    order=sorted(range(len(rows)),key=lambda i:(-s[i],-rows[i]["wavg"],rows[i]["num"]))
    cell=f"{race.get('venue')}{race['surface']}{dc}/t{race.get('today_tier')}"
    print(f"\n=== {label} {post} {race.get('venue')}{race['surface']}{race['distance']}m "
          f"{len(rows)}頭 tier{race.get('today_tier')} [セル {cell}] ===")
    print(f"{'順':>2} {'馬番':>3} {'馬名':<10} {'新スコア':>8} {'現行順':>4} {'単勝':>7}")
    curmap={r['num']:i+1 for i,r in enumerate(rows)}
    for rank,i in enumerate(order,1):
        n=rows[i]['num']; o=tan.get(str(n))
        print(f"{rank:>2} {n:>3} {rows[i]['name']:<10} {s[i]:>+8.3f} {curmap[n]:>4} "
              f"{(str(o)+'倍') if o else '—':>7}")
    top=rows[order[0]]['num']; o1=tan.get(str(top))
    if o1 and float(o1)<2.0:
        print(f"  ★1位{top}番が単勝{o1}倍(<2倍) → 『複勝1点』条件に該当(実測91.8%・ただし期待値は負)")
