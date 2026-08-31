import json, math, statistics as st
rows=[json.loads(l) for l in open('wf_preds_v3ext2.jsonl')]
def imp(o):
    v={k:1.0/float(x) for k,x in o.items() if x and float(x)>0}
    s=sum(v.values()); return {k:x/s for k,x in v.items()}
recs=[]
for r in rows:
    o=r.get('odds') or {}
    if len(o)<5: continue
    p=imp(o)
    srt=sorted(p.items(), key=lambda kv:-kv[1])
    fav=srt[0][0]
    ent=-sum(x*math.log(x) for x in p.values())
    top3=sum(x for _,x in srt[:3])
    gap=srt[0][1]-srt[1][1]
    pay=r.get('payout') or {}
    tan=pay.get('単勝',{}); fuku=pay.get('複勝',{})
    if not tan or not fuku: continue
    hit_t = 1 if fav in tan else 0
    ret_t = tan.get(fav,0)
    hit_f = 1 if fav in fuku else 0
    ret_f = fuku.get(fav,0)
    sc=r.get('scores') or []
    sgap = (sc[0]-sc[1]) if len(sc)>1 else 0
    recs.append(dict(month=r['month'],field=r['field'],fav_p=srt[0][1],ent=ent,top3=top3,gap=gap,sgap=sgap,
                     hit_t=hit_t,ret_t=ret_t,hit_f=hit_f,ret_f=ret_f))
def seg(rs,lo,hi): return [x for x in rs if lo<=x['month']<=hi]
MINE=seg(recs,'202409','202602'); VAL=seg(recs,'202603','202605'); CONF=seg(recs,'202606','202608')
print(f"n MINE={len(MINE)} VAL={len(VAL)} CONF={len(CONF)}")
def report(name,rs,key,nb=5):
    rs=sorted(rs,key=lambda x:x[key])
    n=len(rs); print(f"\n=== {name} split by {key} ({n}R) ===")
    print(f"{'bucket':<8}{'n':>5}{'単的中':>8}{'単ROI':>8}{'複的中':>8}{'複ROI':>8}")
    for i in range(nb):
        b=rs[n*i//nb:n*(i+1)//nb]
        m=len(b)
        ht=sum(x['hit_t'] for x in b)/m*100; rt=sum(x['ret_t'] for x in b)/m
        hf=sum(x['hit_f'] for x in b)/m*100; rf=sum(x['ret_f'] for x in b)/m
        print(f"{i+1:<8}{m:>5}{ht:>7.1f}%{rt:>7.1f}%{hf:>7.1f}%{rf:>7.1f}%")
for k in ['fav_p','ent','field','sgap']:
    report('VAL+CONF',VAL+CONF,k)

# --- 例外除外を重ねる: MINEで閾値決め → VAL/CONFで検証 ---
import itertools
def q(rs,key,p):
    v=sorted(x[key] for x in rs); return v[int(len(v)*p)]
th={k:q(MINE,k,0.60) for k in ['fav_p']}
th['ent']=q(MINE,'ent',0.40)
th['sgap']=q(MINE,'sgap',0.40)
print("\n\n=== 例外除外の積み重ね(閾値はMINEのみで決定) ===")
print("条件: fav_p>=%.3f  ent<=%.3f  sgap>=%.3f"%(th['fav_p'],th['ent'],th['sgap']))
def ev(rs,f,label):
    b=[x for x in rs if f(x)]
    if not b: print(f"{label:<26} n=0"); return
    m=len(b)
    print(f"{label:<26} n={m:<5} 単的中{sum(x['hit_t'] for x in b)/m*100:5.1f}% 単ROI{sum(x['ret_t'] for x in b)/m:6.1f}% "
          f"複的中{sum(x['hit_f'] for x in b)/m*100:5.1f}% 複ROI{sum(x['ret_f'] for x in b)/m:6.1f}%")
conds=[("全レース", lambda x:True),
       ("A:fav_p", lambda x:x['fav_p']>=th['fav_p']),
       ("B:低entropy", lambda x:x['ent']<=th['ent']),
       ("C:得点差大", lambda x:x['sgap']>=th['sgap']),
       ("A+B", lambda x:x['fav_p']>=th['fav_p'] and x['ent']<=th['ent']),
       ("A+C", lambda x:x['fav_p']>=th['fav_p'] and x['sgap']>=th['sgap']),
       ("A+B+C", lambda x:x['fav_p']>=th['fav_p'] and x['ent']<=th['ent'] and x['sgap']>=th['sgap'])]
for nm,f in conds:
    print(f"\n--{nm}--")
    for sn,ss in [("MINE",MINE),("VALIDATE",VAL),("CONFIRM",CONF)]:
        ev(ss,f,"  "+sn)
