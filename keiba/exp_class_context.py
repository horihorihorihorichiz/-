# -*- coding: utf-8 -*-
"""ファミリー3: クラス文脈（tier）特徴量実験。
   - 昇級初戦/降級フラグ、過去走平均tierと今日のtierの差
   - 同クラス以上での複勝実績・経験数
   - 昇級×前走内容の交互作用、頭数変化
   tier数値: 小さいほど上位クラス (2=G1級,3=OP/重賞,4=3勝,5=2勝,6=1勝,8=新馬,10=未勝利)
   usage: python3 exp_class_context.py
"""
import json
import math

import exp_harness as H

# tier生値→クラス序列（小=上位クラス）。7-10は下位帯としてまとめて序列化
_RANK = {2: 1.0, 3: 2.0, 4: 3.0, 5: 4.0, 6: 5.0, 7: 5.5, 8: 6.0, 9: 6.0, 10: 6.0}


def _rk(t):
    return _RANK.get(t)


def _ff(r):
    return r["finish"] / max(r.get("field", 1), 1)


# ---- 特徴量定義 ----

def class_up(h, race, rid):
    """昇級初戦フラグ: 今日のクラスが直近走より上（序列が小さい）なら1"""
    rs = h.get("races", [])
    tr = _rk(race.get("today_tier"))
    if not rs or tr is None:
        return None
    lr = _rk(rs[0].get("tier"))
    if lr is None:
        return None
    return 1.0 if tr < lr else 0.0


def class_down(h, race, rid):
    """降級フラグ: 今日のクラスが直近走より下なら1"""
    rs = h.get("races", [])
    tr = _rk(race.get("today_tier"))
    if not rs or tr is None:
        return None
    lr = _rk(rs[0].get("tier"))
    if lr is None:
        return None
    return 1.0 if tr > lr else 0.0


def tier_gap_mean3(h, race, rid):
    """直近3走の平均クラス序列 - 今日の序列（正=今日は過去より上のクラス=試練）"""
    rs = h.get("races", [])
    tr = _rk(race.get("today_tier"))
    if tr is None:
        return None
    ps = [_rk(r.get("tier")) for r in rs[:3]]
    ps = [p for p in ps if p is not None]
    if not ps:
        return None
    return sum(ps) / len(ps) - tr


def same_class_place(h, race, rid):
    """今日と同クラス以上での複勝率（実績なしはNone）"""
    rs = h.get("races", [])
    tr = _rk(race.get("today_tier"))
    if tr is None:
        return None
    sel = [r for r in rs if _rk(r.get("tier")) is not None and _rk(r["tier"]) <= tr]
    if not sel:
        return None
    return sum(1 for r in sel if r["finish"] <= 3) / len(sel)


def exp_at_class(h, race, rid):
    """同クラス以上の経験数 log1p"""
    rs = h.get("races", [])
    tr = _rk(race.get("today_tier"))
    if tr is None:
        return None
    n = sum(1 for r in rs if _rk(r.get("tier")) is not None and _rk(r["tier"]) <= tr)
    return math.log1p(n)


def classup_lastgood(h, race, rid):
    """昇級×前走内容: 昇級初戦なら前走の良さ(0.5-finfrac)、非昇級は0"""
    cu = class_up(h, race, rid)
    if cu is None:
        return None
    rs = h.get("races", [])
    return cu * (0.5 - _ff(rs[0]))


def field_chg(h, race, rid):
    """頭数変化: 前走頭数 - 今日頭数（正=今日は少頭数）"""
    rs = h.get("races", [])
    tf = race.get("field")
    if not rs or not tf:
        return None
    pf = rs[0].get("field")
    if not pf:
        return None
    return float(pf - tf)


FEATS = {
    "class_up": class_up,
    "class_down": class_down,
    "tier_gap_mean3": tier_gap_mean3,
    "same_class_place": same_class_place,
    "exp_at_class": exp_at_class,
    "classup_lastgood": classup_lastgood,
    "field_chg": field_chg,
}

RUNS = [
    ("A_updown", ["class_up", "class_down", "tier_gap_mean3"]),
    ("B_experience", ["same_class_place", "exp_at_class"]),
    ("C_interact", ["classup_lastgood", "field_chg"]),
]


def main():
    ds = H.load_base()
    print(f"dataset: {len(ds)}R", flush=True)
    for name, fn in FEATS.items():
        H.add_feature(ds, name, fn)
    print("features added", flush=True)

    results = {}
    for label, extra in RUNS:
        r = H.run_experiment(ds, extra=extra, label=label)
        results[label] = r
        base_n = len(r["feats"]) - len(extra)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            print(f"    weight[{f}] = {w:+.4f}", flush=True)

    # D: |重み|>=0.04の特徴量を合流
    picked = []
    for label, extra in RUNS:
        r = results[label]
        base_n = len(r["feats"]) - len(extra)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            if abs(w) >= 0.04 and f not in picked:
                picked.append(f)
    print(f"\nD候補（|w|>=0.04）: {picked}", flush=True)
    if picked and sorted(picked) not in [sorted(e) for _, e in RUNS]:
        r = H.run_experiment(ds, extra=picked, label="D_combo")
        results["D_combo"] = r
        base_n = len(r["feats"]) - len(picked)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            print(f"    weight[{f}] = {w:+.4f}", flush=True)

    json.dump(results,
              open("/tmp/claude-0/-home-user--/a62f6054-2a2d-5711-b990-3a94f7d05b49/scratchpad/exp_class_context_results.json", "w"),
              indent=1, ensure_ascii=False)
    print("\n==== SUMMARY ====")
    for k, v in results.items():
        print(f"{k}: train捕捉5={v['train']['capture5']:.1f}% test捕捉5={v['test']['capture5']:.1f}% "
              f"gate={'WIN' if v['gate'] else 'lose'}")


if __name__ == "__main__":
    main()
