# -*- coding: utf-8 -*-
"""hist_nar/ の result.order(着順+最終単勝オッズ)をNAR結果ページ構造で補完する（1回だけ）。"""
import glob, json, re, sys, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def parse_nar_result(rid):
    h = urllib.request.urlopen(urllib.request.Request(
        f"https://nar.netkeiba.com/race/result.html?race_id={rid}",
        headers=UA), timeout=30).read().decode("utf-8", "replace")
    out = []
    for tr in re.split(r"<tr[ >]", h):
        rk = re.search(r'class="Rank">(\d+)<', tr)
        if not rk:
            continue
        nums = re.findall(r'class="Num[^"]*">\s*<div>(\d+)</div>', tr)
        nm = re.search(r'title="([^"]+)"', tr)
        od = re.search(r'class="Odds[^"]*"[^>]*>\s*(?:<[^>]+>)*\s*([\d.]+)', tr)
        if len(nums) < 2:
            continue
        out.append(dict(rank=rk.group(1), num=int(nums[1]),
                        name=(nm.group(1) if nm else ""),
                        odds=(float(od.group(1)) if od else None)))
    return out


def main():
    files = sorted(glob.glob("hist_nar/*.json"))
    n_fix = n_skip = n_fail = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        if d.get("result", {}).get("order"):
            n_skip += 1
            continue
        rid = f.split("/")[-1][:-5]
        try:
            order = parse_nar_result(rid)
            if len(order) < 5:
                raise RuntimeError(f"行{len(order)}")
            d["result"]["order"] = order
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
            n_fix += 1
            if n_fix % 50 == 0:
                print(f"  {n_fix}件補完", file=sys.stderr)
        except Exception as e:
            n_fail += 1
            print(f"  FAIL {rid}: {e}", file=sys.stderr)
        time.sleep(0.25)
    print(f"補完{n_fix} / 既存{n_skip} / 失敗{n_fail}", file=sys.stderr)


if __name__ == "__main__":
    main()
