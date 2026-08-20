# -*- coding: utf-8 -*-
"""当日トラックバイアス検証 — TRACKBIAS_PROTOCOL.md の機械適用。

  指数: 同一開催日(rid[:10])・同一surfaceの前半レースから
        dB(枠) / sB(脚質=丸め) / cB(当日実4角=生) を as-of 累積 (縮約k=2)
  特徴: I×馬属性の交互作用4本 (tb_draw, tb_style, tb_c4style, tb_c4own)
  一次: u = log pm (オフセット係数1固定) + x·θ, PL top3, θ_MINE凍結の真のOOS ΔLL>0 (VAL/CONF両方)

usage:
  python3 trackbias_eval.py build   # 台帳+horse_cache → trackbias_ds.pkl
  python3 trackbias_eval.py mine    # MINEのみ: 単独検定MINE列 / λCV / θ_MINE / ROI閾値T
  python3 trackbias_eval.py final   # VAL/CONF 1回だけ: 単独検定VAL/CONF・OOS ΔLL・ROI

既存ファイルは一切変更しない（本ファイルは新規・独立）。git操作はしない。
"""
import glob
import json
import math
import os
import pickle
import sys

import numpy as np
from scipy.optimize import minimize

DS = "trackbias_ds.pkl"
MINE_OUT = "trackbias_mine.json"
RESULT = "trackbias_result.json"
FEATS = ["tb_draw", "tb_style", "tb_c4style", "tb_c4own"]
SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
LAM_GRID = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0]
NCV = 5
K_SHRINK = 2.0
ST = {"逃": 1.0, "先": 2.0 / 3.0, "差": 1.0 / 3.0, "追": 0.0}
Z_MINE, Z_VC = 2.5, 2.0
P_Z25, P_Z20_SIGNED = 0.012419, 0.02275


def _dstr(date):
    return "%s-%s-%s" % (date[:4], date[4:6], date[6:8])


