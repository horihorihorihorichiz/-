# -*- coding: utf-8 -*-
"""血統収穫（Ver.101 R5準備）: hist_enrichに登場する全馬の父(種牡馬)を馬ページから取得。
   usage: python3 harvest_sire.py [--workers 3]
   出力: sire_map.json {horse_id: 父馬名}（再実行で続きから）"""
import argparse, glob, json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}
OUT = "sire_map.json"


def fetch_sire(hid):
    req = urllib.request.Request(f"https://db.netkeiba.com/horse/{hid}/", headers=UA)
    h = urllib.request.urlopen(req, timeout=30).read().decode("euc-jp", errors="replace")
    m = re.search(r'blood_table.*?<td[^>]*>\s*<a[^>]*>([^<]+)</a>', h, re.S)
    return m.group(1).strip() if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    ids = set()
    for f in glob.glob("hist_enrich/*.json"):
        for h in json.load(open(f, encoding="utf-8"))["horses"]:
            if h.get("horse_id"):
                ids.add(h["horse_id"])
    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT, encoding="utf-8"))
    todo = sorted(ids - set(done))
    print(f"対象 {len(ids)}頭 / 残り {len(todo)}頭", file=sys.stderr)
    cnt = [0]

    def one(hid):
        try:
            s = fetch_sire(hid)
            time.sleep(0.15)
            return hid, s
        except Exception:
            return hid, None

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for hid, s in ex.map(one, todo):
            if s:
                done[hid] = s
            cnt[0] += 1
            if cnt[0] % 500 == 0:
                json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"  {cnt[0]}/{len(todo)} (取得済み{len(done)})", file=sys.stderr)
    json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"完了: {len(done)}頭の父を取得", file=sys.stderr)


if __name__ == "__main__":
    main()
