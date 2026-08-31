# -*- coding: utf-8 -*-
"""V99W: Ver.99.27配点の学習（V99W_PROTOCOL.md 事前登録に従う）。
腕A=全体1本 w_g / 腕B=条件別4軸（コース/VG/芝ダ×距離帯/クラス帯）。
usage: python3 v99w_fit.py [--stage mine|final]
  mine : MINEのみ（λ選択・内部検証）。VALIDATE/CONFIRMには触れない。
  final: MINE全体で確定学習→VALIDATE/CONFIRMを1回だけ測定。
"""
import argparse, json, pickle, sys
import numpy as np
from scipy.optimize import minimize, minimize_scalar

COMPS = ["tsi", "lts", "fsi", "bonus", "dsi", "nsi", "csi",
         "was", "tas", "hcs", "nrja", "kankai"]
K = len(COMPS)
MAXH = 18


# ───────── データ整形 ─────────
def load_races():
    d = pickle.load(open("comps_v99.pkl", "rb"))
    out = []
    for r in d["races"]:
        hs = [h for h in r["horses"] if h["finish"] is not None]
        if len(hs) < 5:
            continue
        fins = sorted(hs, key=lambda h: (h["finish"], h["num"]))
        if not (fins[0]["finish"] == 1 and fins[1]["finish"] <= 2
                and fins[2]["finish"] <= 3):
            continue
        X = np.zeros((len(hs), K))
        for i, h in enumerate(hs):
            for j, c in enumerate(COMPS[:-1]):
                X[i, j] = h["comps"][c]
            X[i, K-1] = (h["mult"] - 1.0) * 100.0
        mu = X.mean(0)
        sd = X.std(0)
        Z = np.where(sd > 1e-9, (X - mu) / np.where(sd > 1e-9, sd, 1.0), 0.0)
        nums = [h["num"] for h in hs]
        idx = {n: i for i, n in enumerate(nums)}
        top3 = [idx[fins[p]["num"]] for p in range(3)]
        wavg = np.array([h["wavg"] for h in hs])
        out.append(dict(
            rid=r["rid"], month=r["month"], date=r["date"],
            venue=r["venue"], surface=r["surface"], distance=r["distance"],
            dist_cat=r["dist_cat"], vg=r["today_vg"], tier=r["today_tier"],
            Z=Z, Xraw=X, sd=sd, wavg=wavg, top3=top3, nums=nums,
            payout=r["payout"],
            odds={h["num"]: h["odds"] for h in hs}))
    return out


def make_tensor(races, key="Z"):
    R = len(races)
    X = np.zeros((R, MAXH, K))
    M = np.zeros((R, MAXH), dtype=bool)
    W = np.zeros((R, 3), dtype=int)
    S0 = np.full((R, MAXH), -1e18)   # 現行WAvg（タイブレーク/ベースライン用）
    for i, r in enumerate(races):
        n = len(r["nums"])
        X[i, :n] = r[key]
        M[i, :n] = True
        W[i] = r["top3"]
        S0[i, :n] = r["wavg"]
    return X, M, W, S0


# ───────── Plackett-Luce ─────────
def pl_nll_grad(w, X, M, W, l2, w0):
    R = X.shape[0]
    s = X @ w
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
    return (nll / n + l2 * ((w - w0) ** 2).sum(),
            grad / n + 2 * l2 * (w - w0))


def pl_ll_per_race(scores, M, W):
    """各レースの log P(1,2,3着) （温度は scores に織り込み済み）。"""
    R = scores.shape[0]
    masks = M.copy()
    ar = np.arange(R)
    ll = np.zeros(R)
    for pos in range(3):
        sm = np.where(masks, scores, -1e18)
        mx = sm.max(1)
        Z = (np.exp(sm - mx[:, None]) * masks).sum(1)
        win = W[:, pos]
        ll += scores[ar, win] - (mx + np.log(Z))
        masks[ar, win] = False
    return ll


def fit(X, M, W, l2, w0=None, wstart=None):
    w0 = np.zeros(K) if w0 is None else w0
    ws = w0.copy() if wstart is None else wstart.copy()
    res = minimize(lambda w: pl_nll_grad(w, X, M, W, l2, w0), ws,
                   jac=True, method="L-BFGS-B",
                   options=dict(maxiter=500, ftol=1e-12, gtol=1e-9))
    return res.x


def fit_base_temp(S0, M, W):
    """現行WAvgスコアの温度をMINEで1次元最適化。"""
    def nll(logT):
        T = np.exp(logT)
        return -pl_ll_per_race(np.where(M, S0 / T, -1e18), M, W).mean()
    r = minimize_scalar(nll, bounds=(np.log(1.0), np.log(200.0)),
                        method="bounded")
    return float(np.exp(r.x))


