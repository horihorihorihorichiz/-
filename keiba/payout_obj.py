# -*- coding: utf-8 -*-
"""「回収率そのものを目的関数にする」実験 — PAYOUT_OBJ_PROTOCOL.md の事前登録どおり。

  従来の全実験は P(1着) の最大化だった。本実験は目的関数を払戻(=回収率)側に置き換える。
  特徴は全モデル共通で V3 の28特徴（fit_v2.build_row(v4=False)）。**変えるのは目的関数だけ**。

  usage:
    python3 payout_obj.py wf      # 月次WF（8モデル×24fold）→ payout_obj_preds.jsonl
    python3 payout_obj.py eval    # 3分割成績・α・EV買い・見送り基準 → payout_obj_result.json

  ★既存経路は一切変更しない（fit_v2 / wf_compare / calc は読むだけ）。
"""
import argparse
import json
import os
import pickle
import sys
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import fit_v2 as V2

CACHE = "wf_ds_cache_v8.pkl"
PREDS = "payout_obj_preds.jsonl"
RESULT = "payout_obj_result.json"
ODDSDIR = "hist_odds"
START_FOLD = "202409"

SPLITS = [("MINE", "000000", "202602"),
          ("VALIDATE", "202603", "202605"),
          ("CONFIRM", "202606", "202608")]

# 事前登録: M2 のサンプル重み上限（1万円払戻相当）
W_CAP = 100.0
M5_SEED = 20260818

BASE = dict(learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
            feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
            lambda_l2=5.0, verbose=-1)

# ── モデル定義（PROTOCOL §2） ──────────────────────────────────────────
#  kind: rank / binary / reg
#  target: win_payout / place_payout （reg のみ）
#  logt : 目的変数を sign*log1p|v| に変換するか
MODELS = {
    "M1":        dict(kind="rank"),                                  # 現行V3(ベース)
    "M2":        dict(kind="binary", weight="win_payout"),           # 払戻重み
    "M2c":       dict(kind="binary"),                                # 対照(重み無し)
    "M3-l2":     dict(kind="reg", target="win_payout", loss="l2"),
    "M3-huber":  dict(kind="reg", target="win_payout", loss="huber"),
    "M3-log":    dict(kind="reg", target="win_payout", loss="l2", logt=True),
    "M4-l2":     dict(kind="reg", target="place_payout", loss="l2"),
    "M4-huber":  dict(kind="reg", target="place_payout", loss="huber"),
    "M4-log":    dict(kind="reg", target="place_payout", loss="l2", logt=True),
}
LEDGER_M1 = "wf_preds_v3ext2.jsonl"   # M1(現行V3)は既存WF台帳をそのまま使う(PROTOCOL §2-2)
LGB_MODELS = [k for k in MODELS if k != "M1"]   # M1=台帳 / M5=線形探索 は学習しない
ALL_MODELS = ["M1"] + LGB_MODELS + ["M5"]
# EV回帰(予測値そのものが損益)のモデル = 見送り基準(d)の対象
EV_REG = [k for k in LGB_MODELS if MODELS[k]["kind"] == "reg"]


def split_of(m):
    for name, lo, hi in SPLITS:
        if lo <= m <= hi:
            return name
    return None


# ══════════════════════════════════════════════════════════════════════
#  払戻の取り出し
# ══════════════════════════════════════════════════════════════════════
def win_pay(r, n):
    """その馬の単勝払戻(100円あたり)。当たっていなければ0。"""
    return float((r.get("payout") or {}).get("単勝", {}).get(str(n), 0) or 0)


def place_pay(r, n):
    """その馬の複勝払戻。5-7頭立ては2着まで＝払戻が存在するかで的中を定義する。"""
    return float((r.get("payout") or {}).get("複勝", {}).get(str(n), 0) or 0)


# ══════════════════════════════════════════════════════════════════════
#  行列作成
# ══════════════════════════════════════════════════════════════════════
_FC = {}


def feats_of(r):
    """V3の28特徴行列。同じレースを何度も作り直さないようキャッシュする（結果は不変）。"""
    M = _FC.get(r["rid"])
    if M is None:
        M = np.array([V2.build_row(r, n, v4=False) for n in r["ns"]], dtype=np.float32)
        _FC[r["rid"]] = M
    return M


