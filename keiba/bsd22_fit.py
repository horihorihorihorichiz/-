# -*- coding: utf-8 -*-
"""BSD22: corner_ds未使用6特徴の再検定とB-sd22（BSD22_PROTOCOL.md 事前登録に従う）。

usage: python3 bsd22_fit.py [--stage mine|final]
  mine : MINEのみ（6特徴スクリーニング・λ選択）。VALIDATE/CONFIRMに触れない。
  final: 確定学習→VALIDATE/CONFIRMを1回だけ測定→bsd22_result.pkl。

v99w_fit.py / v99w2_fit.py は無変更のままimportして再利用。本番エンジンは触らない。
"""
import argparse
import json
import pickle

import numpy as np

import v99w_fit as V
import v99w2_fit as W2

EXTRA6 = ["pos_var", "pace_lv", "pace_gap", "fwd_fin", "grind", "unlucky"]
MAXH = V.MAXH
SEL_FILE = "bsd22_sel.json"
OUT_FILE = "bsd22_result.pkl"


# ───────── データ結合 ─────────
def attach_all(races):
    """corner_ds の10特徴を結合: r["Z16"](12+4) / r["C6"](未使用6) / r["logpm"] / r["s16"]。"""
    z = np.load("corner_ds.npz", allow_pickle=False)
    A, rid_arr, feats = z["A"], z["rid"], [str(x) for x in z["feats"]]
    F = len(feats)
    idx4 = [feats.index(f) for f in W2.CORNER4]
    idx6 = [feats.index(f) for f in EXTRA6]
    ridx = A[:, F + 4].astype(int)
    num = A[:, F + 5].astype(int)
    mp = {}
    for i in range(len(A)):
        mp[(str(rid_arr[ridx[i]]), int(num[i]))] = A[i]
    prev = pickle.load(open("v99w2_result.pkl", "rb"))
    wg16 = np.array(prev["arm2_w"]["wg16"])
    ws16 = {eval(k): np.array(v) for k, v in prev["arm2_w"]["ws16"].items()}
    joined_r = joined_h = tot_h = 0
    zerocnt = np.zeros(6)
    for r in races:
        n = len(r["nums"])
        C4 = np.zeros((n, 4))
        C6 = np.zeros((n, 6))
        hit = 0
        for i, nm in enumerate(r["nums"]):
            v = mp.get((r["rid"], nm))
            if v is not None:
                C4[i] = v[idx4]
                C6[i] = v[idx6]
                hit += 1
        r["Z16"] = np.hstack([r["Z"], C4])
        r["C6"] = C6
        inv = np.array([1.0 / r["odds"][nm] for nm in r["nums"]])
        r["logpm"] = np.log(inv / inv.sum())
        r["s16"] = r["Z16"] @ ws16.get(V.axis_key(r, "sd"), wg16)
        tot_h += n
        joined_h += hit
        joined_r += 1 if hit else 0
        zerocnt += (C6 == 0.0).sum(0)
    return dict(races=len(races), joined_races=joined_r, horses=tot_h,
                joined_horses=joined_h,
                zero_rate={f: round(float(zerocnt[i] / tot_h), 4)
                           for i, f in enumerate(EXTRA6)}), (wg16, ws16)


def make_off_tensor(races, cols_fn, Kd):
    """X(R,MAXH,Kd), M, W(top3), OFF(=log pm)。"""
    R = len(races)
    X = np.zeros((R, MAXH, Kd))
    M = np.zeros((R, MAXH), dtype=bool)
    W = np.zeros((R, 3), dtype=int)
    OFF = np.zeros((R, MAXH))
    for i, r in enumerate(races):
        n = len(r["nums"])
        c = cols_fn(r)
        X[i, :n] = c.reshape(n, Kd)
        M[i, :n] = True
        W[i] = r["top3"]
        OFF[i, :n] = r["logpm"]
    return X, M, W, OFF


def ll_frozen(races, cols_fn, Kd, w):
    """係数凍結でのレースごと PL log-lik（オフセット=log pm 込み）。"""
    X, M, W, OFF = make_off_tensor(races, cols_fn, Kd)
    S = np.where(M, OFF + X @ w, -1e18)
    return V.pl_ll_per_race(S, M, W)


