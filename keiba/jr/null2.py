import sys,numpy as np,collections
sys.path.insert(0,'/home/user/-/keiba/jr')
import fit as F
rows=F.rows
# precompute arrays per period
P={}
for per in ('MINE','VAL','CONF'):
    cj=[];pj=[];npr=[];kin=[];pk=[];wc=[];ivl=[];off=[];y=[];g=[];gi=0
    for rid,dt,rr in rows:
        if F.period(dt)!=per: continue
        inv=np.array([1.0/r['odds'] for r in rr]); p=inv/inv.sum()
        for r,pp in zip(rr,p):
            cj.append(r['cj'] or ''); pj.append(r['pj'] or ''); npr.append(r['npr'])
            kin.append(r['kin'] if r['kin'] is not None else np.nan)
            pk.append(r['pk'] if r['pk'] is not None else np.nan)
            wc.append(r['wc'] if r['wc'] is not None else 0.0)
            ivl.append(r['ivl'] if r['ivl'] is not None else 0.0)
            off.append(np.log(pp)); y.append(r['win']); g.append(gi)
        gi+=1
    P[per]=dict(cj=np.array(cj),pj=np.array(pj),npr=np.array(npr,float),kin=np.array(kin),
                pk=np.array(pk),wc=np.array(wc,float),ivl=np.array(ivl,float),
                off=np.array(off),y=np.array(y,int),g=np.array(g),ng=gi)

def X_H2(d,pj=None,npr=None):
    cj=d['cj']; pj=d['pj'] if pj is None else pj; npr=d['npr'] if npr is None else npr
    lj=((cj!='')&(pj!='')).astype(float)
    newp=((cj!='')&(npr==0)).astype(float)
    lnr=np.where(cj!='',np.log1p(npr),0.0)
    return np.column_stack([lj,lnr,newp])   # linkj2, lnrides, newpair
def dll(d,X,beta,y=None):
    y=d['y'] if y is None else y
    a=F.ll_parts(X,d['off'],y,d['g'],beta,d['ng'])
    b=F.ll_parts(X,d['off'],y,d['g'],np.zeros(len(beta)),d['ng'])
    return (a-b).mean()

Xs={p:X_H2(P[p]) for p in P}
beta=F.fit(Xs['MINE'],P['MINE']['off'],P['MINE']['y'],P['MINE']['g'],P['MINE']['ng'])
print('H2 beta [linkj2,lnrides,newpair] =',np.round(beta,4))
real={p:dll(P[p],Xs[p],beta) for p in ('VAL','CONF')}
print('real  VAL %+.6f  CONF %+.6f'%(real['VAL'],real['CONF']))

def shuffle_y(d,rg):
    y=np.zeros(len(d['y']),int)
    starts=np.flatnonzero(np.r_[True,np.diff(d['g'])!=0]); ends=np.r_[starts[1:],len(y)]
    pick=starts+ (rg.random(len(starts))*(ends-starts)).astype(int)
    y[pick]=1; return y

rg=np.random.default_rng(7)
A={'VAL':[],'CONF':[]}
for b in range(200):
    ym=shuffle_y(P['MINE'],rg)
    bs=F.fit(Xs['MINE'],P['MINE']['off'],ym,P['MINE']['g'],P['MINE']['ng'])
    for p in ('VAL','CONF'): A[p].append(dll(P[p],Xs[p],bs))
for p in ('VAL','CONF'):
    a=np.array(A[p]); print(f'nullA(label shuffle) {p}: median={np.median(a):+.6f} p99={np.percentile(a,99):+.6f} frac(null>=real)={(a>=real[p]).mean():.3f}')

B={'VAL':[],'CONF':[]}
for b in range(200):
    Xp={}
    for p in P:
        d=P[p]; m=d['pj']!=''
        pjp=d['pj'].copy(); pool=d['cj'][d['cj']!='']
        pjp[m]=pool[rg.integers(0,len(pool),m.sum())]
        nprp=np.where(d['cj']!='', rg.integers(0,3,len(d['npr'])), 0).astype(float)
        Xp[p]=X_H2(d,pjp,nprp)
    bs=F.fit(Xp['MINE'],P['MINE']['off'],P['MINE']['y'],P['MINE']['g'],P['MINE']['ng'])
    for p in ('VAL','CONF'): B[p].append(dll(P[p],Xp[p],bs))
for p in ('VAL','CONF'):
    a=np.array(B[p]); print(f'nullB(jockey permute) {p}: median={np.median(a):+.6f} p99={np.percentile(a,99):+.6f} frac(null>=real)={(a>=real[p]).mean():.3f}')

print('=== base LL/race ===')
for p in ('MINE','VAL','CONF'):
    d=P[p]; print(' ',p,'nR=',d['ng'],'baseLL/race=%.5f'%F.ll_parts(np.zeros((len(d['y']),1)),d['off'],d['y'],d['g'],np.zeros(1),d['ng']).mean())
print('=== descriptives ===')
for p in ('MINE','VAL','CONF'):
    d=P[p]; n=len(d['y']); lj=(d['cj']!='')&(d['pj']!='')
    chg=(d['cj'][lj]!=d['pj'][lj]); newp=(d['npr'][d['cj']!='']==0)
    dk=d['kin']-d['pk']; dkv=dk[~np.isnan(dk)]
    print(f' {p:5s} rows={n} linkedJ={lj.sum()}({100*lj.mean():.1f}%) 乗替率={100*chg.mean():.1f}% 初コンビ率={100*newp.mean():.1f}%')
    print(f'       斤量差 n={len(dkv)} mean={dkv.mean():+.3f} sd={dkv.std():.3f} 非ゼロ={100*(dkv!=0).mean():.1f}% | 馬体重変化 sd={d["wc"].std():.2f} | 間隔>90d={100*(d["ivl"]>90).mean():.1f}%')
