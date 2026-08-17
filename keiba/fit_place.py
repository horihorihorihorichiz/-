# -*- coding: utf-8 -*-
"""3着内(複勝圏)特化モデルの学習器＋Plackett-Luce系の確率変換ユーティリティ。

背景: V8検証で唯一プラスに出た材料が「NDCG@3 が +0.0054(V+C 1550R・P(改善>0)=0.95)」＝
      *勝ち馬当て* ではなく *3着内の並び* が僅かに良くなっていた、というもの。
      そこで目的変数そのものを「3着内=1 / 圏外=0」に変えたモデルを作り、
      複勝・ワイド・三連複という「3着内の並びが効く券種」で市場に勝てるかを測る。

このファイルは **既存経路(V3/V4/V5/V8)を一切変更しない**。
wf_compare.train_fold / fit_v2.build_row を呼ぶだけで、学習ラベルと目的関数のみ差し替える。

主な提供物:
  PLACE_VARIANTS         … 学習設定(v3place / v8place / v3placeL / v8placeL)
  train_place_fold()     … 1fold学習
  predict_place()        … 1レース分の {馬番: 3着内スコア}
  harville_place()       … PL強度 w -> 各馬の P(3着内)  (O(n^2)の閉じた式)
  pl_from_place()        … P(3着内) の並び -> それを再現するPL強度(不動点法)
  trio_probs()/wide_probs() … PL強度 -> 三連複/ワイドの理論確率
"""
import itertools

import numpy as np
import lightgbm as lgb

import fit_v2 as V2

# ── 学習設定 ───────────────────────────────────────────────────────────
# ハイパーパラメータは wf_compare.train_fold の既定値をそのまま使う(事後チューニング禁止)。
# 変えたのは「ラベル」と「目的関数」だけ。
#   binary_place : 3着内=1 / 圏外=0 の二値分類 → 出力がそのまま P(3着内)
#   rank_place   : lambdarank だが label_gain=[0,1] で 3着内を全て利得1(=着順を区別しない)
PLACE_VARIANTS = {
    "v3place":  dict(v4=False, v8=None,        mode="binary_place"),
    "v8place":  dict(v4=False, v8="f1,f2,f4",  mode="binary_place"),
    "v3placeL": dict(v4=False, v8=None,        mode="rank_place"),
    "v8placeL": dict(v4=False, v8="f1,f2,f4",  mode="rank_place"),
}

BIN_PARAMS = dict(objective="binary", metric="binary_logloss",
                  learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1)
RANK_PARAMS = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[3],
                   learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                   feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                   lambda_l2=5.0, verbose=-1, label_gain=[0, 1])


def place_matrix(rs, spec):
    """特徴行列と「3着内=1」ラベルを作る。fit_v2.build_row はそのまま使用。"""
    v4, v8 = spec["v4"], spec.get("v8")
    X, y, grp = [], [], []
    for r in rs:
        inm = set(r["top3"])
        for n in r["ns"]:
            X.append(V2.build_row(r, n, v4, False, False, v8))
            y.append(1.0 if n in inm else 0.0)
        grp.append(len(r["ns"]))
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), grp


