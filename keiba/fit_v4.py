# -*- coding: utf-8 -*-
"""Ver.4 本番学習（2026-07-26）。wf_compare.py の "v4bin2s" が勝った構成をそのまま焼く。

   V3 からの2点の変更:
     1) 特徴に「枠番・馬番相対・今日の馬場×道悪実績・芝ダ×枠・頭数・VG」を追加
        （V3には枠番も今日の馬場も無く、today_vg は学習データ全件2固定のバグだった）
     2) 目的関数を LambdaRank(3着内の並び) から **二値(1着か否か)** に変更
        LambdaRankは1位を過大評価する癖(top-rank inflation)があり、「外枠のモデル2位が
        モデル1位より勝つ」という順位の壊れを生んでいた。二値+枠特徴でこれが消える。
     3) 種違い5本の平均（レース内zで合議）。1本だけだと学習のブレがそのまま順位に出る。

   WF2200Rでの実測(V3→V4bin2s): 1位勝率 24.8→25.5% / 市場との差 -3.0→-2.2pt /
   1位単勝ROI 74.4→76.5% / 三連複1-2-3位ROI 72.5→76.5% / 外枠2位の逆転=消滅。

   usage: python3 fit_v4.py --write
"""
import argparse

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from wf_compare import load_ds, matrix, VARIANTS, train_fold, predict, _zs

SPEC = VARIANTS["v4bin2s"]      # 二値 / lr0.03 / leaves63 / min_data20 / 5seed
TEST_DAYS = {"20260704", "20260705", "20260711", "20260712"}


def seed_specs(k):
    for i in range(k):
        sp = dict(SPEC)
        sp["params"] = dict(SPEC.get("params") or {},
                            bagging_seed=100+i, feature_fraction_seed=200+i,
                            data_random_seed=300+i)
        yield i, sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--prefix", default="model_v4_s")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_ds()
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    names = V2.feat_names(v4=True)
    print(f"データ: train {len(train)}R / test {len(test)}R / 特徴 {len(names)}", flush=True)

    models = []
    for i, sp in seed_specs(a.seeds):
        m = train_fold(train, sp)
        models.append(m)
        print(f"  seed{i}: best_iteration={m.best_iteration}", flush=True)
        if a.write:
            m.save_model(f"{a.prefix}{i}.txt", num_iteration=m.best_iteration)

    imp = np.zeros(len(names))
    for m in models:
        imp += m.feature_importance("gain")
    order = sorted(zip(names, imp), key=lambda x: -x[1])
    print("\n重要度top12: " + ", ".join(f"{k}={v:.0f}" for k, v in order[:12]))
    rank = {k: i+1 for i, (k, _) in enumerate(order)}
    g = dict(order)
    print("V4追加特徴: " + ", ".join(
        f"{k}=#{rank[k]}({g[k]:.0f})" for k in V2.RAW_FEATS + V2.CTX_FEATS))

    # holdout: 1着を1位に置けた率
    if test:
        hit = 0
        for r in test:
            s = {}
            for m in models:
                p = predict(m, r, True)
                z = _zs(p)
                for n in z:
                    s[n] = s.get(n, 0.0) + z[n]/len(models)
            hit += (max(s, key=lambda n: s[n]) == r["top3"][0])
        print(f"\nholdout {len(test)}R: 1着をモデル1位に置けた率 {hit/len(test)*100:.1f}%")

    if a.write:
        print(f"\n{a.prefix}0..{a.seeds-1}.txt に保存した。"
              f"（v2_live はこの{a.seeds}本をレース内zで平均して使う）")


if __name__ == "__main__":
    main()
