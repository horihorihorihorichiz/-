# -*- coding: utf-8 -*-
"""V99W2: V99W強化第2弾（V99W2_PROTOCOL.md 事前登録に従う）。
腕1=B-sd×B-tier加法結合 / 腕2=CORNER4特徴の追加成分 /
腕3=月次ローリング再学習 / 腕4=例外除外との合成。
usage: python3 v99w2_fit.py [--stage mine|final]
  mine : MINEのみ（変種選択・λ選択・最良の腕選択）。VALIDATE/CONFIRMに触れない。
  final: 確定学習→VALIDATE/CONFIRMを各腕1回だけ測定。
"""
import argparse, json, pickle
import numpy as np
from scipy.optimize import minimize

import v99w_fit as V

CORNER4 = ["spd_res", "mgn_abs", "wide4c", "pos_gain"]
MAXH = V.MAXH


# ───────── 一般化PL（K可変・オフセット対応） ─────────
def make_tensor(races, key="Z"):
    Kd = races[0][key].shape[1]
    R = len(races)
    X = np.zeros((R, MAXH, Kd))
    M = np.zeros((R, MAXH), dtype=bool)
    W = np.zeros((R, 3), dtype=int)
    for i, r in enumerate(races):
        n = len(r["nums"])
        X[i, :n] = r[key]
        M[i, :n] = True
        W[i] = r["top3"]
    return X, M, W


def pl_nll_grad(w, X, M, W, l2, w0, off=None):
    R, _, Kd = X.shape
    s = X @ w
    if off is not None:
        s = s + off
    masks = M.copy()
    ar = np.arange(R)
    nll = 0.0
    grad = np.zeros(Kd)
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


def fit(X, M, W, l2, w0=None, wstart=None, off=None):
    Kd = X.shape[2]
    w0 = np.zeros(Kd) if w0 is None else w0
    ws = w0.copy() if wstart is None else wstart.copy()
    res = minimize(lambda w: pl_nll_grad(w, X, M, W, l2, w0, off), ws,
                   jac=True, method="L-BFGS-B",
                   options=dict(maxiter=500, ftol=1e-12, gtol=1e-9))
    return res.x


def scores_matrix(races, score_fn):
    S = np.full((len(races), MAXH), -1e18)
    for i, r in enumerate(races):
        S[i, :len(r["nums"])] = score_fn(r)
    return S


def nll_of(races, score_fn):
    X, M, W = make_tensor(races)
    return -V.pl_ll_per_race(scores_matrix(races, score_fn), M, W).mean()


def eval_full(races, score_fn):
    X, M, W = make_tensor(races)
    ll = V.pl_ll_per_race(scores_matrix(races, score_fn), M, W).mean()
    return dict(n=len(races), ll_per_race=float(ll),
                bets=V.bet_metrics(races, score_fn))


# ───────── corner4 結合（腕2） ─────────
def attach_corner(races):
    z = np.load("corner_ds.npz", allow_pickle=False)
    A, rid_arr, feats = z["A"], z["rid"], [str(x) for x in z["feats"]]
    idx = [feats.index(f) for f in CORNER4]
    F = len(feats)
    ridx = A[:, F + 4].astype(int)
    num = A[:, F + 5].astype(int)
    mp = {}
    for i in range(len(A)):
        mp[(str(rid_arr[ridx[i]]), int(num[i]))] = A[i, idx]
    joined_r = joined_h = tot_h = 0
    zerocnt = np.zeros(4)
    for r in races:
        n = len(r["nums"])
        C = np.zeros((n, 4))
        hit = 0
        for i, nm in enumerate(r["nums"]):
            v = mp.get((r["rid"], nm))
            if v is not None:
                C[i] = v
                hit += 1
        r["Z16"] = np.hstack([r["Z"], C])
        tot_h += n
        joined_h += hit
        joined_r += 1 if hit else 0
        zerocnt += (C == 0.0).sum(0)
    return dict(races=len(races), joined_races=joined_r, horses=tot_h,
                joined_horses=joined_h,
                zero_rate={f: round(float(zerocnt[i] / tot_h), 4)
                           for i, f in enumerate(CORNER4)})


