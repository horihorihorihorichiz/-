# -*- coding: utf-8 -*-
"""市場条件付きモデル（V3非経由）の検証 — MKTCOND_PROTOCOL.md の機械適用。

  u_i = log(pm_i) + x_i·θ        （市場はオフセット・係数1固定）
  q_i = softmax(u) over race     （条件付きロジット・レース内正規化）
  目的 = 3着内の並び（Plackett-Luce 3段展開）

usage:
  python3 mktcond_eval.py build    # 台帳→データ(mktcond_ds.pkl)
  python3 mktcond_eval.py run      # λのCV→θ→OOS ΔLL→α→複勝ROI → mktcond_result.json

既存ファイルは一切変更していない（本ファイルは新規・独立）。git commit はしない。
"""
import glob
import json
import math
import os
import pickle
import sys

import numpy as np
from scipy.optimize import minimize

import corner_feats as CF

DS = "mktcond_ds.pkl"
RESULT = "mktcond_result.json"
FEATS = ["spd_res", "mgn_abs", "wide4c", "pos_gain"]     # CORNER で3段通過した4本のみ
SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
FOLDS = ["202603", "202604", "202605", "202606", "202607", "202608"]
LAM_GRID = [0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0]
NCV = 5
EXC = dict(fav_p=0.341, ent=1.904, sgap=0.066)           # 既存の例外除外条件（確定済み）
# 三次の買い方は「モデルP3上位3頭の三連複1点」に固定（探索なし・試行数0）


# ── 1. データ構築（CORNER と同一の as-of 経路・同一の採用条件） ──────────
def build():
    files = sorted(glob.glob(os.path.join("hist", "*.json")))
    sb = CF.SpeedBench()
    recs = []
    for fp in files:
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        recs.append((d.get("date", ""), os.path.basename(fp)[:-5], d))
    recs.sort(key=lambda x: (x[0], x[1]))

    out = []
    for date, rid, d in recs:
        race, res = d.get("race") or {}, d.get("result") or {}
        horses = race.get("horses") or []
        order = res.get("order") or []
        sb.feed(date, [])
        rank, odds = {}, {}
        for o in order:
            try:
                rank[int(o["num"])] = int(o["rank"])
            except Exception:
                continue
            if o.get("odds"):
                odds[int(o["num"])] = float(o["odds"])
        nums = [h.get("num") for h in horses if h.get("num") is not None]
        have_id = bool(horses) and all(h.get("horse_id") for h in horses)
        have_new = any(r.get("corner_all") for h in horses for r in (h.get("races") or []))
        ok = (len(nums) >= 5 and all(n in odds and odds[n] > 0 for n in nums)
              and any(rank.get(n) == 1 for n in nums))
        if ok and have_id and have_new:
            raw = {h["num"]: CF.feats(h, race, sb) for h in horses}
            Z = {k: CF.z_in_race({n: raw[n][k] for n in raw}) for k in CF.FEATS}
            inv = np.array([1.0 / odds[n] for n in nums])
            pm = inv / inv.sum()
            X = np.array([[Z[k][n] for k in FEATS] for n in nums], dtype=np.float64)
            top3 = []
            for want in (1, 2, 3):
                hit = [i for i, n in enumerate(nums) if rank.get(n) == want]
                top3.append(hit[0] if len(hit) == 1 else -1)
            pay = res.get("payout") or {}
            fuku = pay.get("複勝") or {}
            san = pay.get("三連複") or {}
            out.append(dict(rid=rid, month=date[:6], nums=nums, X=X, pm=pm,
                            top3=top3, fuku={int(k): v for k, v in fuku.items()},
                            san={k: float(v) for k, v in san.items()}))
        sb.feed(date, [r for h in horses for r in (h.get("races") or [])])

    pickle.dump(out, open(DS, "wb"))
    frozen = json.load(open("corner_frozen_ids.json", encoding="utf-8"))["rid"]
    same = set(r["rid"] for r in out) == set(frozen)
    print(f"races={len(out)}  corner_frozen_ids と一致={same}")
    full3 = sum(1 for r in out if all(i >= 0 for i in r["top3"]))
    print(f"1-3着すべて特定できたレース={full3} / {len(out)}")
    print("月別:", {m: sum(1 for r in out if r['month'] == m)
                    for m in sorted({r['month'] for r in out})})


