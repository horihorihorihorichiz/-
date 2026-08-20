import json,glob,collections,pickle,datetime,os
# combined index: horse_id -> {date_int: (jockey_id, kinryo)}
rides=collections.defaultdict(dict)
for f in glob.glob('hist_enrich/*.json'):
    d=json.load(open(f)); dt=int(d['date'])
    for h in d['horses']:
        hid=h.get('horse_id')
        if hid: rides[hid].setdefault(dt,{}).update(jid=h.get('jockey_id'))
for f in glob.glob('hist/*.json'):
    d=json.load(open(f)); dt=int(d['date'])
    for h in d['race']['horses']:
        hid=h.get('horse_id')
        if not hid: continue
        e=rides[hid].setdefault(dt,{})
        if h.get('jockey_id') and not e.get('jid'): e['jid']=h['jockey_id']
        if h.get('kinryo') is not None: e['kin']=h['kinryo']
pickle.dump({k:dict(v) for k,v in rides.items()}, open('jr/rides.pkl','wb'))
def dd(x):
    s=str(x); return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:8]))
# current jockey from enrich too
cur_j={}
for f in glob.glob('hist_enrich/*.json'):
    d=json.load(open(f))
    cur_j[d['race_id']]={h['horse_id']:h.get('jockey_id') for h in d['horses'] if h.get('horse_id')}
pickle.dump(cur_j, open('jr/curj.pkl','wb'))

per=collections.defaultdict(lambda: collections.Counter())
for f in glob.glob('hist/*.json'):
    d=json.load(open(f)); dt=int(d['date']); m=str(dt)[:6]; D=dd(dt); rid=d['race'].get('race_id')
    for h in d['race']['horses']:
        c=per[m]; c['n']+=1
        hid=h.get('horse_id'); L=h.get('last_race_days')
        cj=h.get('jockey_id') or cur_j.get(rid,{}).get(hid)
        if cj: c['curj']+=1
        if not hid or L is None: continue
        pdt=int((D-datetime.timedelta(days=L)).strftime('%Y%m%d'))
        cand=[k for k in rides.get(hid,{}) if abs((D-dd(k)).days-L)<=1 and k<dt]
        if not cand: continue
        c['prev']+=1
        e=rides[hid][max(cand)]
        if e.get('jid'): c['prevj']+=1
        if e.get('kin') is not None: c['prevk']+=1
        if cj and e.get('jid'): c['bothj']+=1
print('month  n  curj%  prev%  prevJ%  bothJ%  prevKin%')
for m in sorted(per):
    c=per[m]; n=c['n']
    print(m,n, *[round(100*c[k]/n,1) for k in ('curj','prev','prevj','bothj','prevk')])
def agg(ms):
    c=collections.Counter()
    for m in ms: c.update(per[m])
    n=c['n']; return n, {k:round(100*c[k]/n,1) for k in ('curj','prev','prevj','bothj','prevk')}
allm=sorted(per)
MINE=[m for m in allm if m<='202602']; VAL=[m for m in allm if '202603'<=m<='202605']; CONF=[m for m in allm if '202606'<=m<='202608']
for nm,ms in (('MINE',MINE),('VAL',VAL),('CONF',CONF)):
    print(nm, agg(ms))
