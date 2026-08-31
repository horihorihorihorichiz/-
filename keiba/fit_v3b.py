# -*- coding: utf-8 -*-
"""Ver.3スイープ + U2アンサンブル。「最強馬に最高得点」の最終詰め。
   usage: python3 fit_v3b.py [--write]"""
import argparse, itertools, json, sys

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
from fit_v2win import winner_metrics
from fit_v3 import to_matrix, scores_from, TEST_DAYS
import exp_harness as H


def kpi_pair(dset, fn):
    k = H.kpi(dset, fn)
    return k["capture5"], k["win1"], k["all3"], k["div_roi"], k["div_n"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = V2.load_dataset("hist", "hist_feat")
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    print(f"train {len(train)} / test {len(test)}", flush=True)
    n_val = max(50, len(train)//10)
    Xt, yt, gt, _ = to_matrix(train[:-n_val])
    Xv, yv, gv, _ = to_matrix(train[-n_val:])
    dtrain = lgb.Dataset(Xt, label=yt, group=gt)
    dval = lgb.Dataset(Xv, label=yv, group=gv, reference=dtrain)

    # U2線形スコア(アンサンブル相手)
    pv = json.load(open("params_v2.json", encoding="utf-8"))
    wU2 = pv["weights_win"]
    def s_u2(r):
        return V2.scores(r, wU2)

    best = None
    for lr, leaves, mdl in itertools.product((0.02, 0.05), (15, 31, 63), (30, 50)):
        params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                      learning_rate=lr, num_leaves=leaves, min_data_in_leaf=mdl,
                      feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                      lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
        m = lgb.train(params, dtrain, num_boost_round=800, valid_sets=[dval],
                      callbacks=[lgb.early_stopping(60, verbose=False)])
        # 選定はtrain内バリデーションのNDCGのみ(testは触らない)
        sc = m.best_score["valid_0"]["ndcg@5"]
        print(f"lr={lr} leaves={leaves} mdl={mdl} iter={m.best_iteration} valNDCG@5={sc:.4f}", flush=True)
        if best is None or sc > best[0]:
            best = (sc, m, (lr, leaves, mdl))
    _, model, hp = best
    print(f"\n選定: lr/leaves/min_data = {hp} (train内バリデーションで選択)", flush=True)

    # z正規化してアンサンブル(V3:U2 = w:1-w)。重みはtrain内バリデーションで選ぶ
    def mk_ens(w):
        def fn(r):
            s3 = scores_from(model, r)
            s2 = s_u2(r)
            def z(d):
                vs = list(d.values())
                mu = sum(vs)/len(vs)
                sd = (sum((v-mu)**2 for v in vs)/len(vs))**0.5 or 1
                return {k: (v-mu)/sd for k, v in d.items()}
            z3, z2 = z(s3), z(s2)
            return {n: w*z3[n] + (1-w)*z2[n] for n in z3}
        return fn
    val_races = train[-n_val:]
    best_w = max((0.0, 0.3, 0.5, 0.7, 1.0),
                 key=lambda w: H.kpi(val_races, mk_ens(w))["capture5"])
    print(f"アンサンブル重み(V3側): {best_w} (train内バリデーションで選択)", flush=True)

    for name, dset in (("train", train), ("test", test)):
        print(f"\n── {name} ──")
        winner_metrics(dset, s_u2, "U2(現行)")
        winner_metrics(dset, lambda r: scores_from(model, r), "V3(スイープ後)")
        winner_metrics(dset, mk_ens(best_w), f"ENS(V3×{best_w})")

    if a.write:
        model.save_model("model_v3.txt", num_iteration=model.best_iteration)
        pv["ensemble_w_v3"] = best_w
        json.dump(pv, open("params_v2.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nmodel_v3.txt + ensemble_w_v3 を保存した。")


if __name__ == "__main__":
    main()
