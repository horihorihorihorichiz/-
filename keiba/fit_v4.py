# -*- coding: utf-8 -*-
"""Ver.4: V3(LambdaRank)に「枠番・今日の馬場・コース特性VG」を足した本番学習。

   V3が持っていなかったもの（2026-07-26 診断）:
     - 枠番      → 「外枠のモデル2位が1位を逆転(+9.3pt)」という順位付けの壊れの原因
     - 今日の馬場 → wet_apt(過去の道悪実績)はあるが「今日が不良か」を知らなかった
     - today_vg  → 学習データ全6,701件で2固定のバグ（hist_fix_vg.py で修正済み）

   追加特徴は fit_v2.RAW_FEATS / fit_v2.CTX_FEATS。レース内z標準化を通すと
   枠番は馬番の順序に潰れ、レース単位の値は全頭0になるため、生値のまま渡す。

   採否は wf_compare.py のゲート4項目で判定する（このスクリプトは学習のみ）。
   usage: python3 fit_v4.py [--rounds 800] [--write]
"""
import argparse

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from fit_v2win import winner_metrics
from wf_compare import load_ds, matrix, predict

TEST_DAYS = {"20260704", "20260705", "20260711", "20260712"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=800)
    ap.add_argument("--lr", type=float, default=0.02)
    ap.add_argument("--leaves", type=int, default=31)
    ap.add_argument("--out", default="model_v4.txt")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_ds()
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    names = V2.feat_names(v4=True)
    print(f"データ: train {len(train)}R / test {len(test)}R / 特徴 {len(names)}", flush=True)

    n_val = max(50, len(train)//10)
    Xt, yt, gt = matrix(train[:-n_val], True)
    Xv, yv, gv = matrix(train[-n_val:], True)
    dtr = lgb.Dataset(Xt, label=yt, group=gt, feature_name=names)
    dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=a.lr, num_leaves=a.leaves, min_data_in_leaf=30,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    model = lgb.train(params, dtr, num_boost_round=a.rounds, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(60, verbose=False)])
    print(f"best_iteration: {model.best_iteration}", flush=True)

    imp = sorted(zip(names, model.feature_importance("gain")), key=lambda x: -x[1])
    print("重要度top12: " + ", ".join(f"{k}={v:.0f}" for k, v in imp[:12]))
    newf = [k for k in V2.RAW_FEATS + V2.CTX_FEATS]
    print("追加特徴の重要度: " + ", ".join(
        f"{k}={dict(imp)[k]:.0f}(#{[x[0] for x in imp].index(k)+1})" for k in newf))

    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        print(f"\n── {name} ──")
        winner_metrics(dset, lambda r: predict(model, r, True), "Ver.4(+枠+馬場+VG)")

    if a.write:
        model.save_model(a.out, num_iteration=model.best_iteration)
        print(f"\n{a.out} に保存した。")


if __name__ == "__main__":
    main()