def train_place_fold(train, spec):
    n_val = max(50, len(train) // 10)
    Xt, yt, gt = place_matrix(train[:-n_val], spec)
    Xv, yv, gv = place_matrix(train[-n_val:], spec)
    if spec["mode"] == "binary_place":
        dtr = lgb.Dataset(Xt, label=yt)
        dva = lgb.Dataset(Xv, label=yv, reference=dtr)
        params = dict(BIN_PARAMS)
    else:
        dtr = lgb.Dataset(Xt, label=yt, group=gt)
        dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
        params = dict(RANK_PARAMS)
    params.update(spec.get("params") or {})
    return lgb.train(params, dtr, num_boost_round=800, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


def predict_place(model, r, spec):
    M = np.array([V2.build_row(r, n, spec["v4"], False, False, spec.get("v8"))
                  for n in r["ns"]], dtype=np.float32)
    return dict(zip(r["ns"], (float(v) for v in model.predict(M))))


# ── Plackett-Luce ユーティリティ ───────────────────────────────────────
def harville_place(w, k=3):
    """PL強度 w(和1) から P(上位k位以内) を返す。k=3 の場合 O(n^2) の閉じた式。

       P(i in top3) = w_i * [ 1 + (T - w_i/(1-w_i)) + (S - rowsum_i - colsum_i) ]
         T    = Σ_j w_j/(1-w_j)
         B_jk = w_j w_k / ((1-w_j)(1-w_j-w_k))   (j≠k)
         S    = ΣΣ B_jk
       (2位確率・3位確率の総和を i を除いて数え上げたもの)
    """
    w = np.asarray(w, dtype=float)
    n = len(w)
    if n <= k:
        return np.ones(n)
    d1 = np.clip(1.0 - w, 1e-9, None)
    if k == 1:
        return w.copy()
    T = float((w / d1).sum())
    p2 = w * (T - w / d1)
    if k == 2:
        return w + p2
    D2 = np.clip(1.0 - w[:, None] - w[None, :], 1e-9, None)
    B = (w[:, None] * w[None, :]) / (d1[:, None] * D2)
    np.fill_diagonal(B, 0.0)
    S = float(B.sum())
    p3 = w * (S - B.sum(axis=1) - B.sum(axis=0))
    return np.clip(w + p2 + p3, 1e-12, 1.0)


def pl_from_place(q, iters=20000, tol=1e-9, ret_iters=False):
    """P(3着内)の並び q (和=3) を再現する PL強度 w を不動点法で求める。
       w <- w * q / harville(w) を正規化しながら繰り返す。

       停止条件は **残差** max|harville(w)-q| < tol（w の変化量ではない）。
       w の変化量で切ると n=4 の強い一極集中ケースで収束前に抜けてしまい、
       残差 1.2e-3 のまま返る事故があったため（2026-08-17 修正）。
       実データ（n>=5）では 20〜300 回で残差 1e-11 に達し早期脱出する。"""
    q = np.clip(np.asarray(q, dtype=float), 1e-6, 1 - 1e-6)
    n = len(q)
    if n <= 3:
        return (np.full(n, 1.0 / n), 0) if ret_iters else np.full(n, 1.0 / n)
    w = q / q.sum()
    it = 0
    for it in range(1, iters + 1):
        h = harville_place(w, 3)
        if np.max(np.abs(h - q)) < tol:
            break
        w = np.clip(w * (q / np.clip(h, 1e-12, None)), 1e-12, None)
        w /= w.sum()
    return (w, it) if ret_iters else w


def _triples(n):
    return np.array(list(itertools.combinations(range(n), 3)), dtype=np.int64)


_TRI_CACHE = {}


def triples(n):
    if n not in _TRI_CACHE:
        _TRI_CACHE[n] = _triples(n)
    return _TRI_CACHE[n]


def trio_probs(w):
    """PL強度 w から全 C(n,3) 組合せの「その3頭が(順不同で)上位3着」確率。
       6通りの順列の PL 確率を足し上げる。返り値: (idx配列(m,3), 確率(m,))"""
    w = np.asarray(w, dtype=float)
    n = len(w)
    if n < 3:
        return np.zeros((0, 3), dtype=np.int64), np.zeros(0)
    tri = triples(n)
    a, b, c = w[tri[:, 0]], w[tri[:, 1]], w[tri[:, 2]]
    prod = a * b * c
    tot = np.zeros(len(tri))
    for x, y in ((a, b), (a, c), (b, a), (b, c), (c, a), (c, b)):
        tot += 1.0 / (np.clip(1.0 - x, 1e-9, None) * np.clip(1.0 - x - y, 1e-9, None))
    return tri, prod * tot


def wide_probs(tri, ptri, n):
    """三連複確率から「2頭とも3着内」= ワイド確率へ集約。返り値: dict[(i,j)] = p"""
    P = np.zeros((n, n))
    np.add.at(P, (tri[:, 0], tri[:, 1]), ptri)
    np.add.at(P, (tri[:, 0], tri[:, 2]), ptri)
    np.add.at(P, (tri[:, 1], tri[:, 2]), ptri)
    return P


def market_place_probs(odds):
    """確定単勝オッズ配列 -> 控除率補正済み勝率(和1) -> Harville で P(3着内)。
       ※事前の複勝オッズは台帳に無いため、これが市場側の代理指標になる(限界は報告書に明記)。"""
    o = np.asarray(odds, dtype=float)
    p = 1.0 / np.clip(o, 1e-6, None)
    p = p / p.sum()
    return p, harville_place(p, 3)


def _selftest():
    rng = np.random.default_rng(0)
    for n in (4, 5, 6, 8):
        w = rng.random(n) ** 2 + 0.01
        w /= w.sum()
        # 総当りで P(上位3) を厳密計算
        brute = np.zeros(n)
        for perm in itertools.permutations(range(n), 3):
            p = 1.0
            rem = 1.0
            for h in perm:
                p *= w[h] / rem
                rem -= w[h]
            for h in perm:
                brute[h] += p
        fast = harville_place(w, 3)
        assert np.allclose(brute, fast, atol=1e-9), (n, brute, fast)
        assert abs(fast.sum() - 3.0) < 1e-8, fast.sum()
        # 三連複の総和=1・ワイド行列の総和=3
        tri, pt = trio_probs(w)
        assert abs(pt.sum() - 1.0) < 1e-8, pt.sum()
        W = wide_probs(tri, pt, n)
        assert abs(W.sum() - 3.0) < 1e-8, W.sum()
        # 逆変換: harville(pl_from_place(q)) == q
        q = harville_place(w, 3)
        w2 = pl_from_place(q)
        assert np.allclose(harville_place(w2, 3), q, atol=1e-6), n
    print("fit_place selftest OK")


if __name__ == "__main__":
    _selftest()
