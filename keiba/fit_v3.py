# -*- coding: utf-8 -*-
"""Ver.3: LightGBM LambdaRank（レース単位のランキング学習）。
   「最強の馬に最高得点」を非線形モデルで直接最適化する（7/14ユーザー指示）。
   ラベル: 1着=3, 2着=2, 3着=1, 圏外=0（NDCG@5≒「3着内馬を上位5位に」のKPIと整合）
   特徴量: Ver.2の27特徴(レース内z) + 生値の一部 + 頭数等のレース文脈。市場情報は不使用。
   ゲート: test捕捉5とwin@1がU2(70.6/26.8)を上回ること。

   usage: python3 fit_v3.py [--rounds 400] [--write]
"""
import argparse, json, math, sys

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from fit_v2win import winner_metrics

TEST_DAYS = {"20260704", "20260705", "20260711", "20260712"}


def to_matrix(ds):
    """レースごとにグループ化した特徴行列・ラベル・グループ長"""
    X, y, grp, meta = [], [], [], []
    for r in ds:
        ns = r["ns"]
        lab = {n: 0 for n in ns}
        for pos, t in enumerate(r["top3"]):
            lab[t] = 3 - pos
        for n in ns:
            row = [r["X"][k][n] for k in V2.FEATS]
            row.append(len(ns))                      # 頭数
            X.append(row)
            y.append(lab[n])
        grp.append(len(ns))
        meta.append(r)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), grp, meta


def scores_from(model, r):
    ns = r["ns"]
    X = np.array([[r["X"][k][n] for k in V2.FEATS] + [len(ns)] for n in ns],
                 dtype=np.float32)
    s = model.predict(X)
    return {n: float(v) for n, v in zip(ns, s)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=400)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--leaves", type=int, default=15)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = V2.load_dataset("hist", "hist_feat")
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    print(f"データ: train {len(train)}R / test {len(test)}R / 特徴 {len(V2.FEATS)+1}", flush=True)

    Xtr, ytr, gtr, _ = to_matrix(train)
    # train内の直近1割をearly-stopping用バリデーションに(時系列順)
    n_val_races = max(50, len(train)//10)
    tr_races = train[:-n_val_races]
    va_races = train[-n_val_races:]
    Xt, yt, gt, _ = to_matrix(tr_races)
    Xv, yv, gv, _ = to_matrix(va_races)

    dtrain = lgb.Dataset(Xt, label=yt, group=gt)
    dval = lgb.Dataset(Xv, label=yv, group=gv, reference=dtrain)
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=a.lr, num_leaves=a.leaves,
                  min_data_in_leaf=50, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    model = lgb.train(params, dtrain, num_boost_round=a.rounds,
                      valid_sets=[dval],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
    print(f"best_iteration: {model.best_iteration}", flush=True)

    imp = sorted(zip(V2.FEATS + ["field"], model.feature_importance("gain")),
                 key=lambda x: -x[1])[:10]
    print("重要度top10: " + ", ".join(f"{k}={v:.0f}" for k, v in imp))

    for name, dset in (("train", train), ("test", test)):
        print(f"\n── {name} ──")
        winner_metrics(dset, lambda r: scores_from(model, r), "Ver.3(LambdaRank)")

    if a.write:
        model.save_model("model_v3.txt", num_iteration=model.best_iteration)
        print("model_v3.txt に保存した。")


if __name__ == "__main__":
    main()
