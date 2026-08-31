# -*- coding: utf-8 -*-
"""絞った上で「それ用の点数配分」: 予想可能レース(A∧B∧C)だけで配点を学習する。
ユーザー仕様の直接実装。学習は MINE∩絞り のみ。VAL/CONF は最後に1回。
比較対象: (a)全レースで学習した汎用B-sd16 (b)市場上位2頭ベースライン(EXCLUSION_REPORT)。
"""
import json, math, numpy as np, collections
import v99w_fit as V
import v99w2_fit as V2

races = V.load_races()
V2.attach_corner(races)
led = {}
for l in open('wf_preds_v3ext2.jsonl'):
    d = json.loads(l)
    s = d.get('scores') or []
    if len(s) >= 2:
        led[d['rid']] = s[0]-s[1]

# 凍結3条件 (EXCLUSION_REPORT_20260818): A fav_p>=0.341 / B ent<=1.904 / C sgapV3>=0.066
def keep(r):
    o = r['odds']
    iv = {k: 1.0/v for k, v in o.items() if v}
    if len(iv) < 6: return False
    tot = sum(iv.values())
    fav = max(iv.values())/tot
    ent = -sum((x/tot)*math.log(x/tot) for x in iv.values())
    sg = led.get(r['rid'])
    return fav >= 0.341 and ent <= 1.904 and (sg is not None and sg >= 0.066)

F = [r for r in races if keep(r)]
seg = lambda rs, lo, hi: [r for r in rs if lo <= r['month'] <= hi]
FM, FV, FC = seg(F,'000000','202602'), seg(F,'202603','202605'), seg(F,'202606','202608')
print(f"絞り後: MINE {len(FM)} / VAL {len(FV)} / CONF {len(FC)}  (全体 {len(races)})")

H, K = 20, 16
def pack(rs):
    R=len(rs); Xp=np.zeros((R,H,K)); mask=np.zeros((R,H),bool); T=np.zeros((R,3),int)
    for i,r in enumerate(rs):
        n=len(r['nums']); Xp[i,:n]=r['Z16']; mask[i,:n]=True; T[i]=r['top3']
    return Xp,mask,T
def ll_grad(w,P):
    Xp,mask,T=P
    s=np.where(mask,Xp@w,-1e9).copy(); alive=mask.copy()
    ll=0.; g=np.zeros(K); R=len(s); idx=np.arange(R)
    for k in range(3):
        m=s.max(1,keepdims=True); e=np.exp(s-m)*alive
        Z=e.sum(1,keepdims=True); p=e/Z; pick=T[:,k]
        ll+=(s[idx,pick]-m[:,0]-np.log(Z[:,0])).sum()
        g+=(Xp[idx,pick]-np.einsum('rh,rhf->rf',p,Xp)).sum(0)
        alive[idx,pick]=False; s[idx,pick]=-1e9
    return ll/R,g/R
def fit(P,w0=None,ridge=0.,anchor=None,iters=300,lr=0.3):
    w=np.zeros(K) if w0 is None else w0.copy()
    a=np.zeros(K) if anchor is None else anchor
    m=np.zeros(K); v=np.zeros(K)
    for t in range(1,iters+1):
        _,g=ll_grad(w,P); g-=ridge*(w-a)
        m=.9*m+.1*g; v=.99*v+.01*g*g
        w+=lr*(m/(1-.9**t))/(np.sqrt(v/(1-.99**t))+1e-8)
    return w

# 汎用B-sd16(全レース学習・既存pkl) と 絞り専用(wF) と 絞り×sd別(wFs)
import pickle, ast
res = pickle.load(open('v99w2_result.pkl','rb'))
wg16 = np.array(res['arm2_w']['wg16'])
ws16 = {ast.literal_eval(k): np.array(v) for k,v in res['arm2_w']['ws16'].items()}
wF = fit(pack(FM))                      # 絞り専用・全体1本
# 絞り×sd別: λはMINE内部後方20%で選択
mm = sorted({r['month'] for r in FM}); cut = mm[int(len(mm)*0.8)]
FIN = [r for r in FM if r['month'] < cut]; FIV = [r for r in FM if r['month'] >= cut]
wF_in = fit(pack(FIN))
def sdkey(r): return V.axis_key(r,'sd')
byc = collections.defaultdict(list)
for r in FIN: byc[sdkey(r)].append(r)
def evll(wmap, base, rs):
    tot=0
    for r in rs:
        w=wmap.get(sdkey(r), base)
        ll,_=ll_grad(w, pack([r])); tot+=ll
    return tot/len(rs)
