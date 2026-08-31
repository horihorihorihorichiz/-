# -*- coding: utf-8 -*-
"""再収穫4項目から作った10特徴の検証 — CORNER_PROTOCOL.md の機械適用。

usage:
  python3 corner_eval.py build     # 台帳→特徴行列(キャッシュ corner_ds.npz)
  python3 corner_eval.py test      # 単独検定(MINE/VALIDATE/CONFIRM) → corner_result.json
  python3 corner_eval.py v10       # V10(V3+通過特徴)のα測定 → corner_result.json に追記

既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import glob
import json
import os
import sys

import numpy as np

import corner_feats as CF

CACHE = "corner_ds.npz"
RESULT = "corner_result.json"
FROZEN = "corner_frozen_ids.json"
SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
Z_MINE, Z_VC = 2.5, 2.0
P_Z25, P_Z20_SIGNED = 0.012419, 0.022750


# ── 1. データ構築 ──────────────────────────────────────────────────────
def build():
    files = sorted(glob.glob(os.path.join("hist", "*.json")))
    sb = CF.SpeedBench()
    rows, rid_of, month = [], [], []
    F = len(CF.FEATS)
    nrace = 0
    skipped = {"noresult": 0, "noodds": 0, "fewhorses": 0, "nocorner": 0}
    recs = []
    for fp in files:
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            skipped["noresult"] += 1
            continue
        recs.append((d.get("date", ""), os.path.basename(fp)[:-5], d))
    recs.sort(key=lambda x: (x[0], x[1]))

    for date, rid, d in recs:
        race, res = d.get("race") or {}, d.get("result") or {}
        horses = race.get("horses") or []
        order = res.get("order") or []
        sb.feed(date, [])          # 当該レース計算前に前日までを確定
        rank, odds = {}, {}
        for o in order:
            try:
                rank[int(o["num"])] = int(o["rank"])
            except Exception:
                continue
            if o.get("odds"):
                odds[int(o["num"])] = float(o["odds"])
        nums = [h.get("num") for h in horses if h.get("num") is not None]
        # 再収穫済み判定（CORNER_PROTOCOL §3-1）
        have_id = bool(horses) and all(h.get("horse_id") for h in horses)
        have_new = any(r.get("corner_all") for h in horses for r in (h.get("races") or []))
        ok = (len(nums) >= 5 and all(n in odds and odds[n] > 0 for n in nums)
              and any(rank.get(n) == 1 for n in nums))
        if ok and have_id and have_new:
            raw = {h["num"]: CF.feats(h, race, sb) for h in horses}
            Z = {k: CF.z_in_race({n: raw[n][k] for n in raw}) for k in CF.FEATS}
            inv = np.array([1.0 / odds[n] for n in nums])
            pm = inv / inv.sum()
            fld = float(race.get("field") or len(nums))
            for i, n in enumerate(nums):
                rows.append([Z[k][n] for k in CF.FEATS]
                            + [np.log(pm[i]), np.log(3.0 / max(fld, 1.0)),
                               1.0 if rank.get(n) == 1 else 0.0,
                               1.0 if rank.get(n, 99) <= 3 else 0.0,
                               float(nrace), float(n)])
            rid_of.append(rid)
            month.append(date[:6])
            nrace += 1
        elif not ok:
            skipped["noodds" if len(nums) >= 5 else "fewhorses"] += 1
        else:
            skipped["nocorner"] += 1
        sb.feed(date, [r for h in horses for r in (h.get("races") or [])])

    A = np.array(rows, dtype=np.float64)
    np.savez_compressed(CACHE, A=A, feats=np.array(CF.FEATS),
                        month=np.array(month), rid=np.array(rid_of))
    json.dump({"n_races": nrace, "rid": rid_of},
              open(FROZEN, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"races={nrace} horses={len(A)} feats={F} skipped={skipped}")
    cov = {}
    for k in CF.FEATS:
        i = CF.FEATS.index(k)
        cov[k] = float(np.mean(A[:, i] != 0.0)) if len(A) else 0.0
    print("非ゼロ率(=値が作れた馬の割合の目安):",
          {k: round(v, 3) for k, v in cov.items()})
    print("月別R:", {m: int((np.array(month) == m).sum()) for m in sorted(set(month))})


def load():
    z = np.load(CACHE, allow_pickle=False)
    A, feats, month = z["A"], list(z["feats"]), z["month"]
    F = len(feats)
    return dict(X=A[:, :F], logpm=A[:, F], logbase=A[:, F + 1],
                ywin=A[:, F + 2], ytop3=A[:, F + 3],
                ridx=A[:, F + 4].astype(int), num=A[:, F + 5].astype(int),
                rid=z["rid"], feats=feats, month=month)


# ── 2. ロジスティック回帰（Newton-Raphson・SE付き） ──────────────────────
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


def loglik(X, y, b):
    p = 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))
    return float(np.sum(y * np.log(np.clip(p, 1e-12, 1)) +
                        (1 - y) * np.log(np.clip(1 - p, 1e-12, 1))))


def split_mask(ds, name):
    lo, hi = SPLITS[name]
    m = np.array([lo <= x <= hi for x in ds["month"]])
    return m[ds["ridx"]]


def base_cols(ds, target):
    one = np.ones(len(ds["logpm"]))
    if target == "win":
        return np.column_stack([one, ds["logpm"]])
    return np.column_stack([one, ds["logpm"], ds["logbase"]])


# ── 3. 単独検定 ────────────────────────────────────────────────────────
def test():
    ds = load()
    feats = ds["feats"]
    out = {"splits": {}, "features": {}, "protocol": "CORNER_PROTOCOL.md"}
    masks = {s: split_mask(ds, s) for s in SPLITS}
    for s, m in masks.items():
        out["splits"][s] = dict(races=int(len(set(ds["ridx"][m].tolist()))),
                                horses=int(m.sum()))
        print(f"{s}: {out['splits'][s]}")

    res = {}
    for target in ("win", "top3"):
        y = ds["ywin"] if target == "win" else ds["ytop3"]
        B = base_cols(ds, target)
        base = {s: logistic(B[m], y[m]) for s, m in masks.items()}
        for fi, fname in enumerate(feats):
            x = ds["X"][:, fi]
            rec = {}
            for s, m in masks.items():
                Xf = np.column_stack([B[m], x[m]])
                b, se, ll = logistic(Xf, y[m])
                rec[s] = dict(coef=float(b[-1]), se=float(se[-1]),
                              z=float(b[-1] / se[-1]) if se[-1] > 0 else 0.0,
                              dll=float(ll - base[s][2]), n=int(m.sum()))
            bm = np.column_stack([B[masks["MINE"]], x[masks["MINE"]]])
            bmine = logistic(bm, y[masks["MINE"]])[0]
            for s in ("VALIDATE", "CONFIRM"):
                m = masks[s]
                Xf = np.column_stack([B[m], x[m]])
                rec[s]["oos_dll"] = float(loglik(Xf, y[m], bmine)
                                          - loglik(B[m], y[m], base["MINE"][0]))
            rec["mine_pass"] = bool(abs(rec["MINE"]["z"]) >= Z_MINE)
            sgn = np.sign(rec["MINE"]["coef"])
            rec["val_pass"] = bool(rec["mine_pass"]
                                   and np.sign(rec["VALIDATE"]["coef"]) == sgn
                                   and abs(rec["VALIDATE"]["z"]) >= Z_VC)
            rec["conf_pass"] = bool(rec["val_pass"]
                                    and np.sign(rec["CONFIRM"]["coef"]) == sgn
                                    and abs(rec["CONFIRM"]["z"]) >= Z_VC)
            res[f"{fname}|{target}"] = rec
    out["features"] = res

    n_trials = len(feats) * 2
    n_mine = sum(1 for v in res.values() if v["mine_pass"])
    n_val = sum(1 for v in res.values() if v["val_pass"])
    n_conf = sum(1 for v in res.values() if v["conf_pass"])
    out["multiple"] = dict(trials=n_trials,
                           mine_pass=n_mine, mine_chance=n_trials * P_Z25,
                           val_pass=n_val, val_chance=n_mine * P_Z20_SIGNED,
                           conf_pass=n_conf,
                           batch_ok=bool(n_val >= 3 * n_mine * P_Z20_SIGNED and n_val > 0))
    print(f"\n試行={n_trials} MINE通過={n_mine}(偶然期待{n_trials*P_Z25:.3f}) "
          f"VAL通過={n_val}(偶然期待{n_mine*P_Z20_SIGNED:.3f}) CONF通過={n_conf} "
          f"バッチ判定={'OK' if out['multiple']['batch_ok'] else 'FAIL'}")
    print(f"\n{'特徴':<12}{'目的':<6}{'MINE z':>9}{'ΔLL':>9}{'VAL z':>8}{'CONF z':>8}  判定")
    for k, v in sorted(res.items(), key=lambda kv: -abs(kv[1]["MINE"]["z"])):
        fn, tg = k.split("|")
        mark = ("合格" if v["conf_pass"] else "VAL通過" if v["val_pass"]
                else "MINE通過" if v["mine_pass"] else "")
        print(f"{fn:<12}{tg:<6}{v['MINE']['z']:>9.2f}{v['MINE']['dll']:>9.1f}"
              f"{v['VALIDATE']['z']:>8.2f}{v['CONFIRM']['z']:>8.2f}  {mark}")
    old = json.load(open(RESULT, encoding="utf-8")) if os.path.exists(RESULT) else {}
    old.update(out)
    json.dump(old, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n→ {RESULT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "build":
        build()
    elif cmd == "test":
        test()
    elif cmd == "v10":
        import corner_v10
        corner_v10.main()
    else:
        print(__doc__)
