# -*- coding: utf-8 -*-
"""ファミリー6: 交互作用・非線形特徴量実験。
   既存15特徴量のレース内z値から
     - ペア積 (105通り)
     - 二乗 z^2 (15)
     - ヒンジ max(z,0) (15)
   を候補生成し、numpy版PL(ハーネスと同一の損失/最適化)で高速スクリーニング
   (screen-train=〜6/7, val=6/13〜6/28, testは一切触らない)。
   greedy前進選択で上位セットを決め、最後に公式 H.run_experiment で判定。
   usage: python3 exp_interactions.py
"""
import itertools
import json
import math
import sys
import time

import numpy as np

import exp_harness as H
import fit_v2 as V2

BASE = list(V2.FEATS)          # 15基本特徴量
VAL_DAYS = {"20260613", "20260614", "20260620", "20260621", "20260627", "20260628"}
WPOS = (3, 1, 0.5)


# ---------- 候補生成: z値から作り、レース内で再z標準化 ----------

def add_z_derived(ds):
    """r['X']のz値から交互作用・非線形候補を全レースに追加。候補名リストを返す"""
    cands = []
    pairs = list(itertools.combinations(BASE, 2))
    for a, b in pairs:
        cands.append(("ix__%s__%s" % (a, b), ("prod", a, b)))
    for a in BASE:
        cands.append(("sq__%s" % a, ("sq", a)))
        cands.append(("hg__%s" % a, ("hinge", a)))
    for r in ds:
        X = r["X"]
        ns = r["ns"]
        for name, (kind, *args) in cands:
            if kind == "prod":
                a, b = args
                vals = {n: X[a][n] * X[b][n] for n in ns}
            elif kind == "sq":
                a = args[0]
                vals = {n: X[a][n] ** 2 for n in ns}
            else:
                a = args[0]
                vals = {n: max(X[a][n], 0.0) for n in ns}
            X[name] = V2.z_in_race(vals)
    return [c[0] for c in cands]


# ---------- numpy版PL(ハーネス_pl_fitと同じ損失・最適化) ----------

def build_tensors(sub, feats):
    R = len(sub)
    N = max(len(r["ns"]) for r in sub)
    F = len(feats)
    X = np.zeros((R, N, F))
    mask = np.zeros((R, N), dtype=bool)
    win = np.zeros((R, 3), dtype=np.int64)
    for i, r in enumerate(sub):
        ns = r["ns"]
        idx = {n: j for j, n in enumerate(ns)}
        mask[i, :len(ns)] = True
        for f_i, f in enumerate(feats):
            col = r["X"][f]
            for n in ns:
                X[i, idx[n], f_i] = col[n]
        for p in range(3):
            win[i, p] = idx[r["top3"][p]]
    return X, mask, win


def fit_np(X, mask, win, cols, l2=0.05, iters=250, lr=0.3):
    Xs = X[:, :, cols]
    R, N, F = Xs.shape
    w = np.zeros(F)
    m = np.zeros(F)
    ar = np.arange(R)
    n_obs = R * sum(WPOS)
    for it in range(iters):
        alive = mask.copy()
        g = np.zeros(F)
        s_all = Xs @ w
        for pos, pw in enumerate(WPOS):
            s = np.where(alive, s_all, -1e30)
            mx = s.max(axis=1, keepdims=True)
            e = np.exp(s - mx)
            e[~alive] = 0.0
            Z = e.sum(axis=1, keepdims=True)
            p = e / Z
            wi = win[:, pos]
            exp_x = np.einsum("rn,rnf->rf", p, Xs)
            g += pw * (exp_x - Xs[ar, wi]).sum(axis=0)
            alive[ar, wi] = False
        g = g / n_obs + 2 * l2 * w
        m = 0.9 * m + g
        w = w - lr * m
    return w


def cap5_np(X, mask, win, cols, w):
    s = X[:, :, cols] @ w
    s = np.where(mask, s, -np.inf)
    top5 = np.argsort(-s, axis=1)[:, :5]
    hit = 0
    for p in range(3):
        hit += (top5 == win[:, p:p + 1]).any(axis=1).sum()
    return hit / (3 * len(s)) * 100


