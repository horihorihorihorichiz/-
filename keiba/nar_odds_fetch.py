# -*- coding: utf-8 -*-
"""hist_nar_flat/hist_nar の全場について結果ページから実単勝オッズ+人気を取得 → nar_odds.json
   （既存hist_nar*のresult.order.odds列は実は「人気」列。実オッズはここに持つ）
   usage: python3 nar_odds_fetch.py --venues 42,43,45 [--sleep 1.1] [--limit N]
   再実行で続きから（nar_odds.json をマージ）。
"""
import argparse, glob, json, os, re, sys, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
OUT = "nar_odds.json"


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues", default="42,43,45")
    ap.add_argument("--sleep", type=float, default=1.1)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    vs = set(a.venues.split(","))
    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT, encoding="utf-8"))
    # 既取得の大井もマージして一元化
    if os.path.exists("oi_odds.json"):
        for k, v in json.load(open("oi_odds.json", encoding="utf-8")).items():
            done.setdefault(k, v)
    rids = sorted({f.split("/")[-1][:12]
                   for f in glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json")
                   if f.split("/")[-1][4:6] in vs})
    todo = [r for r in rids if r not in done]
    print(f"対象{len(rids)}R / 未取得{len(todo)}R", flush=True)
    if a.limit:
        todo = todo[:a.limit]
    n = 0
    for rid in todo:
        try:
            r = parse_full(rid)
            if r:
                done[rid] = r
        except Exception as e:
            print("err", rid, e, flush=True)
        n += 1
        if n % 50 == 0:
            json.dump(done, open(OUT, "w", encoding="utf-8"))
            print(f"{n}/{len(todo)} 済 (計{len(done)})", flush=True)
        time.sleep(a.sleep)
    json.dump(done, open(OUT, "w", encoding="utf-8"))
    print(f"完了: 計{len(done)}レース分の実オッズ", flush=True)


if __name__ == "__main__":
    main()
