# -*- coding: utf-8 -*-
"""新潟千直の専用特徴を収穫: 各出走馬の horse_id を取り、
   「その馬がその日より前に新潟芝1000直を走った成績」を作る。
   出力: n1000_feat.json {rid: {馬番: {horse_id, prior_runs, prior_best, prior_top3}}}
   ※ prior_* はそのレース以前の千直出走のみ(リーク無し)"""
import json, os, re, time
import fetch_race as FR

races = {}
for l in open("n1000_races.jsonl", encoding="utf-8"):
    d = json.loads(l)
    races[d["rid"]] = d
print(f"races={len(races)}")

# --- 1) 各レースの出走馬 horse_id を db ページから取る ---
IDS = "n1000_ids.json"
ids = json.load(open(IDS, encoding="utf-8")) if os.path.exists(IDS) else {}
todo = [r for r in races if r not in ids]
print(f"horse_id未取得: {len(todo)}R")
for i, rid in enumerate(todo):
    try:
        html = FR.get(f"https://db.netkeiba.com/race/{rid}/", "euc-jp")
        m = re.search(r'race_table_01[^>]*>(.*?)</table>', html, re.S)
        if not m:
            continue
        strip = lambda s: re.sub(r'<[^>]+>', '', s).strip()
        head = [strip(h).split("\n")[0] for h in re.findall(r'<th[^>]*>(.*?)</th>', m.group(1), re.S)]
        try:
            inum = head.index("馬番")
        except ValueError:
            continue
        row = {}
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S)[1:]:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
            if len(tds) <= inum:
                continue
            num = strip(tds[inum])
            hid = re.search(r'/horse/(\d+)', tr)
            if num.isdigit() and hid:
                row[num] = hid.group(1)
        ids[rid] = row
        if (i + 1) % 20 == 0:
            json.dump(ids, open(IDS, "w"), ensure_ascii=False)
            print(f"  {i+1}/{len(todo)}", flush=True)
        time.sleep(0.3)
    except Exception as e:
        print(f"  FAIL {rid} {repr(e)[:40]}", flush=True)
json.dump(ids, open(IDS, "w"), ensure_ascii=False)
print(f"horse_id取得済み: {len(ids)}R")

# --- 2) 同コース(新潟芝1000直)の過去成績を、収穫済み104Rの中から構築 ---
#     (netkeibaを再取得せず、手持ちデータだけで作れる=リークも無い)
hist = {}   # horse_id -> [(date, fin, waku, field)]
for rid, r in sorted(races.items(), key=lambda kv: kv[1]["date"]):
    idmap = ids.get(rid, {})
    for h in r["rows"]:
        hid = idmap.get(str(h["num"]))
        if not hid:
            continue
        hist.setdefault(hid, []).append((r["date"], h["fin"], h["waku"], r["field"]))

feat = {}
for rid, r in races.items():
    idmap = ids.get(rid, {})
    row = {}
    for h in r["rows"]:
        hid = idmap.get(str(h["num"]))
        prior = [x for x in hist.get(hid, []) if x[0] < r["date"]] if hid else []
        fins = []
        for _, fin, _, _ in prior:
            m = re.match(r"^(\d+)$", str(fin))
            if m:
                fins.append(int(m.group(1)))
        row[str(h["num"])] = dict(horse_id=hid, prior_runs=len(prior),
                                  prior_best=min(fins) if fins else None,
                                  prior_top3=sum(1 for f in fins if f <= 3))
    feat[rid] = row
json.dump(feat, open("n1000_feat.json", "w", encoding="utf-8"), ensure_ascii=False)
tot = sum(1 for r in feat.values() for v in r.values() if v["prior_runs"] > 0)
print(f"WROTE n1000_feat.json  千直経験馬の延べ数={tot}")
