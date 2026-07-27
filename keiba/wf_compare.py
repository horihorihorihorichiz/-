# -*- coding: utf-8 -*-
"""V3 と V4(枠番・今日の馬場・VG追加) を **同一fold** で突き合わせるウォークフォワード。

   MODEL_V4_PLAN.md の合格ゲート4項目をそのまま計測する:
     1. モデル1位の勝率 − 市場implied(=0.8/単勝オッズ)  … V3は −2.9pt
     2. モデル1位の単勝ROI(全レース)                     … V3は 74.5%
     3. 乖離帯(1位が4人気以下 × 10倍+ × tier6-9)のROI     … V3は 412.2%
     4. 外枠モデル2位の逆転(13-16頭×3日目+×枠7-8)        … V3は +9.3pt(バグの症状)

   usage:
     python3 wf_compare.py --variants v3,v4 [--start-fold 202511] [--dump v4]
"""
import argparse, json, os, pickle, sys
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import fit_v2 as V2
import course

CACHE = "wf_ds_cache.pkl"


def load_ds(force=False):
    if not force and os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    ds = V2.load_dataset("hist", "hist_feat")
    with open(CACHE, "wb") as f:
        pickle.dump(ds, f)
    return ds


def matrix(rs, v4, extra=False):
    X, y, grp = [], [], []
    for r in rs:
        lab = {n: 0 for n in r["ns"]}
        for pos, t in enumerate(r["top3"]):
            lab[t] = 3 - pos
        for n in r["ns"]:
            X.append(V2.build_row(r, n, v4, extra))
            y.append(lab[n])
        grp.append(len(r["ns"]))
    return (np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), grp)


# 検証する学習設定。V4の狙いは「1位の過大評価(top-rank inflation)」を潰すこと
VARIANTS = {
    "v3":    dict(v4=False, params={}),                    # 現行(比較基準)
    "v4":    dict(v4=True,  params={}),                    # 特徴追加のみ
    # 1着だけを利得にして「勝つ馬を1位に」を直接最適化(3着内の分散を止める)
    "v4win": dict(v4=True,  params=dict(ndcg_eval_at=[1], label_gain=[0, 0, 0, 1])),
    # 上位3頭までしかペア勾配を作らない=下位の入替に引っ張られない
    "v4t3":  dict(v4=True,  params=dict(lambdarank_truncation_level=3)),
    # ランキングをやめて「1着か否か」の確率を直接学習(順位圧縮の癖を排除)
    "v4bin": dict(v4=True,  binary=True),
    "v3bin": dict(v4=False, binary=True),
    # 容量を上げた二値
    "v4bin2": dict(v4=True, binary=True,
                   params=dict(learning_rate=0.03, num_leaves=63, min_data_in_leaf=20)),
    # さらに容量を上げた二値
    "v4bin3": dict(v4=True, binary=True,
                   params=dict(learning_rate=0.03, num_leaves=127, min_data_in_leaf=10)),
    # 二値(勝ち馬確率)とランキング(3着内の並び)はズレ方が違う → レース内z平均で合議
    "v4ens": dict(ens=["v4bin", "v4"]),
    "v4ens3": dict(ens=["v4bin", "v4", "v4t3"]),
    # 種違いを平均して学習のブレを消す(順位付けの分散低減。特徴もハイパラも同じ)
    "v4bin2s": dict(v4=True, binary=True, seeds=5,
                    params=dict(learning_rate=0.03, num_leaves=63, min_data_in_leaf=20)),
    "v4bin2s_ens": dict(ens=["v4bin2s", "v4"]),
    # ── V5(2026-07-27): 統一データ(enrich全期間+tsi/騎手率再構築+過去走baba)の上で
    #    「強い馬当て」特徴6本(EXTRA_FEATS)を追加。目的関数は勝った二値のまま ──
    "v5":  dict(v4=True, extra=True, binary=True,
                params=dict(learning_rate=0.03, num_leaves=63, min_data_in_leaf=20)),
    "v5s": dict(v4=True, extra=True, binary=True, seeds=5,
                params=dict(learning_rate=0.03, num_leaves=63, min_data_in_leaf=20)),
    # 統一データの効果を切り分けるための再基準(特徴はV4のまま)
    "v4bin2u": dict(v4=True, binary=True,
                    params=dict(learning_rate=0.03, num_leaves=63, min_data_in_leaf=20)),
}


