# -*- coding: utf-8 -*-
"""特徴量実験の共通ハーネス（エージェント実験用・ものさし統一）。
   使い方（実験スクリプト側）:
       import exp_harness as H
       ds = H.load_base()                      # 基本特徴量入りデータセット
       H.add_feature(ds, "my_feat", fn)        # fn(h, race, rid) -> float|None (馬ごと)
       result = H.run_experiment(ds, extra=["my_feat"], label="実験名")
   ゲート: result["test_capture5"] が H.BASELINE_TEST を超え、trainも改善していれば勝ち。
   標準分割: test = 20260704,20260705,20260711,20260712（変更禁止）
"""
import glob, json, math, os, sys

import fit_v2 as V2

TEST_DAYS = {"20260704", "20260705", "20260711", "20260712"}
# 現行チャンピオン(U2統合 7/14)の実測値: これを超えたら勝ち
BASELINE_TRAIN = 68.7
BASELINE_TEST = 70.6


def load_base(histdir="hist", featdir="hist_feat"):
    """fit_v2の標準データセット + 生のrace/horse参照を持たせる"""
    ds = V2.load_dataset(histdir, featdir)
    for r in ds:
        r["_raw"] = None   # 遅延読み用
    return ds


def add_feature(ds, name, fn, histdir="hist"):
    """fn(horse_dict, race_dict, rid) -> value|None を全レースに適用しz標準化して追加"""
    for r in ds:
        d = json.load(open(os.path.join(histdir, f"{r['rid']}.json"), encoding="utf-8"))
        vals = {}
        by_num = {h["num"]: h for h in d["race"]["horses"]}
        for n in r["ns"]:
            h = by_num.get(n)
            vals[n] = fn(h, d["race"], r["rid"]) if h else None
        r["X"][name] = V2.z_in_race(vals)


def _pl_fit(train, feats, l2=0.05, wpos=(3, 1, 0.5), iters=250, lr=0.3):
    w = [0.0]*len(feats)
    m = [0.0]*len(feats)
    for it in range(iters):
        nll = 0.0
        g = [0.0]*len(feats)
        n_obs = 0.0
        for r in train:
            s = {n: sum(w[i]*r["X"][k][n] for i, k in enumerate(feats)) for n in r["ns"]}
            alive = list(s.keys())
            for pos in range(3):
                pw_ = wpos[pos]
                if pw_ <= 0:
                    break
                winner = r["top3"][pos]
                mx = max(s[n] for n in alive)
                e = {n: math.exp(s[n]-mx) for n in alive}
                Z = sum(e.values())
                p = {n: e[n]/Z for n in alive}
                nll += -pw_*math.log(max(p[winner], 1e-12))
                n_obs += pw_
                for i, k in enumerate(feats):
                    g[i] += -pw_*(r["X"][k][winner] - sum(p[n]*r["X"][k][n] for n in alive))
                alive.remove(winner)
        for i in range(len(feats)):
            g[i] = g[i]/n_obs + 2*l2*w[i]
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
    return w


def kpi(ds, score_fn):
    n = at1 = cap_h = cap_n = cap_all = 0
    roi_s = roi_r = 0.0
    div_s = div_r = 0.0
    for r in ds:
        s = score_fn(r)
        order = sorted(s, key=lambda x: -s[x])
        top5 = set(order[:5])
        inn = sum(1 for t in r["top3"] if t in top5)
        cap_h += inn
        cap_n += 3
        cap_all += (inn == 3)
        n += 1
        at1 += (order[0] == r["top3"][0])
        o = r["odds"].get(order[0])
        if o:
            roi_s += 1
            roi_r += (o if order[0] == r["top3"][0] else 0)
            mrank = sorted(r["odds"], key=lambda h: r["odds"][h]).index(order[0]) + 1
            if mrank >= 4:
                div_s += 1
                div_r += (o if order[0] == r["top3"][0] else 0)
    return dict(capture5=cap_h/cap_n*100, all3=cap_all/n*100, win1=at1/n*100,
                roi=(roi_r/roi_s*100 if roi_s else 0),
                div_roi=(div_r/div_s*100 if div_s else 0), div_n=int(div_s), n=n)


def run_experiment(ds, extra=None, drop=None, label="exp", l2=0.05, wpos=(3, 1, 0.5)):
    feats = [f for f in V2.FEATS if not (drop and f in drop)] + (extra or [])
    train = [r for r in ds if r["date"] not in TEST_DAYS]
    test = [r for r in ds if r["date"] in TEST_DAYS]
    w = _pl_fit(train, feats, l2=l2, wpos=wpos)
    out = {"label": label, "feats": feats,
           "weights": [round(x, 4) for x in w]}
    for name, dset in (("train", train), ("test", test)):
        k = kpi(dset, lambda r: {n: sum(w[i]*r["X"][f][n] for i, f in enumerate(feats))
                                 for n in r["ns"]})
        out[name] = k
        print(f"[{label}] {name}: 捕捉5={k['capture5']:.1f}% 全3頭={k['all3']:.1f}% "
              f"勝1位={k['win1']:.1f}% ROI={k['roi']:.0f}% 乖離ROI={k['div_roi']:.0f}%(n={k['div_n']})")
    out["gate"] = (out["test"]["capture5"] > BASELINE_TEST and
                   out["train"]["capture5"] > BASELINE_TRAIN)
    print(f"[{label}] ゲート: {'勝ち' if out['gate'] else '負け'} "
          f"(基準 train>{BASELINE_TRAIN} test>{BASELINE_TEST})")
    return out
