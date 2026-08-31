import json,glob,collections,pickle,datetime,os
fs=sorted(glob.glob('hist/*.json'))
races=[]
for f in fs:
    d=json.load(open(f))
    races.append(d)
# index horse_id -> list of (date_int, race_id, jockey_id, kinryo, weight)
idx=collections.defaultdict(list)
for d in races:
    dt=int(d['date']); rid=d['race'].get('race_id') or os.path.basename('')
    for h in d['race']['horses']:
        hid=h.get('horse_id')
        if not hid: continue
        idx[hid].append((dt, rid, h.get('jockey_id'), h.get('kinryo'), h.get('weight')))
for k in idx: idx[k].sort()
pickle.dump(dict(idx), open('jr/hidx.pkl','wb'))

def d2date(x):
    s=str(x); return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:8]))

tot=0; have_prior=0; match_days=0; jok=0; kin=0
gap_err=collections.Counter()
for d in races:
    dt=int(d['date']); D=d2date(dt)
    for h in d['race']['horses']:
        hid=h.get('horse_id'); tot+=1
        if not hid: continue
        L=h.get('last_race_days')
        prior=[e for e in idx[hid] if e[0]<dt]
        if not prior: continue
        have_prior+=1
        p=prior[-1]
        gap=(D-d2date(p[0])).days
        if L is not None and abs(gap-L)<=1:
            match_days+=1
            if p[2] and h.get('jockey_id'): jok+=1
            if p[3] is not None and h.get('kinryo') is not None: kin+=1
        gap_err[min(abs(gap-(L if L is not None else -999)),999)]+=1
print('total horse-entries',tot)
print('has prior in hist',have_prior, round(100*have_prior/tot,1),'%')
print('prior==true last race (days match)',match_days, round(100*match_days/tot,1),'%')
print('  with both jockey_id',jok, round(100*jok/tot,1),'%')
print('  with both kinryo',kin, round(100*kin/tot,1),'%')