def fit_off(races, cols_fn, Kd, wstart=None):
    X, M, W, OFF = make_off_tensor(races, cols_fn, Kd)
    return W2.fit(X, M, W, 0.0, w0=np.zeros(Kd), wstart=wstart, off=OFF)


def wald(races, cols_fn, Kd, w, eps=1e-5):
    """数値ヘッセ行列によるSE（総和スケール）。"""
    X, M, W, OFF = make_off_tensor(races, cols_fn, Kd)
    n = 3 * len(races)

    def g(wv):
        _, gr = W2.pl_nll_grad(wv, X, M, W, 0.0, np.zeros(Kd), off=OFF)
        return gr * n
    H = np.zeros((Kd, Kd))
    for j in range(Kd):
        e = np.zeros(Kd)
        e[j] = eps
        H[:, j] = (g(w + e) - g(w - e)) / (2 * eps)
    try:
        se = np.sqrt(np.diag(np.linalg.inv(H)))
    except np.linalg.LinAlgError:
        se = np.full(Kd, np.nan)
    return se


# ───────── メイン ─────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["mine", "final"], default="mine")
    a = ap.parse_args()
    races = V.load_races()
    cstat, (wg16, ws16) = attach_all(races)
    print("corner結合(6特徴):", cstat)
    mine = sorted([r for r in races if r["month"] <= "202602"],
                  key=lambda r: (r["date"], r["rid"]))
    vali = [r for r in races if "202603" <= r["month"] <= "202605"]
    conf = [r for r in races if "202606" <= r["month"] <= "202608"]
    print(f"PL対象: 全{len(races)}R  MINE={len(mine)} VAL={len(vali)} CONF={len(conf)}")
    ncut = int(len(mine) * 0.8)
    tr80, va20 = mine[:ncut], mine[ncut:]
    groups = sorted({V.axis_key(r, "sd") for r in mine})

    if a.stage == "mine":
        sel = {"screening": {}, "selected": []}
        # ベースライン: u = logpm + b*s16 （tr80推定 → va20凍結LL）
        c_base = lambda r: r["s16"].reshape(-1, 1)
        wb = fit_off(tr80, c_base, 1)
        ll_b_va = ll_frozen(va20, c_base, 1, wb)
        print(f"\n[base] u=logpm+b*s16  b(tr80)={wb[0]:.4f}  "
              f"va20 LL計={ll_b_va.sum():.2f} ({len(va20)}R)")
        for fi, f in enumerate(EXTRA6):
            c_f = lambda r, fi=fi: np.column_stack([r["s16"], r["C6"][:, fi]])
            wf_ = fit_off(tr80, c_f, 2, wstart=np.array([wb[0], 0.0]))
            ll_f_va = ll_frozen(va20, c_f, 2, wf_)
            d_va = ll_f_va - ll_b_va
            dll = float(d_va.sum())
            selected = dll > 0.0
            # 診断: 全MINE推定のγ・SE・z・in-sample ΔLL
            wm = fit_off(mine, c_f, 2, wstart=wf_)
            wbm = fit_off(mine, c_base, 1, wstart=wb)
            se = wald(mine, c_f, 2, wm)
            dll_ins = float(ll_frozen(mine, c_f, 2, wm).sum()
                            - ll_frozen(mine, c_base, 1, wbm).sum())
            # 診断: 群別 va20ΔLL 分解と群別γ（全MINE・群内推定）
            gtab = {}
            for gk in groups:
                iv = [i for i, r in enumerate(va20) if V.axis_key(r, "sd") == gk]
                sub = [r for r in mine if V.axis_key(r, "sd") == gk]
                wgm = fit_off(sub, c_f, 2, wstart=wm)
                gtab[str(gk)] = dict(
                    va20_dll=round(float(d_va[iv].sum()), 3), va20_n=len(iv),
                    gamma_mine=round(float(wgm[1]), 4), n_mine=len(sub))
            sel["screening"][f] = dict(
                dll_va20=round(dll, 3), va20_n=len(va20),
                dll_va20_per_race=round(dll / len(va20), 5),
                selected=bool(selected),
                gamma_tr80=round(float(wf_[1]), 4),
                b_tr80=round(float(wf_[0]), 4),
                gamma_mine=round(float(wm[1]), 4),
                se_mine=round(float(se[1]), 4),
                z_mine=round(float(wm[1] / se[1]), 2),
                dll_insample_mine=round(dll_ins, 3),
                groups=gtab)
            if selected:
                sel["selected"].append(f)
            print(f"[scr] {f:8s} va20ΔLL={dll:+8.3f} "
                  f"γ_tr80={wf_[1]:+.4f} γ_MINE={wm[1]:+.4f} "
                  f"z_MINE={wm[1]/se[1]:+.2f} insΔLL={dll_ins:+.2f} "
                  f"→ {'採択' if selected else '不採択'}")
        print(f"\n採択: {sel['selected']} (k={len(sel['selected'])})")
        if sel["selected"]:
            # Z22 構築 → λ選択（V99W2と同一グリッド）
            kidx = [EXTRA6.index(f) for f in sel["selected"]]
            for r in races:
                r["Z22"] = np.hstack([r["Z16"], r["C6"][:, kidx]])
            Xt, Mt, Wt = W2.make_tensor(tr80, "Z22")
            best = (None, 1e18, None)
            print("[λ_g22] tr80→va20 NLL/R:")
            for lg in [0.0003, 0.001, 0.003, 0.01, 0.03]:
                w = W2.fit(Xt, Mt, Wt, lg)
                v = W2.nll_of(va20, lambda r: r["Z22"] @ w)
                print(f"  λ_g22={lg}: {v:.4f}")
                if v < best[1]:
                    best = (lg, v, w)
            sel["lg22"] = best[0]
            wg80_22 = best[2]
            print(f"  → λ_g22={best[0]} (va20 {best[1]:.4f})")
            bb = (None, 1e18)
            print("[λ_sd22] tr80→va20 NLL/R:")
            for lb in [0.01, 0.03, 0.1, 0.3, 1, 3]:
                ws = W2.fit_axis_groups(tr80, "sd", lb, wg80_22, key="Z22")
                v = W2.nll_of(va20, W2.axis_fn(ws, wg80_22, "sd", key="Z22"))
                print(f"  λ_sd22={lb}: {v:.4f}")
                if v < bb[1]:
                    bb = (lb, v)
            sel["lsd22"] = bb[0]
            print(f"  → λ_sd22={bb[0]} (va20 {bb[1]:.4f})")
            # 参考: 同一内部分割でのB-sd16凍結スコアのva20 NLL/R
            sel["va20_nll_Bsd22"] = round(bb[1], 4)
            sel["va20_nll_Bsd16_frozen"] = round(
                W2.nll_of(va20, lambda r: r["s16"]), 4)
        json.dump(sel, open(SEL_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"→ {SEL_FILE} 保存")
        return

    # ══ final: VAL/CONF は本ステージ1回だけ ══
    sel = json.load(open(SEL_FILE, encoding="utf-8"))
    assert sel["selected"], "採択0本ならfinalは実行しない（プロトコル§5）"
    kidx = [EXTRA6.index(f) for f in sel["selected"]]
    for r in races:
        r["Z22"] = np.hstack([r["Z16"], r["C6"][:, kidx]])
    K22 = 16 + len(kidx)
    out = dict(sel=sel, corner_join=cstat, results={})

    # 確定学習（MINE全体）
    Xm, Mm, Wm = W2.make_tensor(mine, "Z22")
    wg22 = W2.fit(Xm, Mm, Wm, sel["lg22"])
    ws22 = W2.fit_axis_groups(mine, "sd", sel["lsd22"], wg22, key="Z22")
    fnB22 = W2.axis_fn(ws22, wg22, "sd", key="Z22")
    fnB16 = lambda r: r["s16"]
    comps22 = V.COMPS + W2.CORNER4 + sel["selected"]
    print("\n確定 wg22:", {c: round(float(x), 4) for c, x in zip(comps22, wg22)})

    splits = (("MINE", mine), ("VALIDATE", vali), ("CONFIRM", conf))
    out["arm_Bsd22"] = {nm: W2.eval_full(sp, fnB22) for nm, sp in splits}
    out["arm_Bsd16_frozen"] = {nm: W2.eval_full(sp, fnB16) for nm, sp in splits}
    out["arm_w"] = dict(wg22=wg22.tolist(), comps22=comps22,
                        ws22={str(k): v.tolist() for k, v in ws22.items()})

    # P1: 市場オフセット条件付きロジット 真のOOS増分
    for r in races:
        r["s22"] = fnB22(r)
    cA = lambda r: r["s16"].reshape(-1, 1)
    cB = lambda r: np.column_stack([r["s16"], r["s22"]])
    cC = lambda r: r["s22"].reshape(-1, 1)
    wA = fit_off(mine, cA, 1)
    wB = fit_off(mine, cB, 2, wstart=np.array([wA[0], 0.0]))
    wC = fit_off(mine, cC, 1)
    print(f"\n[P1係数(MINE凍結)] A: a={wA[0]:.4f} / "
          f"B: a'={wB[0]:.4f} c={wB[1]:.4f} / C: c={wC[0]:.4f}")
    prim = dict(coefs=dict(a=float(wA[0]), a2=float(wB[0]), c=float(wB[1]),
                           c_alone=float(wC[0])))
    pooled = []
    for nm, sp in splits:
        llA = ll_frozen(sp, cA, 1, wA)
        llB = ll_frozen(sp, cB, 2, wB)
        llC = ll_frozen(sp, cC, 1, wC)
        d = llB - llA
        z = float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))
        prim[nm] = dict(n=len(sp), dLL=float(d.sum()),
                        dLL_per_race=float(d.mean()), z=z,
                        LL_A=float(llA.sum()), LL_B=float(llB.sum()),
                        LL_C=float(llC.sum()),
                        head2head_C_minus_A=float(llC.sum() - llA.sum()))
        if nm in ("VALIDATE", "CONFIRM"):
            pooled.append(d)
        # 群別分解
        gd = {}
        for gk in sorted({V.axis_key(r, "sd") for r in sp}):
            iv = [i for i, r in enumerate(sp) if V.axis_key(r, "sd") == gk]
            gd[str(gk)] = dict(n=len(iv), dLL=round(float(d[iv].sum()), 3))
        prim[nm]["groups"] = gd
    dp = np.concatenate(pooled)
    z_pool = float(dp.mean() / (dp.std(ddof=1) / np.sqrt(len(dp))))
    prim["pooled_VAL_CONF"] = dict(n=len(dp), dLL=float(dp.sum()), z=z_pool)
    out["primary"] = prim

    # 判定（事前登録どおり）
    p1 = (prim["VALIDATE"]["dLL"] > 0 and prim["CONFIRM"]["dLL"] > 0
          and z_pool >= 2.45)
    p2 = all(out["arm_Bsd22"][nm]["ll_per_race"]
             > out["arm_Bsd16_frozen"][nm]["ll_per_race"]
             for nm in ("VALIDATE", "CONFIRM"))
    out["verdict"] = dict(P1=bool(p1), P2=bool(p2), PASS=bool(p1 and p2),
                          z_pool=z_pool, z_thr=2.45, trials=7)

    # 表示
    for nm, sp in splits:
        b16 = out["arm_Bsd16_frozen"][nm]
        b22 = out["arm_Bsd22"][nm]
        print(f"\n══ {nm} ({len(sp)}R) ══")
        print(f"  B-sd16 : LL/R={b16['ll_per_race']:.4f}  "
              + V.fmt_bets(b16["bets"]))
        print(f"  B-sd22 : LL/R={b22['ll_per_race']:.4f} "
              f"(Δ{b22['ll_per_race']-b16['ll_per_race']:+.4f})  "
              + V.fmt_bets(b22["bets"]))
        pr = prim[nm]
        print(f"  P1: ΔLL={pr['dLL']:+.3f} ({pr['dLL_per_race']:+.5f}/R) "
              f"z={pr['z']:+.2f}  head2head(C-A)={pr['head2head_C_minus_A']:+.3f}")
    print(f"\npooled(VAL+CONF): ΔLL={prim['pooled_VAL_CONF']['dLL']:+.3f} "
          f"z={z_pool:+.2f} (合格線 z≥2.45)")
    print(f"判定: P1={p1} P2={p2} → {'合格' if p1 and p2 else '未達'}")
    pickle.dump(out, open(OUT_FILE, "wb"))
    print(f"→ {OUT_FILE} 保存")


if __name__ == "__main__":
    main()