def matrix(rs, spec):
    X, y, w, grp = [], [], [], []
    kind = spec["kind"]
    for r in rs:
        win = r["top3"][0]
        M = feats_of(r)
        X.append(M)
        for i, n in enumerate(r["ns"]):
            if kind == "rank":
                lab = 0
                for pos, t in enumerate(r["top3"]):
                    if t == n:
                        lab = 3 - pos
                y.append(lab)
                w.append(1.0)
            elif kind == "binary":
                y.append(1.0 if n == win else 0.0)
                if spec.get("weight") == "win_payout" and n == win:
                    w.append(min(max(win_pay(r, n), 100.0) / 100.0, W_CAP))
                else:
                    w.append(1.0)
            else:                                   # reg
                pay = win_pay(r, n) if spec["target"] == "win_payout" else place_pay(r, n)
                v = pay - 100.0
                if spec.get("logt"):
                    v = np.sign(v) * np.log1p(abs(v))
                y.append(v)
                w.append(1.0)
        grp.append(len(r["ns"]))
    return (np.vstack(X).astype(np.float32), np.array(y, dtype=np.float32),
            np.array(w, dtype=np.float32), grp)


def train_fold(train, spec):
    n_val = max(50, len(train) // 10)
    Xt, yt, wt, gt = matrix(train[:-n_val], spec)
    Xv, yv, wv, gv = matrix(train[-n_val:], spec)
    kind = spec["kind"]
    if kind == "rank":
        dtr = lgb.Dataset(Xt, label=yt, group=gt)
        dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
        p = dict(BASE, objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                 label_gain=[0, 1, 3, 7])
    elif kind == "binary":
        # 学習は払戻重み付き。ただし**早期停止の判定は重み無し**(PROTOCOL §2-1)。
        # 重み付きlogloss はごく一部の高配当行が支配し、1〜2回で停止して学習が起きない。
        dtr = lgb.Dataset(Xt, label=yt, weight=wt)
        dva = lgb.Dataset(Xv, label=yv, reference=dtr)
        p = dict(BASE, objective="binary", metric="binary_logloss")
    else:
        # 早期停止の指標は常に l1(絶対誤差)。l2 は外れ値(高配当)が支配して
        # 2回で停止するため、学習の有無を判定する指標として使えない(PROTOCOL §2-1)。
        dtr = lgb.Dataset(Xt, label=yt)
        dva = lgb.Dataset(Xv, label=yv, reference=dtr)
        if spec["loss"] == "huber":
            p = dict(BASE, objective="huber", alpha=100.0, metric="l1")
        else:
            p = dict(BASE, objective="regression", metric="l1")
    return lgb.train(p, dtr, num_boost_round=800, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


# ══════════════════════════════════════════════════════════════════════
#  M5: 28特徴の線形結合を「上位k頭の単勝flat回収率」で直接探索（MINE期のみ）
# ══════════════════════════════════════════════════════════════════════
def m5_search(ds, k=1, n_rand=4000, verbose=True):
    """MINE期(date[:6] <= 202602)のレースのみで探索。VALIDATE/CONFIRM は触らない。"""
    rs = [r for r in ds if r["date"][:6] <= "202602"]
    Ms, pays = [], []
    for r in rs:
        M = feats_of(r).astype(np.float64)
        # レース内で列標準化（V3のz特徴は既にz済みだが field 等の生値も揃える）
        mu = M.mean(axis=0)
        sd = M.std(axis=0)
        sd[sd == 0] = 1.0
        Ms.append((M - mu) / sd)
        pays.append(np.array([win_pay(r, n) for n in r["ns"]], dtype=np.float64))
    d = Ms[0].shape[1]
    n_r = len(rs)
    K = max(len(p) for p in pays)
    # (n_r, K, d) にパディングして一括評価（無効枠は -inf でマスク）
    X3 = np.zeros((n_r, K, d))
    P2 = np.zeros((n_r, K))
    MASK = np.zeros((n_r, K), dtype=bool)
    for i, (M, P) in enumerate(zip(Ms, pays)):
        kk = len(P)
        X3[i, :kk] = M
        P2[i, :kk] = P
        MASK[i, :kk] = True
    NEG = np.where(MASK, 0.0, -np.inf)
    rowidx = np.arange(n_r)

    def roi(w):
        S = X3 @ w + NEG
        if k == 1:
            idx = np.argmax(S, axis=1)
            tot = P2[rowidx, idx].sum()
        else:
            idx = np.argsort(-S, axis=1)[:, :k]
            tot = np.take_along_axis(P2, idx, axis=1).sum()
        return tot / (100.0 * k * n_r)

    rng = np.random.default_rng(M5_SEED)
    best_w, best = None, -1.0
    for _ in range(n_rand):
        w = rng.standard_normal(d)
        w /= np.linalg.norm(w) or 1.0
        v = roi(w)
        if v > best:
            best, best_w = v, w
    if verbose:
        print(f"[M5] ランダム探索 {n_rand}本: 最良 MINE単勝ROI={best*100:.1f}%", flush=True)
    w = best_w.copy()
    for rnd, step in enumerate((0.5, 0.25, 0.1)):
        improved = True
        while improved:
            improved = False
            for j in range(d):
                for dlt in (step, -step):
                    w2 = w.copy()
                    w2[j] += dlt
                    v = roi(w2)
                    if v > best + 1e-9:
                        best, w, improved = v, w2, True
        if verbose:
            print(f"[M5] 座標降下 step={step}: MINE単勝ROI={best*100:.1f}%", flush=True)
    return w, best


def m5_scores(r, w):
    M = feats_of(r)
    mu = M.mean(axis=0)
    sd = M.std(axis=0)
    sd[sd == 0] = 1.0
    s = ((M - mu) / sd) @ w
    return {n: float(v) for n, v in zip(r["ns"], s)}


# ══════════════════════════════════════════════════════════════════════
#  WF 実行
# ══════════════════════════════════════════════════════════════════════
def run_wf(out=PREDS, only=None):
    if not os.path.exists(CACHE):
        print(f"{CACHE} が無い。wf_compare.py --v8 で dataset を作ること", file=sys.stderr)
        sys.exit(1)
    with open(CACHE, "rb") as f:
        ds = pickle.load(f)
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= START_FOLD]
    print(f"データ {len(ds)}R / fold {len(folds)}本 {folds[0]}〜{folds[-1]}", flush=True)

    names = only or LGB_MODELS
    w5, m5_mine_roi = m5_search(ds)

    rows = []
    for m in folds:
        train = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train) < 400 or not fold:
            continue
        recs = {}
        for r in fold:
            recs[r["rid"]] = dict(
                rid=r["rid"], month=m, split=split_of(m), ns=list(r["ns"]),
                odds={str(k): v for k, v in (r["odds"] or {}).items()},
                top3=list(r["top3"]), payout=r.get("payout") or {},
                field=len(r["ns"]), tier=r.get("tier"), preds={})
        for name in names:
            model = train_fold(train, MODELS[name])
            for r in fold:
                s = model.predict(feats_of(r))
                recs[r["rid"]]["preds"][name] = [round(float(v), 5) for v in s]
        for r in fold:
            s = m5_scores(r, w5)
            recs[r["rid"]]["preds"]["M5"] = [round(s[n], 5) for n in r["ns"]]
        print(f"[{m}] {len(fold)}R 完了", flush=True)
        rows.extend(recs[r["rid"]] for r in fold)
    with open(out, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    json.dump(dict(w=[round(float(v), 5) for v in w5], mine_roi=m5_mine_roi,
                   feats=V2.feat_names(v4=False)),
              open("payout_obj_m5.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(rows)}R を {out} に出力 / M5重みを payout_obj_m5.json に保存")


# ══════════════════════════════════════════════════════════════════════
#  評価
# ══════════════════════════════════════════════════════════════════════
def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def _logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def fit_logit(X, y):
    from scipy.optimize import minimize

    def f(th):
        p = _sig(X @ th)
        nll = -(y * np.log(np.clip(p, 1e-12, None))
                + (1 - y) * np.log(np.clip(1 - p, 1e-12, None))).sum()
        return nll, X.T @ (p - y)
    return minimize(f, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B").x


def cluster_se(X, y, g, th):
    p = _sig(X @ th)
    W = p * (1 - p)
    A = X.T @ (X * W[:, None])
    Ai = np.linalg.pinv(A)
    u = (y - p)[:, None] * X
    gi = np.unique(g, return_inverse=True)[1]
    S = np.zeros((gi.max() + 1, X.shape[1]))
    np.add.at(S, gi, u)
    V = Ai @ (S.T @ S) @ Ai
    return np.sqrt(np.clip(np.diag(V), 0, None))


def load_preds(path=PREDS):
    races = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        d["ns"] = [int(x) for x in d["ns"]]
        d["top3"] = [int(x) for x in d["top3"]]
        d["odds"] = {int(k): float(v) for k, v in d["odds"].items()}
        races.append(d)
    return races


def merge_m1(races, path=LEDGER_M1):
    """M1(現行V3)のスコアを既存WF台帳から取り込む(PROTOCOL §2-2)。
       台帳に無い rid は評価から落とし、全モデルを同一レース集合に揃える。"""
    led = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        led[d["rid"]] = {int(n): float(s) for n, s in zip(d["order"], d["scores"])}
    out, drop = [], 0
    for r in races:
        m = led.get(r["rid"])
        if not m or any(n not in m for n in r["ns"]):
            drop += 1
            continue
        r["preds"]["M1"] = [m[n] for n in r["ns"]]
        out.append(r)
    if drop:
        print(f"※台帳に無い/欠損の {drop}R を除外（全モデル同一集合に揃えるため）")
    return out


def load_odds(rid):
    p = os.path.join(ODDSDIR, f"{rid}.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def zs(v):
    v = np.asarray(v, dtype=float)
    sd = v.std() or 1.0
    return (v - v.mean()) / sd


def prep(races):
    """各レースに人気・zスコア・派生量を付ける。"""
    for r in races:
        od = r["odds"]
        avail = [(od.get(n, 9999.0), n) for n in r["ns"]]
        rank = {n: i + 1 for i, (_, n) in enumerate(sorted(avail, key=lambda t: (t[0], t[1])))}
        r["ninki"] = rank
        r["z"] = {}
        for name, s in r["preds"].items():
            z = zs(s)
            r["z"][name] = {n: float(z[i]) for i, n in enumerate(r["ns"])}
        r["raw_odds"] = load_odds(r["rid"])
    return races


def top1(r, name):
    z = r["z"][name]
    return max(r["ns"], key=lambda n: (z[n], -n))


def top2gap(r, name):
    z = r["z"][name]
    v = sorted((z[n] for n in r["ns"]), reverse=True)
    return v[0] - v[1] if len(v) > 1 else 0.0


def wpay(r, n):
    return float((r.get("payout") or {}).get("単勝", {}).get(str(n), 0) or 0)


def ppay(r, n):
    return float((r.get("payout") or {}).get("複勝", {}).get(str(n), 0) or 0)


def flat_stats(races, name):
    """モデル1位の単勝/複勝 flat 成績。"""
    d = dict(n=0, win_hit=0, win_ret=0.0, pl_hit=0, pl_ret=0.0,
             ninki=0.0, win_pays=[], pl_pays=[])
    for r in races:
        h = top1(r, name)
        d["n"] += 1
        wp, pp = wpay(r, h), ppay(r, h)
        if wp > 0:
            d["win_hit"] += 1
            d["win_pays"].append(wp)
        if pp > 0:
            d["pl_hit"] += 1
            d["pl_pays"].append(pp)
        d["win_ret"] += wp
        d["pl_ret"] += pp
        d["ninki"] += r["ninki"][h]
    n = d["n"] or 1
    return dict(n=d["n"],
                win_hit=round(d["win_hit"] / n * 100, 2),
                win_roi=round(d["win_ret"] / (100.0 * n) * 100, 2),
                win_avg_pay=round(float(np.mean(d["win_pays"])), 1) if d["win_pays"] else 0.0,
                pl_hit=round(d["pl_hit"] / n * 100, 2),
                pl_roi=round(d["pl_ret"] / (100.0 * n) * 100, 2),
                pl_avg_pay=round(float(np.mean(d["pl_pays"])), 1) if d["pl_pays"] else 0.0,
                avg_ninki=round(d["ninki"] / n, 2))


# ── 温度較正（MINE期の勝者尤度MLE）＋ q_model ──────────────────────────
def fit_tau(races, name):
    from scipy.optimize import minimize_scalar

    Z, W = [], []
    for r in races:
        z = np.array([r["z"][name][n] for n in r["ns"]])
        Z.append(z)
        W.append(r["ns"].index(r["top3"][0]))

    def nll(t):
        tot = 0.0
        for z, w in zip(Z, W):
            e = t * z
            e = e - e.max()
            tot += -(e[w] - np.log(np.exp(e).sum()))
        return tot
    res = minimize_scalar(nll, bounds=(0.05, 20.0), method="bounded")
    return float(res.x)


def qmodel(r, name, tau):
    z = np.array([r["z"][name][n] for n in r["ns"]])
    e = np.exp(tau * (z - z.max()))
    p = e / e.sum()
    return {n: float(v) for n, v in zip(r["ns"], p)}


def qmarket(r):
    inv = np.array([1.0 / max(r["odds"].get(n, 9999.0), 1e-6) for n in r["ns"]])
    p = inv / inv.sum()
    return {n: float(v) for n, v in zip(r["ns"], p)}


def harville3(pw, k=3):
    """3着内確率（Harville）。既存 fit_place.harville_place をそのまま使う（実装を増やさない）。
       ※5〜7頭立ての複勝は2着まで＝呼び出し側で k=2 を渡す。"""
    import fit_place as FP
    return FP.harville_place(np.asarray(pw, dtype=float), k)


def place_k(r):
    return 2 if len(r["ns"]) < 8 else 3


def alpha_split(races, name, tau, mode="win"):
    """y ~ α·logit(q_model) + β·logit(q_market) + c （クラスタ頑健SE・分割内プール推定）"""
    Xs, ys, gs = [], [], []
    for gi, r in enumerate(races):
        qm = qmodel(r, name, tau)
        qk = qmarket(r)
        if mode == "place":
            kk = place_k(r)
            pm = harville3(np.array([qm[n] for n in r["ns"]]), kk)
            pk = harville3(np.array([qk[n] for n in r["ns"]]), kk)
            qm = {n: pm[i] for i, n in enumerate(r["ns"])}
            qk = {n: pk[i] for i, n in enumerate(r["ns"])}
            hit = set(r["top3"][:place_k(r)])
        else:
            hit = {r["top3"][0]}
        for n in r["ns"]:
            Xs.append([_logit(qm[n]), _logit(qk[n]), 1.0])
            ys.append(1.0 if n in hit else 0.0)
            gs.append(gi)
    X = np.array(Xs)
    y = np.array(ys)
    g = np.array(gs)
    th = fit_logit(X, y)
    se = cluster_se(X, y, g, th)
    return dict(alpha=round(float(th[0]), 4), se=round(float(se[0]), 4),
                z=round(float(th[0] / max(se[0], 1e-9)), 2),
                beta=round(float(th[1]), 4), n=int(len(races)))


def ev_bets(races, name, tau, thr=1.2):
    """EV = q_model × 実オッズ ≥ thr の馬を単勝/複勝それぞれ100円ずつ。精算は実払戻。"""
    out = {}
    for kind in ("win", "place"):
        n = hit = 0
        ret = 0.0
        for r in races:
            ro = r["raw_odds"]
            if not ro:
                continue
            qm = qmodel(r, name, tau)
            if kind == "place":
                pm = harville3(np.array([qm[h] for h in r["ns"]]), place_k(r))
                q = {h: pm[i] for i, h in enumerate(r["ns"])}
                book = ro.get("fuku") or {}
            else:
                q = qm
                book = ro.get("tan") or {}
            for h in r["ns"]:
                o = book.get(str(h))
                if not o:
                    continue
                if q[h] * float(o) >= thr:
                    n += 1
                    pay = wpay(r, h) if kind == "win" else ppay(r, h)
                    if pay > 0:
                        hit += 1
                    ret += pay
        out[kind] = dict(n=n, hit=round(hit / n * 100, 2) if n else 0.0,
                         roi=round(ret / (100.0 * n) * 100, 2) if n else 0.0)
    return out


def ev_bets_direct(races, name, thr=20.0):
    """M3/M4 の予測値そのもの（=予想損益/100円）で買う。pred>=thr の馬を単勝100円。"""
    n = hit = 0
    ret = 0.0
    for r in races:
        s = r["preds"][name]
        for i, h in enumerate(r["ns"]):
            if s[i] >= thr:
                n += 1
                pay = wpay(r, h)
                if pay > 0:
                    hit += 1
                ret += pay
    return dict(n=n, hit=round(hit / n * 100, 2) if n else 0.0,
                roi=round(ret / (100.0 * n) * 100, 2) if n else 0.0)


# ── 見送り基準（PROTOCOL §4） ────────────────────────────────────────
def skip_filters(mine, name):
    """MINE期の分布から閾値を作る。戻り: {ラベル: レース判定関数}"""
    f = {}
    z1 = np.array([r["z"][name][top1(r, name)] for r in mine])
    gp = np.array([top2gap(r, name) for r in mine])
    for X in (10, 20, 30, 50):
        t = float(np.quantile(z1, 1 - X / 100.0))
        f[f"a_top{X}%"] = (lambda r, t=t, nm=name: r["z"][nm][top1(r, nm)] >= t)
        t2 = float(np.quantile(gp, 1 - X / 100.0))
        f[f"b_gap{X}%"] = (lambda r, t=t2, nm=name: top2gap(r, nm) >= t2)
    bands = [("<2", 0.0, 2.0), ("2-4", 2.0, 4.0), ("4-7", 4.0, 7.0),
             ("7-15", 7.0, 15.0), ("15-50", 15.0, 50.0), (">=50", 50.0, 1e9)]
    for lb, lo, hi in bands:
        f[f"c_odds{lb}"] = (lambda r, lo=lo, hi=hi, nm=name:
                            lo <= r["odds"].get(top1(r, nm), 9999.0) < hi)
    if name in EV_REG:
        for t in (0, 20, 50, 100):
            f[f"d_pred>={t}"] = (lambda r, t=t, nm=name: max(r["preds"][nm]) >= t)
    return f


def filtered_stats(races, name, fn):
    sel = [r for r in races if fn(r)]
    st = flat_stats(sel, name) if sel else dict(n=0)
    st["skip_rate"] = round((1 - len(sel) / max(len(races), 1)) * 100, 1)
    return st


def run_eval(path=PREDS):
    races = prep(merge_m1(load_preds(path)))
    by = defaultdict(list)
    for r in races:
        by[r["split"]].append(r)
    mine = by["MINE"]
    print(f"読み込み {len(races)}R: " +
          " / ".join(f"{k} {len(v)}R" for k, v in by.items()))

    res = dict(n_races={k: len(v) for k, v in by.items()}, tau={},
               flat={}, alpha={}, ev={}, ev_direct={}, filters={}, trials=0)
    names = [n for n in ALL_MODELS if n in races[0]["preds"]]
    trials = 0
    for name in names:
        tau = fit_tau(mine, name)
        res["tau"][name] = round(tau, 3)
        res["flat"][name] = {}
        res["alpha"][name] = {}
        res["ev"][name] = {}
        for sp in ("MINE", "VALIDATE", "CONFIRM"):
            rs = by[sp]
            res["flat"][name][sp] = flat_stats(rs, name)
            res["alpha"][name][sp] = {m: alpha_split(rs, name, tau, m)
                                      for m in ("win", "place")}
            res["ev"][name][sp] = ev_bets(rs, name, tau)
        trials += 2                                   # 単勝flat + 複勝flat
        if name in EV_REG:
            res["ev_direct"][name] = {sp: {f"pred>={t}": ev_bets_direct(by[sp], name, t)
                                           for t in (0, 20, 50, 100)}
                                      for sp in ("MINE", "VALIDATE", "CONFIRM")}
        fl = skip_filters(mine, name)
        res["filters"][name] = {}
        for lb, fn in fl.items():
            res["filters"][name][lb] = {sp: filtered_stats(by[sp], name, fn)
                                        for sp in ("VALIDATE", "CONFIRM")}
            trials += 1
        print(f"[{name}] tau={tau:.2f} 完了", flush=True)
    res["trials"] = trials
    json.dump(res, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{RESULT} に保存（総試行数 {trials}）")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["wf", "eval"])
    ap.add_argument("--only", default=None, help="学習するモデルをカンマ区切りで限定")
    a = ap.parse_args()
    if a.cmd == "wf":
        run_wf(only=a.only.split(",") if a.only else None)
    else:
        run_eval()


if __name__ == "__main__":
    main()
