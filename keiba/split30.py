# -*- coding: utf-8 -*-
"""堀川システムを約30個に分けるなら、どの分け方が最良か（2026-08-22・指示「30システム分けたほうがいい」）。

現状6群(芝ダ×距離帯)、コース単位120は混合なら効くと実測済み(course_sweep30.py)。
その中間=約30セルの分け方を総当たりで比較する。1セルあたり約440Rで標本も足りる。

比較する分け方(セル数15〜45を狙う):
  場×距離帯(30) / 場×芝ダ(20) / 場×芝ダ×距離帯(60→薄いセルは6群へ)
  VG×距離帯×芝ダ(24) / 芝ダ×距離6段階(12) / 芝ダ×距離帯×頭数(12)
  芝ダ×距離帯×クラス(30) / 場×クラス(30) / 芝ダ×距離帯×点差(12)
  距離6段階×頭数3(18) / 場×距離2段階(20) / 芝ダ×距離帯×馬場(18)
各分け方について λ(縮小)を4段階、縮小先=6群 で学習し、
さらに6群との混合(α=0.5)も試す。null control(セル割当乱数)を必ず併走。

判定: null を未知2期間**とも**上回ること。上回った中で最良を採用。
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2


def dcat6(d):
    return ("~1200" if d <= 1200 else "1300-1400" if d <= 1400 else
            "1500-1600" if d <= 1600 else "1700-1800" if d <= 1800 else
            "1900-2000" if d <= 2000 else "2100+")


def fcat(f):
    return "少" if f <= 10 else "中" if f <= 14 else "多"


SPLITS = {
    "場×距離帯":        lambda r: f"{r.get('venue')}/{r['dist_cat']}",
    "場×芝ダ":          lambda r: f"{r.get('venue')}/{r['surface']}",
    "場×芝ダ×距離帯":     lambda r: f"{r.get('venue')}/{r['surface']}{r['dist_cat']}",
    "VG×距離帯×芝ダ":     lambda r: f"VG{r['vg']}/{r['surface']}{r['dist_cat']}",
    "芝ダ×距離6段階":     lambda r: f"{r['surface']}/{dcat6(r['distance'])}",
    "芝ダ×距離帯×頭数":    lambda r: f"{r['surface']}{r['dist_cat']}/{fcat(len(r['nums']))}",
    "芝ダ×距離帯×クラス":   lambda r: f"{r['surface']}{r['dist_cat']}/t{r['tier']}",
    "場×クラス":         lambda r: f"{r.get('venue')}/t{r['tier']}",
    "距離6段階×頭数":     lambda r: f"{dcat6(r['distance'])}/{fcat(len(r['nums']))}",
    "場×距離2段階":       lambda r: f"{r.get('venue')}/{'短' if r['distance']<=1600 else '長'}",
    "コース(120)":       lambda r: f"{r.get('venue')}{r['surface']}{r['distance']}",
}


def sd_key(r):
    return f"{r['surface']}{r['dist_cat']}"


def fit_by(races, keyfn, l2, base_of, min_n=40):
    out = {}
    by = collections.defaultdict(list)
    for r in races:
        k = keyfn(r)
        if k:
            by[k].append(r)
    for k, sub in by.items():
        if len(sub) < min_n:
            continue
        base = base_of(sub[0])
        X, M, W = V2.make_tensor(sub, key="Z16")
        out[k] = V2.fit(X, M, W, l2, w0=base, wstart=base)
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
    w_sd = fit_by(MINE, sd_key, 0.2, lambda r: w_all, min_n=1)
    base_of = lambda r: w_sd.get(sd_key(r), w_all)
    print(f"MINE {len(MINE)} VAL {len(VAL)} CONF {len(CONF)}", file=sys.stderr)

    res = {}
    # 基準
    res["①6群(現行)"] = ("base", 6, ev(MINE, base_of), ev(VAL, base_of), ev(CONF, base_of))

    # null: セル割当を乱数(30セル相当)
    rs = np.random.RandomState(41)
    fk = {r["rid"]: f"N{rs.randint(30)}" for r in races}
    for lam in (0.3, 1.0):
        wn = fit_by(MINE, lambda r: fk[r["rid"]], lam, base_of)
        f = lambda r, wn=wn: wn.get(fk[r["rid"]], base_of(r))
        res[f"null30 λ={lam:g}"] = ("null", 30, ev(MINE, f), ev(VAL, f), ev(CONF, f))

    for nm, kf in SPLITS.items():
        ncell = len({kf(r) for r in MINE})
        for lam in (0.3, 1.0, 3.0):
            wc = fit_by(MINE, kf, lam, base_of)
            f = lambda r, wc=wc, kf=kf: wc.get(kf(r), base_of(r))
            res[f"{nm} λ={lam:g}"] = ("split", ncell, ev(MINE, f), ev(VAL, f), ev(CONF, f))
        # 6群との混合
        wc = fit_by(MINE, kf, 0.3, base_of)
        def mk(wc=wc, kf=kf):
            def g(r):
                c = wc.get(kf(r))
                b = base_of(r)
                return b if c is None else 0.5 * c + 0.5 * b
            return g
        f = mk()
        res[f"{nm} 混合50%"] = ("mix", ncell, ev(MINE, f), ev(VAL, f), ev(CONF, f))

    nb_v = max(v[3][1] for v in res.values() if v[0] == "null")
    nb_c = max(v[4][1] for v in res.values() if v[0] == "null")
    print(f"\nnull control 最良: VAL 3着内 {nb_v:.1f}% / CONF 3着内 {nb_c:.1f}%")
    print("=" * 104)
    print(f"{'分け方':<24}{'セル':>5}{'MINE 3着内':>11}{'VAL':>8}{'CONF':>8}{'VAL複2':>8}{'CONF複2':>8}  判定")
    rows = sorted(res.items(), key=lambda kv: -(kv[1][3][1] + kv[1][4][1]))
    for k, (kind, nc, m, v, c) in rows:
        ok = "○" if (kind not in ("null",) and v[1] > nb_v and c[1] > nb_c) else ("null" if kind == "null" else "×")
        print(f"{k:<24}{nc:>5}{m[1]:>10.1f}%{v[1]:>7.1f}%{c[1]:>7.1f}%{v[2]:>7.1f}%{c[2]:>7.1f}%  {ok}")
    json.dump({k: {"kind": v[0], "cells": v[1], "MINE": v[2], "VAL": v[3], "CONF": v[4]}
               for k, v in res.items()}, open("split30.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved split30.json")


if __name__ == "__main__":
    main()