# ───────── 腕1: 加法結合 ─────────
def fit_axis_groups(races, axis, l2, wg, key="Z", wsd=None):
    ws = {}
    for k in sorted({V.axis_key(r, axis) for r in races}):
        sub = [r for r in races if V.axis_key(r, axis) == k]
        X, M, W = make_tensor(sub, key)
        st = None if wsd is None else wsd.get(k)
        ws[k] = fit(X, M, W, l2, w0=wg, wstart=wg if st is None else st)
    return ws


def backfit(races, wg, l_sd, l_tier, rounds=5):
    Kd = len(wg)
    dsd = {k: np.zeros(Kd) for k in sorted({V.axis_key(r, "sd") for r in races})}
    dti = {k: np.zeros(Kd) for k in sorted({V.axis_key(r, "tier") for r in races})}
    for _ in range(rounds):
        for axis, dd, other, oaxis, l2 in (
                ("sd", dsd, dti, "tier", l_sd),
                ("tier", dti, dsd, "sd", l_tier)):
            for k in dd:
                sub = [r for r in races if V.axis_key(r, axis) == k]
                if not sub:
                    continue
                X, M, W = make_tensor(sub)
                off = np.zeros((len(sub), MAXH))
                for i, r in enumerate(sub):
                    n = len(r["nums"])
                    off[i, :n] = r["Z"] @ (wg + other[V.axis_key(r, oaxis)])
                dd[k] = fit(X, M, W, l2, w0=np.zeros(Kd), wstart=dd[k], off=off)
    return dsd, dti


def combo_fn(wg, dsd, dti):
    z = np.zeros(len(wg))
    def fn(r):
        return r["Z"] @ (wg + dsd.get(V.axis_key(r, "sd"), z)
                         + dti.get(V.axis_key(r, "tier"), z))
    return fn


def axis_fn(ws, wg, axis, key="Z"):
    def fn(r):
        return r[key] @ ws.get(V.axis_key(r, axis), wg)
    return fn


# ───────── 腕4: 市場指標 ─────────
def market_stats(r):
    xs = [(n, o) for n, o in r["odds"].items() if o and o > 0]
    miss = len(r["odds"]) - len(xs)
    if len(xs) < 5:
        return None, miss
    inv = np.array([1.0 / o for _, o in xs])
    p = inv / inv.sum()
    return dict(fav=float(p.max()), ent=float(-(p * np.log(p)).sum())), miss


def market_top2(r):
    xs = sorted((o, n) for n, o in r["odds"].items() if o and o > 0)
    return [n for _, n in xs[:2]]


def market_fuku2(races):
    hit = stake = ret = 0
    for r in races:
        fuku = r["payout"].get("複勝", {})
        stake += 200
        for n in market_top2(r):
            v = fuku.get(str(n))
            if v:
                hit += 1
                ret += v
    nb = stake // 100
    return dict(hits=hit, bets=nb, hitrate=100.0 * hit / max(nb, 1),
                roi=100.0 * ret / max(stake, 1))


