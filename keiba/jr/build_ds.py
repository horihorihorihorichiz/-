import json,glob,collections,pickle,datetime,os,numpy as np
def dd(x):
    s=str(x); return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:8]))

# ---- ride index: horse_id -> {date:{jid,kin}} ----
rides=collections.defaultdict(dict)
for f in glob.glob('hist_enrich/*.json'):
    d=json.load(open(f)); dt=int(d['date'])
    for h in d['horses']:
        hid=h.get('horse_id')
        if hid and h.get('jockey_id'): rides[hid].setdefault(dt,{})['jid']=h['jockey_id']
cur_j={}
for f in glob.glob('hist_enrich/*.json'):
    d=json.load(open(f))
    cur_j[d['race_id']]={h['horse_id']:h.get('jockey_id') for h in d['horses'] if h.get('horse_id')}
for f in glob.glob('hist/*.json'):
    d=json.load(open(f)); dt=int(d['date'])
    for h in d['race']['horses']:
        hid=h.get('horse_id')
        if not hid: continue
        e=rides[hid].setdefault(dt,{})
        if h.get('jockey_id') and not e.get('jid'): e['jid']=h['jockey_id']
        if h.get('kinryo') is not None: e['kin']=h['kinryo']

rows=[]; rid_of=[]
files=sorted(glob.glob('hist/*.json'))
for f in files:
    d=json.load(open(f)); dt=int(d['date']); D=dd(dt); rid=d['race'].get('race_id') or os.path.basename(f)[:-5]
    res={o['num']:o for o in d['result']['order']}
    hs=d['race']['horses']
    if len(hs)<4: continue
    ok=True
    rr=[]
    for h in hs:
        o=res.get(h['num'])
        if o is None or not o.get('odds'): ok=False; break
        hid=h.get('horse_id')
        cj=h.get('jockey_id') or cur_j.get(rid,{}).get(hid)
        L=h.get('last_race_days'); kin=h.get('kinryo'); wc=h.get('weight_change')
        pj=None; pk=None
        if hid and L is not None:
            cand=[k for k in rides.get(hid,{}) if k<dt and abs((D-dd(k)).days-L)<=1]
            if cand:
                e=rides[hid][max(cand)]; pj=e.get('jid'); pk=e.get('kin')
        # career pair experience (strictly before D)
        npr=0
        if hid and cj:
            for k,e in rides.get(hid,{}).items():
                if k<dt and e.get('jid')==cj: npr+=1
        rr.append(dict(num=h['num'],odds=float(o['odds']),win=1 if str(o.get('rank'))=='1' else 0,
                       cj=cj,pj=pj,kin=kin,pk=pk,wc=wc,ivl=L,npr=npr,hid=hid))
    if not ok: continue
    if sum(r['win'] for r in rr)!=1: continue
    rows.append((rid,dt,rr))

print('races',len(rows),'entries',sum(len(r[2]) for r in rows))
pickle.dump(rows, open('jr/rows.pkl','wb'))
