# -*- coding: utf-8 -*-
"""ファミリー4: 展開・脚質の文脈（レース内の相対的な展開有利）特徴量実験。
   - 先行圧力（他馬の先行度合計）×自分の脚質位置 = 展開利
   - 逃げ候補が単独か複数か（単騎逃げボーナス/競り合いペナルティ）
   - 今日の馬番×距離・馬番×先行力の交互作用
   レース全体はrace_dict["horses"]の過去走情報のみで走査（市場情報・当該レース結果は不使用）。
   usage: python3 exp_pace_context.py
"""
import json

import exp_harness as H

STYLE_POS = {"逃": 0.10, "先": 0.30, "差": 0.60, "追": 0.85}


def _ep(h):
    """早期ポジション指数: 過去走の corner4/field 平均（直近5走）。無ければ紙上脚質で代用。0=最前"""
    rs = h.get("races", [])
    cf = [r["corner4"] / max(r.get("field", 1), 1) for r in rs[:5] if r.get("corner4")]
    if cf:
        return sum(cf) / len(cf)
    return STYLE_POS.get(h.get("paper_style"))


def _frontness(ep):
    """先行度: ep<=0.35 の馬がどれだけ前に行くか（0〜1）"""
    if ep is None:
        return 0.0
    return max(0.0, (0.35 - ep)) / 0.35


def _is_esc(h):
    """逃げ候補判定: 紙上脚質が逃、またはコーナー通過が極端に前"""
    if h.get("paper_style") == "逃":
        return True
    ep = _ep(h)
    return ep is not None and ep < 0.15


# ---- 特徴量定義 ----

def pace_adv(h, race, rid):
    """展開利(コーナー実績ベース): 自分のep × 他馬の先行圧力。
       前圧が高いレースほど差し馬が有利（値大）、先行馬は不利（値小）"""
    ep_i = _ep(h)
    if ep_i is None:
        return None
    press = sum(_frontness(_ep(o)) for o in race["horses"] if o["num"] != h["num"])
    return ep_i * press / max(race.get("field", 10), 1)


def pace_adv_s(h, race, rid):
    """展開利(紙上脚質ベース): 脚質位置 × 他馬の逃+先の頭数比率"""
    sp = STYLE_POS.get(h.get("paper_style"))
    if sp is None:
        return None
    nf = sum(1 for o in race["horses"]
             if o["num"] != h["num"] and o.get("paper_style") in ("逃", "先"))
    return sp * nf / max(race.get("field", 10), 1)


def lone_esc(h, race, rid):
    """単騎逃げ: 逃げ候補が自分だけ=+1、2頭=0、3頭以上=負。非逃げ馬=0"""
    if not _is_esc(h):
        return 0.0
    n_esc = sum(1 for o in race["horses"] if _is_esc(o))
    return float(2 - n_esc)


def post_frac(h, race, rid):
    """今日の馬番の相対位置（0=最内〜1=大外）。符号は学習に委ねる"""
    return h["num"] / max(race.get("field", 1), 1)


def post_x_dist(h, race, rid):
    """馬番×距離の交互作用: (馬番位置-0.5)×距離の長短。短距離で外枠の損得を捉える"""
    pf = h["num"] / max(race.get("field", 1), 1)
    return (pf - 0.5) * (race.get("distance", 1600) - 1600) / 400.0


def post_x_front(h, race, rid):
    """内枠×先行力: 内枠の先行馬はロスなく前を取れる"""
    pf = h["num"] / max(race.get("field", 1), 1)
    return (0.5 - pf) * _frontness(_ep(h))


FEATS = {
    "pace_adv": pace_adv,
    "pace_adv_s": pace_adv_s,
    "lone_esc": lone_esc,
    "post_frac": post_frac,
    "post_x_dist": post_x_dist,
    "post_x_front": post_x_front,
}

RUNS = [
    ("A_pace", ["pace_adv", "pace_adv_s", "lone_esc"]),
    ("B_draw", ["post_frac", "post_x_dist", "post_x_front"]),
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

    # C: A/Bで|重み|>=0.04 の追加特徴量を合流
    picked = []
    for label, extra in RUNS:
        r = results[label]
        base_n = len(r["feats"]) - len(extra)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            if abs(w) >= 0.04 and f not in picked:
                picked.append(f)
    print(f"\nC候補（|w|>=0.04）: {picked}", flush=True)
    if picked and sorted(picked) not in [sorted(e) for _, e in RUNS]:
        r = H.run_experiment(ds, extra=picked, label="C_combo")
        results["C_combo"] = r
        base_n = len(r["feats"]) - len(picked)
        for f, w in zip(r["feats"][base_n:], r["weights"][base_n:]):
            print(f"    weight[{f}] = {w:+.4f}", flush=True)

    json.dump(results,
              open("/tmp/claude-0/-home-user--/a62f6054-2a2d-5711-b990-3a94f7d05b49/scratchpad/exp_pace_context_results.json", "w"),
              indent=1, ensure_ascii=False)
    print("\n==== SUMMARY ====")
    for k, v in results.items():
        print(f"{k}: train捕捉5={v['train']['capture5']:.1f}% test捕捉5={v['test']['capture5']:.1f}% "
              f"gate={'WIN' if v['gate'] else 'lose'}")


if __name__ == "__main__":
    main()
