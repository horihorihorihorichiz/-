# -*- coding: utf-8 -*-
"""大井レースの結果ページから実単勝オッズ+人気を再取得 → oi_odds.json
   （既存hist_nar*のodds列は実は人気列だったため、実オッズを別途持つ）"""
import glob, json, os, re, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}

def parse_full(rid):
    h = urllib.request.urlopen(urllib.request.Request(
        f"https://nar.netkeiba.com/race/result.html?race_id={rid}",
        headers=UA), timeout=30).read().decode("utf-8", "replace")
    out = {}
    for tr in re.split(r"<tr[ >]", h):
        rk = re.search(r'class="Rank">(\d+)<', tr)
        if not rk:
            continue
        nums = re.findall(r'class="Num[^"]*">\s*<div>(\d+)</div>', tr)
        if len(nums) < 2:
            continue
        pop = od = None
        for cls, v in re.findall(r'class="(Odds[^"]*)"[^>]*>\s*(?:<[^>]+>)*\s*([\d.]+)', tr):
            if "Txt_R" in cls:
                od = float(v)
            else:
                pop = int(float(v))
        out[nums[1]] = dict(rank=int(rk.group(1)), odds=od, pop=pop)
    return out

def main():
    done = {}
    if os.path.exists("oi_odds.json"):
        done = json.load(open("oi_odds.json", encoding="utf-8"))
    rids = sorted({f.split("/")[-1][:12]
                   for f in glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json")
                   if f.split("/")[-1][4:6] == "44"})
    n = 0
    for rid in rids:
        if rid in done:
            continue
        try:
            r = parse_full(rid)
            if r:
                done[rid] = r
        except Exception as e:
            print("err", rid, e, flush=True)
        n += 1
        if n % 50 == 0:
            print(f"{n}件処理 / 取得済み計{len(done)}", flush=True)
            json.dump(done, open("oi_odds.json", "w", encoding="utf-8"))
        time.sleep(0.35)
    json.dump(done, open("oi_odds.json", "w", encoding="utf-8"))
    print(f"完了: {len(done)}レース分の実オッズ", flush=True)

if __name__ == "__main__":
    main()
