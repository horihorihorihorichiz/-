# -*- coding: utf-8 -*-
"""DISCOVER 段階3-4（DISCOVER_PROTOCOL.md §5-§6 の実装）。

段階3: MINE通過候補を多重共線性除去(|ρ|>=0.8)→L2つき条件付きロジットで束ねる。
       (a) 市場log-oddsオフセット版（一次基準用） (b) B-sd16オフセット版（買い目評価用・既存に"追加"）
段階4: VALIDATE/CONFIRM を1回だけ測る（真のOOS）。
usage: python3 discover_fit.py
既存ファイルは変更しない。
"""
import json, pickle
import numpy as np
from scipy.optimize import minimize

import v99w_fit as V
import v99w2_fit as V2
import discover_feats as DF
import discover_mine as DM

MAXH = V.MAXH
LGRID = [3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1]
CORR_THR = 0.8


# ───────── 多特徴 PL(top3) with offset + L2 ─────────
def nll_grad(w, X, M, W, off, l2):
    R, _, K = X.shape
    s = X @ w + off
    masks = M.copy()
    ar = np.arange(R)
    nll = 0.0
    grad = np.zeros(K)
    for pos in range(3):
        sm = np.where(masks, s, -1e18)
        mx = sm.max(1)
        e = np.exp(sm - mx[:, None]) * masks
        Z = e.sum(1)
        p = e / Z[:, None]
        win = W[:, pos]
        nll += -(s[ar, win] - (mx + np.log(Z))).sum()
        Ex = np.einsum("rh,rhk->rk", p, X)
        grad += -(X[ar, win] - Ex).sum(0)
        masks[ar, win] = False
    n = 3 * R
    return nll / n + l2 * (w * w).sum(), grad / n + 2 * l2 * w


def fit_w(X, M, W, off, l2):
    K = X.shape[2]
    r = minimize(lambda w: nll_grad(w, X, M, W, off, l2), np.zeros(K),
                 jac=True, method="L-BFGS-B",
                 options=dict(maxiter=800, ftol=1e-13, gtol=1e-10))
    return r.x


def ll_sum(scores, M, W):
    return V.pl_ll_per_race(np.where(M, scores, -1e18), M, W).sum()


# ───────── 買い目（ワイド追加版・既存 bet_metrics は変更せず自前で持つ） ─────────
def bets(races, idxs, score_fn):
    m = {k: [0, 0, 0] for k in ("fuku1", "fuku2", "wide", "trio")}
    for i in idxs:
        r = races[i]
        sc = score_fn(i)
        order = sorted(range(len(r["nums"])),
                       key=lambda j: (-sc[j], r["nums"][j]))
        top = [r["nums"][j] for j in order]
        po = r["payout"]
        fuku, wide, trio = po.get("複勝", {}), po.get("ワイド", {}), po.get("三連複", {})
        m["fuku1"][1] += 100
        v = fuku.get(str(top[0]))
        if v:
            m["fuku1"][0] += 1
            m["fuku1"][2] += v
        m["fuku2"][1] += 200
        for n in top[:2]:
            v = fuku.get(str(n))
            if v:
                m["fuku2"][0] += 1
                m["fuku2"][2] += v
        m["wide"][1] += 100
        v = wide.get("-".join(str(x) for x in sorted(top[:2])))
        if v:
            m["wide"][0] += 1
            m["wide"][2] += v
        m["trio"][1] += 100
        v = trio.get("-".join(str(x) for x in sorted(top[:3])))
        if v:
            m["trio"][0] += 1
            m["trio"][2] += v
    out = {}
    for k, (hit, stake, ret) in m.items():
        nb = stake // 100
        out[k] = dict(hits=hit, bets=nb, hitrate=round(100.0 * hit / max(nb, 1), 2),
                      roi=round(100.0 * ret / max(stake, 1), 2))
    return out


def fmt(b):
    return (f"複1 {b['fuku1']['hitrate']:5.2f}%/{b['fuku1']['roi']:6.2f}%  "
            f"複2 {b['fuku2']['hitrate']:5.2f}%/{b['fuku2']['roi']:6.2f}%  "
            f"ワイド {b['wide']['hitrate']:5.2f}%/{b['wide']['roi']:6.2f}%  "
            f"三連複 {b['trio']['hitrate']:4.2f}%/{b['trio']['roi']:6.2f}%")