# ── 2. 行列化（Plackett-Luce 3段のためのマスク） ────────────────────────
def pack(races, feats_dim=None):
    n = len(races)
    K = max(len(r["nums"]) for r in races)
    F = races[0]["X"].shape[1] if feats_dim is None else feats_dim
    X = np.zeros((n, K, F))
    O = np.full((n, K), -1e30)
    M = np.zeros((n, K), bool)
    W = np.full((n, 3), -1, int)
    for i, r in enumerate(races):
        m = len(r["nums"])
        X[i, :m] = r["X"][:, :F]
        O[i, :m] = np.log(r["pm"])
        M[i, :m] = True
        W[i] = r["top3"]
    return X, O, M, W


def _steps(M, W):
    """3段それぞれの候補マスクと有効フラグ"""
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
    """Plackett-Luce 3段の対数尤度と勾配（θのみ。オフセットは係数1固定）"""
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


def fit(races, lam, F=None):
    X, O, M, W = pack(races, F)
    k = X.shape[2]

    def f(th):
        ll, g = ll_grad(th, X, O, M, W, lam)
        return -ll, -g

    r = minimize(f, np.zeros(k), jac=True, method="L-BFGS-B",
                 options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-10})
    return r.x


def loglik(races, th, F=None):
    X, O, M, W = pack(races, F)
    return ll_grad(th, X, O, M, W, 0.0)[0]


# ── 3. Harville で3着内確率 ────────────────────────────────────────────
def harville_top3(q):
    q = np.clip(np.asarray(q, dtype=np.float64), 1e-12, 1 - 1e-12)
    q = q / q.sum()
    n = len(q)
    d1 = np.clip(1.0 - q, 1e-9, None)                     # 1 - q_j
    a = q / d1                                            # q_j/(1-q_j)
    A = a.sum() - a                                       # Σ_{j≠i}
    d2 = np.clip(1.0 - q[:, None] - q[None, :], 1e-9, None)   # 1 - q_j - q_k
    Mjk = (q[:, None] / d1[:, None]) * (q[None, :] / d2)      # j 1着, k 2着
    np.fill_diagonal(Mjk, 0.0)
    S = Mjk.sum()
    R = Mjk.sum(axis=1)
    C = Mjk.sum(axis=0)
    B = S - R - C
    p3 = q * (1.0 + A + B)
    return np.clip(p3, 0.0, 1.0)


# ── 4. 本体 ───────────────────────────────────────────────────────────
def seg(races, name):
    lo, hi = SPLITS[name]
    return [r for r in races if lo <= r["month"] <= hi]


def cv_lambda(mine):
    """MINE 内部5分割CV（レース単位・rid のハッシュで固定）"""
    fold = np.array([int(r["rid"]) % NCV for r in mine])
    res = {}
    for lam in LAM_GRID:
        tot, nn = 0.0, 0
        for f in range(NCV):
            tr = [r for r, x in zip(mine, fold) if x != f]
            te = [r for r, x in zip(mine, fold) if x == f]
            th = fit(tr, lam)
            tot += loglik(te, th)
            nn += len(te)
        res[lam] = tot / nn
        print(f"  λ={lam:<7} held-out LL/R = {res[lam]:.6f}")
    best = max(res, key=res.get)
    print(f"  → 選択 λ={best}")
    return best, res


