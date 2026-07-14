# -*- coding: utf-8 -*-
"""ファミリー1: コース適性の深掘り実験。
   過去9走から「今日の条件(表面/距離帯/馬場)との一致度」特徴を作り捕捉率を測る。
   usage: python3 exp_course_apt.py [A B C ...]   (省略時は全部)
"""
import sys
import exp_harness as H

def _fin(p):
    return -(p["finish"] / max(p["field"], 1))

def _mean(xs):
    return sum(xs)/len(xs) if xs else None

def surf_perf(h, race, rid):
    """今日と同じ表面(芝/ダ)での平均着順率"""
    rs = [p for p in h.get("races", []) if p.get("surface") == race.get("surface")]
    return _mean([_fin(p) for p in rs])

def surf_diff(h, race, rid):
    """同表面成績 − 全体成績（表面の得手差分）"""
    rs = h.get("races", [])
    if not rs:
        return None
    mt = [p for p in rs if p.get("surface") == race.get("surface")]
    if not mt:
        return None
    return _mean([_fin(p) for p in mt]) - _mean([_fin(p) for p in rs])

def surf_switch(h, race, rid):
    """芝ダ替わりフラグ（前走と今日で表面が違う）"""
    rs = h.get("races", [])
    if not rs:
        return None
    return 1.0 if rs[0].get("surface") != race.get("surface") else 0.0

def db_perf(h, race, rid):
    """今日の距離±200mでの平均着順率"""
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
    """距離帯ベスト着順率（一発の実績）"""
    D = race.get("distance", 1600)
    rs = [p for p in h.get("races", []) if abs(p["dist"] - D) <= 200]
    return max([_fin(p) for p in rs]) if rs else None

def exact_dist_place(h, race, rid):
    """今日の距離ピッタリでの複勝率"""
    D = race.get("distance", 1600)
    rs = [p for p in h.get("races", []) if p["dist"] == D]
    if not rs:
        return None
    return sum(1 for p in rs if p["finish"] <= 3) / len(rs)

def cond_perf(h, race, rid):
    """同表面かつ±200m帯（今日の条件そのもの）での成績"""
    D = race.get("distance", 1600)
    S = race.get("surface")
    rs = [p for p in h.get("races", []) if p.get("surface") == S and abs(p["dist"] - D) <= 200]
    return _mean([_fin(p) for p in rs])

def wet_apt(h, race, rid):
    """今日が道悪(稍/重/不)の時だけ、道悪実績(offtrack_finishes)の平均着順"""
    if race.get("baba") == "良":
        return None
    ofl = h.get("offtrack_finishes") or []
    return -_mean(ofl) if ofl else None

FEATS = {"surf_perf": surf_perf, "surf_diff": surf_diff, "surf_switch": surf_switch,
         "db_perf": db_perf, "db_diff": db_diff, "db_best": db_best,
         "exact_dist_place": exact_dist_place, "cond_perf": cond_perf, "wet_apt": wet_apt}

EXPS = {
    # A: ファミリー全部盛り（L2に整理させて有効成分を見る）
    "A": ["surf_perf", "db_perf", "cond_perf", "db_best", "exact_dist_place",
          "surf_diff", "db_diff", "surf_switch", "wet_apt"],
    # B: 冗長ペア(surf_perf/db_perf/cond_perf)を cond_perf に集約 + 直交成分
    "B": ["cond_perf", "db_best", "exact_dist_place", "surf_switch", "wet_apt"],
    # C: 差分(得手差)中心の直交セット
    "C": ["surf_diff", "db_diff", "db_best", "surf_switch", "wet_apt"],
}

if __name__ == "__main__":
    which = sys.argv[1:] or list(EXPS)
    ds = H.load_base()
    need = sorted({f for k in which for f in EXPS[k]})
    for name in need:
        H.add_feature(ds, name, FEATS[name])
    results = {}
    for k in which:
        results[k] = H.run_experiment(ds, extra=EXPS[k], label=f"course_apt_{k}")
        print(f"  weights({k}): " + ", ".join(
            f"{f}={w:+.3f}" for f, w in zip(results[k]["feats"], results[k]["weights"])
            if f in EXPS[k]))
