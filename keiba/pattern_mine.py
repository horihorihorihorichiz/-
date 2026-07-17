# -*- coding: utf-8 -*-
"""パターンカタログの採掘（7/14ユーザー指示: 「これは買い」のパターンを統計で決める）。
   月次ウォークフォワード(未来を知らないV3)で、候補パターン群のROIを一斉測定する。
   各パターン=「条件(モデル判定×レース特徴)→買い目(100円/点)」。実払戻で精算。

   usage: python3 pattern_mine.py [--start-fold 202511]
   出力: pattern_stats.json + 表
"""
import argparse, itertools, json, os, sys
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from fit_v3 import to_matrix, scores_from


def mrank_of(top, odds_map):
    if top not in odds_map:
        return 99
    return sorted(odds_map, key=lambda h: odds_map[h]).index(top) + 1


def settle_one(kind, key, payout):
    t = payout.get(kind, {})
    return t.get(key, 0)


def eval_patterns(fold, model):
    """各レースで全候補パターンの買い目を作り精算。返り値: {pattern: [stake, ret, n_bets, n_races]}"""
    P = defaultdict(lambda: [0, 0, 0, 0])
    for r in fold:
        hp = os.path.join("hist", f"{r['rid']}.json")
        if not os.path.exists(hp):
            continue
        d = json.load(open(hp, encoding="utf-8"))
        payout = d["result"].get("payout", {})
        s = scores_from(model, r)
        order = sorted(s, key=lambda x: -s[x])
        t1, t2, t3_, t4, t5 = (order + [None]*5)[:5]
        odds = r["odds"]
        mr = mrank_of(t1, odds)
        nf = len(r["ns"])
        fs = "小頭数" if nf <= 12 else "多頭数"
        mrb = "1人気" if mr == 1 else ("2-3人気" if mr <= 3 else "4人気以下")

        def bet(name, kind, key, pts=1):
            ret = settle_one(kind, key, payout)
            P[name][0] += 100*pts if pts == 1 else 100
            P[name][1] += ret
            P[name][2] += 1
        def race_mark(name):
            P[name][3] += 1

        # --- 単勝/複勝(1位・人気帯別) ---
        race_mark(f"単勝1位[{mrb}]")
        bet(f"単勝1位[{mrb}]", "単勝", str(t1))
        race_mark(f"複勝1位[{mrb}]")
        bet(f"複勝1位[{mrb}]", "複勝", str(t1))
        # --- ワイド ---
        if t2:
            k12 = "-".join(map(str, sorted((t1, t2))))
            race_mark(f"ワイド1-2位[{mrb}]")
            bet(f"ワイド1-2位[{mrb}]", "ワイド", k12)
        if t3_:
            race_mark(f"ワイドBOX上位3[{fs}]")
            for a, b in itertools.combinations((t1, t2, t3_), 2):
                bet(f"ワイドBOX上位3[{fs}]", "ワイド", "-".join(map(str, sorted((a, b)))))
        # --- 馬連 ---
        if t2:
            race_mark(f"馬連1-2位[{mrb}]")
            bet(f"馬連1-2位[{mrb}]", "馬連", "-".join(map(str, sorted((t1, t2)))))
        # --- 三連複 ---
        if t5:
            top5 = [t1, t2, t3_, t4, t5]
            race_mark(f"三連複BOX上位5[{fs}]")
            for c in itertools.combinations(top5, 3):
                bet(f"三連複BOX上位5[{fs}]", "三連複", "-".join(map(str, sorted(c))))
            race_mark(f"三連複軸1位ながし2-5位[{fs}]")
            for pair in itertools.combinations(top5[1:], 2):
                c = tuple(sorted((t1,) + pair))
                bet(f"三連複軸1位ながし2-5位[{fs}]", "三連複", "-".join(map(str, c)))
            race_mark(f"三連複BOX上位4[{fs}]")
            for c in itertools.combinations(top5[:4], 3):
                bet(f"三連複BOX上位4[{fs}]", "三連複", "-".join(map(str, sorted(c))))
        # --- 乖離単勝(基準パターン) ---
        if mr >= 4:
            race_mark("乖離単勝(1位が4人気以下)")
            bet("乖離単勝(1位が4人気以下)", "単勝", str(t1))
            race_mark("乖離複勝(1位が4人気以下)")
            bet("乖離複勝(1位が4人気以下)", "複勝", str(t1))
    return P


def month_of(r):
    return r["date"][:6]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-fold", default="202511")
    a = ap.parse_args()
    ds = V2.load_dataset("hist", "hist_feat")
    months = sorted({month_of(r) for r in ds})
    folds = [m for m in months if m >= a.start_fold]
    print(f"データ{len(ds)}R folds={folds}", flush=True)

    agg = defaultdict(lambda: [0, 0, 0, 0])
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=0.05, num_leaves=15, min_data_in_leaf=50,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    for m in folds:
        train = [r for r in ds if month_of(r) < m]
        fold = [r for r in ds if month_of(r) == m]
        if len(train) < 400 or not fold:
            continue
        nv = max(50, len(train)//10)
        Xt, yt, gt, _ = to_matrix(train[:-nv])
        Xv, yv, gv, _ = to_matrix(train[-nv:])
        dtr = lgb.Dataset(Xt, label=yt, group=gt)
        dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
        model = lgb.train(params, dtr, num_boost_round=400, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(50, verbose=False)])
        P = eval_patterns(fold, model)
        for k, v in P.items():
            for i in range(4):
                agg[k][i] += v[i]
        print(f"[{m}] 済", flush=True)

    print("\n==== パターン別ウォークフォワードROI(未来を知らない状態・100円/点) ====")
    rows = []
    for k, (st, ret, nb, nr) in sorted(agg.items(), key=lambda x: -(x[1][1]/x[1][0] if x[1][0] else 0)):
        roi = ret/st*100 if st else 0
        rows.append(dict(pattern=k, stake=st, ret=ret, roi=round(roi, 1),
                         bets=nb, races=nr))
        print(f"  {k:28s} ROI {roi:6.1f}%  投{st:>7} 戻{int(ret):>7} ({nr}R)")
    json.dump(rows, open("pattern_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ pattern_stats.json")


if __name__ == "__main__":
    main()
