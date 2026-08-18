import json, math
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
    if not pay.get('複勝'): continue
    mkt=[k for k,_ in srt]
    R.append(dict(month=r['month'],fav_p=srt[0][1],ent=ent,sgap=sc[0]-sc[1],mkt=mkt,
                  tan={k:float(o[k]) for k in mkt}, fuku=pay['複勝'], mdl=[str(x) for x in (r.get('order') or [])]))
seg=lambda lo,hi:[x for x in R if lo<=x['month']<=hi]
MINE,VAL,CONF=seg('202409','202602'),seg('202603','202605'),seg('202606','202608')
sel=lambda x: x['fav_p']>=0.341 and x['ent']<=1.904 and x['sgap']>=0.066
M,V,C=[[x for x in s if sel(x)] for s in (MINE,VAL,CONF)]

def buy(rs, pick, floor):
    """pick: function(x)->list of 馬番str ; floor: 単勝オッズ下限"""
    c=r_=h=n=0
    for x in rs:
        hs=[k for k in pick(x) if x['tan'].get(k,0)>=floor]
        if not hs: continue
        n+=1; got=0
        for k in hs:
            c+=100
            v=x['fuku'].get(k)
            if v: r_+=v; got=1
        h+=got
    return n,(h/n*100 if n else 0),(r_/c*100 if c else 0)

picks={
 '市場1位':      lambda x:[x['mkt'][0]],
 '市場2位':      lambda x:[x['mkt'][1]],
 '市場3位':      lambda x:[x['mkt'][2]],
 '市場1-2位':    lambda x:x['mkt'][:2],
 'モデル1位':    lambda x:[x['mdl'][0]] if x['mdl'] else [],
 'モデル1位∧市場3位以下': lambda x:[x['mdl'][0]] if x['mdl'] and x['mdl'][0] in x['mkt'][2:] else [],
}
print("=== 例外除外後レース内での買い方 × 単勝オッズ下限 (MINE) ===")
print(f"{'買い方':<24}{'floor':>6}{'n':>6}{'的中':>8}{'ROI':>8}")
best=[]
for pn,pf in picks.items():
    for fl in [1.0,1.5,2.0,2.5,3.0,4.0,5.0,7.0,10.0]:
        n,h,roi=buy(M,pf,fl)
        if n>=100:
            print(f"{pn:<24}{fl:>6.1f}{n:>6}{h:>7.1f}%{roi:>7.1f}%")
            best.append((roi,pn,fl,pf))
best.sort(reverse=True)
print("\n=== MINE上位3案を VALIDATE / CONFIRM に1回だけ通す（多重比較=54通り） ===")
for roi,pn,fl,pf in best[:3]:
    print(f"\n[{pn} / 単勝floor {fl}倍]  MINE ROI {roi:.1f}%")
    for sn,ss in [("VALIDATE",V),("CONFIRM",C)]:
        n,h,r2=buy(ss,pf,fl)
        print(f"   {sn:<10} n={n:<5} 的中{h:5.1f}%  ROI {r2:6.1f}%")

print("\n\n=== 追試: 『市場2番人気の複勝』を floor無しでそのまま通す（探索なし・1案のみ） ===")
p2=picks['市場2位']; p1=picks['市場1位']
for lab,rs_all,rs_keep in [("全レース",None,None)]:
    pass
print(f"{'集合':<14}{'買い方':<10}{'n':>6}{'的中':>8}{'ROI':>8}")
for sn,(allr,keepr) in {"MINE":(MINE,M),"VALIDATE":(VAL,V),"CONFIRM":(CONF,C)}.items():
    for setlab,rs in [("除外なし",allr),("例外除外後",keepr)]:
        for pl,pf in [("市場1位",p1),("市場2位",p2)]:
            n,h,roi=buy(rs,pf,1.0)
            print(f"{sn+'/'+setlab:<20}{pl:<10}{n:>6}{h:>7.1f}%{roi:>7.1f}%")
    print()
