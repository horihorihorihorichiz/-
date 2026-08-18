# -*- coding: utf-8 -*-
"""V10 = V3(28特徴+field) + 「MINEとVALIDATEを通過した通過順/ペース特徴」の条件付きロジット。
   CORNER_PROTOCOL.md §4 の機械適用。V7・V9 と同じ二段構成で α（市場への付加情報）を測る。

   usage: python3 corner_v10.py     （corner_eval.py v10 からも呼ばれる）
   既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import json

import numpy as np
from scipy.optimize import minimize

import fit_v2 as V2

RESULT = "corner_result.json"
FOLDS = ["202603", "202604", "202605", "202606", "202607", "202608"]
L2 = 1e-3


def passing_feats():
    res = json.load(open(RESULT, encoding="utf-8"))["features"]
    got = []
    for k, v in res.items():
        if v["mine_pass"] and v["val_pass"]:
            f = k.split("|")[0]
            if f not in got:
                got.append(f)
    return got


def log_softmax(U, M):
    U = np.where(M, U, -1e30)
    mx = U.max(axis=1, keepdims=True)
    return U - (mx + np.log(np.exp(U - mx).sum(axis=1, keepdims=True)))


def fit_cl(X, M, W, l2=L2):
    idx = np.arange(len(W))
    k = X.shape[0]

    def f(th):
        U = np.tensordot(th, X, axes=1)
        lp = log_softmax(U, M)
        nll = -lp[idx, W].sum() + l2 * len(W) * float(th @ th)
        P = np.where(M, np.exp(lp), 0.0)
        g = (P[None] * X).sum(axis=2).sum(axis=1) - X[:, idx, W].sum(axis=1) \
            + 2 * l2 * len(W) * th
        return nll, g

    r = minimize(f, np.zeros(k), jac=True, method="L-BFGS-B",
                 options={"maxiter": 500})
    return r.x


def main():
    feats = passing_feats()
    print(f"V10に載せる通過特徴: {feats}")
    if not feats:
        print("通過特徴ゼロ → 事前登録どおり V10 は作らない")
        old = json.load(open(RESULT, encoding="utf-8"))
        old["v10"] = {"built": False, "reason": "MINE&VAL 両方を通過した特徴がゼロ"}
        json.dump(old, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return

    frozen = set(json.load(open("corner_frozen_ids.json", encoding="utf-8"))["rid"])
    pz = np.load("corner_ds.npz", allow_pickle=False)
    pf = list(pz["feats"])
    F = len(pf)
    A, rids = pz["A"], list(pz["rid"])
    cols = [pf.index(x) for x in feats]
    zmap = {}
    for row in A:
        rid = rids[int(row[F + 4])]
        zmap.setdefault(rid, {})[int(row[F + 5])] = [row[c] for c in cols]

    ds = [r for r in V2.load_dataset("hist", "hist_feat") if r["rid"] in frozen]
    races = []
    for r in ds:
        if r["rid"] not in zmap:
            continue
        zz = zmap[r["rid"]]
        ns = [n for n in r["ns"] if n in r["odds"] and r["odds"][n] > 0 and n in zz]
        if len(ns) < 5 or r["top3"][0] not in ns:
            continue
        v3 = np.array([V2.build_row(r, n, v4=False) for n in ns], dtype=float)
        new = np.array([zz[n] for n in ns], dtype=float)
        o = np.array([r["odds"][n] for n in ns], dtype=float)
        pm = (1.0 / o) / (1.0 / o).sum()
        races.append(dict(rid=r["rid"], month=r["date"][:6], v3=v3, new=new,
                          lpm=np.log(pm), w=ns.index(r["top3"][0])))
    print(f"V10データ: {len(races)}R  V3列={races[0]['v3'].shape[1]}  追加列={len(feats)}")

    K = max(len(r["lpm"]) for r in races)
    kv3 = races[0]["v3"].shape[1]

    def pack(rs, with_new):
        n = len(rs)
        k = kv3 + (len(feats) if with_new else 0)
        X = np.zeros((k, n, K)); M = np.zeros((n, K), bool); W = np.zeros(n, int)
        LPM = np.zeros((n, K))
        for i, r in enumerate(rs):
            m = len(r["lpm"])
            blk = np.hstack([r["v3"], r["new"]]) if with_new else r["v3"]
            X[:, i, :m] = blk.T
            M[i, :m] = True
            LPM[i, :m] = r["lpm"]
            W[i] = r["w"]
        return X, M, W, LPM

    out = {"built": True, "feats": feats, "l2": L2, "folds": {}}
    for m in FOLDS:
        tr = [r for r in races if r["month"] < m]
        te = [r for r in races if r["month"] == m]
        if not te or len(tr) < 200:
            print(f"{m}: スキップ(train={len(tr)} test={len(te)})")
            continue
        line = {"n_train": len(tr), "n_test": len(te)}
        for tag, wn in (("V3", False), ("V10", True)):
            Xtr, Mtr, Wtr, _ = pack(tr, wn)
            th = fit_cl(Xtr, Mtr, Wtr)
            Xte, Mte, Wte, LPM = pack(te, wn)
            L = log_softmax(np.tensordot(th, Xte, axes=1), Mte)
            X2 = np.stack([L, LPM])
            ab = fit_cl(X2, Mte, Wte, l2=0.0)
            idx = np.arange(len(Wte))
            nll_m = float(-log_softmax(L, Mte)[idx, Wte].mean())
            nll_k = float(-log_softmax(LPM, Mte)[idx, Wte].mean())
            nll_b = float(-log_softmax(np.tensordot(ab, X2, axes=1),
                                       Mte)[idx, Wte].mean())
            line[tag] = dict(alpha=float(ab[0]), beta=float(ab[1]),
                             nll_model=nll_m, nll_market=nll_k, nll_blend=nll_b)
        line["alpha_diff"] = line["V10"]["alpha"] - line["V3"]["alpha"]
        out["folds"][m] = line
        print(f"{m}: train={len(tr):5d} test={len(te):4d} "
              f"α(V3)={line['V3']['alpha']:+.4f} α(V10)={line['V10']['alpha']:+.4f} "
              f"差={line['alpha_diff']:+.4f} β(V10)={line['V10']['beta']:+.3f} "
              f"NLL 市場{line['V10']['nll_market']:.4f}→混合{line['V10']['nll_blend']:.4f}")

    a10 = [out["folds"][m]["V10"]["alpha"] for m in FOLDS if m in out["folds"]]
    a3 = [out["folds"][m]["V3"]["alpha"] for m in FOLDS if m in out["folds"]]
    run = best = 0
    for a in a10:
        run = run + 1 if a > 0 else 0
        best = max(best, run)
    out["alpha_v10"] = a10
    out["alpha_v3"] = a3
    out["max_consecutive_positive"] = best
    out["primary_pass"] = bool(best >= 3)
    print(f"\nα(V10) 連続正の最大 = {best} → 一次{'合格' if best >= 3 else '不合格'}")
    old = json.load(open(RESULT, encoding="utf-8"))
    old["v10"] = out
    json.dump(old, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {RESULT}")


if __name__ == "__main__":
    main()
