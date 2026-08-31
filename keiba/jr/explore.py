import sys,pickle,numpy as np
sys.path.insert(0,'/home/user/-/keiba/jr')
import fit as F

def mine_only(spec,label):
    X,o,y,g,names,_=F.build(spec,'MINE'); ng=g.max()+1
    b=F.fit(X,o,y,g,ng)
    d=F.ll_parts(X,o,y,g,b,ng)-F.ll_parts(X,o,y,g,np.zeros(len(b)),ng)
    # LR chi2
    lr=2*d.sum()
    print(f'{label:28s} k={len(b)} dLL/race(in-sample)={d.mean():+.6f} LRchi2={lr:8.2f} beta={dict(zip(names,np.round(b,4)))}')
    return d.mean()

trials=[]
for s,l in [(('H1',),'H1 chg'),
            (('H2',),'H2 newpair+lnrides'),
            (('H3',),'H3 dk clip3 + dk_pos'),
            (('H3lin',),'H3lin dk clip3'),
            (('H4',),'H4 wc,wc2,lng,wc*lng'),
            (('H4b',),'H4b wc,wc2'),
            (('H1','H2'),'H1+H2'),
            (('H1','H2','H3','H4'),'H5 all')]:
    mine_only(s,l); trials.append(l)
print('MINE trials run:',len(trials))