def main():
    races = V.load_races()
    cstat = V2.attach_corner(races)
    print("corner結合:", cstat)
    A, race_idx, num, keep, ctx, st = DF.load_ds()
    grid = DF.Grid(race_idx, len(races))
    D = DF.derive(A)
    OFF, W, ok, dstat = DM.build_market(races, grid)
    month = np.array([r["month"] for r in races])
    mine = ok & (month <= "202602")
    vali = ok & (month >= "202603") & (month <= "202605")
    conf = ok & (month >= "202606") & (month <= "202608")
    MASK = grid.MASK

    res = json.load(open("discover_mine_result.json", encoding="utf-8"))
    zc = res["z_crit"]
    passed = {r["name"]: r for r in res["all"] if abs(r["z"]) >= zc}
    order = sorted(passed.values(), key=lambda r: -abs(r["z"]))
    print(f"MINE通過 {len(order)}本 (z_crit={zc:.3f})")

    # 通過候補の Z を再生成
    Zs = {}
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        if name in passed:
            Zs[name] = Z.astype(np.float32)
    assert len(Zs) == len(passed)

    # ── 多重共線性除去（MINEの馬行での相関） ──
    Mm = MASK[mine]
    rows = np.column_stack([Zs[r["name"]][mine][Mm] for r in order])
    keepn = []
    kept_cols = []
    for j, r in enumerate(order):
        x = rows[:, j]
        if any(abs(np.corrcoef(x, rows[:, k])[0, 1]) >= CORR_THR for k in kept_cols):
            continue
        kept_cols.append(j)
        keepn.append(r)
    print(f"多重共線性除去後: {len(keepn)}本")
    for r in keepn:
        print(f"  {r['name']:26s} z={r['z']:+7.2f} ΔLL={r['dll']:+7.1f}  {r['ja']}")

    names = [r["name"] for r in keepn]
    K = len(names)
    Xall = np.stack([Zs[n] for n in names], axis=2)     # (R, MAXH, K)

    # ══ (a) 市場オフセット版: λ選択 → 確定学習 → 3期のΔLL ══
    mi = np.where(mine)[0]
    ncut = int(len(mi) * 0.8)
    tr, va = mi[:ncut], mi[ncut:]
    best = (None, 1e18)
    print("\n[a] 市場オフセット版 λ選択 (MINE内部80/20 val NLL/R):")
    for l2 in LGRID:
        w = fit_w(Xall[tr], MASK[tr], W[tr], OFF[tr], l2)
        nv = -V.pl_ll_per_race(np.where(MASK[va], Xall[va] @ w + OFF[va], -1e18),
                               MASK[va], W[va]).mean()
        print(f"  λ={l2}: {nv:.4f}")
        if nv < best[1]:
            best = (l2, nv)
    l2a = best[0]
    base_va = -V.pl_ll_per_race(np.where(MASK[va], OFF[va], -1e18),
                                MASK[va], W[va]).mean()
    print(f"  → λ={l2a} (市場のみ {base_va:.4f})")
    wa = fit_w(Xall[mi], MASK[mi], W[mi], OFF[mi], l2a)

    dll = {}
    for nm, sp in (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf)):
        ix = np.where(sp)[0]
        l1 = ll_sum(Xall[ix] @ wa + OFF[ix], MASK[ix], W[ix])
        l0 = ll_sum(OFF[ix], MASK[ix], W[ix])
        dll[nm] = dict(n=int(sp.sum()), dll=float(l1 - l0),
                       dll_per_race=float((l1 - l0) / sp.sum()))
        print(f"  {nm}: ΔLL={l1-l0:+.2f} nats ({(l1-l0)/sp.sum():+.5f}/R, {int(sp.sum())}R)")

    # ══ (b) B-sd16 に追加する版 ══
    prev = pickle.load(open("v99w2_result.pkl", "rb"))
    wg16 = np.array(prev["arm2_w"]["wg16"])
    ws16 = {eval(k): np.array(v) for k, v in prev["arm2_w"]["ws16"].items()}
    S16 = np.full((len(races), MAXH), -1e18)
    for i, r in enumerate(races):
        w = ws16.get(V.axis_key(r, "sd"), wg16)
        S16[i, :len(r["nums"])] = r["Z16"] @ w
    OFFB = np.where(MASK, S16, 0.0)

    best = (None, 1e18)
    print("\n[b] B-sd16オフセット版 λ選択 (MINE内部80/20 val NLL/R):")
    for l2 in LGRID:
        w = fit_w(Xall[tr], MASK[tr], W[tr], OFFB[tr], l2)
        nv = -V.pl_ll_per_race(np.where(MASK[va], Xall[va] @ w + OFFB[va], -1e18),
                               MASK[va], W[va]).mean()
        print(f"  λ={l2}: {nv:.4f}")
        if nv < best[1]:
            best = (l2, nv)
    l2b = best[0]
    b16_va = -V.pl_ll_per_race(np.where(MASK[va], OFFB[va], -1e18),
                               MASK[va], W[va]).mean()
    print(f"  → λ={l2b} (B-sd16のみ {b16_va:.4f})")
    wb = fit_w(Xall[mi], MASK[mi], W[mi], OFFB[mi], l2b)

    print("\n  加点の配点 v (zスケール):")
    for n, x in sorted(zip(names, wb), key=lambda t: -abs(t[1])):
        print(f"    {n:26s} {x:+.4f}")

    out_bets = {}
    print("\n══ 買い目（B-sd16 単体 → B-sd16+発掘加点） ══")
    for nm, sp in (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf)):
        ix = np.where(sp)[0]
        f16 = lambda i: S16[i, :len(races[i]["nums"])]
        fnew = lambda i: (S16[i, :len(races[i]["nums"])]
                          + Xall[i, :len(races[i]["nums"])] @ wb)
        b0 = bets(races, ix, f16)
        b1 = bets(races, ix, fnew)
        # 参考: B-sd16 の対数尤度も
        l0 = ll_sum(np.where(MASK[ix], S16[ix], -1e18), MASK[ix], W[ix])
        l1 = ll_sum(np.where(MASK[ix], S16[ix] + Xall[ix] @ wb, -1e18),
                    MASK[ix], W[ix])
        out_bets[nm] = dict(n=int(sp.sum()), bsd16=b0, plus=b1,
                            ll_bsd16=float(l0 / sp.sum()),
                            ll_plus=float(l1 / sp.sum()))
        print(f"\n── {nm} ({int(sp.sum())}R) ──")
        print(f"  B-sd16      : {fmt(b0)}  LL/R={l0/sp.sum():.4f}")
        print(f"  +発掘加点   : {fmt(b1)}  LL/R={l1/sp.sum():.4f}")
        print(f"  差分        : 複1 {b1['fuku1']['hitrate']-b0['fuku1']['hitrate']:+.2f}pt/"
              f"{b1['fuku1']['roi']-b0['fuku1']['roi']:+.2f}pt  "
              f"複2 {b1['fuku2']['hitrate']-b0['fuku2']['hitrate']:+.2f}pt/"
              f"{b1['fuku2']['roi']-b0['fuku2']['roi']:+.2f}pt  "
              f"ワイド {b1['wide']['hitrate']-b0['wide']['hitrate']:+.2f}pt/"
              f"{b1['wide']['roi']-b0['wide']['roi']:+.2f}pt  "
              f"三連複 {b1['trio']['hitrate']-b0['trio']['hitrate']:+.2f}pt/"
              f"{b1['trio']['roi']-b0['trio']['roi']:+.2f}pt")

    # ── 判定 ──
    prim = dll["VALIDATE"]["dll"] > 0 and dll["CONFIRM"]["dll"] > 0
    def d(nm, k, m):
        return out_bets[nm]["plus"][k][m] - out_bets[nm]["bsd16"][k][m]
    sec = all(d(nm, k, "hitrate") >= 2.0 for nm in ("VALIDATE", "CONFIRM")
              for k in ("fuku1", "fuku2")) and \
          all(d(nm, k, "roi") >= 0 for nm in ("VALIDATE", "CONFIRM")
              for k in ("fuku1", "fuku2"))
    print(f"\n判定: 一次(市場条件付きOOS ΔLL>0 が VAL/CONF 両方) = {'合格' if prim else '不合格'}")
    print(f"      二次(複勝的中率+2pt かつ ROI低下なし) = {'合格' if sec else '不合格'}")

    out = dict(
        sel=dict(z_crit=zc, n_generated=res["n_generated"], n_tested=res["n_tested"],
                 n_pass=len(order), n_after_corr=K, corr_thr=CORR_THR,
                 l2_market=l2a, l2_bsd16=l2b, lgrid=LGRID),
        feats=[dict(name=r["name"], ja=r["ja"], z=r["z"], dll=r["dll"],
                    beta=r["beta"], cov=r["cov"]) for r in keepn],
        w_market={n: float(x) for n, x in zip(names, wa)},
        w_bsd16_add={n: float(x) for n, x in zip(names, wb)},
        results=dict(market_dll=dll, bets=out_bets),
        verdict=dict(primary=bool(prim), secondary=bool(sec)))
    pickle.dump(out, open("discover_result.pkl", "wb"))
    json.dump(out, open("discover_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ discover_result.pkl / .json 保存")


if __name__ == "__main__":
    main()
