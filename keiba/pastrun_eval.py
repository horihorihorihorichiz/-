# -*- coding: utf-8 -*-
"""過去走「使い残し」特徴の検証 — PASTRUN_PROTOCOL.md の機械適用。

usage:
  python3 pastrun_eval.py build            # 台帳→特徴行列(キャッシュ pastrun_ds.npz)
  python3 pastrun_eval.py test             # 単独検定(MINE/VALIDATE/CONFIRM) → pastrun_result.json
  python3 pastrun_eval.py v9               # V9(V3+通過特徴)のα測定 → pastrun_result.json に追記

既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import glob
import json
import os
import sys

import numpy as np

import pastrun_feats as PF

CACHE = "pastrun_ds.npz"
RESULT = "pastrun_result.json"
SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
Z_MINE, Z_VC = 2.5, 2.0
P_Z25, P_Z20_SIGNED = 0.012419, 0.022750   # 両側P(|z|>=2.5) / 片側P(z>=2.0)


# ── 1. データ構築 ──────────────────────────────────────────────────────
def build():
    files = sorted(glob.glob(os.path.join("hist", "*.json")))
    bench, hdb = PF.AgariBench(), PF.AsOfHorse()
    rows, rid_of, month = [], [], []
    F = len(PF.FEATS)
    nrace = 0
    skipped = {"noresult": 0, "noodds": 0, "fewhorses": 0}
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
        # 日付が進んだら as-of 台帳を確定（当該レースの計算前に前日までを反映）
        bench.feed(date, [])
        hdb.feed(date, [])
        rank = {}
        odds = {}
        for o in order:
            try:
                rank[int(o["num"])] = int(o["rank"])
            except Exception:
                continue
            if o.get("odds"):
                odds[int(o["num"])] = float(o["odds"])
        nums = [h.get("num") for h in horses if h.get("num") is not None]
        ok = (len(nums) >= 5 and all(n in odds and odds[n] > 0 for n in nums)
              and any(rank.get(n) == 1 for n in nums))
        if ok:
            raw = {}
            for h in horses:
                raw[h["num"]] = PF.feats(h, race, bench, hdb)
            Z = {k: PF.z_in_race({n: raw[n][k] for n in raw}) for k in PF.FEATS}
            inv = np.array([1.0 / odds[n] for n in nums])
            pm = inv / inv.sum()
            fld = float(race.get("field") or len(nums))
            for i, n in enumerate(nums):
                rows.append([Z[k][n] for k in PF.FEATS]
                            + [np.log(pm[i]), np.log(3.0 / max(fld, 1.0)),
                               1.0 if rank.get(n) == 1 else 0.0,
                               1.0 if rank.get(n, 99) <= 3 else 0.0,
                               float(nrace), float(n)])
            rid_of.append(rid)
            month.append(date[:6])
            nrace += 1
        else:
            skipped["noodds" if len(nums) >= 5 else "fewhorses"] += 1
        # 当該レース分を台帳に投入（同日の他レースには pend のまま届かない）
        bench.feed(date, [r for h in horses for r in (h.get("races") or [])])
        hdb.feed(date, horses)

    A = np.array(rows, dtype=np.float64)
    np.savez_compressed(CACHE, A=A, feats=np.array(PF.FEATS),
                        month=np.array(month), rid=np.array(rid_of))
    print(f"races={nrace} horses={len(A)} feats={F} skipped={skipped}")
    print("月別:", {m: int((np.array(month) == m).sum()) for m in sorted(set(month))[-8:]})


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
    out = {"splits": {}, "features": {}, "protocol": "PASTRUN_PROTOCOL.md"}
    masks = {s: split_mask(ds, s) for s in SPLITS}
    for s, m in masks.items():
        out["splits"][s] = dict(races=int(len(set(ds["ridx"][m].tolist()))),
                                horses=int(m.sum()))
        print(f"{s}: {out['splits'][s]}")

    res = {}
    for target in ("win", "top3"):
        y = ds["ywin"] if target == "win" else ds["ytop3"]
        B = base_cols(ds, target)
        base = {}
        for s, m in masks.items():
            base[s] = logistic(B[m], y[m])
        for fi, fname in enumerate(feats):
            x = ds["X"][:, fi]
            rec = {}
            for s, m in masks.items():
                Xf = np.column_stack([B[m], x[m]])
                b, se, ll = logistic(Xf, y[m])
                rec[s] = dict(coef=float(b[-1]), se=float(se[-1]),
                              z=float(b[-1] / se[-1]) if se[-1] > 0 else 0.0,
                              dll=float(ll - base[s][2]), n=int(m.sum()))
            # MINE係数をそのまま当てたOOS ΔLL（参考）
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
    print(f"\n試行={n_trials} MINE通過={n_mine}(偶然期待{n_trials*P_Z25:.2f}) "
          f"VAL通過={n_val}(偶然期待{n_mine*P_Z20_SIGNED:.2f}) CONF通過={n_conf} "
          f"バッチ判定={'OK' if out['multiple']['batch_ok'] else 'FAIL'}")
    print(f"\n{'特徴':<18}{'目的':<6}{'MINE z':>9}{'ΔLL':>9}{'VAL z':>8}{'CONF z':>8}  判定")
    for k, v in sorted(res.items(), key=lambda kv: -abs(kv[1]["MINE"]["z"])):
        fn, tg = k.split("|")
        mark = ("合格" if v["conf_pass"] else "VAL通過" if v["val_pass"]
                else "MINE通過" if v["mine_pass"] else "")
        print(f"{fn:<18}{tg:<6}{v['MINE']['z']:>9.2f}{v['MINE']['dll']:>9.1f}"
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
    elif cmd == "v9":
        import pastrun_v9
        pastrun_v9.main()
    else:
        print(__doc__)
