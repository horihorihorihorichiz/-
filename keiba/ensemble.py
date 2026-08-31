# -*- coding: utf-8 -*-
"""特徴部分集合アンサンブル（5専門家合議）実験 — ENSEMBLE_PROTOCOL.md の事前登録どおり。

  同じ全データ・同じ学習手順（V3と完全同一のハイパラ）で、**使う特徴だけ**を変えた
  5つの専門家モデルを作り、その1位馬の一致度 k で買うことに価値があるかを測る。

  usage:
    python3 ensemble.py wf            # 月次WF（5専門家 × 目的2系統 × 24fold）→ ensemble_preds.jsonl
    python3 ensemble.py eval          # 合議・相関・α・k別成績 → ensemble_result.json

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

PREDS = "ensemble_preds.jsonl"
RESULT = "ensemble_result.json"
CACHE_V8 = "wf_ds_cache_v8.pkl"
BASELINE = "wf_preds_v3ext2.jsonl"      # 汎用V3のWF台帳（同一fold・同一レース集合）

SPLITS = [("MINE", "000000", "202602"),
          ("VALIDATE", "202603", "202605"),
          ("CONFIRM", "202606", "202608")]


def split_of(m):
    for name, lo, hi in SPLITS:
        if lo <= m <= hi:
            return name
    return None


# ── 事前登録の特徴割当（ENSEMBLE_PROTOCOL.md §2 と同一・重複ゼロ） ──────────
EXPERTS = {
    "E1": ["idx_mean3", "idx_last", "idx_best", "idx_trend", "agari_best",
           "agari_mean3_rel", "agari_dist_match", "agari_close_q"],
    "E2": ["fin_frac", "fin_w", "fin_best2", "class_fin", "bigfield_fin",
           "classup_lastgood", "layoff_lastfin", "n_runs", "days_log", "kinryo", "wchg"],
    "E3": ["corner_frac", "corner_gain", "ep", "ep_rel", "press", "front_n", "pace_adv",
           "waku", "waku_rel", "umaban_rel", "waku_x_dirt", "field", "field_chg",
           "f2_wide_mean3", "f2_wide_max", "f2_kick_mean3", "f2_kick_max", "f2_last",
           "tb_n", "tb_waku", "tb_waku_surf", "tb_front", "tb_front_surf", "tb_upset",
           "tb_x_waku", "tb_x_ep"],
    "E4": ["j_top3", "t_top3"],
    "E5": ["csi", "cond_perf", "db_best", "exact_dist_place", "surf_switch", "wet_apt",
           "dist_chg", "wet_fin", "wet_x_baba", "baba_today", "today_vg", "is_dirt",
           "cp_n", "cp_waku", "cp_front", "cp_fav", "cp_x_waku", "cp_x_ep",
           "cs_runs", "cs_top3", "cs_fin"],
}
TARGETS = ("win", "top3")


# ── 特徴値の取り出し（dataset の4つの置き場から名前で引く） ──────────────
def value(r, n, k):
    x = r["X"].get(k)
    if x is not None:
        return float(x[n])
    rx = r["raw_extra"].get(n) or {}
    if k in rx:
        v = rx[k]
        return float(v) if v is not None else 0.0
    v8r = (r.get("v8_raw") or {}).get(n) or {}
    if k in v8r:
        v = v8r[k]
        return float(v) if v is not None else 0.0
    if k in r["ctx"]:
        return float(r["ctx"][k])
    v8c = r.get("v8_ctx") or {}
    if k in v8c:
        v = v8c[k]
        return float(v) if v is not None else 0.0
    raise KeyError(f"未知の特徴名: {k}")


def matrix(rs, feats, target):
    X, y, grp = [], [], []
    for r in rs:
        lab = {n: 0 for n in r["ns"]}
        if target == "top3":
            for pos, t in enumerate(r["top3"]):
                lab[t] = 3 - pos
        else:                       # win: 1着だけ利得3（label_gain はV3と同一のまま）
            lab[r["top3"][0]] = 3
        for n in r["ns"]:
            X.append([value(r, n, k) for k in feats])
            y.append(lab[n])
        grp.append(len(r["ns"]))
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), grp


def train_fold(train, feats, target):
    """wf_compare.train_fold の lambdarank 枝と完全同一のハイパラ・同一の検証分割。"""
    n_val = max(50, len(train) // 10)
    Xt, yt, gt = matrix(train[:-n_val], feats, target)
    Xv, yv, gv = matrix(train[-n_val:], feats, target)
    dtr = lgb.Dataset(Xt, label=yt, group=gt)
    dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=0.02, num_leaves=31, min_data_in_leaf=30,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    return lgb.train(params, dtr, num_boost_round=800, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(60, verbose=False)])


def predict(model, r, feats):
    M = np.array([[value(r, n, k) for k in feats] for n in r["ns"]], dtype=np.float32)
    s = model.predict(M)
    return {n: float(v) for n, v in zip(r["ns"], s)}


def run_wf(start_fold="202409", out=PREDS):
    if not os.path.exists(CACHE_V8):
        print(f"{CACHE_V8} が無い。wf_compare.py --v8 で dataset を作ること", file=sys.stderr)
        sys.exit(1)
    with open(CACHE_V8, "rb") as f:
        ds = pickle.load(f)
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= start_fold]
    print(f"データ {len(ds)}R / fold {len(folds)}本 {folds[0]}〜{folds[-1]}", flush=True)
    rows = []
    for m in folds:
        train = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train) < 400 or not fold:
            continue
        recs = {r["rid"]: dict(rid=r["rid"], month=m, split=split_of(m),
                               ns=list(r["ns"]), odds=r["odds"], top3=r["top3"],
                               payout=r.get("payout") or {}, field=len(r["ns"]),
                               tier=r.get("tier"), surface=r.get("surface"),
                               dist=r.get("dist"), venue=r.get("venue"),
                               baba=r.get("baba"), preds={})
                for r in fold}
        for tgt in TARGETS:
            for e, feats in EXPERTS.items():
                model = train_fold(train, feats, tgt)
                for r in fold:
                    s = predict(model, r, feats)
                    recs[r["rid"]]["preds"][f"{e}_{tgt}"] = [round(s[n], 5) for n in r["ns"]]
        print(f"[{m}] {len(fold)}R 完了", flush=True)
        rows.extend(recs[r["rid"]] for r in fold)
    with open(out, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"{len(rows)}R を {out} に出力")


# ══════════════════════════════════════════════════════════════════════
#  評価
# ══════════════════════════════════════════════════════════════════════
def _logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


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
    B = np.zeros_like(A)
    for gi in np.unique(g):
        s = u[g == gi].sum(axis=0)
        B += np.outer(s, s)
    V = Ai @ B @ Ai
    return np.sqrt(np.clip(np.diag(V), 0, None))


def harville_place(pw, k=3):
    """勝率ベクトル -> 3着内確率（Harville近似・モンテカルロ不要の再帰版は重いので
       place系と同じ fit_place の実装を使う）"""
    import fit_place as FP
    return FP.harville_place(np.asarray(pw, dtype=float), k)


def rankdata(a):
    a = np.asarray(a, dtype=float)
    order = np.argsort(a)
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1)
    # 同点は平均順位
    _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, ranks)
        ranks = (sums / cnt)[inv]
    return ranks


def load_preds(path=PREDS):
    races = []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        d["odds"] = {int(k): float(v) for k, v in d["odds"].items()}
        d["ns"] = [int(x) for x in d["ns"]]
        d["top3"] = [int(x) for x in d["top3"]]
        races.append(d)
    return races


def consensus(d, tgt):
    """5専門家の1位馬 -> (合議馬, k)。最頻が並んだら合議なし(k=1)。"""
    picks = []
    for e in EXPERTS:
        s = d["preds"][f"{e}_{tgt}"]
        picks.append(d["ns"][int(np.argmax(s))])
    cnt = defaultdict(int)
    for p in picks:
        cnt[p] += 1
    mx = max(cnt.values())
    top = [h for h, c in cnt.items() if c == mx]
    if len(top) > 1:
        return None, 1
    return top[0], mx


def fuku_pay(d, h):
    return int((d["payout"].get("複勝") or {}).get(str(h), 0))


def flat_stats(rows):
    """rows = [(horse, race)] -> 単勝/複勝flat"""
    n = len(rows)
    if not n:
        return dict(n=0)
    win = sum(1 for h, d in rows if h == d["top3"][0])
    top3 = sum(1 for h, d in rows if h in d["top3"])
    tan = sum(d["odds"].get(h, 0) * 100 if h == d["top3"][0] else 0 for h, d in rows)
    fuk = sum(fuku_pay(d, h) for h, d in rows)
    return dict(n=n, win_rate=round(win / n * 100, 1), top3_rate=round(top3 / n * 100, 1),
                tan_roi=round(tan / (n * 100) * 100, 1), fuku_roi=round(fuk / (n * 100) * 100, 1),
                wins=win, t3=top3)


def market_fav(d):
    ok = [h for h in d["ns"] if d["odds"].get(h)]
    return min(ok, key=lambda h: d["odds"][h]) if ok else None


def load_baseline():
    """汎用V3の1位（同一fold・同一レース）"""
    top = {}
    if not os.path.exists(BASELINE):
        return top
    for line in open(BASELINE, encoding="utf-8"):
        d = json.loads(line)
        if d.get("order"):
            top[d["rid"]] = int(d["order"][0])
    return top


def corr_matrix(races, tgt):
    """レース内zスコアの Spearman 順位相関を全レース平均した 5x5 行列"""
    keys = list(EXPERTS)
    acc = np.zeros((5, 5))
    cnt = 0
    for d in races:
        R = [rankdata(d["preds"][f"{e}_{tgt}"]) for e in keys]
        R = np.array(R)
        if R.shape[1] < 3:
            continue
        C = np.corrcoef(R)
        acc += np.nan_to_num(C)
        cnt += 1
    return (acc / max(cnt, 1)).round(3).tolist(), cnt


def alpha_fold(races, tgt, mode="win"):
    """fold(月)ごとに当該foldのレースで推定:
       logit P(y) = c + β·logit q_market + Σ_k α_k·1[k人合議の馬] (+ α_v3·1[V3 1位])"""
    base = load_baseline()
    out = {}
    months = sorted({d["month"] for d in races})
    for m in months:
        rs = [d for d in races if d["month"] == m]
        Xs, ys, gs = [], [], []
        for gi, d in enumerate(rs):
            ns = [h for h in d["ns"] if d["odds"].get(h)]
            if len(ns) < 5:
                continue
            pw = np.array([1.0 / d["odds"][h] for h in ns])
            pw = pw / pw.sum()
            if mode == "win":
                q = pw
                y = np.array([1.0 if h == d["top3"][0] else 0.0 for h in ns])
            else:
                q = harville_place(pw, 3)
                y = np.array([1.0 if h in d["top3"] else 0.0 for h in ns])
            cons, k = consensus(d, tgt)
            v3 = base.get(d["rid"])
            cols = [_logit(q)]
            for kk in (2, 3, 4, 5):
                cols.append(np.array([1.0 if (h == cons and k == kk) else 0.0 for h in ns]))
            cols.append(np.array([1.0 if h == v3 else 0.0 for h in ns]))
            cols.append(np.ones(len(ns)))
            Xs.append(np.stack(cols, axis=1))
            ys.append(y)
            gs.append(np.full(len(ns), gi))
        if not Xs:
            continue
        X = np.concatenate(Xs)
        y = np.concatenate(ys)
        g = np.concatenate(gs)
        th = fit_logit(X, y)
        se = cluster_se(X, y, g, th)
        out[m] = dict(split=split_of(m), n_races=len(rs),
                      beta_mkt=round(float(th[0]), 4),
                      a2=round(float(th[1]), 4), a3=round(float(th[2]), 4),
                      a4=round(float(th[3]), 4), a5=round(float(th[4]), 4),
                      a_v3=round(float(th[5]), 4),
                      z2=round(float(th[1] / max(se[1], 1e-9)), 2),
                      z3=round(float(th[2] / max(se[2], 1e-9)), 2),
                      z4=round(float(th[3] / max(se[3], 1e-9)), 2),
                      z5=round(float(th[4] / max(se[4], 1e-9)), 2),
                      z_v3=round(float(th[5] / max(se[5], 1e-9)), 2))
    return out


def alpha_k4(races, tgt, mode="win"):
    """k>=4 をひとまとめにしたダミーでの α（一次基準はこれで判定）"""
    base = load_baseline()
    out = {}
    for m in sorted({d["month"] for d in races}):
        rs = [d for d in races if d["month"] == m]
        Xs, ys, gs = [], [], []
        for gi, d in enumerate(rs):
            ns = [h for h in d["ns"] if d["odds"].get(h)]
            if len(ns) < 5:
                continue
            pw = np.array([1.0 / d["odds"][h] for h in ns])
            pw = pw / pw.sum()
            if mode == "win":
                q = pw
                y = np.array([1.0 if h == d["top3"][0] else 0.0 for h in ns])
            else:
                q = harville_place(pw, 3)
                y = np.array([1.0 if h in d["top3"] else 0.0 for h in ns])
            cons, k = consensus(d, tgt)
            cols = [_logit(q),
                    np.array([1.0 if (h == cons and k >= 4) else 0.0 for h in ns]),
                    np.ones(len(ns))]
            Xs.append(np.stack(cols, axis=1))
            ys.append(y)
            gs.append(np.full(len(ns), gi))
        X = np.concatenate(Xs)
        y = np.concatenate(ys)
        g = np.concatenate(gs)
        th = fit_logit(X, y)
        se = cluster_se(X, y, g, th)
        out[m] = dict(split=split_of(m), alpha=round(float(th[1]), 4),
                      z=round(float(th[1] / max(se[1], 1e-9)), 2))
    return out


def run_eval(path=PREDS, out=RESULT):
    races = load_preds(path)
    base = load_baseline()
    res = dict(n_races=len(races), splits={}, corr={}, k_dist={}, k_table={},
               bench={}, alpha={}, alpha_k4={}, skip_rule={})
    for sp, _, _ in SPLITS:
        res["splits"][sp] = sum(1 for d in races if d["split"] == sp)

    for tgt in TARGETS:
        C, cnt = corr_matrix(races, tgt)
        res["corr"][tgt] = dict(labels=list(EXPERTS), matrix=C, n_races=cnt)

        # k分布・k別成績
        kd = defaultdict(lambda: defaultdict(int))
        rows = defaultdict(lambda: defaultdict(list))
        for d in races:
            cons, k = consensus(d, tgt)
            kd[d["split"]][k] += 1
            kd["ALL"][k] += 1
            if cons is not None and k >= 2 and d["odds"].get(cons):
                rows[d["split"]][k].append((cons, d))
                rows["ALL"][k].append((cons, d))
                if k >= 4:
                    rows[d["split"]]["4+"].append((cons, d))
                    rows["ALL"]["4+"].append((cons, d))
        res["k_dist"][tgt] = {s: dict(v) for s, v in kd.items()}
        res["k_table"][tgt] = {s: {str(k): flat_stats(v) for k, v in kk.items()}
                               for s, kk in rows.items()}

    # ベンチマーク: 汎用V3 1位 / 市場1番人気
    for name, pick in (("v3_top1", lambda d: base.get(d["rid"])),
                       ("market_fav", market_fav)):
        acc = defaultdict(list)
        for d in races:
            h = pick(d)
            if h and d["odds"].get(h):
                acc[d["split"]].append((h, d))
                acc["ALL"].append((h, d))
        res["bench"][name] = {s: flat_stats(v) for s, v in acc.items()}

    # 「k<=2 は見送る」ルールの価値（V3 1位を買う前提で、合議が割れたレースを外す）
    for tgt in TARGETS:
        acc = defaultdict(lambda: defaultdict(list))
        for d in races:
            _, k = consensus(d, tgt)
            h = base.get(d["rid"])
            if not h or not d["odds"].get(h):
                continue
            key = "k<=2" if k <= 2 else "k>=3"
            acc[d["split"]][key].append((h, d))
            acc["ALL"][key].append((h, d))
        res["skip_rule"][tgt] = {s: {k: flat_stats(v) for k, v in kk.items()}
                                 for s, kk in acc.items()}

    # α
    for tgt in TARGETS:
        for mode in ("win", "place"):
            res["alpha"][f"{tgt}_{mode}"] = alpha_fold(races, tgt, mode)
            res["alpha_k4"][f"{tgt}_{mode}"] = alpha_k4(races, tgt, mode)

    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res["corr"], ensure_ascii=False, indent=1))
    print(json.dumps(res["k_table"], ensure_ascii=False, indent=1))
    print(json.dumps(res["bench"], ensure_ascii=False, indent=1))
    print(json.dumps(res["alpha_k4"], ensure_ascii=False, indent=1))
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["wf", "eval"])
    ap.add_argument("--start-fold", default="202409")
    ap.add_argument("--preds", default=PREDS)
    ap.add_argument("--out", default=RESULT)
    a = ap.parse_args()
    if a.cmd == "wf":
        run_wf(a.start_fold, a.preds)
    else:
        run_eval(a.preds, a.out)


if __name__ == "__main__":
    main()
