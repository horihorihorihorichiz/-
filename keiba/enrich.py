# -*- coding: utf-8 -*-
"""hist/ の全レースについて結果ページを再取得し、自前スピード指数と騎手ファクターの
   材料（全馬の走破タイム・騎手・調教師・horse_id・上り・人気・オッズ・馬体重）を
   hist_enrich/<race_id>.json に保存する（Ver.101 A1/A2の収穫パス）。

   usage: python3 enrich.py [--workers 3]
   再実行すれば続きから（既存はスキップ）。"""
import argparse, glob, json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}


def t2sec(s):
    m = re.match(r"(?:(\d+):)?(\d+)\.(\d)", s or "")
    if not m:
        return None
    return (int(m.group(1) or 0))*60 + int(m.group(2)) + int(m.group(3))/10.0


def fetch_enrich(rid):
    host = "race.netkeiba.com" if rid[4:6] in {"%02d" % i for i in range(1, 11)} else "nar.netkeiba.com"
    req = urllib.request.Request(f"https://{host}/race/result.html?race_id={rid}", headers=UA)
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*".*?</tr>', h, re.S):
        num = re.search(r'class="Num Txt_C">\s*<div>(\d+)</div>', tr)
        if not num:
            continue
        rank = re.search(r'class="Rank">([^<]*)<', tr)
        hid = re.search(r'db\.netkeiba\.com/horse/(\d+)', tr)
        name = re.search(r'class="HorseNameSpan">([^<]+)<', tr)
        tm = re.search(r'class="Time">\s*(?:<span[^>]*>)?\s*([\d:.]+)', tr)
        agari = re.search(r'class="Time BgOrange[^"]*"[^>]*>\s*([\d.]+)', tr) or \
                re.search(r'class="Time[^"]*"[^>]*>\s*(3[0-9]\.\d)', tr)
        jockey = re.search(r'jockey/result/recent/(\d+)/[^>]*>\s*<span[^>]*>\s*([^<]+?)\s*</span>', tr, re.S)
        trainer = re.search(r'trainer/result/recent/(\d+)/[^>]*>\s*<span[^>]*>\s*([^<]+?)\s*</span>', tr, re.S)
        ninki = re.search(r'class="Odds[^"]*Txt_C"[^>]*>\s*(?:<[^>]+>)*\s*(\d+)', tr)
        odds = re.search(r'class="Odds Txt_R"[^>]*>\s*(?:<[^>]+>)*\s*([\d.]+)', tr)
        wt = re.search(r'class="Weight"[^>]*>\s*(\d{3})', tr)
        rows.append(dict(
            num=int(num.group(1)),
            rank=(rank.group(1).strip() if rank else ""),
            horse_id=(hid.group(1) if hid else None),
            name=(name.group(1).strip() if name else ""),
            time=(tm.group(1) if tm else None),
            time_sec=t2sec(tm.group(1) if tm else None),
            agari=(float(agari.group(1)) if agari else None),
            jockey=(jockey.group(2).strip() if jockey else None),
            jockey_id=(jockey.group(1) if jockey else None),
            trainer=(trainer.group(2).strip() if trainer else None),
            trainer_id=(trainer.group(1) if trainer else None),
            ninki=(int(ninki.group(1)) if ninki else None),
            odds=(float(odds.group(1)) if odds else None),
            weight=(int(wt.group(1)) if wt else None)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--outdir", default="hist_enrich")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    rids = [os.path.basename(f)[:-5] for f in glob.glob(os.path.join(a.histdir, "*.json"))]
    todo = [r for r in rids if not os.path.exists(os.path.join(a.outdir, f"{r}.json"))]
    print(f"enrich対象: {len(todo)}/{len(rids)}R", file=sys.stderr)
    done = [0]

    def one(rid):
        try:
            rows = fetch_enrich(rid)
            if not rows:
                return f"{rid} EMPTY"
            meta = json.load(open(os.path.join(a.histdir, f"{rid}.json"), encoding="utf-8"))
            out = dict(race_id=rid, date=meta.get("date", ""),
                       name=meta["race"].get("name", ""),
                       venue=meta["race"].get("venue", ""),
                       surface=meta["race"].get("surface", ""),
                       distance=meta["race"].get("distance", 0),
                       baba=meta["race"].get("baba", ""),
                       tier=meta["race"].get("today_tier", 0),
                       horses=rows)
            json.dump(out, open(os.path.join(a.outdir, f"{rid}.json"), "w",
                                encoding="utf-8"), ensure_ascii=False)
            done[0] += 1
            if done[0] % 100 == 0:
                print(f"  {done[0]}R done", file=sys.stderr)
            time.sleep(0.2)
            return f"{rid} OK"
        except Exception as e:
            return f"{rid} FAIL {e}"

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        fails = [m for m in ex.map(one, todo) if "OK" not in m]
    print(f"完了: 成功{done[0]} 失敗{len(fails)}", file=sys.stderr)
    for m in fails[:10]:
        print(" ", m, file=sys.stderr)


if __name__ == "__main__":
    main()
