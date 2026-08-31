import pickle,numpy as np,sys
from scipy.optimize import minimize
rows=pickle.load(open('jr/rows.pkl','rb'))

def period(dt):
    m=str(dt)[:6]
    if m<='202602': return 'MINE'
    if m<='202605': return 'VAL'
    return 'CONF'

def feats(r,spec):
    cj,pj,kin,pk,wc,ivl,npr=r['cj'],r['pj'],r['kin'],r['pk'],r['wc'],r['ivl'],r['npr']
    lj=1.0 if (cj and pj) else 0.0
    lk=1.0 if (pk is not None and kin is not None) else 0.0
    f={}
    if 'H1' in spec:
        f['chg']=(1.0 if (lj and cj!=pj) else 0.0); f['linkj']=lj
    if 'H2' in spec:
        f['newpair']=(1.0 if (cj and npr==0) else 0.0)
        f['lnrides']=np.log1p(npr) if cj else 0.0
        if 'H1' not in spec: f['linkj2']=lj
    if 'H3' in spec:
        dk=(kin-pk) if lk else 0.0
        dk=max(-3.0,min(3.0,dk))
        f['dk']=dk; f['dk_pos']=max(dk,0.0); f['linkk']=lk
    if 'H3lin' in spec:
        dk=(kin-pk) if lk else 0.0
        f['dk']=max(-3.0,min(3.0,dk)); f['linkk']=lk
    if 'H4' in spec:
        w=float(wc) if wc is not None else 0.0
        w=max(-30.0,min(30.0,w)); v=float(ivl) if ivl is not None else 0.0
        lng=1.0 if v>90 else 0.0
        f['wc']=w/10.0; f['wc2']=(w/10.0)**2; f['lng']=lng; f['wc_lng']=(w/10.0)*lng
    if 'H4b' in spec:
        w=float(wc) if wc is not None else 0.0
        w=max(-30.0,min(30.0,w)); v=float(ivl) if ivl is not None else 0.0
        f['wc']=w/10.0; f['wc2']=(w/10.0)**2
    return f

def build(spec, per=None):
    names=None; X=[];off=[];y=[];g=[];rids=[]
    gi=0
    for rid,dt,rr in rows:
        if per and period(dt)!=per: continue
        inv=np.array([1.0/r['odds'] for r in rr]); p=inv/inv.sum()
        fs=[feats(r,spec) for r in rr]
        if names is None: names=sorted(fs[0].keys())
        for r,f,pp in zip(rr,fs,p):
            X.append([f[n] for n in names]); off.append(np.log(pp)); y.append(r['win']); g.append(gi)
        rids.append(rid); gi+=1
    return np.array(X,float),np.array(off),np.array(y,int),np.array(g),names,rids

def ll_parts(X,off,y,g,beta,ng):
    u=off+X@beta
    m=np.full(ng,-1e18); np.maximum.at(m,g,u)
    e=np.exp(u-m[g]); s=np.zeros(ng); np.add.at(s,g,e)
    lse=m+np.log(s)
    win=np.zeros(ng); np.add.at(win,g,u*y)
    return win-lse   # per race LL

def fit(X,off,y,g,ng):
    k=X.shape[1]
    def nll(b):
        u=off+X@b
        m=np.full(ng,-1e18); np.maximum.at(m,g,u)
        e=np.exp(u-m[g]); s=np.zeros(ng); np.add.at(s,g,e)
        p=e/s[g]
        L=np.sum(u*y)-np.sum(m+np.log(s))
        gr=X.T@(y-p)
        return -L, -gr
    r=minimize(nll,np.zeros(k),jac=True,method='L-BFGS-B')
    return r.x

def evaluate(spec,label,B=2000,seed=0):
    Xm,om,ym,gm,names,_=build(spec,'MINE'); ngm=gm.max()+1
    beta=fit(Xm,om,ym,gm,ngm)
    out={'spec':label,'names':names,'beta':dict(zip(names,np.round(beta,4)))}
    rng=np.random.default_rng(seed)
    for per in ('MINE','VAL','CONF'):
        X,o,yy,g,_,rids=build(spec,per); ng=g.max()+1
        d=ll_parts(X,o,yy,g,beta,ng)-ll_parts(X,o,yy,g,np.zeros(len(beta)),ng)
        mean=d.mean()
        idx=rng.integers(0,ng,size=(B,ng))
        bs=d[idx].mean(axis=1)
        p=float((bs<=0).mean())
        out[per]=(ng,round(float(mean),6),round(float(np.percentile(bs,2.5)),6),round(float(np.percentile(bs,97.5)),6),p)
    return out

if __name__=='__main__':
    specs=eval(sys.argv[1]) if len(sys.argv)>1 else [('H1',),('H2',),('H3',),('H4',),('H1','H2','H3','H4')]
    for s in specs:
        r=evaluate(s,'+'.join(s))
        print('---',r['spec'])
        print('  beta',r['beta'])
        for per in ('MINE','VAL','CONF'):
            ng,m,lo,hi,p=r[per]
            print(f'  {per:5s} nR={ng:5d} dLL/race={m:+.6f} CI95=[{lo:+.6f},{hi:+.6f}] p(one-sided)={p:.4f}')