# ── 1. build ──────────────────────────────────────────────────────────
def build():
    files = sorted(glob.glob(os.path.join("hist", "*.json")))
    raw = []
    need = {}                      # horse_id -> set(date_str)
    for fp in files:
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        rid = os.path.basename(fp)[:-5]
        date = d.get("date", "")
        raw.append((date, rid, d))
        for h in (d.get("race") or {}).get("horses") or []:
            hid = h.get("horse_id")
            if hid:
                need.setdefault(hid, set()).add(_dstr(date))
    raw.sort(key=lambda x: (x[0], x[1]))
    print(f"hist races={len(raw)}  unique horses={len(need)}")

    # 当日レコード (corner4) を horse_cache から回収
    day_c4 = {}                    # (hid, date_str) -> corner4
    miss = 0
    for i, (hid, dates) in enumerate(need.items()):
        try:
            recs = json.load(open(os.path.join("horse_cache", hid + ".json"),
                                  encoding="utf-8"))
        except Exception:
            miss += 1
            continue
        for r in recs:
            pd = r.get("_pdate")
            if pd in dates and r.get("corner4") is not None:
                day_c4[(hid, pd)] = int(r["corner4"])
        if (i + 1) % 5000 == 0:
            print(f"  cache {i+1}/{len(need)}")
    print(f"cache done: day-records={len(day_c4)}  missing-files={miss}")

    # レースごとの基本量
    prep = {}
    for date, rid, d in raw:
        race, res = d.get("race") or {}, d.get("result") or {}
        horses = race.get("horses") or []
        order = res.get("order") or []
        nums = [h["num"] for h in horses if h.get("num") is not None]
        if len(nums) < 2:
            continue
        F = len(nums)
        rank, odds = {}, {}
        for o in order:
            try:
                rank[int(o["num"])] = int(o["rank"])
            except Exception:
                continue
            if o.get("odds"):
                odds[int(o["num"])] = float(o["odds"])
        top3 = res.get("top3") or []
        hmap = {h["num"]: h for h in horses}
        nd = {n: (n - 1.0) / (F - 1.0) for n in nums}
        st = {n: ST.get(hmap[n].get("paper_style")) for n in nums}
        c4 = {}
        ds_ = _dstr(date)
        for n in nums:
            v = day_c4.get((hmap[n].get("horse_id"), ds_))
            if v is not None:
                c4[n] = 1.0 - (v - 1.0) / (F - 1.0)
        prep[rid] = dict(date=date, rid=rid, surface=race.get("surface"),
                         rno=int(rid[10:12]), grp=rid[:10], nums=nums, F=F,
                         nd=nd, st=st, c4=c4, top3=list(top3), rank=rank,
                         odds=odds, hmap=hmap,
                         payout=res.get("payout") or {})

    # 前半レース寄与 (as-of: 同グループ・同surface・rno小)
    def contrib(p):
        t3 = [n for n in p["top3"] if n in p["hmap"]]
        if len(t3) != 3:
            return None, None, None
        nums = p["nums"]
        dB = (np.mean([p["nd"][n] for n in t3])
              - np.mean([p["nd"][n] for n in nums]))
        svals = [p["st"][n] for n in nums if p["st"][n] is not None]
        st3 = [p["st"][n] for n in t3 if p["st"][n] is not None]
        sB = (np.mean(st3) - np.mean(svals)) if (len(st3) >= 2 and svals) else None
        cB = None
        if all(n in p["c4"] for n in t3):
            cvals = [p["c4"][n] for n in nums if n in p["c4"]]
            if cvals:
                cB = np.mean([p["c4"][n] for n in t3]) - np.mean(cvals)
        return dB, sB, cB

    groups = {}
    for p in prep.values():
        groups.setdefault((p["grp"], p["surface"]), []).append(p)

    out = []
    for key, plist in groups.items():
        plist.sort(key=lambda p: p["rno"])
        cum = dict(dB=[], sB=[], cB=[])
        for p in plist:
            I = {}
            nE = {}
            for x in ("dB", "sB", "cB"):
                vals = cum[x]
                nE[x] = len(vals)
                I[x] = sum(vals) / (len(vals) + K_SHRINK) if vals else 0.0
            p["I"], p["nE"] = I, nE
            dB, sB, cB = contrib(p)
            if dB is not None:
                cum["dB"].append(dB)
            if sB is not None:
                cum["sB"].append(sB)
            if cB is not None:
                cum["cB"].append(cB)

    # 対象レース行列 (採用条件: 5頭以上・全頭確定オッズ・1着特定)
    for date, rid, d in raw:
        p = prep.get(rid)
        if p is None:
            continue
        nums = p["nums"]
        if len(nums) < 5:
            continue
        if not all(n in p["odds"] and p["odds"][n] > 0 for n in nums):
            continue
        if not any(p["rank"].get(n) == 1 for n in nums):
            continue
        F = len(nums)
        inv = np.array([1.0 / p["odds"][n] for n in nums])
        pm = inv / inv.sum()
        # 属性 (レース内centered, 欠損=0)
        ndm = np.mean([p["nd"][n] for n in nums])
        draw_c = {n: p["nd"][n] - ndm for n in nums}
        sv = [p["st"][n] for n in nums if p["st"][n] is not None]
        sm = np.mean(sv) if sv else 0.0
        style_c = {n: (p["st"][n] - sm) if p["st"][n] is not None else 0.0
                   for n in nums}
        own = {}
        for n in nums:
            frs = []
            for r in (p["hmap"][n].get("races") or [])[:5]:
                c, f = r.get("corner4"), r.get("field")
                if c is not None and f and f >= 2:
                    frs.append(1.0 - (c - 1.0) / (f - 1.0))
            own[n] = np.mean(frs) if frs else None
        ov = [v for v in own.values() if v is not None]
        om = np.mean(ov) if ov else 0.0
        own4_c = {n: (own[n] - om) if own[n] is not None else 0.0 for n in nums}
        I = p["I"]
        X = np.array([[I["dB"] * draw_c[n],
                       I["sB"] * style_c[n],
                       I["cB"] * style_c[n],
                       I["cB"] * own4_c[n]] for n in nums], dtype=np.float64)
        top3 = []
        for want in (1, 2, 3):
            hit = [i for i, n in enumerate(nums) if p["rank"].get(n) == want]
            top3.append(hit[0] if len(hit) == 1 else -1)
        ytop3 = np.array([1.0 if (p["rank"].get(n) or 99) <= 3 else 0.0
                          for n in nums])
        pay = p["payout"]
        fuku = {int(k): v for k, v in (pay.get("複勝") or {}).items()}
        wide = {k: v for k, v in (pay.get("ワイド") or {}).items()}
        out.append(dict(rid=rid, month=date[:6], nums=nums, F=F, X=X, pm=pm,
                        top3=top3, ytop3=ytop3, I=I, nE=p["nE"],
                        fuku=fuku, wide=wide))
    pickle.dump(out, open(DS, "wb"))
    ms = sorted({r["month"] for r in out})
    print(f"target races={len(out)}  months {ms[0]}..{ms[-1]}")
    for s, (lo, hi) in SPLITS.items():
        n = sum(1 for r in out if lo <= r["month"] <= hi)
        print(f"  {s}: {n}R")
    nE = [r["nE"]["dB"] for r in out]
    print("nE_dB dist:", {k: nE.count(k) for k in sorted(set(nE))})
    z = sum(1 for r in out if np.allclose(r["X"], 0))
    print(f"races with all-zero features: {z}")


