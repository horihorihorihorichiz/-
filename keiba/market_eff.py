# -*- coding: utf-8 -*-
"""市場効率の直接測定: JRA vs NAR(南関東)。
   人気帯／オッズ帯ごとに「実勝率」と「implied確率(1/odds を正規化)」を比較し、
   単勝フラット買いのROI(=控除率を超えるエッジがあるか)を出す。
   数字は全て手持ちデータの実測。usage: python3 market_eff.py [--out csv]
"""
import argparse, glob, json, math, os, random
from collections import defaultdict

VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
         "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
         "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"}
NANKAN = {"42", "43", "44", "45"}


# ---------- ロード ----------
def load_jra():
    """hist/*.json の result.order(ninki, odds, rank) から (race_id, [runner...]) を作る。"""
    out = []
    for f in sorted(glob.glob("hist/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        order = d.get("result", {}).get("order") or []
        rs = []
        for o in order:
            od, nk, rk = o.get("odds"), o.get("ninki"), str(o.get("rank", ""))
            if not od or not nk or not rk.isdigit():
                continue
            rs.append(dict(pop=int(nk), odds=float(od), win=(int(rk) == 1)))
        if len(rs) >= 5 and sum(r["win"] for r in rs) == 1:
            out.append((f.split("/")[-1][:12], "JRA", rs))
    return out


def load_nar():
    """nar_odds.json / oi_odds.json(実オッズ+人気) から同形式を作る。"""
    src = {}
    for p in ("oi_odds.json", "nar_odds.json"):
        if os.path.exists(p):
            for k, v in json.load(open(p, encoding="utf-8")).items():
                src.setdefault(k, v)
    out = []
    for rid, hs in src.items():
        rs = []
        for _num, h in hs.items():
            od, pp, rk = h.get("odds"), h.get("pop"), h.get("rank")
            if not od or not pp or not rk:
                continue
            rs.append(dict(pop=int(pp), odds=float(od), win=(int(rk) == 1)))
        if len(rs) >= 5 and sum(r["win"] for r in rs) == 1:
            out.append((rid, VENUE.get(rid[4:6], rid[4:6]), rs))
    return out


# ---------- 集計 ----------
def overround(races):
    """1レースあたりの sum(1/odds)。1/これ = (1-控除率)の実測値。"""
    vals = [sum(1.0 / r["odds"] for r in rs) for _r, _v, rs in races]
    vals.sort()
    n = len(vals)
    return (sum(vals) / n, vals[n // 2], n) if n else (0, 0, 0)


def by_bucket(races, key):
    """key(runner)->bucket。bucket -> dict(n, wins, roi, imp, nimp)"""
    B = defaultdict(lambda: dict(n=0, wins=0, ret=0.0, imp=0.0, nimp=0.0))
    for _rid, _v, rs in races:
        tot = sum(1.0 / r["odds"] for r in rs)
        for r in rs:
            b = key(r)
            if b is None:
                continue
            d = B[b]
            d["n"] += 1
            d["wins"] += r["win"]
            d["ret"] += (r["odds"] * 100.0 if r["win"] else 0.0)
            d["imp"] += 1.0 / r["odds"]
            d["nimp"] += (1.0 / r["odds"]) / tot
    return B


def boot_roi(samples, iters=2000, seed=7):
    """ROI(=平均払戻/100)のブートストラップ95%CI。samples=各賭けの払戻(円,100円賭け)。"""
    rnd = random.Random(seed)
    n = len(samples)
    if n < 30:
        return (None, None)
    outs = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += samples[rnd.randrange(n)]
        outs.append(s / n / 100.0)
    outs.sort()
    return (outs[int(iters * 0.025)], outs[int(iters * 0.975)])


def roi_samples(races, key, target):
    out = []
    for _rid, _v, rs in races:
        for r in rs:
            if key(r) == target:
                out.append(r["odds"] * 100.0 if r["win"] else 0.0)
    return out


def show(name, races, key, labels, ci=True):
    B = by_bucket(races, key)
    print(f"\n### {name}  ({len(races)}R)")
    print(f"{'帯':>10} {'頭数':>7} {'勝':>6} {'実勝率%':>8} {'正規implied%':>12} "
          f"{'素implied%':>10} {'ROI%':>7} {'ROI95%CI':>16}")
    rows = []
    for b in labels:
        d = B.get(b)
        if not d or d["n"] == 0:
            continue
        wr = d["wins"] / d["n"] * 100
        nimp = d["nimp"] / d["n"] * 100
        imp = d["imp"] / d["n"] * 100
        roi = d["ret"] / d["n"]
        lo = hi = None
        if ci:
            lo, hi = boot_roi(roi_samples(races, key, b))
        cis = f"[{lo*100:5.0f},{hi*100:5.0f}]" if lo is not None else "     -"
        print(f"{str(b):>10} {d['n']:>7} {d['wins']:>6} {wr:>8.2f} {nimp:>12.2f} "
              f"{imp:>10.2f} {roi:>7.1f} {cis:>16}")
        rows.append((b, d["n"], d["wins"], wr, nimp, imp, roi, lo, hi))
    return rows


def two_prop_z(w1, n1, w2, n2):
    if min(n1, n2) == 0:
        return None
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (p1 - p2) / se if se > 0 else None


def norm_sf(z):
    return 0.5 * math.erfc(abs(z) / math.sqrt(2)) * 2


POPS = list(range(1, 11))
OBANDS = [("~1.5", 0, 1.5), ("1.5-2.5", 1.5, 2.5), ("2.5-4", 2.5, 4), ("4-6", 4, 6),
          ("6-10", 6, 10), ("10-20", 10, 20), ("20-50", 20, 50), ("50-100", 50, 100),
          ("100+", 100, 1e9)]


def okey(r):
    for lab, lo, hi in OBANDS:
        if lo < r["odds"] <= hi:
            return lab
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nankan-only", action="store_true")
    a = ap.parse_args()
    jra = load_jra()
    nar = load_nar()
    if a.nankan_only:
        nar = [x for x in nar if x[0][4:6] in NANKAN]
    print(f"JRA {len(jra)}R / NAR {len(nar)}R")
    cnt = defaultdict(int)
    for rid, v, _ in nar:
        cnt[v] += 1
    print("NAR内訳:", dict(sorted(cnt.items(), key=lambda x: -x[1])))

    for nm, dat in (("JRA", jra), ("NAR", nar)):
        m, md, n = overround(dat)
        print(f"{nm} オーバーラウンド sum(1/odds): 平均{m:.4f} 中央{md:.4f} "
              f"→ 実効控除率 平均{(1-1/m)*100:.1f}% 中央{(1-1/md)*100:.1f}% ({n}R)")

    pk = lambda r: r["pop"] if r["pop"] <= 10 else None
    rj = show("JRA 人気別", jra, pk, POPS)
    rn = show("NAR 人気別", nar, pk, POPS)
    print("\n### 人気別 実勝率のJRA-NAR差(2標本z検定)")
    print(f"{'人気':>4} {'JRA勝率%':>9} {'NAR勝率%':>9} {'差pt':>7} {'z':>7} {'p':>9}")
    dj = {r[0]: r for r in rj}
    dn = {r[0]: r for r in rn}
    for p in POPS:
        if p in dj and p in dn:
            z = two_prop_z(dj[p][2], dj[p][1], dn[p][2], dn[p][1])
            print(f"{p:>4} {dj[p][3]:>9.2f} {dn[p][3]:>9.2f} "
                  f"{dj[p][3]-dn[p][3]:>7.2f} {z:>7.2f} {norm_sf(z):>9.4f}")

    show("JRA オッズ帯別", jra, okey, [b[0] for b in OBANDS])
    show("NAR オッズ帯別", nar, okey, [b[0] for b in OBANDS])

    # 場別 ROI(単勝フラット・全頭)
    print("\n### 場別 単勝フラット全頭ROI（=市場の実効払戻率。100-これ が実効控除率）")
    per = defaultdict(lambda: [0, 0.0])
    for _rid, v, rs in nar:
        for r in rs:
            per[v][0] += 1
            per[v][1] += (r["odds"] * 100 if r["win"] else 0)
    jn = jr = 0
    for _rid, _v, rs in jra:
        for r in rs:
            jn += 1
            jr += (r["odds"] * 100 if r["win"] else 0)
    print(f"  JRA  {jr/jn:6.1f}%  ({jn}頭)")
    for v, (n, ret) in sorted(per.items(), key=lambda x: -x[1][0]):
        print(f"  {v:4s} {ret/n:6.1f}%  ({n}頭)")


if __name__ == "__main__":
    main()