# ───────── 購入評価 ─────────
def rank_horses(r, score):
    o = sorted(range(len(r["nums"])),
               key=lambda i: (-score[i], -r["wavg"][i], r["nums"][i]))
    return [r["nums"][i] for i in o]


def bet_metrics(races, score_fn):
    """score_fn(race)->np.array。返り値: 券種別 (的中数, 賭金, 払戻)。"""
    m = dict(win=[0, 0, 0], fuku1=[0, 0, 0], fuku2=[0, 0, 0], trio=[0, 0, 0])
    for r in races:
        top = rank_horses(r, score_fn(r))
        po = r["payout"]
        tan = po.get("単勝", {})
        fuku = po.get("複勝", {})
        trio = po.get("三連複", {})
        # 単勝1点
        m["win"][1] += 100
        v = tan.get(str(top[0]))
        if v:
            m["win"][0] += 1
            m["win"][2] += v
        # 複勝1点/2点
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
        # 三連複1点
        m["trio"][1] += 100
        key = "-".join(str(x) for x in sorted(top[:3]))
        v = trio.get(key)
        if v:
            m["trio"][0] += 1
            m["trio"][2] += v
    out = {}
    for k, (hit, stake, ret) in m.items():
        nb = stake // 100
        out[k] = dict(hits=hit, bets=nb, hitrate=100.0 * hit / max(nb, 1),
                      roi=100.0 * ret / max(stake, 1))
    return out


def eval_all(races, score_fn, ll_scores, M, W):
    ll = pl_ll_per_race(ll_scores, M, W)
    bm = bet_metrics(races, score_fn)
    return dict(n=len(races), ll_per_race=float(ll.mean()), bets=bm)


# ───────── 条件軸 ─────────
def axis_key(r, axis):
    if axis == "course":
        return (r["venue"], r["surface"], r["distance"])
    if axis == "vg":
        return r["vg"]
    if axis == "sd":
        return (r["surface"], r["dist_cat"])
    if axis == "tier":
        t = r["tier"]
        return "tier34" if t in (3, 4) else f"tier{t}"
    raise ValueError(axis)


def fit_axis(axis, groups_def, train, l2b, wg):
    """train内で各グループの w_c を学習。返り値 {key: w_c}。"""
    ws = {}
    for key in groups_def:
        sub = [r for r in train if axis_key(r, axis) == key]
        if not sub:
            ws[key] = wg.copy()
            continue
        X, M, W, _ = make_tensor(sub)
        ws[key] = fit(X, M, W, l2b, w0=wg, wstart=wg)
    return ws


def axis_scores(races, axis, ws, wg):
    """各レースにグループ重み(無ければwg)を適用したスコア行列。"""
    R = len(races)
    S = np.full((R, MAXH), -1e18)
    for i, r in enumerate(races):
        w = ws.get(axis_key(r, axis), wg)
        n = len(r["nums"])
        S[i, :n] = r["Z"] @ w
    return S


def axis_score_fn(axis, ws, wg):
    def fn(r):
        w = ws.get(axis_key(r, axis), wg)
        return r["Z"] @ w
    return fn


