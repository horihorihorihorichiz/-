import sys,numpy as np,pickle,collections
sys.path.insert(0,'/home/user/-/keiba/jr')
import fit as F
rows=F.rows

# ---- scale: base LL/race ----
print('=== base (market-only) LL per race ===')
for per in ('MINE','VAL','CONF'):
    X,o,y,g,names,_=F.build(('H1',),per); ng=g.max()+1
    base=F.ll_parts(X,o,y,g,np.zeros(X.shape[1]),ng)
    print(f'  {per:5s} nR={ng} baseLL/race={base.mean():.5f}  (top1 market hit={np.mean([1 for _ in range(0)]) if False else 0:.0f})')

# ---- descriptives ----
print('=== descriptives (linked rows only) ===')
for per in ('MINE','VAL','CONF'):
    n=0;lk=0;chg=0;newp=0;dks=[];wcs=[];lng=0;ntot=0
    for rid,dt,rr in rows:
        if F.period(dt)!=per: continue
        for r in rr:
            ntot+=1
            if r['cj'] and r['pj']:
                lk+=1; chg+= (r['cj']!=r['pj'])
                if r['npr']==0: newp+=1
            if r['pk'] is not None and r['kin'] is not None: dks.append(r['kin']-r['pk'])
            if r['wc'] is not None: wcs.append(r['wc'])
            if r['ivl'] and r['ivl']>90: lng+=1
    dks=np.array(dks); wcs=np.array(wcs)
    print(f'  {per:5s} rows={ntot} linkedJ={lk}({100*lk/ntot:.1f}%) 乗替率={100*chg/max(lk,1):.1f}% 初コンビ率={100*newp/max(lk,1):.1f}%')
    print(f'         斤量差 mean={dks.mean():+.3f} sd={dks.std():.3f} |dk|>0の割合={100*(dks!=0).mean():.1f}%  馬体重変化 sd={wcs.std():.2f}  間隔>90d={100*lng/ntot:.1f}%')

# ---- null control for H2 (only hypothesis with dLL>0 in both VAL & CONF) ----
print('=== null control: H2 ===')
rng=np.random.default_rng(7)
def h2_dll(per,beta):
    X,o,y,g,names,_=F.build(('H2',),per); ng=g.max()+1
    return (F.ll_parts(X,o,y,g,beta,ng)-F.ll_parts(X,o,y,g,np.zeros(len(beta)),ng)).mean()
Xm,om,ym,gm,names,_=F.build(('H2',),'MINE'); ngm=gm.max()+1
beta=F.fit(Xm,om,ym,gm,ngm)
real={p:h2_dll(p,beta) for p in ('VAL','CONF')}
print('  real  VAL %+.6f  CONF %+.6f' % (real['VAL'],real['CONF']))

# null A: shuffle winner within race (market offset unchanged), refit on MINE, eval VAL/CONF
def shuffled_rows(seed):
    r2=[];rg=np.random.default_rng(seed)
    for rid,dt,rr in rows:
        k=rg.integers(0,len(rr))
        nn=[dict(x) for x in rr]
        for i,x in enumerate(nn): x['win']=1 if i==k else 0
        r2.append((rid,dt,nn))
    return r2
orig=F.rows
nullA={'VAL':[], 'CONF':[]}
for b in range(200):
    F.rows=shuffled_rows(1000+b)
    Xs,os_,ys,gs,_,_=F.build(('H2',),'MINE'); bs=F.fit(Xs,os_,ys,gs,gs.max()+1)
    for p in ('VAL','CONF'):
        X,o,y,g,_,_=F.build(('H2',),p); ng=g.max()+1
        nullA[p].append((F.ll_parts(X,o,y,g,bs,ng)-F.ll_parts(X,o,y,g,np.zeros(len(bs)),ng)).mean())
F.rows=orig
for p in ('VAL','CONF'):
    a=np.array(nullA[p]); pct=(a>=real[p]).mean()
    print(f'  nullA(label shuffle) {p}: median={np.median(a):+.6f} p99={np.percentile(a,99):+.6f}  frac(null>=real)={pct:.3f}')

# null B: permute previous-jockey IDs within period (destroys the "change" info)
def permuted_rows(seed):
    rg=np.random.default_rng(seed)
    pool=collections.defaultdict(list)
    for rid,dt,rr in rows:
        for r in rr:
            if r['cj']: pool[F.period(dt)].append(r['cj'])
    r2=[]
    for rid,dt,rr in rows:
        per=F.period(dt); nn=[dict(x) for x in rr]
        for x in nn:
            x['pj']=pool[per][rg.integers(0,len(pool[per]))] if x['pj'] else None
            x['npr']=int(rg.integers(0,3)) if x['cj'] else 0
        r2.append((rid,dt,nn))
    return r2
nullB={'VAL':[], 'CONF':[]}
for b in range(200):
    F.rows=permuted_rows(5000+b)
    Xs,os_,ys,gs,_,_=F.build(('H2',),'MINE'); bs=F.fit(Xs,os_,ys,gs,gs.max()+1)
    for p in ('VAL','CONF'):
        X,o,y,g,_,_=F.build(('H2',),p); ng=g.max()+1
        nullB[p].append((F.ll_parts(X,o,y,g,bs,ng)-F.ll_parts(X,o,y,g,np.zeros(len(bs)),ng)).mean())
F.rows=orig
for p in ('VAL','CONF'):
    a=np.array(nullB[p]); pct=(a>=real[p]).mean()
    print(f'  nullB(jockeyID permute) {p}: median={np.median(a):+.6f} p99={np.percentile(a,99):+.6f}  frac(null>=real)={pct:.3f}')