def roi_sanrenpuku(races, key="p3"):
    """三連複1点買いのROI。P3上位3頭の組み合わせを1点だけ買う。"""
    n_r = hit = 0
    payout = 0.0
    for r in races:
        if not r.get("san") or len(r["nums"]) < 3:
            continue
        top = np.argsort(-r[key])[:3]
        k = "-".join(str(x) for x in sorted(r["nums"][i] for i in top))
        n_r += 1
        v = r["san"].get(k)
        if v:
            payout += float(v)
            hit += 1
    if not n_r:
        return dict(n_races=0, n_bets=0, roi=0.0, hit=0.0, avg_pay=0.0)
    return dict(n_races=n_r, n_bets=n_r, roi=payout / (100.0 * n_r) * 100.0,
                hit=hit / n_r * 100.0,
                avg_pay=(payout / hit) if hit else 0.0)


def main():
    races = pickle.load(open(DS, "rb"))
    for r in races:
        r["_int"] = None
    out = {"protocol": "MKTCOND_PROTOCOL.md", "feats": FEATS}

    mine, val, conf = seg(races, "MINE"), seg(races, "VALIDATE"), seg(races, "CONFIRM")
    out["n"] = {k: len(v) for k, v in
                (("MINE", mine), ("VALIDATE", val), ("CONFIRM", conf))}
    print(f"MINE={len(mine)}R VALIDATE={len(val)}R CONFIRM={len(conf)}R")

    print("\n── λ の内部CV（MINEのみ） ──")
    lam, cvres = cv_lambda(mine)
    out["lambda"] = lam
    out["cv"] = {str(k): v for k, v in cvres.items()}

    th = fit(mine, lam)
    out["theta_MINE"] = dict(zip(FEATS, th.tolist()))
    print(f"\nθ(MINE) = " + "  ".join(f"{k}={v:+.4f}" for k, v in zip(FEATS, th)))

    # 3-0-1 符号一致（VAL / CONF 単独で再推定）
    signs = {}
    for nm, ss in (("VALIDATE", val), ("CONFIRM", conf)):
        t = fit(ss, lam)
        signs[nm] = dict(theta=dict(zip(FEATS, t.tolist())),
                         agree={f: bool(np.sign(a) == np.sign(b) and a != 0)
                                for f, a, b in zip(FEATS, th, t)})
        print(f"θ({nm})   = " + "  ".join(f"{k}={v:+.4f}" for k, v in zip(FEATS, t))
              + "  符号一致=" + "".join("○" if signs[nm]["agree"][f] else "×" for f in FEATS))
    out["sign_check"] = signs

    # 3-0-2 真のOOS ΔLL
    zero = np.zeros(len(FEATS))
    dll = {}
    for nm, ss in (("MINE", mine), ("VALIDATE", val), ("CONFIRM", conf)):
        d = loglik(ss, th) - loglik(ss, zero)
        dll[nm] = dict(dll=float(d), n_races=len(ss), per_race=float(d / len(ss)))
        tag = "（期内）" if nm == "MINE" else "（真のOOS）"
        print(f"ΔLL {nm}{tag} = {d:+.3f} nats / {len(ss)}R = {d/len(ss):+.5f}/R")
    out["delta_ll"] = dll
    out["primary_pass"] = bool(dll["VALIDATE"]["dll"] > 0 and dll["CONFIRM"]["dll"] > 0)
    print(f"一次判定（VAL ΔLL>0 かつ CONF ΔLL>0）= "
          f"{'合格' if out['primary_pass'] else '不合格'}")

    # 3-0-3 α（追加項を1本のスコアにまとめる）
    print("\n── α（フォールド別・s = x·θ_MINE を1列で再推定） ──")
    alphas = {}
    for m in FOLDS:
        ss = [r for r in races if r["month"] == m]
        if not ss:
            continue
        sub = [dict(nums=r["nums"], pm=r["pm"], top3=r["top3"],
                    X=(r["X"] @ th).reshape(-1, 1)) for r in ss]
        a = fit(sub, 0.0, F=1)[0]
        d = loglik(sub, np.array([a]), F=1) - loglik(sub, np.array([0.0]), F=1)
        alphas[m] = dict(alpha=float(a), n=len(ss), dll_infold=float(d))
        print(f"  {m}: n={len(ss):4d}R  α={a:+.4f}  期内ΔLL={d:+.3f}")
    out["alpha"] = alphas
    av = [v["alpha"] for v in alphas.values()]
    out["secondary_pass"] = bool(len(av) == len(FOLDS) and all(a > 0 for a in av))
    print(f"二次判定（α>0 が6フォールド全部）= "
          f"{'合格' if out['secondary_pass'] else '不合格'}"
          f"（正 {sum(1 for a in av if a>0)}/{len(av)}）")

    # ── 三次: 例外除外レースでの三連複1点ROI（2026-08-19 差し替え） ──
    print("\n── 三次: 例外除外(A∧B∧C)レースでの三連複1点ROI ──")
    wf = {}
    for line in open("wf_preds_v3ext2.jsonl", encoding="utf-8"):
        d = json.loads(line)
        o = d.get("odds") or {}
        if len(o) < 5:
            continue
        v = {k: 1.0 / float(x) for k, x in o.items() if x and float(x) > 0}
        s = sum(v.values())
        p = sorted((x / s for x in v.values()), reverse=True)
        ent = -sum(x * math.log(x) for x in p)
        sc = d.get("scores") or []
        wf[d["rid"]] = dict(fav_p=p[0], ent=ent,
                            sgap=(sc[0] - sc[1]) if len(sc) > 1 else 0.0)
    keep = []
    for r in races:
        w = wf.get(r["rid"])
        if not w:
            continue
        if (w["fav_p"] >= EXC["fav_p"] and w["ent"] <= EXC["ent"]
                and w["sgap"] >= EXC["sgap"]):
            q = np.exp(np.log(r["pm"]) + r["X"] @ th)
            q = q / q.sum()
            r["p3"] = harville_top3(q)
            r["p3m"] = harville_top3(r["pm"])
            keep.append(r)
    km, kv, kc = seg(keep, "MINE"), seg(keep, "VALIDATE"), seg(keep, "CONFIRM")
    out["exclusion"] = dict(n_common=len({r["rid"] for r in races} & set(wf)),
                            MINE=len(km), VALIDATE=len(kv), CONFIRM=len(kc))
    print(f"A∧B∧C 残存: MINE={len(km)}R VALIDATE={len(kv)}R CONFIRM={len(kc)}R")

    # 買い方の探索は無し（試行数0）。モデル P3 上位3頭の三連複1点に固定。
    out["roi_trials"] = 0
    fin = {}
    for nm, ss in (("MINE", km), ("VALIDATE", kv), ("CONFIRM", kc)):
        s = roi_sanrenpuku(ss, "p3")
        b = roi_sanrenpuku(ss, "p3m")
        fin[nm] = dict(model=s, market=b)
        print(f"  {nm:<9} n={s['n_races']:>4}R  三連複ROI {s['roi']:>6.1f}% "
              f"的中 {s['hit']:>5.1f}% 平均配当 {s['avg_pay']:>7.0f}円   "
              f"[市場のみ(θ=0): ROI {b['roi']:.1f}% 的中 {b['hit']:.1f}%]")
    out["roi_final"] = fin
    out["tertiary_pass"] = bool(fin["VALIDATE"]["model"]["roi"] > 100.0
                                and fin["CONFIRM"]["model"]["roi"] > 100.0
                                and fin["VALIDATE"]["model"]["n_races"] >= 80
                                and fin["CONFIRM"]["model"]["n_races"] >= 80)
    print(f"三次判定（VAL/CONF 両方で三連複ROI>100% かつ n>=80R）= "
          f"{'合格' if out['tertiary_pass'] else '不合格'}")

    out["overall_pass"] = bool(out["primary_pass"] and out["secondary_pass"]
                               and out.get("tertiary_pass"))
    print(f"\n総合判定 = {'合格' if out['overall_pass'] else '不合格'}")
    json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {RESULT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "build":
        build()
    elif cmd == "run":
        main()
    else:
        print(__doc__)
