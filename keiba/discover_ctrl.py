# -*- coding: utf-8 -*-
"""DISCOVER 補足検査（事前登録の一次基準の**後**に実施した頑健性検査。基準の変更ではない）。

一次基準では市場log-oddsの係数を1に固定している。単勝オッズ逆数の正規化確率には
控除率と人気-穴バイアス(FLB)による既知の歪みがあるため、「オッズ水準の言い換え」に過ぎない
特徴でも係数1固定なら有意になりうる。そこで**市場log-oddsの係数aを自由推定**したうえで
同じ検定をやり直し、何本が生き残るか・束にしたときのOOS ΔLLがどれだけ残るかを測る。

usage: python3 discover_ctrl.py
既存ファイルは変更しない。
"""
import json, pickle
import numpy as np

import v99w_fit as V
import discover_feats as DF
import discover_mine as DM
import discover_fit as DFIT

MAXH = V.MAXH


def ll_g_h(w, X, M, W, off=None):
    """PL(top3) の対数尤度・勾配・ヘシアン（解析）。X=(R,H,K)"""
    R, H, K = X.shape
    s = X @ w
    if off is not None:
        s = s + off
    masks = M.copy()
    ar = np.arange(R)
    ll = 0.0
    g = np.zeros(K)
    Hs = np.zeros((K, K))
    for pos in range(3):
        sm = np.where(masks, s, -1e18)
        mx = sm.max(1)
        e = np.exp(sm - mx[:, None]) * masks
        Z = e.sum(1)
        p = e / Z[:, None]
        win = W[:, pos]
        ll += (s[ar, win] - (mx + np.log(Z))).sum()
        Ex = np.einsum("rh,rhk->rk", p, X)
        g += (X[ar, win] - Ex).sum(0)
        Exx = np.einsum("rh,rhj,rhk->rjk", p, X, X)
        Hs += -(Exx - np.einsum("rj,rk->rjk", Ex, Ex)).sum(0)
        masks[ar, win] = False
    return ll, g, Hs


def newton(X, M, W, w0=None, iters=30):
    K = X.shape[2]
    w = np.zeros(K) if w0 is None else w0.copy()
    for _ in range(iters):
        ll, g, Hs = ll_g_h(w, X, M, W)
        try:
            step = np.linalg.solve(Hs, g)
        except np.linalg.LinAlgError:
            break
        step = np.clip(step, -1.0, 1.0)
        w = w - step
        if np.abs(step).max() < 1e-9:
            break
    ll, g, Hs = ll_g_h(w, X, M, W)
    cov = np.linalg.inv(-Hs)
    return w, ll, np.sqrt(np.diag(cov))


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
    U = np.where(MASK, OFF, 0.0)          # 市場 log p（自由係数の列）

    res = json.load(open("discover_mine_result.json", encoding="utf-8"))
    zc = res["z_crit"]

    Mm, Wm, Um = MASK[mine], W[mine], U[mine]
    # a のみ（帰無モデル）
    Xa = Um[:, :, None]
    wa, lla, sea = newton(Xa, Mm, Wm)
    print(f"市場log-odds 単独: a={wa[0]:.4f} (SE {sea[0]:.4f}) "
          f"LL/R={lla/Mm.shape[0]:.4f}  ※a=1固定なら"
          f"{DFIT.ll_sum(np.where(Mm, Um, -1e18), Mm, Wm)/Mm.shape[0]:.4f}")

    rows = []
    n = 0
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        cov = float(np.isfinite(v[np.isin(race_idx, np.where(mine)[0])]).mean())
        Zm = Z[mine]
        if cov < DM.COV_MIN or Zm[Mm].std() < 1e-9:
            continue
        n += 1
        X2 = np.stack([Um, Zm], axis=2)
        w2, ll2, se2 = newton(X2, Mm, Wm, w0=np.array([wa[0], 0.0]))
        rows.append(dict(name=name, ja=ja, a=round(float(w2[0]), 4),
                         beta=round(float(w2[1]), 5),
                         z=round(float(w2[1] / se2[1]), 3),
                         dll=round(float(ll2 - lla), 2)))
        if n % 200 == 0:
            print(f"  ... {n}本", flush=True)

    zs = np.array([r["z"] for r in rows])
    npass = int((np.abs(zs) >= zc).sum())
    print(f"\n[補足] 市場係数aを自由推定したときの MINE 通過本数 = {npass} / {n}"
          f"  (係数1固定なら {res['n_pass']})")
    top = sorted(rows, key=lambda r: -abs(r["z"]))[:25]
    print("── 自由係数版 |z|上位25 ──")
    for r in top:
        print(f"  {r['name']:26s} z={r['z']:+7.2f} ΔLL={r['dll']:+7.1f} a={r['a']:.3f}  {r['ja']}")

    # 束（段階3で残した140本）を自由係数版で OOS 評価
    d = json.load(open("discover_result.json", encoding="utf-8"))
    names = [f["name"] for f in d["feats"]]
    Zs = {}
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        if name in set(names):
            Zs[name] = Z.astype(np.float32)
    Xb = np.stack([Zs[nm] for nm in names], axis=2)
    mi = np.where(mine)[0]
    XA = np.concatenate([U[..., None], Xb], axis=2)
    l2 = d["sel"]["l2_market"]
    # a は無正則化・特徴のみL2（w0=0, a に罰則をかけないため列を分けて最適化）
    from scipy.optimize import minimize

    def obj(w):
        nll, g = DFIT.nll_grad(w, XA[mi], MASK[mi], W[mi], np.zeros_like(U[mi]), 0.0)
        pen = l2 * (w[1:] ** 2).sum()
        gp = np.zeros_like(w)
        gp[1:] = 2 * l2 * w[1:]
        return nll + pen, g + gp

    r0 = minimize(obj, np.concatenate([[wa[0]], np.zeros(len(names))]),
                  jac=True, method="L-BFGS-B",
                  options=dict(maxiter=800, ftol=1e-13, gtol=1e-10))
    wfull = r0.x
    print(f"\n束(140本)＋自由市場係数: a={wfull[0]:.4f}")
    out = {}
    for nm, sp in (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf)):
        ix = np.where(sp)[0]
        # 帰無: a のみ（MINEで推定した a0 を固定）
        l0 = DFIT.ll_sum(np.where(MASK[ix], wa[0] * U[ix], -1e18), MASK[ix], W[ix])
        l1 = DFIT.ll_sum(np.where(MASK[ix], XA[ix] @ wfull, -1e18), MASK[ix], W[ix])
        out[nm] = dict(n=int(sp.sum()), dll=float(l1 - l0),
                       dll_per_race=float((l1 - l0) / sp.sum()))
        print(f"  {nm}: ΔLL={l1-l0:+.2f} nats ({(l1-l0)/sp.sum():+.5f}/R, {int(sp.sum())}R)")

    json.dump(dict(a_market=float(wa[0]), z_crit=zc, n_tested=n,
                   n_pass_free_a=npass, n_pass_fixed_a=res["n_pass"],
                   block_dll=out, rows=rows),
              open("discover_ctrl_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ discover_ctrl_result.json 保存")


if __name__ == "__main__":
    main()
