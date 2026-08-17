# -*- coding: utf-8 -*-
"""「市場が薄い＝歪む」仮説の直接検定。
   代理変数=レース番号(前半R＝売上が小さい)・頭数・クラス(tier)。
   人気1/2/3の単勝・複勝ROIがそこで有意に良くなるかを見る。
   usage: python3 nar_thin.py
"""
import glob, json, random
from collections import defaultdict

VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
         "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
         "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"}


def boot(s, iters=1200, seed=9):
    rnd = random.Random(seed)
    n = len(s)
    if n < 50:
        return (None, None)
    o = []
    for _ in range(iters):
        t = 0.0
        for _ in range(n):
            t += s[rnd.randrange(n)]
        o.append(t / n)
    o.sort()
    return (o[int(iters * .025)], o[int(iters * .975)])


def load(nar):
    rows = []
    files = (sorted(glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json"))
             if nar else sorted(glob.glob("hist/*.json")))
    seen = set()
    for f in files:
        rid = f.split("/")[-1][:12]
        if rid in seen:
            continue
        seen.add(rid)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        race, res = d.get("race", {}), d.get("result", {})
        order = res.get("order") or []
        po = res.get("payout") or {}
        tan = {str(k): v for k, v in (po.get("単勝") or {}).items()}
        fuku = {str(k): v for k, v in (po.get("複勝") or {}).items()}
        if not tan or not fuku or len(order) < 5:
            continue
        try:
            rno = int(rid[10:12])
        except Exception:
            continue
        for o in order:
            p = o.get("ninki") if not nar else o.get("odds")
            rk = str(o.get("rank", ""))
            if not p or not rk.isdigit():
                continue
            rows.append(dict(pop=int(p), rno=rno, field=len(order),
                             tier=race.get("today_tier"),
                             venue=VENUE.get(rid[4:6], "JRA") if nar else "JRA",
                             w=(tan.get(str(o["num"]), 0) if int(rk) == 1 else 0),
                             p=fuku.get(str(o["num"]), 0)))
    return rows


def show(title, rows, keyfn, order=None):
    G = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["pop"] > 3:
            continue
        k = keyfn(r)
        if k is None:
            continue
        G[k][r["pop"]].append((r["w"], r["p"]))
    print(f"\n### {title}")
    print(f"{'区分':>12} {'n(1番)':>7} {'単1':>7} {'単1 95%CI':>14} {'複1':>7} "
          f"{'複1 95%CI':>14} {'単2':>7} {'単3':>7}")
    keys = order or sorted(G)
    for k in keys:
        if k not in G or len(G[k].get(1, [])) < 100:
            continue
        w1 = [x[0] for x in G[k][1]]
        p1 = [x[1] for x in G[k][1]]
        wl, wh = boot(w1)
        pl, ph = boot(p1)
        w2 = [x[0] for x in G[k].get(2, [])] or [0]
        w3 = [x[0] for x in G[k].get(3, [])] or [0]
        print(f"{str(k):>12} {len(w1):>7} {sum(w1)/len(w1):>7.1f} "
              f"{('[%3.0f,%3.0f]' % (wl, wh)) if wl else '-':>14} "
              f"{sum(p1)/len(p1):>7.1f} "
              f"{('[%3.0f,%3.0f]' % (pl, ph)) if pl else '-':>14} "
              f"{sum(w2)/len(w2):>7.1f} {sum(w3)/len(w3):>7.1f}")


def main():
    for nar in (True, False):
        rows = load(nar)
        nm = "NAR" if nar else "JRA"
        print(f"\n{'='*88}\n{nm}: {len(rows)}頭分")
        show(f"{nm} レース番号帯（前半R=売上小＝薄い市場の代理）", rows,
             lambda r: "1-4R" if r["rno"] <= 4 else "5-8R" if r["rno"] <= 8
             else "9-10R" if r["rno"] <= 10 else "11-12R",
             ["1-4R", "5-8R", "9-10R", "11-12R"])
        show(f"{nm} 頭数", rows,
             lambda r: "~9頭" if r["field"] <= 9 else "10-12頭" if r["field"] <= 12
             else "13-14頭" if r["field"] <= 14 else "15頭+",
             ["~9頭", "10-12頭", "13-14頭", "15頭+"])
        if nar:
            show("NAR 場別(南関4場)", [r for r in rows if r["venue"] in
                                  ("大井", "川崎", "船橋", "浦和")],
                 lambda r: r["venue"], ["大井", "川崎", "船橋", "浦和"])


if __name__ == "__main__":
    main()
