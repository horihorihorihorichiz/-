# -*- coding: utf-8 -*-
"""ファミリー1(コース適性)候補特徴の事前スクリーニング。
   フル学習せず、train内で top3馬 vs その他 の z値差・既存特徴との相関を測る。"""
import json, math, os, sys
import exp_harness as H

def _fin(p):
    return -(p["finish"] / max(p["field"], 1))

def _mean(xs):
    return sum(xs)/len(xs) if xs else None

# ---- 候補特徴 ----
def surf_perf(h, race, rid):
    rs = [p for p in h.get("races", []) if p.get("surface") == race.get("surface")]
    return _mean([_fin(p) for p in rs])

def surf_diff(h, race, rid):
    rs = h.get("races", [])
    if not rs:
        return None
    mt = [p for p in rs if p.get("surface") == race.get("surface")]
    if not mt:
        return None
    return _mean([_fin(p) for p in mt]) - _mean([_fin(p) for p in rs])

def surf_frac(h, race, rid):
    rs = h.get("races", [])
    if not rs:
        return None
    return sum(1 for p in rs if p.get("surface") == race.get("surface")) / len(rs)

def surf_switch(h, race, rid):
    rs = h.get("races", [])
    if not rs:
        return None
    return 1.0 if rs[0].get("surface") != race.get("surface") else 0.0

def db_perf(h, race, rid):
    D = race.get("distance", 1600)
    rs = [p for p in h.get("races", []) if abs(p["dist"] - D) <= 200]
    return _mean([_fin(p) for p in rs])

def db_diff(h, race, rid):
    rs = h.get("races", [])
    if not rs:
        return None
    D = race.get("distance", 1600)
    mt = [p for p in rs if abs(p["dist"] - D) <= 200]
    if not mt:
        return None
    return _mean([_fin(p) for p in mt]) - _mean([_fin(p) for p in rs])

def db_best(h, race, rid):
    D = race.get("distance", 1600)
    rs = [p for p in h.get("races", []) if abs(p["dist"] - D) <= 200]
    return max([_fin(p) for p in rs]) if rs else None

def db_n(h, race, rid):
    D = race.get("distance", 1600)
    return sum(1 for p in h.get("races", []) if abs(p["dist"] - D) <= 200)

def exact_dist_place(h, race, rid):
    D = race.get("distance", 1600)
    rs = [p for p in h.get("races", []) if p["dist"] == D]
    if not rs:
        return None
    return sum(1 for p in rs if p["finish"] <= 3) / len(rs)

def cond_perf(h, race, rid):
    """今日と同表面かつ±200m帯での成績"""
    D = race.get("distance", 1600)
    S = race.get("surface")
    rs = [p for p in h.get("races", []) if p.get("surface") == S and abs(p["dist"] - D) <= 200]
    return _mean([_fin(p) for p in rs])

def cond_tsi(h, race, rid):
    D = race.get("distance", 1600)
    S = race.get("surface")
    xs = [p["tsi"] for p in h.get("races", [])
          if p.get("surface") == S and abs(p["dist"] - D) <= 200 and p.get("tsi") is not None]
    return _mean(xs)

def wet_apt(h, race, rid):
    if race.get("baba") == "良":
        return None
    ofl = h.get("offtrack_finishes") or []
    return -_mean(ofl) if ofl else None

CANDS = [("surf_perf", surf_perf), ("surf_diff", surf_diff), ("surf_frac", surf_frac),
         ("surf_switch", surf_switch), ("db_perf", db_perf), ("db_diff", db_diff),
         ("db_best", db_best), ("db_n", db_n), ("exact_dist_place", exact_dist_place),
         ("cond_perf", cond_perf), ("cond_tsi", cond_tsi), ("wet_apt", wet_apt)]

ds = H.load_base()
train = [r for r in ds if r["date"] not in H.TEST_DAYS]
print(f"train {len(train)}R")

for name, fn in CANDS:
    H.add_feature(ds, name, fn)

import fit_v2 as V2
BASE = V2.FEATS
for name, _ in CANDS:
    zt, zo, nz = [], [], 0
    corrs = {}
    for r in train:
        for n in r["ns"]:
            v = r["X"][name][n]
            if v != 0.0:
                nz += 1
            (zt if n in r["top3"] else zo).append(v)
    # 相関(既存特徴と): 全馬プールで単純相関
    for b in BASE:
        xs, ys = [], []
        for r in train:
            for n in r["ns"]:
                xs.append(r["X"][name][n]); ys.append(r["X"][b][n])
        mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
        sx = (sum((x-mx)**2 for x in xs))**.5; sy = (sum((y-my)**2 for y in ys))**.5
        c = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy) if sx*sy else 0
        corrs[b] = c
    top2 = sorted(corrs.items(), key=lambda kv: -abs(kv[1]))[:2]
    dt = sum(zt)/len(zt) - sum(zo)/len(zo)
    print(f"{name:18s} Δz(top3-other)={dt:+.3f}  nonzero={nz}  "
          f"maxcorr: {top2[0][0]}={top2[0][1]:+.2f}, {top2[1][0]}={top2[1][1]:+.2f}")
