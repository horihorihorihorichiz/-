# -*- coding: utf-8 -*-
"""ウォークフォワード検証（「勝てるかの証明」装置）。
   月ごとに「その月より前だけで学習→その月を判定」を繰り返す＝未来を知らないシステムの成績。
   計測: ①エッジ購入エンジンのROI ②乖離バケット単勝のROI ③捕捉KPI
   注意: オッズは最終オッズ（実購入はもっと早い時刻=これより甘い可能性がある方向のバイアス）。

   usage: python3 walkforward.py [--start-fold 202511] [--iters 150]
"""
import argparse, json, math, os, sys
from collections import defaultdict

import fit_v2 as V2
import exp_harness as H
import predict as PR
import validate as VAL
from v2_blend import p_market_from, blend


def month_of(r):
    return r["date"][:6]


def fit_fold(train, iters):
    return H._pl_fit(train, V2.FEATS, l2=0.10, wpos=(3, 1, 0.5), iters=iters)


def fold_eval(fold_ds, w, a_pl, b_pl, scale=1.0):
    """エッジ購入エンジンをU2確率で走らせ実払戻で精算"""
    go = staked = returned = 0
    div_s = div_r = 0.0
    cap_h = cap_n = 0
    bykind = defaultdict(lambda: [0, 0])
    for r in fold_ds:
        s = V2.scores(r, w)
        order = sorted(s, key=lambda x: -s[x])
        top5 = set(order[:5])
        cap_h += sum(1 for t in r["top3"] if t in top5)
        cap_n += 3
        # 乖離バケット単勝(モデル1位が4番人気以下→100円)
        top = order[0]
        o = r["odds"].get(top)
        if o and sorted(r["odds"], key=lambda h: r["odds"][h]).index(top) + 1 >= 4:
            div_s += 100
            div_r += (o*100 if top == r["top3"][0] else 0)
        # エッジ購入
        op = os.path.join("hist_odds", f"{r['rid']}.json")
        hp = os.path.join("hist", f"{r['rid']}.json")
        if not os.path.exists(op):
            continue
        odds = json.load(open(op, encoding="utf-8"))
        tan_map = {int(k): v for k, v in odds.get("tan", {}).items() if v}
        q = p_market_from(tan_map)
        mx = max(s.values())
        e = {n: math.exp(s[n]-mx) for n in s}
        Z = sum(e.values())
        pm = {n: e[n]/Z for n in e}
        pp = blend(pm, q, a_pl, b_pl)
        pw = blend(pm, q, 0.0, 1.0)
        picks, total, dec = PR.build_buylist_ev([], odds, edge_scale=scale,
                                                pb_override=dict(win=pw, place=pp))
        if not picks:
            continue
        d = json.load(open(hp, encoding="utf-8"))
        ret = VAL.settle(picks, d["result"].get("payout", {}))
        go += 1
        staked += total
        returned += ret
        for kind, lbl, o_, st, p, ev in picks:
            hit = VAL.settle([(kind, lbl, o_, st, p, ev)], d["result"].get("payout", {}))
            bykind[kind][0] += st
            bykind[kind][1] += hit
    return dict(n=len(fold_ds), go=go, staked=staked, returned=returned,
                div_staked=div_s, div_returned=div_r,
                capture5=cap_h/cap_n*100 if cap_n else 0,
                bykind={k: v for k, v in bykind.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-fold", default="202511", help="この月からウォークフォワード")
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()

    ds = V2.load_dataset("hist", "hist_feat")
    months = sorted({month_of(r) for r in ds})
    folds = [m for m in months if m >= a.start_fold]
    print(f"データ{len(ds)}R / 月{months[0]}〜{months[-1]} / 検証フォールド: {folds}", flush=True)

    agg = defaultdict(float)
    rows = []
    for m in folds:
        train = [r for r in ds if month_of(r) < m]
        fold = [r for r in ds if month_of(r) == m]
        if len(train) < 400 or not fold:
            continue
        w = fit_fold(train, a.iters)
        # placeブレンドは小グリッドで月ごとにフィット(trainのみ)
        best = (9e9, 0.03, 0.85)
        sub = train[-600:]   # 直近600Rで十分(高速化)
        from v2_blend import nll_top3
        for aa in (0.0, 0.03, 0.05):
            for bb in (0.8, 0.85, 0.9):
                v = nll_top3(sub, w, aa, bb)
                if v < best[0]:
                    best = (v, aa, bb)
        _, a_pl, b_pl = best
        r = fold_eval(fold, w, a_pl, b_pl, scale=a.scale)
        rows.append((m, r))
        for k in ("go", "staked", "returned", "div_staked", "div_returned", "n"):
            agg[k] += r[k]
        roi = r["returned"]/r["staked"]*100 if r["staked"] else 0
        droi = r["div_returned"]/r["div_staked"]*100 if r["div_staked"] else 0
        print(f"[{m}] {r['n']}R GO{r['go']} 投{r['staked']} 戻{r['returned']} "
              f"ROI {roi:.0f}% | 乖離単勝ROI {droi:.0f}% | 捕捉5 {r['capture5']:.1f}%", flush=True)

    print("\n==== ウォークフォワード総合(未来を知らないシステムの成績) ====")
    roi = agg["returned"]/agg["staked"]*100 if agg["staked"] else 0
    droi = agg["div_returned"]/agg["div_staked"]*100 if agg["div_staked"] else 0
    print(f"対象 {int(agg['n'])}R / GO {int(agg['go'])}R")
    print(f"エッジ購入: 投{int(agg['staked'])}円 戻{int(agg['returned'])}円 ROI {roi:.1f}%")
    print(f"乖離バケット単勝: 投{int(agg['div_staked'])}円 戻{int(agg['div_returned'])}円 ROI {droi:.1f}%")
    json.dump(dict(rows=[(m, r) for m, r in rows], total=dict(agg)),
              open("walkforward_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