# ───────── メイン ─────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["mine", "final"], default="mine")
    a = ap.parse_args()
    races = V.load_races()
    cstat = attach_corner(races)
    print("corner結合:", cstat)
    mine = sorted([r for r in races if r["month"] <= "202602"],
                  key=lambda r: (r["date"], r["rid"]))
    vali = [r for r in races if "202603" <= r["month"] <= "202605"]
    conf = [r for r in races if "202606" <= r["month"] <= "202608"]
    print(f"PL対象: 全{len(races)}R  MINE={len(mine)} VAL={len(vali)} CONF={len(conf)}")

    prev = pickle.load(open("v99w_result.pkl", "rb"))
    wg = np.array([prev["wg"][c] for c in V.COMPS])
    wsd1 = {eval(k): np.array(v) for k, v in prev["ws_axes"]["sd"].items()}
    wti1 = {k: np.array(v) for k, v in prev["ws_axes"]["tier"].items()}
    L_G, L_SD, L_TI = 0.0003, 0.1, 0.3   # 第1弾確定値（流用・事前登録どおり）

    ncut = int(len(mine) * 0.8)
    tr80, va20 = mine[:ncut], mine[ncut:]

    if a.stage == "mine":
        sel = {}
        # 内部の共通土台: tr80で腕A(12)を学習
        Xt, Mt, Wt = make_tensor(tr80)
        wg80 = fit(Xt, Mt, Wt, L_G)
        n_armA = nll_of(va20, lambda r: r["Z"] @ wg80)
        print(f"\n[内部] armA(12) va20 NLL/R = {n_armA:.4f}")
        # 参照: B-sd(12) tr80版
        wsd80 = fit_axis_groups(tr80, "sd", L_SD, wg80)
        n_bsd = nll_of(va20, axis_fn(wsd80, wg80, "sd"))
        print(f"[内部] B-sd(12)  va20 NLL/R = {n_bsd:.4f}")

        # ── 腕1 変種選択 ──
        wti80 = fit_axis_groups(tr80, "tier", L_TI, wg80)
        dsd_s = {k: w - wg80 for k, w in wsd80.items()}
        dti_s = {k: w - wg80 for k, w in wti80.items()}
        n_sum = nll_of(va20, combo_fn(wg80, dsd_s, dti_s))
        dsd_b, dti_b = backfit(tr80, wg80, L_SD, L_TI, rounds=5)
        n_bf = nll_of(va20, combo_fn(wg80, dsd_b, dti_b))
        sel["arm1_variant"] = "backfit" if n_bf < n_sum else "simple"
        print(f"\n[腕1] simple-sum va20={n_sum:.4f} / backfit va20={n_bf:.4f}"
              f" → 選択 {sel['arm1_variant']}")

        # ── 腕2 λ選択 ──
        Xt6, Mt6, Wt6 = make_tensor(tr80, "Z16")
        best = (None, 1e18, None)
        print("\n[腕2] λ_g16 グリッド (va20 NLL/R):")
        for lg in [0.0003, 0.001, 0.003, 0.01, 0.03]:
            w = fit(Xt6, Mt6, Wt6, lg)
            v = nll_of(va20, lambda r: r["Z16"] @ w)
            print(f"  λ_g16={lg}: {v:.4f}")
            if v < best[1]:
                best = (lg, v, w)
        sel["lg16"] = best[0]
        wg80_16, n_armA16 = best[2], best[1]
        print(f"  → 選択 λ_g16={best[0]} (va20 {best[1]:.4f})")
        bb = (None, 1e18)
        print("[腕2] λ_sd16 グリッド (va20 NLL/R):")
        for lb in [0.01, 0.03, 0.1, 0.3, 1, 3]:
            ws = fit_axis_groups(tr80, "sd", lb, wg80_16, key="Z16")
            v = nll_of(va20, axis_fn(ws, wg80_16, "sd", key="Z16"))
            print(f"  λ_sd16={lb}: {v:.4f}")
            if v < bb[1]:
                bb = (lb, v)
        sel["lsd16"] = bb[0]
        n_bsd16 = bb[1]
        print(f"  → 選択 λ_sd16={bb[0]} (va20 {bb[1]:.4f})")

        # ── 腕4 最良の腕（va20 NLL/R 最小） ──
        n_combo = min(n_sum, n_bf)
        cands = {"armA": n_armA, "B-sd": n_bsd, "combo": n_combo,
                 "armA16": n_armA16, "B-sd16": n_bsd16}
        sel["best_arm"] = min(cands, key=cands.get)
        sel["va20_nll"] = {k: round(v, 4) for k, v in cands.items()}
        print(f"\n[腕4] va20 NLL/R: {sel['va20_nll']} → 最良={sel['best_arm']}")
        json.dump(sel, open("v99w2_sel.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("→ v99w2_sel.json 保存")
        return

    # ══ final ══
    sel = json.load(open("v99w2_sel.json", encoding="utf-8"))
    out = dict(sel=sel, corner_join=cstat, results={})
    splits = (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf))

    # ── 腕1 確定学習（MINE全体） ──
    if sel["arm1_variant"] == "simple":
        dsd = {k: w - wg for k, w in wsd1.items()}
        dti = {k: w - wg for k, w in wti1.items()}
    else:
        dsd, dti = backfit(mine, wg, L_SD, L_TI, rounds=5)
    fn1 = combo_fn(wg, dsd, dti)
    out["arm1"] = {nm: eval_full(sp, fn1) for nm, sp in splits}
    out["arm1_w"] = dict(
        dsd={str(k): v.tolist() for k, v in dsd.items()},
        dti={str(k): v.tolist() for k, v in dti.items()})

    # ── 腕2 確定学習 ──
    Xm6, Mm6, Wm6 = make_tensor(mine, "Z16")
    wg16 = fit(Xm6, Mm6, Wm6, sel["lg16"])
    ws16 = fit_axis_groups(mine, "sd", sel["lsd16"], wg16, key="Z16")
    fnA16 = lambda r: r["Z16"] @ wg16
    fnB16 = axis_fn(ws16, wg16, "sd", key="Z16")
    out["arm2_armA16"] = {nm: eval_full(sp, fnA16) for nm, sp in splits}
    out["arm2_Bsd16"] = {nm: eval_full(sp, fnB16) for nm, sp in splits}
    out["arm2_w"] = dict(wg16=wg16.tolist(),
                         ws16={str(k): v.tolist() for k, v in ws16.items()})

    # ── 腕3 ローリング ──
    months = ["202603", "202604", "202605", "202606", "202607", "202608"]
    roll = {}
    wprev, wsdprev = wg.copy(), None
    trainN = {}
    for m in months:
        tr = [r for r in races if r["month"] < m]
        trainN[m] = len(tr)
        X, M, W = make_tensor(tr)
        wm = fit(X, M, W, L_G, wstart=wprev)
        wsm = fit_axis_groups(tr, "sd", L_SD, wm, wsd=wsdprev)
        roll[m] = (wm, wsm)
        wprev, wsdprev = wm, wsm
    print("腕3 学習R数:", trainN)
    out["arm3_trainN"] = trainN

    def roll_fnA(r):
        return r["Z"] @ roll[r["month"]][0]

    def roll_fnB(r):
        wm, wsm = roll[r["month"]]
        return r["Z"] @ wsm.get(V.axis_key(r, "sd"), wm)

    out["arm3"] = {}
    for nm, sp in (("VALIDATE", vali), ("CONFIRM", conf)):
        out["arm3"][nm] = dict(rollA=eval_full(sp, roll_fnA),
                               rollB=eval_full(sp, roll_fnB))
    permA, permB = {}, {}
    for m in months:
        sp = [r for r in races if r["month"] == m]
        Xs, Ms, Ws = make_tensor(sp)
        permA[m] = float(V.pl_ll_per_race(
            scores_matrix(sp, roll_fnA), Ms, Ws).mean())
        permB[m] = float(V.pl_ll_per_race(
            scores_matrix(sp, roll_fnB), Ms, Ws).mean())
    out["arm3_permonth"] = dict(rollA=permA, rollB=permB, n={
        m: len([r for r in races if r["month"] == m]) for m in months})

    # ── 腕4 例外除外 ──
    best_fn = {"armA": lambda r: r["Z"] @ wg,
               "B-sd": axis_fn(wsd1, wg, "sd"),
               "combo": fn1, "armA16": fnA16, "B-sd16": fnB16}[sel["best_arm"]]
    wf = {}
    for line in open("wf_preds_v3ext2.jsonl", encoding="utf-8"):
        d = json.loads(line)
        s = d.get("scores") or []
        if len(s) >= 2:
            wf[d["rid"]] = s[0] - s[1]
    stats, miss_h, few = {}, 0, 0
    for r in races:
        st, miss = market_stats(r)
        miss_h += miss
        if st is None:
            few += 1
            continue
        sc = np.sort(best_fn(r))[::-1]
        st["sgapL"] = float(sc[0] - sc[1])
        st["sgapV3"] = wf.get(r["rid"])
        stats[r["rid"]] = st
    thrL = float(np.percentile(
        [stats[r["rid"]]["sgapL"] for r in mine if r["rid"] in stats], 40))
    sel["sgapL_thr"] = round(thrL, 4)
    print(f"腕4: sgap_L 閾値(MINE 40pct) = {thrL:.4f}  "
          f"オッズ欠馬={miss_h} 5頭未満除外={few}R "
          f"wf非結合={sum(1 for r in races if r['rid'] in stats and stats[r['rid']]['sgapV3'] is None)}R")
    out["arm4"] = dict(sgapL_thr=thrL, odds_missing_horses=miss_h,
                       few_odds_races=few, res={})
    for var in ("V3", "L"):
        for nm, sp in splits:
            keep = []
            n_nosgap = 0
            for r in sp:
                st = stats.get(r["rid"])
                if st is None:
                    continue
                sg = st["sgapV3"] if var == "V3" else st["sgapL"]
                if sg is None:
                    n_nosgap += 1
                    continue
                thr = 0.066 if var == "V3" else thrL
                if st["fav"] >= 0.341 and st["ent"] <= 1.904 and sg >= thr:
                    keep.append(r)
            res = dict(n=len(keep), n_total=len(sp), n_nosgap=n_nosgap,
                       model=V.bet_metrics(keep, best_fn),
                       mkt_fuku2=market_fuku2(keep))
            out["arm4"]["res"][f"{var}|{nm}"] = res

    # ── 出力 ──
    base = prev["results"]
    for nm, _ in splits:
        b = base[nm]
        print(f"\n══ {nm} ══")
        print(f"  現行     : LL/R={b['base']['ll_per_race']:.4f}  "
              + V.fmt_bets(b["base"]["bets"]))
        for lbl, res in (("armA(第1弾)", b["armA"]), ("B-sd(第1弾)", b["armB_sd"]),
                         ("B-tier(第1弾)", b["armB_tier"]),
                         ("腕1 combo", out["arm1"][nm]),
                         ("腕2 armA16", out["arm2_armA16"][nm]),
                         ("腕2 B-sd16", out["arm2_Bsd16"][nm])):
            print(f"  {lbl:12s}: LL/R={res['ll_per_race']:.4f} "
                  f"(Δ現行{res['ll_per_race']-b['base']['ll_per_race']:+.4f})  "
                  + V.fmt_bets(res["bets"]))
        if nm in ("VALIDATE", "CONFIRM"):
            for lbl, res in (("腕3 rollA", out["arm3"][nm]["rollA"]),
                             ("腕3 rollB-sd", out["arm3"][nm]["rollB"])):
                print(f"  {lbl:12s}: LL/R={res['ll_per_race']:.4f} "
                      f"(Δ現行{res['ll_per_race']-b['base']['ll_per_race']:+.4f})  "
                      + V.fmt_bets(res["bets"]))
    print("\n── 腕3 月別 LL/R ──")
    for m in months:
        print(f"  {m}: rollA={permA[m]:.4f} rollB={permB[m]:.4f} "
              f"n={out['arm3_permonth']['n'][m]} trainR={trainN[m]}")
    print(f"\n── 腕4 (最良の腕={sel['best_arm']}) ──")
    for k, res in out["arm4"]["res"].items():
        mf = res["mkt_fuku2"]
        print(f"  [{k}] n={res['n']}/{res['n_total']} (sgap欠={res['n_nosgap']})  "
              f"市場複2 {mf['hitrate']:.1f}%/{mf['roi']:.1f}%  "
              + V.fmt_bets(res["model"]))
    pickle.dump(out, open("v99w2_result.pkl", "wb"))
    print("\n→ v99w2_result.pkl 保存")


if __name__ == "__main__":
    main()
