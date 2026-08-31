# -*- coding: utf-8 -*-
"""NAR全レースで「モデル(V3/calc+v2_live)1位」対「市場1位(1番人気)」を、
   JRAのV4/V5/V7報告と同じKPI(1位勝率・単勝ROI・上位5の3着内捕捉)で比較する。
   人気は result.order の "odds" フィールド（実体は人気列）を使用。
   usage: python3 nar_model_eval.py [--venues 42,43,44,45] [--limit N]
"""
import argparse, glob, json, math, os, random, sys
from collections import defaultdict

import calc, v2_live

VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
         "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
         "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"}


def wilson(k, n):
    if n == 0:
        return (0, 0)
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def boot(s, iters=1500, seed=5):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jra", action="store_true",
                    help="同じKPIをJRA(hist/)で出す＝対照群")
    a = ap.parse_args()
    vs = set(a.venues.split(",")) if a.venues else None
    if a.jra:
        files = sorted(glob.glob("hist/*.json"))
        VENUE.clear()
    else:
        files = sorted(glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json"))
    if vs and not a.jra:
        files = [f for f in files if f.split("/")[-1][4:6] in vs]
    if a.limit:
        files = files[:a.limit]
    n_ok = err = 0
    m_win = k_win = 0
    m_cap = k_cap = cap_d = 0
    m_roi, k_roi = [], []
    per = defaultdict(lambda: [0, 0, 0])   # venue -> [n, model win, market win]
    agree = 0
    seen = set()
    for f in files:
        rid = f.split("/")[-1][:12]
        if rid in seen:
            continue
        seen.add(rid)
        try:
            d = json.load(open(f, encoding="utf-8"))
            race = d["race"]
            res = calc.run(race)
            v2_live.rescore(race, res["rows"])
        except Exception:
            err += 1
            continue
        order = d.get("result", {}).get("order") or []
        payout = d.get("result", {}).get("payout") or {}
        tan = {str(k): v for k, v in (payout.get("単勝") or {}).items()}
        pk = "ninki" if a.jra else "odds"   # NARの"odds"は実体が人気列
        pop = {o["num"]: o[pk] for o in order if o.get(pk)}
        top3 = [o["num"] for o in order if str(o.get("rank", "")) in ("1", "2", "3")]
        winner = next((o["num"] for o in order if str(o.get("rank", "")) == "1"), None)
        if len(top3) < 3 or len(pop) < 6 or winner is None or not tan:
            continue
        mo = [r["num"] for r in res["rows"]]
        ko = sorted(pop, key=lambda h: pop[h])
        if not mo or not ko:
            continue
        n_ok += 1
        v = "JRA" if a.jra else VENUE.get(rid[4:6], rid[4:6])
        per[v][0] += 1
        m1, k1 = mo[0], ko[0]
        agree += (m1 == k1)
        m_win += (m1 == winner)
        k_win += (k1 == winner)
        per[v][1] += (m1 == winner)
        per[v][2] += (k1 == winner)
        m_roi.append(tan.get(str(m1), 0) if m1 == winner else 0)
        k_roi.append(tan.get(str(k1), 0) if k1 == winner else 0)
        m5, k5 = set(mo[:5]), set(ko[:5])
        m_cap += sum(1 for t in top3 if t in m5)
        k_cap += sum(1 for t in top3 if t in k5)
        cap_d += 3

    print(f"評価 {n_ok}R (読込失敗{err})  モデル1位=市場1位の一致率 {agree/max(n_ok,1)*100:.1f}%")
    for nm, w, r in (("モデル", m_win, m_roi), ("市場 ", k_win, k_roi)):
        lo, hi = wilson(w, n_ok)
        rl, rh = boot(r)
        print(f"  {nm}1位 勝率 {w/n_ok*100:5.2f}% [{lo*100:.2f},{hi*100:.2f}]  "
              f"単勝ROI {sum(r)/len(r):6.1f}% [{rl:.0f},{rh:.0f}]")
    print(f"  上位5の3着内捕捉: モデル {m_cap/cap_d*100:.1f}% vs 市場 {k_cap/cap_d*100:.1f}%")
    d1 = m_win / n_ok - k_win / n_ok
    print(f"  差(モデル-市場) 1位勝率 {d1*100:+.2f}pt / 単勝ROI "
          f"{(sum(m_roi)/len(m_roi))-(sum(k_roi)/len(k_roi)):+.1f}pt")
    print("\n場別 (n>=100):")
    print(f"{'場':>6} {'R':>6} {'モデル1位勝率':>12} {'市場1位勝率':>11} {'差pt':>7}")
    for v, (n, mw, kw) in sorted(per.items(), key=lambda x: -x[1][0]):
        if n < 100:
            continue
        print(f"{v:>6} {n:>6} {mw/n*100:>12.2f} {kw/n*100:>11.2f} "
              f"{(mw-kw)/n*100:>+7.2f}")


if __name__ == "__main__":
    main()
