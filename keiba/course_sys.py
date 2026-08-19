# -*- coding: utf-8 -*-
# コースごとに「最も稼げた買い方」をMINEだけで選び、コース別システム表を作る。
# ポートフォリオ全体を VALIDATE / CONFIRM に1回だけ通す。
import json, math, itertools, collections
exec(open('/tmp/claude-0/-home-user--/a62f6054-2a2d-5711-b990-3a94f7d05b49/scratchpad/allbets.py').read().split("print(f\"{'買い方'")[0])

def course(x): return f"{x['venue']}{x['surface']}{x['dist']}"
by=collections.defaultdict(lambda:{'M':[],'V':[],'C':[]})
for x in MINE: by[course(x)]['M'].append(x)
for x in VAL:  by[course(x)]['V'].append(x)
for x in CONF: by[course(x)]['C'].append(x)

MENU=ALL  # 16戦略
MIN_N=40
chosen={}
for cs,d in sorted(by.items()):
    if len(d['M'])<MIN_N: continue
    best=None
    for nm,f in MENU.items():
        n,h,roi=ev(d['M'],f)
        if n>=MIN_N and (best is None or roi>best[2]):
            best=(nm,n,roi,h,f)
    if best: chosen[cs]=best
print(f"コース数(全体): {len(by)} / MINE {MIN_N}R以上で採用: {len(chosen)}")

# ポートフォリオ評価: 各コースは自分の採用戦略で買う
def port(rs):
    c=r_=h=n=0
    for x in rs:
        cs=course(x)
        if cs not in chosen: continue
        f=chosen[cs][4]; bets=f(x)
        if any(b[1] is None for b in bets): continue
        n+=1; got=0
        for bt,key,u in bets:
            c+=100*u
            v=(x['pay'].get(bt) or {}).get(key)
            if v: r_+=v*u; got=1
        h+=got
    return n,(h/n*100 if n else 0),(r_/c*100 if c else 0)
print("\n=== コース別システム・ポートフォリオ(全レース対象) ===")
for lab,rs in [("MINE(選択に使用)",MINE),("VALIDATE(未知)",VAL),("CONFIRM(未知)",CONF)]:
    n,h,roi=port(rs); print(f"{lab:<18} n={n:<5} 的中{h:5.1f}%  ROI {roi:6.1f}%")

# 例外除外と併用した場合
def port2(rs):
    return port([x for x in rs if sel(x)])
print("\n=== 同・例外除外(A∧B∧C)と併用 ===")
for lab,rs in [("MINE",MINE),("VALIDATE",VAL),("CONFIRM",CONF)]:
    n,h,roi=port2(rs); print(f"{lab:<18} n={n:<5} 的中{h:5.1f}%  ROI {roi:6.1f}%")

# ヌル対照: 戦略をコースに無作為割当したら同じMINE ROIが出るか(選択バイアスの物差し)
import random
random.seed(7)
strats=list(MENU.values())
null_rois=[]
for t in range(200):
    assign={cs:random.choice(strats) for cs in chosen}
    c=r_=0
    for x in MINE:
        cs=course(x)
        if cs not in assign: continue
        bets=assign[cs](x)
        if any(b[1] is None for b in bets): continue
        for bt,key,u in bets:
            c+=100*u; v=(x['pay'].get(bt) or {}).get(key)
            if v: r_+=v*u
    null_rois.append(r_/c*100)
mn=port(MINE)[2]
import statistics as st
print(f"\nヌル対照(無作為割当200回): MINE ROI 平均{st.mean(null_rois):.1f}% 最大{max(null_rois):.1f}%")
print(f"採用ポートフォリオのMINE ROI {mn:.1f}% は 16戦略から最良を選んだ結果 (かさ上げ分 = {mn-st.mean(null_rois):.1f}pt)")

json.dump({cs:{'strategy':b[0],'mine_n':b[1],'mine_roi':round(b[2],1),'mine_hit':round(b[3],1)}
           for cs,b in chosen.items()}, open('course_systems_choice.json','w'), ensure_ascii=False, indent=1)
# コース別のVAL/CONF成績も保存
detail={}
for cs,b in chosen.items():
    d=by[cs]; f=b[4]; row={'strategy':b[0]}
    for w,key in [('M','MINE'),('V','VAL'),('C','CONF')]:
        n,h,roi=ev(d[w],f); row[key]={'n':n,'hit':round(h,1),'roi':round(roi,1)}
    detail[cs]=row
json.dump(detail, open('course_systems_detail.json','w'), ensure_ascii=False, indent=1)
print("\nsaved course_systems_choice.json / course_systems_detail.json")