# ── 2. 推定器 (corner_eval / mktcond_eval と同一実装のコピー) ─────────
def logistic(X, y, iters=60, tol=1e-10):
    n, k = X.shape
    b = np.zeros(k)
    ll = -np.inf
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        g = X.T @ (y - p)
        W = np.clip(p * (1 - p), 1e-9, None)
        H = (X * W[:, None]).T @ X + np.eye(k) * 1e-8
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        b = b + step
        new = float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) +
                           (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))
        if abs(new - ll) < tol:
            ll = new
            break
        ll = new
    eta = np.clip(X @ b, -30, 30)
    p = 1.0 / (1.0 + np.exp(-eta))
    ll = float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) +
                      (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))
    W = np.clip(p * (1 - p), 1e-9, None)
    H = (X * W[:, None]).T @ X + np.eye(k) * 1e-8
    cov = np.linalg.inv(H)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    return b, se, ll


def loglik_lr(X, y, b):
    p = 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))
    return float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) +
                        (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))


def pack(races):
    n = len(races)
    K = max(len(r["nums"]) for r in races)
    F = races[0]["X"].shape[1]
    X = np.zeros((n, K, F))
    O = np.full((n, K), -1e30)
    M = np.zeros((n, K), bool)
    W = np.full((n, 3), -1, int)
    for i, r in enumerate(races):
        m = len(r["nums"])
        X[i, :m] = r["X"]
        O[i, :m] = np.log(r["pm"])
        M[i, :m] = True
        W[i] = r["top3"]
    return X, O, M, W


def _steps(M, W):
    masks, valid = [], []
    cur = M.copy()
    for s in range(3):
        v = W[:, s] >= 0
        masks.append(cur.copy())
        valid.append(v)
        nxt = cur.copy()
        idx = np.where(v)[0]
        nxt[idx, W[idx, s]] = False
        cur = nxt
    return masks, valid


def ll_grad(th, X, O, M, W, lam):
    n = X.shape[0]
    U = O + X @ th
    masks, valid = _steps(M, W)
    ll = 0.0
    g = np.zeros_like(th)
    for s in range(3):
        msk, v = masks[s], valid[s]
        if not v.any():
            continue
        Us = np.where(msk, U, -1e30)
        mx = Us.max(axis=1, keepdims=True)
        ex = np.where(msk, np.exp(Us - mx), 0.0)
        lse = (mx[:, 0] + np.log(ex.sum(axis=1)))
        idx = np.where(v)[0]
        w = W[idx, s]
        ll += float(U[idx, w].sum() - lse[idx].sum())
        P = ex / ex.sum(axis=1, keepdims=True)
        g += X[idx, w, :].sum(axis=0) - np.einsum("nk,nkf->f", P[idx], X[idx])
    pen = lam * n * float(th @ th)
    return ll - pen, g - 2.0 * lam * n * th


def fit_pl(races, lam):
    X, O, M, W = pack(races)
    k = X.shape[2]

    def f(th):
        ll, g = ll_grad(th, X, O, M, W, lam)
        return -ll, -g

    r = minimize(f, np.zeros(k), jac=True, method="L-BFGS-B",
                 options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-10})
    return r.x


def loglik_pl(races, th):
    X, O, M, W = pack(races)
    return ll_grad(th, X, O, M, W, 0.0)[0]


def seg(races, name):
    lo, hi = SPLITS[name]
    return [r for r in races if lo <= r["month"] <= hi]


def rows_of(races):
    """馬単位の行列 (単独検定用)"""
    X, lpm, lbase, y, ridx = [], [], [], [], []
    for i, r in enumerate(races):
        for j, n in enumerate(r["nums"]):
            X.append(r["X"][j])
            lpm.append(math.log(r["pm"][j]))
            lbase.append(math.log(3.0 / r["F"]))
            y.append(r["ytop3"][j])
            ridx.append(i)
    return (np.array(X), np.array(lpm), np.array(lbase),
            np.array(y), np.array(ridx))