def _zs(s):
    """レース内zスコア化(異なる目的関数の出力を同じ土俵に載せる)"""
    xs = list(s.values())
    m = sum(xs)/len(xs)
    sd = (sum((x-m)**2 for x in xs)/len(xs))**0.5 or 1.0
    return {n: (v-m)/sd for n, v in s.items()}


def fit_predict(train, fold, name):
    """foldの各レースについて {num: score} を返す。アンサンブルもここで解決する。"""
    spec = VARIANTS[name]
    if spec.get("ens"):
        parts = [fit_predict(train, fold, sub) for sub in spec["ens"]]
        return [{n: sum(_zs(p[i])[n] for p in parts)/len(parts) for n in p0}
                for i, p0 in enumerate(parts[0])]
    k = spec.get("seeds") or 1
    if k > 1:
        outs = []
        for i in range(k):
            sp = dict(spec)
            sp["params"] = dict(spec.get("params") or {},
                                bagging_seed=100+i, feature_fraction_seed=200+i,
                                data_random_seed=300+i)
            m = train_fold(train, sp)
            outs.append([predict(m, r, spec["v4"], bool(spec.get("extra"))) for r in fold])
        return [{n: sum(_zs(o[i])[n] for o in outs)/k for n in outs[0][i]}
                for i in range(len(fold))]
    model = train_fold(train, spec)
    return [predict(model, r, spec["v4"], bool(spec.get("extra"))) for r in fold]


