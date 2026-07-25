# -*- coding: utf-8 -*-
"""新潟芝1000m直線の過去レースを db.netkeiba から収穫。
   rid総当たり(新潟=04, 回1-4, 日1-16, R1-12)で芝1000のみ抽出。
   出力: n1000_races.jsonl {rid, date, name, field, baba, rows:[{fin,waku,num,odds,pop,name}], pay:{...}}
   usage: python3 n1000_harvest.py 2021 2025  (途中再開可: 既存ridはスキップ)"""
import json, os, re, sys, time
import fetch_race as FR

OUT = "n1000_races.jsonl"
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["rid"])
        except Exception: pass

COURSE_RE = re.compile(r'芝[^<m]{0,8}1000m')

def parse(html, rid):
    if not COURSE_RE.search(html):
        return None
    m = re.search(r'race_table_01[^>]*>(.*?)</table>', html, re.S)
    if not m:
        return None
    strip = lambda s: re.sub(r'<[^>]+>', '', s).strip()
    head = [strip(h).split("\n")[0] for h in re.findall(r'<th[^>]*>(.*?)</th>', m.group(1), re.S)]
    try:
        I = {k: head.index(k) for k in ["着順", "枠番", "馬番", "馬名", "単勝", "人気", "上り"]}
    except ValueError:
        return None
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S)[1:]:
        tds = [strip(t) for t in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if len(tds) <= I["人気"]:
            continue
        num = tds[I["馬番"]]
        if not num.isdigit():
            continue
        odds = tds[I["単勝"]]; pop = tds[I["人気"]]
        rows.append(dict(fin=tds[I["着順"]], waku=int(tds[I["枠番"]] or 0),
                         num=int(num), name=tds[I["馬名"]],
                         agari=tds[I["上り"]],
                         odds=float(odds) if re.match(r'^\d+(\.\d+)?$', odds) else None,
                         pop=int(pop) if pop.isdigit() else None))
    if not rows:
        return None
    tm = re.search(r'<title>([^<|]{2,40})', html)
    dt = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', html)
    baba = re.search(r'芝\s*:\s*([^&<]+)', html)
    pay = {}
    for sec in re.findall(r'<th[^>]*>(単勝|複勝|三連複|馬連|ワイド)</th>(.*?)</tr>', html, re.S):
        kind, body = sec
        nums = re.findall(r'>([\d\s\-]+)<', body)
        yen = re.findall(r'>([\d,]+)円?<', body)
        pay[kind] = {"raw_nums": [n.strip() for n in nums[:3]], "raw_yen": [y for y in yen[:3]]}
    return dict(rid=rid, name=tm.group(1).strip() if tm else "",
                date="%s%02d%02d" % (dt.group(1), int(dt.group(2)), int(dt.group(3))) if dt else "",
                baba=baba.group(1).strip()[:2] if baba else "", field=len(rows), rows=rows, pay=pay)

y0, y1 = int(sys.argv[1]), int(sys.argv[2])
found = 0; scanned = 0
with open(OUT, "a", encoding="utf-8") as f:
    for y in range(y0, y1 + 1):
        for kai in range(1, 5):
            day_empty = 0
            for day in range(1, 17):
                hit_day = False
                for rr in range(1, 13):
                    rid = f"{y}04{kai:02d}{day:02d}{rr:02d}"
                    if rid in done:
                        hit_day = True
                        continue
                    scanned += 1
                    try:
                        html = FR.get(f"https://db.netkeiba.com/race/{rid}/", "euc-jp")
                    except Exception:
                        time.sleep(1.0); continue
                    if "race_table_01" not in html:
                        break  # このRが無い=以降のRも無い(日が存在しない)
                    hit_day = True
                    d = parse(html, rid)
                    if d:
                        f.write(json.dumps(d, ensure_ascii=False) + "\n"); f.flush()
                        found += 1
                        print(f"FOUND {rid} {d['date']} {d['name'][:16]} field={d['field']}", flush=True)
                    time.sleep(0.35)
                if not hit_day:
                    day_empty += 1
                    if day_empty >= 3:
                        break  # この回はもう無い
print(f"DONE scanned={scanned} found={found}")