# ── 3. mine (MINEのみ・決定はここまで) ────────────────────────────────
def mine():
    races = pickle.load(open(DS, "rb"))
    mine_r = seg(races, "MINE")
    print(f"MINE races={len(mine_r)}")
    out = {}

    # 3-1 単独検定 (MINE列)
    Xf, lpm, lbase, y, _ = rows_of(mine_r)
    B = np.column_stack([np.ones(len(y)), lpm, lbase])
    b0, _, ll0 = logistic(B, y)
    single = {}
    for fi, fname in enumerate(FEATS):
        Xc = np.column_stack([B, Xf[:, fi]])
        b, se, ll = logistic(Xc, y)
        z = float(b[-1] / se[-1]) if se[-1] > 0 else 0.0
        single[fname] = dict(MINE=dict(coef=float(b[-1]), se=float(se[-1]),
                                       z=z, dll=float(ll - ll0), n=int(len(y))),
                             mine_pass=bool(abs(z) >= Z_MINE))
        print(f"  {fname:<12} MINE coef={b[-1]:+.3f} z={z:+.2f} "
              f"dLL={ll - ll0:+.2f} pass={abs(z) >= Z_MINE}")
    out["single_MINE"] = single
    out["mine_rows"] = int(len(y))

    # 3-2 λ CV (レース単位 int(rid)%5)
    cvres = {}
    for lam in LAM_GRID:
        tot, nr = 0.0, 0
        for k in range(NCV):
            tr = [r for r in mine_r if int(r["rid"]) % NCV != k]
            te = [r for r in mine_r if int(r["rid"]) % NCV == k]
            th = fit_pl(tr, lam)
            tot += loglik_pl(te, th)
            nr += len(te)
        cvres[str(lam)] = tot / nr
        print(f"  lam={lam:<7} heldout LL/R={tot / nr:.6f}")
    lam_best = float(max(cvres, key=lambda k: cvres[k]))
    out["cv"] = cvres
    out["lam"] = lam_best
    th = fit_pl(mine_r, lam_best)
    out["theta_MINE"] = [float(v) for v in th]
    ll_mine = loglik_pl(mine_r, th)
    ll_mkt = loglik_pl(mine_r, np.zeros(len(FEATS)))
    out["mine_dll"] = float(ll_mine - ll_mkt)
    out["mine_mkt_llpr"] = float(ll_mkt / len(mine_r))
    print(f"lam={lam_best} theta={np.round(th, 4)} "
          f"MINE dLL={ll_mine - ll_mkt:+.3f} ({len(mine_r)}R)")

    # 3-3 ROI閾値T (MINE・nE_dB>=3 の S 80パーセンタイル)
    S = [max(abs(r["I"]["dB"]), abs(r["I"]["cB"]))
         for r in mine_r if r["nE"]["dB"] >= 3]
    T = float(np.percentile(S, 80))
    out["T"] = T
    out["T_n"] = len(S)
    print(f"T(80pct of S, MINE, nE_dB>=3, n={len(S)}) = {T:.5f}")

    json.dump(out, open(MINE_OUT, "w"), ensure_ascii=False, indent=1)
    print("saved", MINE_OUT)