# ---------- メイン ----------

def main():
    t0 = time.time()
    ds = H.load_base()
    print("races=%d" % len(ds), flush=True)
    cands = add_z_derived(ds)
    print("candidates=%d  (%.0fs)" % (len(cands), time.time() - t0), flush=True)

    train_all = [r for r in ds if r["date"] not in H.TEST_DAYS]
    scr = [r for r in train_all if r["date"] not in VAL_DAYS]
    val = [r for r in train_all if r["date"] in VAL_DAYS]
    print("screen-train=%d val=%d" % (len(scr), len(val)), flush=True)

    feats_all = BASE + cands
    fidx = {f: i for i, f in enumerate(feats_all)}
    Xtr, mtr, wtr = build_tensors(scr, feats_all)
    Xva, mva, wva = build_tensors(val, feats_all)

    base_cols = [fidx[f] for f in BASE]
    w0 = fit_np(Xtr, mtr, wtr, base_cols)
    base_val = cap5_np(Xva, mva, wva, base_cols, w0)
    print("base val capture5 = %.2f%%  (%.0fs)" % (base_val, time.time() - t0), flush=True)

    # ラウンド1: 単独追加の一括スクリーニング
    scores = []
    for k, c in enumerate(cands):
        cols = base_cols + [fidx[c]]
        w = fit_np(Xtr, mtr, wtr, cols, iters=150)
        cv = cap5_np(Xva, mva, wva, cols, w)
        scores.append((cv, c))
        if (k + 1) % 20 == 0:
            print("  screened %d/%d (%.0fs)" % (k + 1, len(cands), time.time() - t0), flush=True)
    scores.sort(reverse=True)
    print("--- top15 single-add (val capture5) ---", flush=True)
    for cv, c in scores[:15]:
        print("  %+.2f  %s (%.2f%%)" % (cv - base_val, c, cv), flush=True)

    # greedy前進選択(上位12候補プールから最大6個)
    pool = [c for _, c in scores[:12]]
    sel = []
    best = base_val
    while len(sel) < 6:
        cand_best, cand_val = None, best
        for c in pool:
            if c in sel:
                continue
            cols = base_cols + [fidx[x] for x in sel + [c]]
            w = fit_np(Xtr, mtr, wtr, cols)
            cv = cap5_np(Xva, mva, wva, cols, w)
            if cv > cand_val + 1e-9:
                cand_best, cand_val = c, cv
        if cand_best is None:
            break
        sel.append(cand_best)
        best = cand_val
        print("greedy +%s -> val %.2f%%" % (cand_best, best), flush=True)
    print("selected: %s  (val %.2f%% vs base %.2f%%)  (%.0fs)" % (sel, best, base_val, time.time() - t0), flush=True)

    # ---- 公式判定(run_experiment) 最大3本 ----
    results = []
    if sel:
        results.append(H.run_experiment(ds, extra=sel, label="ix_greedy_l2=0.05"))
        results.append(H.run_experiment(ds, extra=sel, l2=0.1, label="ix_greedy_l2=0.10"))
        if len(sel) > 3:
            results.append(H.run_experiment(ds, extra=sel[:3], label="ix_top3_l2=0.05"))
        else:
            top1 = scores[0][1]
            if top1 not in sel:
                results.append(H.run_experiment(ds, extra=[top1], label="ix_single_best"))
    else:
        results.append(H.run_experiment(ds, extra=[scores[0][1]], label="ix_single_best"))
    print("=== summary ===", flush=True)
    for r in results:
        print(json.dumps({"label": r["label"], "extra": [f for f in r["feats"] if f not in BASE],
                          "train_cap5": round(r["train"]["capture5"], 2),
                          "test_cap5": round(r["test"]["capture5"], 2),
                          "gate": r["gate"]}, ensure_ascii=False), flush=True)
    print("total %.0fs" % (time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