base_iv = evll({}, wF_in, FIV)
best=None
for lam in [10.,3.,1.,0.3]:
    wmap={k: fit(pack(v), w0=wF_in, ridge=lam, anchor=wF_in, iters=200) for k,v in byc.items() if len(v)>=25}
    x=evll(wmap, wF_in, FIV)
    print(f"  λ={lam:<5} 内部検証ΔLL/R={x-base_iv:+.4f}")
    if best is None or x>best[1]: best=(lam,x)
lam=best[0]; print("採用λ=",lam)
bycM=collections.defaultdict(list)
for r in FM: bycM[sdkey(r)].append(r)
wFs={k: fit(pack(v), w0=wF, ridge=lam, anchor=wF, iters=250) for k,v in bycM.items() if len(v)>=25}

def rank_of(r, mode):
    if mode=='gen':  w = ws16.get(sdkey(r), wg16)
    elif mode=='flt': w = wF
    else:            w = wFs.get(sdkey(r), wF)
    s = r['Z16'] @ w
    key = sorted(range(len(s)), key=lambda i: (-s[i], -r['wavg'][i], r['nums'][i]))
    return [r['nums'][i] for i in key]
def mkt_rank(r):
    return [n for n,_ in sorted(r['odds'].items(), key=lambda kv: kv[1])]

def k2(a,b): a,b=int(a),int(b); return f"{min(a,b)}-{max(a,b)}"
def k3(t): s=sorted(int(x) for x in t); return "-".join(map(str,s))
def evalset(rs, ranker):
    out={}
    def acc(nm,c,r_,h,n): out[nm]=(n, h/n*100 if n else 0, r_/c*100 if c else 0)
    import itertools
    c1=r1=h1=c2=r2=h2=cw=rw=hw=ct=rt=ht=n=0
    for r in rs:
        rk=ranker(r); fin=[r['nums'][i] for i in r['top3']]
        pay=r['payout']; n+=1
        v=(pay.get('複勝') or {}).get(str(rk[0])) or (pay.get('複勝') or {}).get(rk[0])
        # payoutキーが文字列/数値どちらか吸収
        fuku=pay.get('複勝') or {}
        fuku={int(k):x for k,x in fuku.items()}
        c1+=100; v=fuku.get(int(rk[0]))
        if v: r1+=v; h1+=1
        c2+=200; got=0
        for hh in rk[:2]:
            v=fuku.get(int(hh))
            if v: r2+=v; got=1
        h2+=got
        wd={k:x for k,x in (pay.get('ワイド') or {}).items()}
        cw+=100; v=wd.get(k2(rk[0],rk[1]))
        if v: rw+=v; hw+=1
        tr=pay.get('三連複') or {}
        ct+=100; v=tr.get(k3(rk[:3]))
        if v: rt+=v; ht+=1
    acc('複勝1点',c1,r1,h1,n); acc('複勝2点',c2,r2,h2,n)
    acc('ワイド1-2',cw,rw,hw,n); acc('三連複上位3',ct,rt,ht,n)
    return out

print("\n=== 絞ったレース内での比較(的中率% / ROI%) ===")
for nm, rs in [("MINE",FM),("VALIDATE",FV),("CONFIRM",FC)]:
    print(f"\n-- {nm} n={len(rs)} --")
    rows={}
    for lab,mode in [("市場上位2頭",None),("汎用B-sd16",'gen'),("絞り専用配点",'flt'),("絞り×sd別配点",'sds')]:
        ranker = mkt_rank if mode is None else (lambda r,m=mode: rank_of(r,m))
        rows[lab]=evalset(rs, ranker)
    kinds=['複勝1点','複勝2点','ワイド1-2','三連複上位3']
    print(f"{'方式':<14}"+"".join(f"{k:>16}" for k in kinds))
    for lab,o in rows.items():
        print(f"{lab:<14}"+"".join(f"{o[k][1]:6.1f}/{o[k][2]:6.1f}  " for k in kinds))
np.save('/tmp/claude-0/-home-user--/a62f6054-2a2d-5711-b990-3a94f7d05b49/scratchpad/wF.npy', wF)
