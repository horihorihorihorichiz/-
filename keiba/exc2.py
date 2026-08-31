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
    ent=-sum(x*math.log(x) for x in p.values())
    sc=r.get('scores') or []; od=r.get('order') or []
    if len(sc)<3: continue
    pay=r.get('payout') or {}
    if not pay.get('複勝'): continue
    mkt=[k for k,_ in srt]          # 市場人気順(馬番str)
    mdl=[str(x) for x in od]        # モデル順
    R.append(dict(month=r['month'],fav_p=srt[0][1],ent=ent,sgap=sc[0]-sc[1],
                  mkt=mkt,mdl=mdl,pay=pay,field=r['field']))
def seg(lo,hi): return [x for x in R if lo<=x['month']<=hi]
MINE,VAL,CONF=seg('202409','202602'),seg('202603','202605'),seg('202606','202608')
def q(rs,k,p):
    v=sorted(x[k] for x in rs); return v[int(len(v)*p)]
TH=(q(MINE,'fav_p',0.60),q(MINE,'ent',0.40),q(MINE,'sgap',0.40))
sel=lambda x: x['fav_p']>=TH[0] and x['ent']<=TH[1] and x['sgap']>=TH[2]

def wide_key(a,b):
    for k in (f"{min(int(a),int(b))}-{max(int(a),int(b))}",):
        return k
def trio_key(t):
    s=sorted(int(v) for v in t); return "-".join(map(str,s))

def run(rs,label):
    out={}
    def acc(name,cost,ret,hit,n):
        out[name]=(n,hit/n*100 if n else 0, ret/cost*100 if cost else 0)
    # 1) 複勝 市場1番人気
    c=r_=h=n=0
    for x in rs:
        f=x['mkt'][0]; c+=100; n+=1
        v=x['pay'].get('複勝',{}).get(f)
        if v: r_+=v; h+=1
    acc('複勝 市場1人気(1点)',c,r_,h,n)
    # 2) 複勝 市場上位2頭
    c=r_=h=n=0
    for x in rs:
        n+=1; got=0
        for f in x['mkt'][:2]:
            c+=100; v=x['pay'].get('複勝',{}).get(f)
            if v: r_+=v; got=1
        h+=got
    acc('複勝 市場上位2(2点)',c,r_,h,n)
    # 3) ワイド 市場上位2頭BOX(1点)
    c=r_=h=n=0
    for x in rs:
        n+=1; c+=100
        k=wide_key(x['mkt'][0],x['mkt'][1])
        v=(x['pay'].get('ワイド') or {}).get(k)
        if v: r_+=v; h+=1
    acc('ワイド 市場1-2(1点)',c,r_,h,n)
    # 4) ワイド 市場上位3頭BOX(3点)
    c=r_=h=n=0
    for x in rs:
        n+=1; got=0
        for a,b in itertools.combinations(x['mkt'][:3],2):
            c+=100; v=(x['pay'].get('ワイド') or {}).get(wide_key(a,b))
            if v: r_+=v; got=1
        h+=got
    acc('ワイド 市場上位3BOX(3点)',c,r_,h,n)
    # 5) 三連複 市場上位3(1点)
    c=r_=h=n=0
    for x in rs:
        n+=1; c+=100
        v=(x['pay'].get('三連複') or {}).get(trio_key(x['mkt'][:3]))
        if v: r_+=v; h+=1
    acc('三連複 市場上位3(1点)',c,r_,h,n)
    # 6) 三連複 市場上位4BOX(4点)
    c=r_=h=n=0
    for x in rs:
        n+=1; got=0
        for t in itertools.combinations(x['mkt'][:4],3):
            c+=100; v=(x['pay'].get('三連複') or {}).get(trio_key(t))
            if v: r_+=v; got=1
        h+=got
    acc('三連複 市場上位4BOX(4点)',c,r_,h,n)
    # 7) 三連複 市場1位軸-2~5流し(6点)
    c=r_=h=n=0
    for x in rs:
        n+=1; got=0
        ax=x['mkt'][0]
        for a,b in itertools.combinations(x['mkt'][1:5],2):
            c+=100; v=(x['pay'].get('三連複') or {}).get(trio_key([ax,a,b]))
            if v: r_+=v; got=1
        h+=got
    acc('三連複 1位軸-2~5流し(6点)',c,r_,h,n)
    # 8) 三連複 モデル上位3(1点)
    c=r_=h=n=0
    for x in rs:
        n+=1; c+=100
        v=(x['pay'].get('三連複') or {}).get(trio_key(x['mdl'][:3]))
        if v: r_+=v; h+=1
    acc('三連複 モデル上位3(1点)',c,r_,h,n)
    print(f"\n########## {label}  n={len(rs)}R ##########")
    print(f"{'買い方':<26}{'的中率':>8}{'ROI':>9}")
    for k,(n,h,roi) in out.items():
        print(f"{k:<26}{h:>7.1f}%{roi:>8.1f}%")
    return out

for nm,ss in [("MINE",MINE),("VALIDATE",VAL),("CONFIRM",CONF)]:
    run([x for x in ss if sel(x)], f"{nm} 例外除外後(A+B+C)")
