# -*- coding: utf-8 -*-
"""Ver.5 本番学習（2026-07-27）。

   V5 = 統一データ(enrich2年化でtsi被覆66%・騎手率全期間・過去走baba66.8%)
        + V4の枠/今日の馬場/VG特徴 + 強さ特徴6本(EXTRA_FEATS) + 二値目的関数。

   WF2200R実測(wf_compare v5): 1位勝率26.7% / 市場implied比-1.3pt / 単勝ROI80.3% /
   乖離帯315% / 外枠2位逆転なし。※種分散は25.8-26.7%(v5a/v5b)＝上振れ込みで読む。
   種平均(v5s)は尖りが鈍り全ゲート劣後のため単体モデルを採用。

   既定エンジンはV3のまま(パターン台帳はV3得点で採掘)。V5は KEIBA_ENGINE=v5 で有効化。
   usage: python3 fit_v5.py --write
"""
import argparse

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from wf_compare import load_ds, matrix, VARIANTS, train_fold, predict, _zs

SPEC = VARIANTS["v5"]
TEST_DAYS = {"20260704", "20260705", "20260711", "20260712"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="model_v5.txt")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_ds()
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    names = V2.feat_names(v4=True, extra=True)
    print(f"データ: train {len(train)}R / test {len(test)}R / 特徴 {len(names)}", flush=True)

    model = train_fold(train, SPEC)
    print(f"best_iteration: {model.best_iteration}", flush=True)

    imp = sorted(zip(names, model.feature_importance("gain")), key=lambda x: -x[1])
    print("重要度top12: " + ", ".join(f"{k}={v:.0f}" for k, v in imp[:12]))
    rank = {k: i+1 for i, (k, _) in enumerate(imp)}
    print("強さ特徴6本: " + ", ".join(f"{k}=#{rank[k]}" for k in V2.EXTRA_FEATS))

    if test:
        hit = 0
        for r in test:
            s = predict(model, r, True, True)
            hit += (max(s, key=lambda n: s[n]) == r["top3"][0])
        print(f"holdout {len(test)}R: 1着をモデル1位に置けた率 {hit/len(test)*100:.1f}%")

    if a.write:
        model.save_model(a.out, num_iteration=model.best_iteration)
        print(f"{a.out} に保存した。( KEIBA_ENGINE=v5 で有効化 / 42特徴 )")


if __name__ == "__main__":
    main()
