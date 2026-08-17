# -*- coding: utf-8 -*-
"""人気別の単勝/複勝フラットROIを、払戻(payout)ベースで JRA vs NAR全場 で比較。
   実オッズ列が無くても払戻から実測できるため、hist_nar_flat の全5592Rが使える。
   ※hist_nar*/result.order の "odds" フィールドは実際には「人気」列（検証済み）。
   usage: python3 market_eff2.py
"""
import glob, json, math, random
from collections import defaultdict

VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
         "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
         "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"}
NANKAN = {"42", "43", "44", "45"}


def rec(rid, group, order, payout, popkey):
    tan = {str(k): v for k, v in (payout.get("単勝") or {}).items()}
    fuku = {str(k): v for k, v in (payout.get("複勝") or {}).items()}
    if not tan or not fuku:
        return None
    rs = []
    for o in order:
        p = popkey(o)
        rk = str(o.get("rank", ""))
        if not p or not rk.isdigit():
            continue
        num = str(o["num"])
        rs.append(dict(pop=int(p), win_ret=tan.get(num, 0) if int(rk) == 1 else 0,
                       plc_ret=fuku.get(num, 0), field=len(order)))
    if len(rs) < 5:
        return None
    return (rid, group, rs, len(order))


def load_jra():
    out = []
    for f in sorted(glob.glob("hist/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        r = rec(f.split("/")[-1][:12], "JRA", d.get("result", {}).get("order") or [],
                d.get("result", {}).get("payout") or {}, lambda o: o.get("ninki"))
        if r:
            out.append(r)
    return out


def load_nar():
    out = []
    for f in sorted(glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rid = f.split("/")[-1][:12]
        # 注: この "odds" は人気列
        r = rec(rid, VENUE.get(rid[4:6], rid[4:6]),
                d.get("result", {}).get("order") or [],
                d.get("result", {}).get("payout") or {}, lambda o: o.get("odds"))
        if r:
            out.append(r)
    seen, uniq = set(), []
    for r in out:
        if r[0] in seen:
            continue
        seen.add(r[0])
        uniq.append(r)
    return uniq


def boot(samples, iters=1500, seed=11):
    rnd = random.Random(seed)
    n = len(samples)
    if n < 50:
        return (None, None)
    o = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += samples[rnd.randrange(n)]
        o.append(s / n)
    o.sort()
    return (o[int(iters * .025)], o[int(iters * .975)])


def table(name, data, field=None, pops=range(1, 11)):
    d = [x for x in data if field is None or field(x[3])]
    W = defaultdict(list)
    P = defaultdict(list)
    for _rid, _g, rs, _f in d:
        for r in rs:
            if r["pop"] <= 10:
                W[r["pop"]].append(r["win_ret"])
                P[r["pop"]].append(r["plc_ret"])
    print(f"\n### {name}  ({len(d)}R)")
    print(f"{'人気':>4} {'頭数':>7} {'単ROI%':>8} {'単95%CI':>15} {'複ROI%':>8} {'複95%CI':>15}")
    rows = {}
    for p in pops:
        if p not in W or len(W[p]) < 30:
            continue
        wr = sum(W[p]) / len(W[p])
        pr = sum(P[p]) / len(P[p])
        wl, wh = boot(W[p])
        pl, ph = boot(P[p])
        print(f"{p:>4} {len(W[p]):>7} {wr:>8.1f} "
              f"{('[%4.0f,%4.0f]' % (wl, wh)) if wl else '-':>15} {pr:>8.1f} "
              f"{('[%4.0f,%4.0f]' % (pl, ph)) if pl else '-':>15}")
        rows[p] = (len(W[p]), wr, wl, wh, pr, pl, ph)
    return rows


def main():
    jra = load_jra()
    nar = load_nar()
    print(f"JRA {len(jra)}R / NAR {len(nar)}R")
    c = defaultdict(int)
    for _r, g, _rs, _f in nar:
        c[g] += 1
    print("NAR場別:", dict(sorted(c.items(), key=lambda x: -x[1])))

    table("JRA 全体", jra)
    table("NAR 全場", nar)
    nk = [x for x in nar if x[0][4:6] in NANKAN]
    table("NAR 南関東4場", nk)

    print("\n### 場別（人気1〜3の単勝ROI / 複勝ROI）")
    print(f"{'場':>6} {'R数':>6} " + " ".join(f"{'単'+str(p):>7}" for p in (1, 2, 3))
          + " " + " ".join(f"{'複'+str(p):>7}" for p in (1, 2, 3)))
    groups = defaultdict(list)
    for x in nar:
        groups[x[1]].append(x)
    groups["JRA"] = jra
    for g, dat in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(dat) < 100:
            continue
        W = defaultdict(list)
        P = defaultdict(list)
        for _rid, _g, rs, _f in dat:
            for r in rs:
                if r["pop"] <= 3:
                    W[r["pop"]].append(r["win_ret"])
                    P[r["pop"]].append(r["plc_ret"])
        w = [sum(W[p]) / len(W[p]) if W[p] else 0 for p in (1, 2, 3)]
        pp = [sum(P[p]) / len(P[p]) if P[p] else 0 for p in (1, 2, 3)]
        print(f"{g:>6} {len(dat):>6} " + " ".join(f"{v:>7.1f}" for v in w)
              + " " + " ".join(f"{v:>7.1f}" for v in pp))

    print("\n### 頭数別（NAR南関 vs JRA）1番人気 単勝ROI")
    for lab, fn in (("~9頭", lambda f: f <= 9), ("10-12頭", lambda f: 10 <= f <= 12),
                    ("13-14頭", lambda f: 13 <= f <= 14), ("15頭+", lambda f: f >= 15)):
        for nm, dat in (("JRA", jra), ("南関", nk)):
            s = [r["win_ret"] for _i, _g, rs, f in dat if fn(f) for r in rs if r["pop"] == 1]
            sp = [r["plc_ret"] for _i, _g, rs, f in dat if fn(f) for r in rs if r["pop"] == 1]
            if len(s) >= 50:
                lo, hi = boot(s)
                print(f"  {lab:>8} {nm:>4} n={len(s):>5} 単ROI {sum(s)/len(s):6.1f}% "
                      f"[{lo:.0f},{hi:.0f}]  複ROI {sum(sp)/len(sp):6.1f}%")


if __name__ == "__main__":
    main()
