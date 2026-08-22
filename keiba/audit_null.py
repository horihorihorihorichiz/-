# -*- coding: utf-8 -*-
"""本日の分析の自己監査②: 「12構成から最良を選ぶ」行為そのものをnullで再現する。

疑い(本命): split60では実データ側は12構成を試して最良(VAL+CONF最大)を選んだのに、
nullは2構成しか試していない。選択の自由度が違う。
実力ゼロのデータで「12構成→最良を選ぶ」を8回繰り返し、選ばれたnull勝者の
VAL/CONFの分布を出す。実データの勝者(VAL56.5/CONF57.0)がこの分布の上端を
超えないなら、49分割の上乗せは選択バイアスで説明がつく。
"""
import json, collections, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2

def sd(r):  return f"{r['surface']}{r['dist_cat']}"
def k30(r): return f"{r['surface']}{r['dist_cat']}/t{r['tier']}"

def fit_by(races, kf, l2, base_of, min_n):
    out={}; by=collections.defaultdict(list)
    for r in races: by[kf(r)].append(r)
    for k,sub in by.items():
        if len(sub)<min_n: continue
        b=base_of(sub[0]); X,M,W=V2.make_tensor(sub,key="Z16")
        out[k]=V2.fit(X,M,W,l2,w0=b,wstart=b)
    return out

def ev3(races, wfn):
    n=len(races); t3=0
    for r in races:
        s=r["Z16"]@wfn(r)
        o=sorted(range(len(s)),key=lambda i:(-s[i],-r["wavg"][i],r["nums"][i]))
        t3+=int(o[0] in set(r["top3"]))
    return t3/n*100

races=V.load_races(); V2.attach_corner(races)
K=races[0]["Z16"].shape[1]
seg=lambda lo,hi:[r for r in races if lo<=r["month"]<=hi]
MINE,VAL,CONF=seg('000000','202602'),seg('202603','202605'),seg('202606','202608')
X,M,W=V2.make_tensor(MINE,key="Z16")
w_all=V2.fit(X,M,W,1.0,w0=np.zeros(K),wstart=np.zeros(K))
w6=fit_by(MINE,sd,0.2,lambda r:w_all,1); b6=lambda r:w6.get(sd(r),w_all)
w30=fit_by(MINE,k30,0.3,b6,40);          b30=lambda r:w30.get(k30(r),b6(r))
base_val=ev3(VAL,b30); base_conf=ev3(CONF,b30)
print(f"30分割のみ: VAL {base_val:.1f} / CONF {base_conf:.1f}", flush=True)

SIZES=[52,60,60,100,150,120]     # split60で試した実データ側の分割サイズと同数
rs=np.random.RandomState(97)
results=[]
for t in range(8):
    cands=[]
    for si,ncell in enumerate(SIZES):
        fk={r["rid"]: f"T{t}S{si}N{rs.randint(ncell)}" for r in races}
        wn=fit_by(MINE, lambda r: fk[r["rid"]], 0.3, b30, 40)
        for a in (0.3,0.5):
            def g(r, wn=wn, fk=fk, a=a):
                c=wn.get(fk[r["rid"]]); b=b30(r)
                return b if c is None else a*c+(1-a)*b
            v=ev3(VAL,g); c=ev3(CONF,g)
            cands.append((v+c, v, c, ncell, a))
    best=max(cands)
    results.append(best)
    print(f"  null試行{t+1}: 12構成の最良 = VAL {best[1]:.1f} / CONF {best[2]:.1f} "
          f"({best[3]}セル 混合{best[4]:.0%})", flush=True)

vs=[b[1] for b in results]; cs=[b[2] for b in results]
print(f"\nnull最良の分布(8試行): VAL 平均{np.mean(vs):.1f} 最大{max(vs):.1f} / "
      f"CONF 平均{np.mean(cs):.1f} 最大{max(cs):.1f}")
print(f"実データの勝者: VAL 56.5 / CONF 57.0")
n_ge=sum(1 for b in results if b[1]>=56.5 and b[2]>=57.0)
print(f"実データ勝者を(VAL・CONFとも)上回ったnull試行: {n_ge}/8")
json.dump({"base":[base_val,base_conf],"null_best":results},
          open("audit_null.json","w"))
