# -*- coding: utf-8 -*-
"""V9 = V3(28特徴+field) + 「MINEとVALIDATEを通過した過去走特徴」の条件付きロジット。
   PASTRUN_PROTOCOL.md §4 の機械適用。V7 と同じ二段構成で α（市場への付加情報）を測る。

   usage: python3 pastrun_v9.py     （pastrun_eval.py v9 からも呼ばれる）
   既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import json

import numpy as np
from scipy.optimize import minimize

import fit_v2 as V2

RESULT = "pastrun_result.json"
FOLDS = ["202603", "202604", "202605", "202606", "202607", "202608"]
L2 = 1e-3          # 一段目の L2（レース内z特徴なのでスケールは揃っている）


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
    """条件付きロジット。X=(k,n,K) M=(n,K) W=勝者index"""
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
    print(f"V9に載せる通過特徴: {feats}")
    if not feats:
        print("通過特徴ゼロ → 事前登録どおり V9 は作らない")
        return

    frozen = set(json.load(open("pastrun_frozen_ids.json", encoding="utf-8"))["rid"])
    pz = np.load("pastrun_ds.npz", allow_pickle=False)
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
    print(f"V9データ: {len(races)}R  V3列={races[0]['v3'].shape[1]}  追加列={len(feats)}")

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

    out = {"feats": feats, "l2": L2, "folds": {}}
    for m in FOLDS:
        tr = [r for r in races if r["month"] < m]
        te = [r for r in races if r["month"] == m]
        if not te or len(tr) < 200:
            continue
        line = {"n_train": len(tr), "n_test": len(te)}
        for tag, wn in (("V3", False), ("V9", True)):
            Xtr, Mtr, Wtr, _ = pack(tr, wn)
            th = fit_cl(Xtr, Mtr, Wtr)
            Xte, Mte, Wte, LPM = pack(te, wn)
            L = log_softmax(np.tensordot(th, Xte, axes=1), Mte)      # log p_model
            X2 = np.stack([L, LPM])
            ab = fit_cl(X2, Mte, Wte, l2=0.0)
            idx = np.arange(len(Wte))
            nll_m = float(-log_softmax(L, Mte)[idx, Wte].mean())
            nll_k = float(-log_softmax(LPM, Mte)[idx, Wte].mean())
            nll_b = float(-log_softmax(np.tensordot(ab, X2, axes=1),
                                       Mte)[idx, Wte].mean())
            line[tag] = dict(alpha=float(ab[0]), beta=float(ab[1]),
                             nll_model=nll_m, nll_market=nll_k, nll_blend=nll_b)
        line["alpha_diff"] = line["V9"]["alpha"] - line["V3"]["alpha"]
        out["folds"][m] = line
        print(f"{m}: train={len(tr):5d} test={len(te):4d} "
              f"α(V3)={line['V3']['alpha']:+.4f} α(V9)={line['V9']['alpha']:+.4f} "
              f"差={line['alpha_diff']:+.4f} "
              f"β(V9)={line['V9']['beta']:+.3f} "
              f"NLL 市場{line['V9']['nll_market']:.4f}→混合{line['V9']['nll_blend']:.4f}")

    a9 = [out["folds"][m]["V9"]["alpha"] for m in FOLDS if m in out["folds"]]
    a3 = [out["folds"][m]["V3"]["alpha"] for m in FOLDS if m in out["folds"]]
    run = best = 0
    for a in a9:
        run = run + 1 if a > 0 else 0
        best = max(best, run)
    out["alpha_v9"] = a9
    out["alpha_v3"] = a3
    out["max_consecutive_positive"] = best
    out["primary_pass"] = bool(best >= 3)
    print(f"\nα(V9) 連続正の最大 = {best} → 一次{'合格' if best >= 3 else '不合格'}")
    old = json.load(open(RESULT, encoding="utf-8"))
    old["v9"] = out
    json.dump(old, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {RESULT}")


if __name__ == "__main__":
    main()