# ── 4. final (VALIDATE/CONFIRM 各1回だけ) ─────────────────────────────
def final():
    races = pickle.load(open(DS, "rb"))
    mn = json.load(open(MINE_OUT, encoding="utf-8"))
    th = np.array(mn["theta_MINE"])
    T = mn["T"]
    out = dict(protocol="TRACKBIAS_PROTOCOL.md", mine=mn, splits={})
    segs = {s: seg(races, s) for s in SPLITS}
    for s, rr in segs.items():
        out["splits"][s] = dict(races=len(rr),
                                horses=int(sum(len(r["nums"]) for r in rr)))
        print(s, out["splits"][s])

    # 4-1 単独検定 VAL/CONF (MINE通過のみ再推定; 全特徴の数字も記録)
    single = mn["single_MINE"]
    for s in ("VALIDATE", "CONFIRM"):
        Xf, lpm, lbase, y, _ = rows_of(segs[s])
        B = np.column_stack([np.ones(len(y)), lpm, lbase])
        _, _, ll0 = logistic(B, y)
        for fi, fname in enumerate(FEATS):
            Xc = np.column_stack([B, Xf[:, fi]])
            b, se, ll = logistic(Xc, y)
            z = float(b[-1] / se[-1]) if se[-1] > 0 else 0.0
            single[fname][s] = dict(coef=float(b[-1]), z=z,
                                    dll=float(ll - ll0), n=int(len(y)))
    for fname in FEATS:
        rec = single[fname]
        sgn = np.sign(rec["MINE"]["coef"])
        rec["val_pass"] = bool(rec["mine_pass"]
                               and np.sign(rec["VALIDATE"]["coef"]) == sgn
                               and abs(rec["VALIDATE"]["z"]) >= Z_VC)
        rec["conf_pass"] = bool(rec["val_pass"]
                                and np.sign(rec["CONFIRM"]["coef"]) == sgn
                                and abs(rec["CONFIRM"]["z"]) >= Z_VC)
    n_mine = sum(1 for v in single.values() if v["mine_pass"])
    n_val = sum(1 for v in single.values() if v["val_pass"])
    n_conf = sum(1 for v in single.values() if v["conf_pass"])
    out["multiple"] = dict(trials=len(FEATS), mine_pass=n_mine,
                           mine_chance=len(FEATS) * P_Z25,
                           val_pass=n_val, val_chance=n_mine * P_Z20_SIGNED,
                           conf_pass=n_conf)
    out["single"] = single

    # 4-2 一次: 真のOOS ΔLL
    prim = {}
    for s in ("VALIDATE", "CONFIRM"):
        rr = segs[s]
        dll = float(loglik_pl(rr, th) - loglik_pl(rr, np.zeros(len(FEATS))))
        prim[s] = dict(dll=dll, races=len(rr), dll_per_race=dll / len(rr))
        # 記述統計: nE_dB>=4 / <4 の内訳
        hi = [r for r in rr if r["nE"]["dB"] >= 4]
        lo = [r for r in rr if r["nE"]["dB"] < 4]
        for tag, sub in (("nE>=4", hi), ("nE<4", lo)):
            if sub:
                d = float(loglik_pl(sub, th)
                          - loglik_pl(sub, np.zeros(len(FEATS))))
                prim[s][tag] = dict(dll=d, races=len(sub))
        print(f"{s}: OOS dLL={dll:+.3f} ({len(rr)}R)")
    prim["pass"] = bool(prim["VALIDATE"]["dll"] > 0 and prim["CONFIRM"]["dll"] > 0)
    out["primary"] = prim

    # 4-3 ROI (2ルール固定)
    def roi(rr):
        elig = [r for r in rr if r["nE"]["dB"] >= 3
                and max(abs(r["I"]["dB"]), abs(r["I"]["cB"])) >= T]
        r1_cost = r1_ret = r1_hit = 0
        r2_cost = r2_ret = r2_hit = 0
        for r in elig:
            a = r["X"] @ th
            i1 = int(np.argmax(a))
            n1 = r["nums"][i1]
            r1_cost += 100
            if n1 in r["fuku"]:
                r1_ret += r["fuku"][n1]
                r1_hit += 1
            q = np.log(r["pm"]) + r["X"] @ th
            top2 = sorted(np.argsort(-q)[:2].tolist())
            a2, b2 = sorted((r["nums"][top2[0]], r["nums"][top2[1]]))
            key = f"{a2}-{b2}"
            r2_cost += 100
            if key in r["wide"]:
                r2_ret += r["wide"][key]
                r2_hit += 1
        n = len(elig)
        return dict(n=n,
                    R1=dict(cost=r1_cost, ret=r1_ret, hit=r1_hit,
                            roi=r1_ret / r1_cost * 100 if r1_cost else None),
                    R2=dict(cost=r2_cost, ret=r2_ret, hit=r2_hit,
                            roi=r2_ret / r2_cost * 100 if r2_cost else None))

    out["roi"] = {}
    for s in ("MINE", "VALIDATE", "CONFIRM"):
        out["roi"][s] = roi(segs[s])
        print(s, "ROI:", out["roi"][s])

    json.dump(out, open(RESULT, "w"), ensure_ascii=False, indent=1)
    print("saved", RESULT)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build()
    elif cmd == "mine":
        mine()
    elif cmd == "final":
        final()
    else:
        print(__doc__)
