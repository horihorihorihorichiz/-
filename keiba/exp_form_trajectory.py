# -*- coding: utf-8 -*-
"""ファミリー2: フォーム軌道（直近走の流れ）特徴量実験。
   - 着順/指数トレンド（直近3走の傾き）
   - 連続好走streak・大敗からの巻き返し履歴
   - 休養明け×前走成績の交互作用・2走前との比較
   usage: python3 exp_form_trajectory.py
"""
import json
import math

import exp_harness as H


def _ff(r):
    """finish fraction: 0(勝ち)〜1(最下位)"""
    return r["finish"] / max(r.get("field", 1), 1)


def _slope(ys):
    """ys[0]=最新。x=0(新)..n-1(古)への最小二乗傾き。正=昔ほど悪い=上昇基調"""
    n = len(ys)
    if n < 2:
        return None
    xm = (n - 1) / 2
    ym = sum(ys) / n
    num = sum((i - xm) * (ys[i] - ym) for i in range(n))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den


# ---- 特徴量定義 ----

def fin_trend3(h, race, rid):
    """直近3走の着順フラクションの傾き（正=良化トレンド）"""
    rs = h.get("races", [])
    fs = [_ff(r) for r in rs[:3]]
    return _slope(fs)


def tsi_trend3(h, race, rid):
    """直近3走のタイム指数の傾き（新しいほど高い=正）"""
    rs = h.get("races", [])
    ts = [r.get("tsi") for r in rs[:3]]
    ts = [t for t in ts if t is not None]
    if len(ts) < 2:
        return None
    s = _slope(ts)
    return -s if s is not None else None  # 指数は高いほど良い→符号反転で「良化=正」


def fin_mean3(h, race, rid):
    """直近3走の着順フラクション平均（前走だけで判断しない・符号反転で良い=正）"""
    rs = h.get("races", [])
    fs = [_ff(r) for r in rs[:3]]
    return -sum(fs) / len(fs) if fs else None


def streak_top3(h, race, rid):
    """最新から連続で3着内に入っている回数"""
    rs = h.get("races", [])
    if not rs:
        return None
    c = 0
    for r in rs:
        if r["finish"] <= 3:
            c += 1
        else:
            break
    return float(c)


def rebound_flag(h, race, rid):
    """前走大敗(下位35%)だが2-3走前に3着内あり=巻き返し候補フラグ"""
    rs = h.get("races", [])
    if len(rs) < 2:
        return None
    if _ff(rs[0]) <= 0.65:
        return 0.0
    return 1.0 if any(r["finish"] <= 3 for r in rs[1:3]) else 0.0


def rebound_hist(h, race, rid):
    """過去の「大敗→次走3着内」率（巻き返し実績。大敗経験なしはNone）"""
    rs = h.get("races", [])
    hits = cnt = 0
    for i in range(len(rs) - 1):
        if _ff(rs[i + 1]) > 0.65:  # rs[i+1]で大敗→次走がrs[i]
            cnt += 1
            if rs[i]["finish"] <= 3:
                hits += 1
    return hits / cnt if cnt else None


def layoff_lastfin(h, race, rid):
    """休養明け×前走成績の交互作用: log(間隔)×(前走の良さ)"""
    rs = h.get("races", [])
    if not rs:
        return None
    days = h.get("last_race_days") or 30
    return math.log1p(min(days, 365)) * (0.5 - _ff(rs[0]))


def fin_best2(h, race, rid):
    """直近2走のベスト着順フラクション（2走前との比較・良い=正）"""
    rs = h.get("races", [])
    fs = [_ff(r) for r in rs[:2]]
    return -min(fs) if fs else None


FEATS = {
    "fin_trend3": fin_trend3,
    "tsi_trend3": tsi_trend3,
    "fin_mean3": fin_mean3,
    "streak_top3": streak_top3,
    "rebound_flag": rebound_flag,
    "rebound_hist": rebound_hist,
    "layoff_lastfin": layoff_lastfin,
    "fin_best2": fin_best2,
}

RUNS = [
    ("A_trend", ["fin_trend3", "fin_mean3", "tsi_trend3"]),
    ("B_streak_rebound", ["streak_top3", "rebound_flag", "rebound_hist"]),
    ("C_2back_layoff", ["fin_best2", "layoff_lastfin"]),
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
        # 各追加特徴量の学習重みを表示
        base_n = len(r["feats"]) - len(extra)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            print(f"    weight[{f}] = {w:+.4f}", flush=True)

    # D: A/B/Cで|重み|>=0.04の追加特徴量を合流させた最終ラン
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

    json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in results.items()},
              open("/tmp/claude-0/-home-user--/a62f6054-2a2d-5711-b990-3a94f7d05b49/scratchpad/exp_form_trajectory_results.json", "w"),
              indent=1, ensure_ascii=False)
    print("\n==== SUMMARY ====")
    for k, v in results.items():
        print(f"{k}: train捕捉5={v['train']['capture5']:.1f}% test捕捉5={v['test']['capture5']:.1f}% "
              f"gate={'WIN' if v['gate'] else 'lose'}")


if __name__ == "__main__":
    main()
