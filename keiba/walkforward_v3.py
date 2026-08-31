# -*- coding: utf-8 -*-
"""Ver.3(LambdaRank)のウォークフォワード検証。
   月ごとに「その月より前だけで学習」→その月の (a)モデル1位単勝全買い
   (b)乖離単勝(1位が4番人気以下のみ) (c)捕捉KPI を実払戻で精算。
   usage: python3 walkforward_v3.py [--start-fold 202511]"""
import argparse, json
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from fit_v3 import to_matrix, scores_from


def month_of(r):
    return r["date"][:6]


def train_fold(train):
    n_val = max(50, len(train)//10)
    Xt, yt, gt, _ = to_matrix(train[:-n_val])
    Xv, yv, gv, _ = to_matrix(train[-n_val:])
    dtr = lgb.Dataset(Xt, label=yt, group=gt)
    dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    return lgb.train(params, dtr, num_boost_round=800, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-fold", default="202511")
    a = ap.parse_args()
    ds = V2.load_dataset("hist", "hist_feat")
    months = sorted({month_of(r) for r in ds})
    folds = [m for m in months if m >= a.start_fold]
    print(f"データ{len(ds)}R / 検証: {folds}", flush=True)

    agg = defaultdict(float)
    for m in folds:
        train = [r for r in ds if month_of(r) < m]
        fold = [r for r in ds if month_of(r) == m]
        if len(train) < 400 or not fold:
            continue
        model = train_fold(train)
        flat_s = flat_r = div_s = div_r = 0.0
        cap = capn = 0
        w1 = 0
        for r in fold:
            s = scores_from(model, r)
            order = sorted(s, key=lambda x: -s[x])
            top5 = set(order[:5])
            cap += sum(1 for t in r["top3"] if t in top5)
            capn += 3
            top = order[0]
            w1 += (top == r["top3"][0])
            o = r["odds"].get(top)
            if not o:
                continue
            hit = (o*100 if top == r["top3"][0] else 0)
            flat_s += 100
            flat_r += hit
            if sorted(r["odds"], key=lambda h: r["odds"][h]).index(top) + 1 >= 4:
                div_s += 100
                div_r += hit
        agg["flat_s"] += flat_s; agg["flat_r"] += flat_r
        agg["div_s"] += div_s; agg["div_r"] += div_r
        agg["cap"] += cap; agg["capn"] += capn
        agg["w1"] += w1; agg["n"] += len(fold)
        print(f"[{m}] {len(fold)}R 勝1位率{w1/len(fold)*100:.1f}% 捕捉{cap/capn*100:.1f}% | "
              f"1位単勝全買い {flat_r/flat_s*100 if flat_s else 0:.0f}% | "
              f"乖離単勝 {div_r/div_s*100 if div_s else 0:.0f}% ({int(div_s/100)}点)", flush=True)

    print("\n==== V3 ウォークフォワード総合 ====")
    print(f"対象 {int(agg['n'])}R / 勝1位率 {agg['w1']/agg['n']*100:.1f}% / 捕捉5 {agg['cap']/agg['capn']*100:.1f}%")
    print(f"1位単勝全買い: 投{int(agg['flat_s'])} 戻{int(agg['flat_r'])} ROI {agg['flat_r']/agg['flat_s']*100:.1f}%")
    print(f"乖離単勝: 投{int(agg['div_s'])} 戻{int(agg['div_r'])} ROI {agg['div_r']/agg['div_s']*100:.1f}% ({int(agg['div_s']/100)}点)")
    json.dump(dict(agg), open("walkforward_v3_result.json", "w"), indent=1)


if __name__ == "__main__":
    main()
