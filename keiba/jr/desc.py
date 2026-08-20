import sys,numpy as np
sys.path.insert(0,'/home/user/-/keiba/jr')
import fit as F
rows=F.rows
def tab(sel_fn,label,pers=('MINE','VAL','CONF')):
    print(f'--- {label} ---')
    print(' 期    群    n     市場想定勝率  実勝率   実/想定')
    for per in pers:
        acc={}
        for rid,dt,rr in rows:
            if F.period(dt)!=per: continue
            inv=np.array([1.0/r['odds'] for r in rr]); p=inv/inv.sum()
            for r,pp in zip(rr,p):
                k=sel_fn(r)
                if k is None: continue
                a=acc.setdefault(k,[0,0.0,0])
                a[0]+=1; a[1]+=pp; a[2]+=r['win']
        for k in sorted(acc):
            n,ps,w=acc[k]
            print(f' {per:5s} {str(k):8s} {n:6d}  {100*ps/n:6.2f}%   {100*w/n:6.2f}%   {w/ps:6.3f}')
tab(lambda r: ('乗替' if r['cj']!=r['pj'] else '継続') if (r['cj'] and r['pj']) else None, '(a) 乗り替わり')
tab(lambda r: ('初コンビ' if r['npr']==0 else '経験有') if (r['cj'] and r['pj']) else None, '(a2) 当該馬騎乗経験')
def dkb(r):
    if r['pk'] is None or r['kin'] is None: return None
    d=r['kin']-r['pk']
    return '減' if d<=-0.5 else ('増' if d>=0.5 else '同')
tab(dkb,'(b) 斤量前走差')
def wcb(r):
    w=r['wc'] if r['wc'] is not None else 0; v=r['ivl'] or 0
    lg='長' if v>90 else '短'
    b='<-6' if w<-6 else ('-6..-1' if w<0 else ('0' if w==0 else ('+1..+6' if w<=6 else '>+6')))
    return lg+b
tab(wcb,'(c) 馬体重変化 x 間隔(>90d=長)')