# ───────── メイン ─────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["mine", "final"], default="mine")
    a = ap.parse_args()
    races = load_races()
    mine = sorted([r for r in races if r["month"] <= "202602"],
                  key=lambda r: (r["date"], r["rid"]))
    vali = [r for r in races if "202603" <= r["month"] <= "202605"]
    conf = [r for r in races if "202606" <= r["month"] <= "202608"]
    print(f"PL対象: 全{len(races)}R  MINE={len(mine)} VALIDATE={len(vali)} "
          f"CONFIRM={len(conf)}")

    ncut = int(len(mine) * 0.8)
    tr80, va20 = mine[:ncut], mine[ncut:]
    Xt, Mt, Wt, S0t = make_tensor(tr80)
    Xv, Mv, Wv, S0v = make_tensor(va20)
    Xm, Mm, Wm, S0m = make_tensor(mine)

    # 現行ベースライン温度（MINE全体で1回）
    Tb = fit_base_temp(S0m, Mm, Wm)
    print(f"現行WAvg温度 T_base={Tb:.3f} (MINEで最適化)")

    # σ̄_k（MINEのレース内std平均）— 換算表用
    sbar = np.mean([r["sd"] for r in mine], axis=0)
    print("σ̄_k(MINE):", {c: round(float(s), 3) for c, s in zip(COMPS, sbar)})

    # ── 腕A: λ_g 選択（内部分割） ──
    print("\n── 腕A λ_g グリッド（train80→val20 NLL/R, 小さいほど良い）──")
    base_val = -pl_ll_per_race(np.where(Mv, S0v / Tb, -1e18), Mv, Wv).mean()
    print(f"  現行(等重み,T={Tb:.1f}): val20 NLL/R={base_val:.4f}")
    best = (None, 1e18, None)
    for lg in [0.0003, 0.001, 0.003, 0.01, 0.03]:
        w = fit(Xt, Mt, Wt, lg)
        v = -pl_ll_per_race(np.where(Mv, Xv @ w, -1e18), Mv, Wv).mean()
        print(f"  λ_g={lg}: val20 NLL/R={v:.4f}")
        if v < best[1]:
            best = (lg, v, w)
    lg_sel = best[0]
    print(f"  → 選択 λ_g={lg_sel}")

    # ── 腕B: 軸ごとに λ_B 選択（内部分割; wg=train80で学習した腕A重み） ──
    wg80 = best[2]
    axes = ["course", "vg", "sd", "tier"]
    groups = {}
    cg = {}
    for r in mine:
        cg.setdefault(axis_key(r, "course"), 0)
        cg[axis_key(r, "course")] += 1
    groups["course"] = sorted([k for k, v in cg.items() if v >= 40])
    groups["vg"] = sorted({axis_key(r, "vg") for r in mine})
    groups["sd"] = sorted({axis_key(r, "sd") for r in mine})
    groups["tier"] = sorted({axis_key(r, "tier") for r in mine})
    lb_sel = {}
    print("\n── 腕B λ_B グリッド（軸ごと; val20 NLL/R）──")
    armA_val = best[1]
    for ax in axes:
        print(f"  [{ax}] groups={len(groups[ax])}  (腕A val20={armA_val:.4f})")
        bb = (None, 1e18)
        for lb in [0.01, 0.03, 0.1, 0.3, 1, 3]:
            ws = fit_axis(ax, groups[ax], tr80, lb, wg80)
            S = axis_scores(va20, ax, ws, wg80)
            v = -pl_ll_per_race(S, Mv, Wv).mean()
            print(f"    λ_B={lb}: val20 NLL/R={v:.4f}")
            if v < bb[1]:
                bb = (lb, v)
        lb_sel[ax] = bb[0]
        print(f"    → 選択 λ_B={bb[0]} (val20 {bb[1]:.4f})")

    sel = dict(lg=lg_sel, lb=lb_sel, Tb=Tb,
               sbar={c: float(s) for c, s in zip(COMPS, sbar)},
               groups={ax: [str(g) for g in groups[ax]] for ax in axes})
    json.dump(sel, open("v99w_sel.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n選択結果を v99w_sel.json に保存。")

    if a.stage == "mine":
        return

    # ══ final: MINE全体で確定学習 → 各期を1回だけ測定 ══
    wg = fit(Xm, Mm, Wm, lg_sel)
    print("\n確定 w_g (zスケール):",
          {c: round(float(x), 4) for c, x in zip(COMPS, wg)})
    ws_axes = {ax: fit_axis(ax, groups[ax], mine, lb_sel[ax], wg)
               for ax in axes}

    results = {}
    for name, split in (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf)):
        X, M, W, S0 = make_tensor(split)
        res = {}
        res["base"] = eval_all(split, lambda r: r["wavg"],
                               np.where(M, S0 / Tb, -1e18), M, W)
        res["armA"] = eval_all(split, lambda r: r["Z"] @ wg,
                               np.where(M, X @ wg, -1e18), M, W)
        for ax in axes:
            S = axis_scores(split, ax, ws_axes[ax], wg)
            res[f"armB_{ax}"] = eval_all(split, axis_score_fn(ax, ws_axes[ax], wg),
                                         S, M, W)
        results[name] = res

    # 出力
    for name in ("MINE", "VALIDATE", "CONFIRM"):
        res = results[name]
        print(f"\n══ {name} ({res['base']['n']}R) ══")
        b = res["base"]
        print(f"  現行   : LL/R={b['ll_per_race']:.4f}  " + fmt_bets(b["bets"]))
        for k in ["armA"] + [f"armB_{ax}" for ax in axes]:
            e = res[k]
            print(f"  {k:11s}: LL/R={e['ll_per_race']:.4f} "
                  f"(Δ{e['ll_per_race']-b['ll_per_race']:+.4f})  "
                  + fmt_bets(e["bets"]))

    out = dict(sel=sel, wg={c: float(x) for c, x in zip(COMPS, wg)},
               ws_axes={ax: {str(k): [float(x) for x in v]
                             for k, v in ws_axes[ax].items()} for ax in axes},
               results=results)
    pickle.dump(out, open("v99w_result.pkl", "wb"))
    print("\n結果を v99w_result.pkl に保存。")


def fmt_bets(b):
    return ("単勝 {win[hitrate]:.1f}%/{win[roi]:.1f}%  "
            "複1 {fuku1[hitrate]:.1f}%/{fuku1[roi]:.1f}%  "
            "複2 {fuku2[hitrate]:.1f}%/{fuku2[roi]:.1f}%  "
            "三連複 {trio[hitrate]:.1f}%/{trio[roi]:.1f}%"
            " (的中率/ROI)").format(**b)


if __name__ == "__main__":
    main()
