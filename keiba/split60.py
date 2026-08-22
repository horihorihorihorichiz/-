# -*- coding: utf-8 -*-
"""50〜70セルの分け方を30分割の上に重ねて測る（2026-08-22・指示「60くらいになってもいいよ」）。

course_on30.py で「30分割+コース(120)混合50%」がVAL57.0/CONF56.5と最良になった。
混合50%が最良＝コース重みを半分だけ使うのが良い＝セル数を減らして各セルを厚くする方が
素直かもしれない。120と30の中間(50-70セル)を同じ階層構造で測る。

階層: 全体1本 → 6群 → 30分割(芝ダ×距離帯×クラス) → 【この段を差し替えて比較】
null: 60セル乱数(セル数を揃えた公平な相手)
"""
import json, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2


def dcat6(d):
    return ("~1200" if d <= 1200 else "13-14" if d <= 1400 else "15-16" if d <= 1600
            else "17-18" if d <= 1800 else "19-20" if d <= 2000 else "21+")


def sd(r):  return f"{r['surface']}{r['dist_cat']}"
def k30(r): return f"{r['surface']}{r['dist_cat']}/t{r['tier']}"

CAND = {
    "場×芝ダ×距離帯(52)":     lambda r: f"{r.get('venue')}{r['surface']}{r['dist_cat']}",
    "芝ダ×距離6段×クラス(60)":  lambda r: f"{r['surface']}{dcat6(r['distance'])}/t{r['tier']}",
    "VG×距離帯×クラス(60)":    lambda r: f"VG{r['vg']}{r['dist_cat']}/t{r['tier']}",
    "場×芝ダ×クラス(100)":     lambda r: f"{r.get('venue')}{r['surface']}/t{r['tier']}",
    "場×距離帯×クラス(150)":    lambda r: f"{r.get('venue')}{r['dist_cat']}/t{r['tier']}",
    "コース(120)":           lambda r: f"{r.get('venue')}{r['surface']}{r['distance']}",
}


def fit_by(races, keyfn, l2, base_of, min_n):
    out = {}
    by = collections.defaultdict(list)
    for r in races:
        by[keyfn(r)].append(r)
    for k, sub in by.items():
        if len(sub) < min_n:
            continue
        b = base_of(sub[0])
        X, M, W = V2.make_tensor(sub, key="Z16")
        out[k] = V2.fit(X, M, W, l2, w0=b, wstart=b)
    return out


def ev(races, wfn):
    n = len(races); win = t3 = 0; cost = ret = 0
    for r in races:
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
        win += int(o[0] == r["top3"][0]); t3 += int(o[0] in set(r["top3"]))
        pl = {int(k): float(v) for k, v in ((r["payout"] or {}).get("複勝") or {}).items()}
        for i in o[:2]:
            cost += 100; ret += pl.get(r["nums"][i], 0.0)
    return (win / n * 100, t3 / n * 100, ret / cost * 100 if cost else 0)


def main():
    races = V.load_races(); V2.attach_corner(races)
    K = races[0]["Z16"].shape[1]
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    X, M, W = V2.make_tensor(MINE, key="Z16")
    w_all = V2.fit(X, M, W, 1.0, w0=np.zeros(K), wstart=np.zeros(K))
    w6 = fit_by(MINE, sd, 0.2, lambda r: w_all, 1)
    b6 = lambda r: w6.get(sd(r), w_all)
    w30 = fit_by(MINE, k30, 0.3, b6, 40)
    b30 = lambda r: w30.get(k30(r), b6(r))

    res = {"②30分割(30)": (30, ev(MINE, b30), ev(VAL, b30), ev(CONF, b30))}
    for nm, kf in CAND.items():
        nc = len({kf(r) for r in MINE})
        wc = fit_by(MINE, kf, 0.3, b30, 40)
        for a in (0.3, 0.5):
            def mk(a=a, wc=wc, kf=kf):
                def g(r):
                    c = wc.get(kf(r)); b = b30(r)
                    return b if c is None else a * c + (1 - a) * b
                return g
            f = mk()
            res[f"30+{nm} 混合{a:.0%}"] = (nc, ev(MINE, f), ev(VAL, f), ev(CONF, f))
    rs = np.random.RandomState(67)
    for ncell in (60, 120):
        fk = {r["rid"]: f"N{rs.randint(ncell)}" for r in races}
        wn = fit_by(MINE, lambda r: fk[r["rid"]], 0.3, b30, 40)
        def g(r, wn=wn, fk=fk):
            c = wn.get(fk[r["rid"]]); b = b30(r)
            return b if c is None else 0.5 * c + 0.5 * b
        res[f"null{ncell}セル 混合50%"] = (ncell, ev(MINE, g), ev(VAL, g), ev(CONF, g))

    nv = max(v[2][1] for k, v in res.items() if k.startswith("null"))
    ncf = max(v[3][1] for k, v in res.items() if k.startswith("null"))
    print(f"null最良: VAL {nv:.1f}% / CONF {ncf:.1f}%")
    print("=" * 96)
    print(f"{'構成':<28}{'セル':>5}{'MINE':>9}{'VAL':>8}{'CONF':>8}{'VAL複2':>8}{'CONF複2':>8}  判定")
    for k, (nc, m, v, c) in sorted(res.items(), key=lambda kv: -(kv[1][2][1] + kv[1][3][1])):
        mark = "null" if k.startswith("null") else ("○" if v[1] > nv and c[1] > ncf else "×")
        print(f"{k:<28}{nc:>5}{m[1]:>8.1f}%{v[1]:>7.1f}%{c[1]:>7.1f}%{v[2]:>7.1f}%{c[2]:>7.1f}%  {mark}")
    json.dump({k: {"cells": v[0], "MINE": v[1], "VAL": v[2], "CONF": v[3]}
               for k, v in res.items()}, open("split60.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
