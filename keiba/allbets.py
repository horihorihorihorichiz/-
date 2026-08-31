# -*- coding: utf-8 -*-
# 券種を複勝に絞らず、全8券種を例外除外(A∧B∧C)の内側で測る
import json, math, itertools
rows=[json.loads(l) for l in open('wf_preds_v3ext2.jsonl')]
def imp(o):
    v={k:1.0/float(x) for k,x in o.items() if x and float(x)>0}
    s=sum(v.values()); return {k:x/s for k,x in v.items()}
R=[]
for r in rows:
    o=r.get('odds') or {}
    if len(o)<6: continue
    p=imp(o); srt=sorted(p.items(),key=lambda kv:-kv[1])
    ent=-sum(x*math.log(x) for x in p.values()); sc=r.get('scores') or []
    if len(sc)<3: continue
    pay=r.get('payout') or {}
    R.append(dict(month=r['month'],fav_p=srt[0][1],ent=ent,sgap=sc[0]-sc[1],
                  mkt=[k for k,_ in srt],mdl=[str(x) for x in (r.get('order') or [])],
                  pay=pay,venue=r.get('venue'),surface=r.get('surface'),dist=r.get('dist')))
seg=lambda lo,hi:[x for x in R if lo<=x['month']<=hi]
MINE,VAL,CONF=seg('202409','202602'),seg('202603','202605'),seg('202606','202608')
sel=lambda x: x['fav_p']>=0.341 and x['ent']<=1.904 and x['sgap']>=0.066
M,V,C=[[x for x in s if sel(x)] for s in (MINE,VAL,CONF)]

def k2(a,b): a,b=int(a),int(b); return f"{min(a,b)}-{max(a,b)}"
def k3(t): return "-".join(map(str,sorted(int(v) for v in t)))
def kex(a,b): return f"{int(a)}→{int(b)}"
def kex3(a,b,c_): return f"{int(a)}→{int(b)}→{int(c_)}"

def STRATS(src):  # src: 'mkt' or 'mdl'
    g=lambda x,i: x[src][i] if len(x[src])>i else None
    return {
      f'単勝 {src}1位(1点)':      lambda x:[('単勝',g(x,0),1)],
      f'複勝 {src}上位2(2点)':    lambda x:[('複勝',g(x,0),1),('複勝',g(x,1),1)],
      f'ワイド {src}1-2(1点)':    lambda x:[('ワイド',k2(g(x,0),g(x,1)),1)],
      f'馬連 {src}1-2(1点)':      lambda x:[('馬連',k2(g(x,0),g(x,1)),1)],
      f'馬単 {src}1→2(1点)':      lambda x:[('馬単',kex(g(x,0),g(x,1)),1)],
      f'三連複 {src}上位3(1点)':  lambda x:[('三連複',k3(x[src][:3]),1)],
      f'三連単 {src}1→2→3(1点)': lambda x:[('三連単',kex3(g(x,0),g(x,1),g(x,2)),1)],
      f'三連単 {src}上位3BOX(6点)':lambda x:[('三連単',kex3(*pm),1) for pm in itertools.permutations(x[src][:3])],
    }
ALL={**STRATS('mkt'),**STRATS('mdl')}
def ev(rs,f):
    c=r_=h=n=0
    for x in rs:
        bets=f(x)
        if any(b[1] is None for b in bets): continue
        n+=1; got=0
        for bt,key,u in bets:
            c+=100*u
            v=(x['pay'].get(bt) or {}).get(key)
            if v: r_+=v*u; got=1
        h+=got
    return n,(h/n*100 if n else 0),(r_/c*100 if c else 0)
print(f"{'買い方':<26}{'MINE(的中/ROI)':>20}{'VALIDATE':>18}{'CONFIRM':>18}")
for nm,f in ALL.items():
    out=[]
    for ss in (M,V,C):
        n,h,roi=ev(ss,f); out.append(f"{h:5.1f}%/{roi:6.1f}%")
    print(f"{nm:<26}{out[0]:>20}{out[1]:>18}{out[2]:>18}")
