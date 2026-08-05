# -*- coding: utf-8 -*-
"""展開(ペース・脚質構成)の角度からの台帳分析。
   事前情報のみ: 各馬の過去走corner4/field(直近5走)から早期位置epを推定し、
   レースの脚質構成(先行圧・単騎逃げ)×モデル上位馬の脚質で「展開利」を分類。
   台帳(wf_preds_v3)のモデル順位・確定オッズ・払戻で dev(≤202603)/conf(≥202604) を分けて検証。
   usage: python3 exp_tenkai.py [--null N]  (--null で展開ラベルのシャッフル偽陽性測定)
"""
import argparse, glob, json, random
from collections import defaultdict

import sim_rank as SR

STYLE_POS = {"逃": 0.10, "先": 0.30, "差": 0.60, "追": 0.85}


def ep_of(h):
    rs = h.get("races", [])
    cf = [r["corner4"]/max(r.get("field") or 1, 1) for r in rs[:5] if r.get("corner4")]
    if cf:
        return sum(cf)/len(cf)
    return STYLE_POS.get(h.get("paper_style"))


def tenkai_of(race, order):
    """レースの展開特徴。全て馬柱由来(事前情報)"""
    eps = {}
    for h in race["horses"]:
        e = ep_of(h)
        if e is not None:
            eps[h["num"]] = e
    if len(eps) < max(5, len(race["horses"])*0.7):
        return None
    n_front = sum(1 for e in eps.values() if e <= 0.20)
    pressure = sum(max(0.0, 0.30-e)/0.30 for e in eps.values()) / len(eps)
    t = eps.get(order[0])
    if t is None:
        return None
    sty = "逃" if t <= 0.17 else "先" if t <= 0.38 else "差" if t <= 0.60 else "追"
    if n_front == 1 and t <= 0.20:
        scen = "単騎逃げ(1位が唯一の逃げ)"
    elif n_front >= 3 and t <= 0.25:
        scen = "逃げ競合(1位前・先行3頭+)"
    elif pressure >= 0.115 and t >= 0.50:
        scen = "差し×先行圧高"
    elif pressure <= 0.055 and t >= 0.50:
        scen = "差し×スロー(展開不利)"
    else:
        scen = "中立"
    return dict(eps=eps, n_front=n_front, pressure=pressure,
                top_ep=t, top_sty=sty, scen=scen)


def seg_of(r):
    return "dev" if r["m"] <= "202603" else "conf"


def acc_add(a, inv, ret):
    a["n"] += 1
    a["inv"] += inv
    a["ret"] += ret
    a["hit"] += (1 if ret > 0 else 0)


def fmt(a):
    if not a["inv"]:
        return "-"
    return f"ROI{a['ret']/a['inv']*100:6.1f}% {int(a['n']):4d}R 的中{int(a['hit'])}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--null", type=int, default=0)
    a = ap.parse_args()
    rid_date = {}
    for f in glob.glob("hist/*.json"):
        try:
            rid_date[f.split("/")[-1][:12]] = json.load(open(f, encoding="utf-8")).get("date", "")
        except Exception:
            pass
    rows = SR.load("wf_preds_v3.jsonl")
    joined = []
    for r in rows:
        r["date"] = rid_date.get(r["rid"], "")
        try:
            race = json.load(open(f"hist/{r['rid']}.json", encoding="utf-8"))["race"]
        except Exception:
            continue
        tk = tenkai_of(race, r["order"])
        if tk is None:
            continue
        tk["venue"] = race.get("venue")
        tk["surface"] = race.get("surface")
        tk["dist"] = race.get("distance")
        joined.append((r, tk))
    print(f"展開特徴付与: {len(joined)}/{len(rows)}R")

    def run_pass(joined, label, quiet=False):
        # A) モデル1位 単勝100円 の展開シナリオ別成績
        A = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        # B) 既存◎発火(最良)の展開シナリオ別成績
        B = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        for r, tk in joined:
            seg = seg_of(r)
            top = r["order"][0]
            tanpay = r["pay"].get("単勝", {})
            winner = int(list(tanpay.keys())[0]) if tanpay else None
            hit_ret = float(tanpay[str(top)]) if str(top) in tanpay else 0
            for key in (tk["scen"], f"1位脚質={tk['top_sty']}"):
                acc_add(A[key][seg], 100, hit_ret)
                acc_add(A[key]["all"], 100, hit_ret)
            buy, hc = SR.classify_race(r)
            if buy:
                best = max(buy, key=lambda f: f[2])
                st = SR.settle_fire(r, best[0], best[3])
                if st is not None:
                    pts, pay100 = st
                    acc_add(B[tk["scen"]][seg], pts*100, pay100)
                    acc_add(B[tk["scen"]]["all"], pts*100, pay100)
        if quiet:
            return A, B
        print(f"\n=== {label} ===")
        print("\n[A] モデル1位に単勝100円(全レース) 展開別:")
        for k in sorted(A, key=lambda k: -A[k]["all"]["n"]):
            print(f"  {k:<24s} 全:{fmt(A[k]['all'])} | dev:{fmt(A[k]['dev'])} | conf:{fmt(A[k]['conf'])}")
        print("\n[B] 既存◎パターン最良発火の展開別:")
        for k in sorted(B, key=lambda k: -B[k]["all"]["n"]):
            print(f"  {k:<24s} 全:{fmt(B[k]['all'])} | dev:{fmt(B[k]['dev'])} | conf:{fmt(B[k]['conf'])}")
        return A, B

    run_pass(joined, "実データ")

    # C) 場×芝ダ: 勝ち馬の早期位置(前有利か差し有利か) 夏3場向け
    C = defaultdict(list)
    for r, tk in joined:
        tanpay = r["pay"].get("単勝", {})
        if not tanpay:
            continue
        w = int(list(tanpay.keys())[0])
        e = tk["eps"].get(w)
        if e is not None:
            C[(tk["venue"], tk["surface"])].append(e)
    print("\n[C] 勝ち馬の平均早期位置(小さい=前有利) 場×芝ダ n>=30:")
    for k in sorted(C, key=lambda k: len(C[k]), reverse=True):
        v = C[k]
        if len(v) < 30:
            continue
        front = sum(1 for x in v if x <= 0.35)/len(v)
        print(f"  {str(k):<18s} n={len(v):4d} 平均ep={sum(v)/len(v):.3f} 前(ep<=0.35)勝率シェア={front*100:.0f}%")

    if a.null:
        # 展開ラベルを頭数近いレース間でシャッフルして同じ集計→偽陽性の分布
        random.seed(7)
        base_A, base_B = run_pass(joined, "", quiet=True)
        def best_spread(A):
            rois = [A[k]["conf"]["ret"]/A[k]["conf"]["inv"]*100
                    for k in A if A[k]["conf"]["inv"] >= 3000]
            return max(rois)-min(rois) if len(rois) >= 2 else 0
        real = best_spread(base_A)
        nulls = []
        for it in range(a.null):
            sh = [tk for _, tk in joined]
            random.shuffle(sh)
            jj = [(r, s) for (r, _), s in zip(joined, sh)]
            An, Bn = run_pass(jj, "", quiet=True)
            nulls.append(best_spread(An))
        nulls.sort()
        med = nulls[len(nulls)//2]
        p = sum(1 for x in nulls if x >= real)/len(nulls)
        print(f"\n[null] confでのシナリオ間ROI最大差: 実データ{real:.1f}pt vs null中央値{med:.1f}pt (p={p:.2f}, {a.null}回)")


if __name__ == "__main__":
    main()
