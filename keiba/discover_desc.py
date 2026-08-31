# -*- coding: utf-8 -*-
"""DISCOVER 補足2: (1)市場log-oddsの2次項まで統制した場合の束のOOS ΔLL、
(2)見つかった共通点を「実測の勝率 vs 市場implied勝率」で人が読める形に落とす記述表。

usage: python3 discover_desc.py
既存ファイルは変更しない。
"""
import json
import numpy as np
from scipy.optimize import minimize

import v99w_fit as V
import discover_feats as DF
import discover_mine as DM
import discover_fit as DFIT
import discover_ctrl as DC

HEAD = ["win|mean3", "top3|rank_mean3", "tier|rank_mean5", "margin|rank_mean3",
        "top3|sameDistMean9", "fin|min5", "move_last|mean5", "spd|rank_mean9"]


def main():
    races = V.load_races()
    A, race_idx, num, keep, ctx, st = DF.load_ds()
    grid = DF.Grid(race_idx, len(races))
    D = DF.derive(A)
    OFF, W, ok, dstat = DM.build_market(races, grid)
    month = np.array([r["month"] for r in races])
    mine = ok & (month <= "202602")
    vali = ok & (month >= "202603") & (month <= "202605")
    conf = ok & (month >= "202606") & (month <= "202608")
    MASK = grid.MASK
    U = np.where(MASK, OFF, 0.0)
    # レース内で中心化した2次項（スケール差を避ける）
    n = MASK.sum(1)
    mu = (U * MASK).sum(1) / np.maximum(n, 1)
    U2 = np.where(MASK, (U - mu[:, None]) ** 2, 0.0)
    m2 = (U2 * MASK).sum(1) / np.maximum(n, 1)
    U2 = np.where(MASK, U2 - m2[:, None], 0.0)

    d = json.load(open("discover_result.json", encoding="utf-8"))
    names = [f["name"] for f in d["feats"]]
    Zs, vals = {}, {}
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        if name in set(names):
            Zs[name] = Z.astype(np.float32)
        if name in HEAD:
            vals[name] = (ja, Z.astype(np.float32))
    Xb = np.stack([Zs[nm] for nm in names], axis=2)
    mi = np.where(mine)[0]
    l2 = d["sel"]["l2_market"]

    # ── (1) 市場 1次+2次 を統制した束のOOS ──
    XC = np.concatenate([U[..., None], U2[..., None]], axis=2)
    wc, llc, sec = DC.newton(XC[mi], MASK[mi], W[mi], w0=np.array([0.85, 0.0]))
    print(f"統制のみ: a1={wc[0]:.4f}(SE {sec[0]:.4f}) a2={wc[1]:.4f}(SE {sec[1]:.4f}) "
          f"LL/R={llc/len(mi):.4f}")
    XA = np.concatenate([XC, Xb], axis=2)

    def obj(w):
        nll, g = DFIT.nll_grad(w, XA[mi], MASK[mi], W[mi],
                               np.zeros((len(mi), V.MAXH)), 0.0)
        gp = np.zeros_like(w)
        gp[2:] = 2 * l2 * w[2:]
        return nll + l2 * (w[2:] ** 2).sum(), g + gp

    r0 = minimize(obj, np.concatenate([wc, np.zeros(len(names))]), jac=True,
                  method="L-BFGS-B", options=dict(maxiter=800, ftol=1e-13))
    wf = r0.x
    print(f"束+統制: a1={wf[0]:.4f} a2={wf[1]:.4f}")
    out = {}
    for nm, sp in (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf)):
        ix = np.where(sp)[0]
        l0 = DFIT.ll_sum(np.where(MASK[ix], XC[ix] @ wc, -1e18), MASK[ix], W[ix])
        l1 = DFIT.ll_sum(np.where(MASK[ix], XA[ix] @ wf, -1e18), MASK[ix], W[ix])
        out[nm] = dict(n=int(sp.sum()), dll=float(l1 - l0),
                       dll_per_race=float((l1 - l0) / sp.sum()))
        print(f"  {nm}: ΔLL={l1-l0:+.2f} nats ({(l1-l0)/sp.sum():+.5f}/R)")

    # ── (2) 記述表: 特徴z の5分位 × 実測勝率 vs 市場implied勝率 ──
    pm = np.where(MASK, np.exp(OFF), np.nan)
    winf = np.zeros_like(pm)
    top3f = np.zeros_like(pm)
    ar = np.arange(len(races))
    for pos in range(3):
        top3f[ar, W[:, pos]] = 1.0
    winf[ar, W[:, 0]] = 1.0
    tables = {}
    for split_name, sp in (("MINE", mine), ("OOS(VAL+CONF)", vali | conf)):
        sel = sp[:, None] & MASK
        for nm in HEAD:
            ja, Z = vals[nm]
            z = Z[sel]
            p = pm[sel]
            wf_ = winf[sel]
            t3 = top3f[sel]
            q = np.quantile(z, [0.2, 0.4, 0.6, 0.8])
            b = np.digitize(z, q)
            rows = []
            for k in range(5):
                m = b == k
                rows.append(dict(bucket=k + 1, n=int(m.sum()),
                                 z=round(float(z[m].mean()), 3),
                                 imp=round(100 * float(p[m].mean()), 2),
                                 act=round(100 * float(wf_[m].mean()), 2),
                                 edge=round(100 * float(wf_[m].mean() - p[m].mean()), 2),
                                 top3=round(100 * float(t3[m].mean()), 2)))
            tables[f"{split_name}|{nm}"] = dict(ja=ja, rows=rows)
            if split_name == "MINE":
                print(f"\n[{nm}] {ja}")
            else:
                print(f"[OOS] {nm}")
            print("   z5分位   n     平均z  市場implied勝率  実測勝率   差(pt)  実測3着内率")
            for r in rows:
                print(f"    {r['bucket']}   {r['n']:6d}  {r['z']:+6.2f}   "
                      f"{r['imp']:8.2f}%   {r['act']:8.2f}%  {r['edge']:+6.2f}   {r['top3']:7.2f}%")

    json.dump(dict(quad_control=dict(a1=float(wc[0]), a2=float(wc[1]),
                                     block_dll=out), tables=tables),
              open("discover_desc_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n→ discover_desc_result.json 保存")


if __name__ == "__main__":
    main()