def train_fold(train, spec):
    v4 = spec["v4"]
    ex = bool(spec.get("extra"))
    n_val = max(50, len(train)//10)
    Xt, yt, gt = matrix(train[:-n_val], v4, ex)
    Xv, yv, gv = matrix(train[-n_val:], v4, ex)
    if spec.get("binary"):
        yt = (yt == 3).astype(np.float32)
        yv = (yv == 3).astype(np.float32)
        dtr = lgb.Dataset(Xt, label=yt)
        dva = lgb.Dataset(Xv, label=yv, reference=dtr)
        params = dict(objective="binary", metric="binary_logloss",
                      learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                      feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                      lambda_l2=5.0, verbose=-1)
    else:
        dtr = lgb.Dataset(Xt, label=yt, group=gt)
        dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
        params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                      learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                      feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                      lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    params.update(spec.get("params") or {})
    return lgb.train(params, dtr, num_boost_round=800, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


def predict(model, r, v4, extra=False):
    M = np.array([V2.build_row(r, n, v4, extra) for n in r["ns"]], dtype=np.float32)
    s = model.predict(M)
    return {n: float(v) for n, v in zip(r["ns"], s)}


class Acc:
    """ゲート4項目のアキュムレータ"""
    def __init__(self):
        self.d = defaultdict(float)
        self.rows = []

    def add(self, r, s):
        d = self.d
        order = sorted(s, key=lambda x: -s[x])
        win = r["top3"][0]
        d["n"] += 1
        d["cap"] += sum(1 for t in r["top3"] if t in set(order[:5]))
        d["capn"] += 3
        odds = r["odds"]
        rid = r["rid"]
        day = int(rid[8:10]) if len(rid) >= 10 else 0
        field = len(r["ns"])
        mkt = sorted([h for h in odds if odds[h]], key=lambda h: odds[h])
        for k in (1, 2, 3):
            if len(order) < k:
                continue
            h = order[k-1]
            o = odds.get(h)
            if not o:
                continue
            d[f"r{k}_n"] += 1
            d[f"r{k}_win"] += (h == win)
            d[f"r{k}_imp"] += 0.8/o
        # ゲート2: 1位単勝全買い
        t1 = order[0]
        o1 = odds.get(t1)
        if o1:
            d["tan_s"] += 100
            d["tan_r"] += o1*100 if t1 == win else 0
            pop1 = mkt.index(t1) + 1 if t1 in mkt else 99
            # ゲート3: 乖離帯 (1位が4人気以下 × 10倍+ × tier6-9)
            if pop1 >= 4:
                d["kai_s"] += 100
                d["kai_r"] += o1*100 if t1 == win else 0
                if r.get("tier") and 6 <= r["tier"] <= 9 and o1 >= 10.0:
                    d["top_s"] += 100
                    d["top_r"] += o1*100 if t1 == win else 0
                    d["top_hits"] += (t1 == win)
        # ゲート4: 外枠モデル2位(13-16頭 × 3日目+ × 枠7-8)
        if 13 <= field <= 16 and day >= 3 and len(order) >= 2:
            for k in (1, 2):
                h = order[k-1]
                o = odds.get(h)
                if not o:
                    continue
                w = course.jra_waku(int(h), field)
                if k == 2 and w < 7:
                    continue
                d[f"g4_{k}_n"] += 1
                d[f"g4_{k}_win"] += (h == win)
                d[f"g4_{k}_imp"] += 0.8/o

    def report(self, label):
        d = self.d
        def pct(a, b): return (d[a]/d[b]*100) if d[b] else 0.0
        r1d = pct("r1_win", "r1_n") - pct("r1_imp", "r1_n")
        r2d = pct("r2_win", "r2_n") - pct("r2_imp", "r2_n")
        g4_1 = pct("g4_1_win", "g4_1_n") - pct("g4_1_imp", "g4_1_n")
        g4_2 = pct("g4_2_win", "g4_2_n") - pct("g4_2_imp", "g4_2_n")
        print(f"\n==== {label} : {int(d['n'])}R ====")
        print(f"  捕捉5            {pct('cap','capn'):.1f}%")
        print(f"  ①1位 勝率{pct('r1_win','r1_n'):5.1f}% vs 市場implied{pct('r1_imp','r1_n'):5.1f}%"
              f"  → {r1d:+.1f}pt   (2位 {r2d:+.1f}pt / 3位 "
              f"{pct('r3_win','r3_n')-pct('r3_imp','r3_n'):+.1f}pt)")
        print(f"  ②1位単勝全買いROI {pct('tan_r','tan_s'):.1f}%  ({int(d['tan_s']/100)}点)")
        print(f"  ③乖離帯10倍+×tier6-9 ROI {pct('top_r','top_s'):.1f}%"
              f"  ({int(d['top_s']/100)}点 / 的中{int(d['top_hits'])})"
              f"   ※乖離単勝全体 {pct('kai_r','kai_s'):.1f}% ({int(d['kai_s']/100)}点)")
        print(f"  ④外枠2位の逆転   1位{g4_1:+.1f}pt / 外枠2位{g4_2:+.1f}pt"
              f"  (勝率 {pct('g4_1_win','g4_1_n'):.1f}% vs {pct('g4_2_win','g4_2_n'):.1f}%"
              f" / n={int(d['g4_1_n'])},{int(d['g4_2_n'])})")
        return dict(r1_diff=r1d, tan_roi=pct("tan_r", "tan_s"),
                    top_roi=pct("top_r", "top_s"), top_n=int(d["top_s"]/100),
                    g4_2_diff=g4_2, cap=pct("cap", "capn"),
                    r1_win=pct("r1_win", "r1_n"), n=int(d["n"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3,v4")
    ap.add_argument("--start-fold", default="202511")
    ap.add_argument("--reload", action="store_true")
    ap.add_argument("--dump", default="", help="この variant の予測を wf_preds_<v>.jsonl に出す")
    ap.add_argument("--trunc", type=int, default=0,
                    help="lambdarank_truncation_level (0=既定のまま)")
    a = ap.parse_args()

    ds = load_ds(a.reload)
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= a.start_fold]
    variants = a.variants.split(",")
    print(f"データ {len(ds)}R / fold {folds} / variants {variants}", flush=True)

    accs = {v: Acc() for v in variants}
    dump = []
    for m in folds:
        train = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train) < 400 or not fold:
            continue
        line = [f"[{m}] {len(fold)}R"]
        for v in variants:
            preds = fit_predict(train, fold, v)
            for r, s in zip(fold, preds):
                accs[v].add(r, s)
                if v == a.dump:
                    order = sorted(s, key=lambda x: -s[x])
                    dump.append(dict(rid=r["rid"], month=m, order=order,
                                     scores=[round(s[n], 4) for n in order],
                                     odds=r["odds"], top3=r["top3"],
                                     payout=r.get("payout") or {},
                                     surface=r["surface"], dist=r["dist"],
                                     tier=r["tier"], baba=r["baba"],
                                     venue=r["venue"], field=len(r["ns"])))
            d = accs[v].d
            line.append(f"{v}: 1位勝率{d['r1_win']/max(d['r1_n'],1)*100:.1f}%(累計)")
        print(" | ".join(line), flush=True)

    res = {v: accs[v].report(v.upper()) for v in variants}
    if a.dump and dump:
        with open(f"wf_preds_{a.dump}.jsonl", "w", encoding="utf-8") as f:
            for x in dump:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"\n{len(dump)}R を wf_preds_{a.dump}.jsonl に出力")
    json.dump(res, open("wf_compare_result.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
