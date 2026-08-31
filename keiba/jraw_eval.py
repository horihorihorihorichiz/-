# -*- coding: utf-8 -*-
"""騎手・斤量の「生の変化」検証 — JOCKEY_RAW_PROTOCOL.md の機械適用。

usage:
  python3 jraw_eval.py build    # hist + jockey_fill.json → jraw_ds.npz（被覆率も出力）
  python3 jraw_eval.py test     # 条件付きロジット MINE/VAL/CONF → jraw_result.json
  python3 jraw_eval.py diag     # 合格特徴の permutation 較正 + jchg×jexp クロス表

既存ファイル（本番エンジン・hist/）は一切変更しない。
"""
import datetime
import glob
import json
import os
import sys

import numpy as np

CACHE = "jraw_ds.npz"
RESULT = "jraw_result.json"
FILL = "jockey_fill.json"
FEATS = ["jchg", "jexp", "kin_chg", "wchg", "wx"]
CTRLS = ["c_wchg", "c_ldays"]          # wx検定の統制主効果
SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
Z_MINE = 2.5


def prev_date(datestr, k):
    dt = datetime.date(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:8]))
    return (dt - datetime.timedelta(days=int(k))).strftime("%Y%m%d")


# ── build ──────────────────────────────────────────────────────────────
def build():
    fill = json.load(open(FILL, encoding="utf-8")) if os.path.exists(FILL) else {}
    recs = []
    for fp in sorted(glob.glob(os.path.join("hist", "*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        recs.append((d.get("date", ""), os.path.basename(fp)[:-5], d))
    recs.sort(key=lambda x: (x[0], x[1]))

    # 騎手ID: hist優先、無ければ fill
    def jk_of(rid, h):
        j = h.get("jockey_id")
        if j:
            return j
        return (fill.get(rid) or {}).get(str(h.get("num")))

    # index (date, horse_id) -> (jockey_id, kinryo)   ※参照は date < today のみ
    idx = {}
    # horse_id -> list of (date, jockey_id)  騎乗経験用
    rides = {}
    for date, rid, d in recs:
        for h in d["race"].get("horses") or []:
            hid = h.get("horse_id")
            if not hid:
                continue
            jk = jk_of(rid, h)
            idx[(date, hid)] = (jk, h.get("kinryo"))
            rides.setdefault(hid, []).append((date, jk))

    rows, rid_of, month = [], [], []
    xtab = {"chg_exp": 0, "chg_noexp": 0, "same_exp": 0, "same_noexp": 0}
    nrace = 0
    ncov = {k: 0 for k in FEATS}
    ncov_split = {s: {k: 0 for k in FEATS} for s in SPLITS}
    nrow_split = {s: 0 for s in SPLITS}
    skipped = {"fewhorses": 0, "noodds": 0, "nowinner": 0}
    for date, rid, d in recs:
        race, res = d.get("race") or {}, d.get("result") or {}
        horses = race.get("horses") or []
        order = res.get("order") or []
        rank, odds = {}, {}
        for o in order:
            try:
                rank[int(o["num"])] = int(o["rank"])
            except Exception:
                continue
            if o.get("odds"):
                odds[int(o["num"])] = float(o["odds"])
        nums = [h.get("num") for h in horses if h.get("num") is not None]
        if len(nums) < 5:
            skipped["fewhorses"] += 1
            continue
        if not all(n in odds and odds[n] > 0 for n in nums):
            skipped["noodds"] += 1
            continue
        if not any(rank.get(n) == 1 for n in nums):
            skipped["nowinner"] += 1
            continue
        m = date[:6]
        sp = next((s for s, (lo, hi) in SPLITS.items() if lo <= m <= hi), None)

        raw = {}
        for h in horses:
            hid = h.get("horse_id")
            jk = jk_of(rid, h)
            lrd = h.get("last_race_days")
            kin = h.get("kinryo")
            wc = h.get("weight_change")
            wt = h.get("weight")
            n_past = len(h.get("races") or [])
            pj = pk = None
            if hid and lrd is not None and lrd > 0:
                pd_ = prev_date(date, lrd)
                if (pd_, hid) in idx:
                    pj, pk = idx[(pd_, hid)]
            f = {}
            # jchg
            f["jchg"] = (None if (pj is None or jk is None)
                         else (1.0 if pj != jk else 0.0))
            # jexp: date より前の hist 出走に今回騎手が登場するか
            f["jexp"] = None
            if hid and jk is not None:
                past = [(dt, j) for dt, j in rides.get(hid, []) if dt < date]
                if past:
                    f["jexp"] = 1.0 if any(j == jk for _, j in past) else 0.0
            # kin_chg
            f["kin_chg"] = (None if (pk is None or kin is None)
                            else float(np.clip(kin - pk, -4, 4)))
            # wchg / wx
            if wt and n_past >= 1 and wc is not None:
                wcl = float(np.clip(wc, -30, 30))
                f["wchg"] = wcl
                if lrd is not None and lrd >= 1:
                    f["wx"] = (wcl / 10.0) * float(np.log(max(lrd, 7) / 28.0))
                    f["c_ldays"] = float(np.log(max(lrd, 1)))
                else:
                    f["wx"] = None
                    f["c_ldays"] = None
                f["c_wchg"] = wcl
            else:
                f["wchg"] = f["wx"] = f["c_wchg"] = f["c_ldays"] = None
            if f["jchg"] is not None and f["jexp"] is not None:
                key = ("chg_" if f["jchg"] else "same_") + \
                      ("exp" if f["jexp"] else "noexp")
                xtab[key] += 1
            raw[h["num"]] = f

        # レース内中心化（定義済みの平均を引く・欠損=0）
        cen = {}
        for k in FEATS + CTRLS:
            vals = [raw[n][k] for n in raw if raw[n][k] is not None]
            mu = float(np.mean(vals)) if vals else 0.0
            cen[k] = {n: (raw[n][k] - mu if raw[n][k] is not None else 0.0)
                      for n in raw}
            if k in FEATS:
                ncov[k] += len(vals)
                if sp:
                    ncov_split[sp][k] += len(vals)
        if sp:
            nrow_split[sp] += len(nums)

        inv = np.array([1.0 / odds[n] for n in nums])
        pm = inv / inv.sum()
        for i, n in enumerate(nums):
            rows.append([cen[k][n] for k in FEATS + CTRLS]
                        + [float(np.log(pm[i])),
                           1.0 if rank.get(n) == 1 else 0.0]
                        + [1.0 if raw[n][k] is not None else 0.0 for k in FEATS]
                        + [float(nrace), float(n)])
        rid_of.append(rid)
        month.append(m)
        nrace += 1

    A = np.array(rows, dtype=np.float64)
    np.savez_compressed(CACHE, A=A, feats=np.array(FEATS + CTRLS),
                        month=np.array(month), rid=np.array(rid_of))
    nrow = len(A)
    print(f"races={nrace} horses={nrow} skipped={skipped}")
    cov_all = {k: ncov[k] / nrow for k in FEATS}
    print("被覆率(全体):", {k: round(v, 3) for k, v in cov_all.items()})
    covs = {}
    for s in SPLITS:
        covs[s] = {k: (ncov_split[s][k] / nrow_split[s] if nrow_split[s] else 0.0)
                   for k in FEATS}
        print(f"被覆率({s}, rows={nrow_split[s]}):",
              {k: round(v, 3) for k, v in covs[s].items()})
    print("jchg×jexp:", xtab)
    out = {"xtab": xtab, "coverage_all": cov_all, "coverage_split": covs,
           "rows_split": nrow_split, "n_races": nrace, "n_rows": nrow,
           "measurable": {k: bool(all(covs[s][k] >= 0.5 for s in SPLITS))
                          for k in FEATS}}
    print("測定可能(被覆50%以上 in 全分割):", out["measurable"])
    old = json.load(open(RESULT, encoding="utf-8")) if os.path.exists(RESULT) else {}
    old["build"] = out
    json.dump(old, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load():
    z = np.load(CACHE, allow_pickle=False)
    A = z["A"]
    F = len(FEATS) + len(CTRLS)
    names = FEATS + CTRLS
    X = {names[i]: A[:, i] for i in range(F)}
    defs = {FEATS[i]: A[:, F + 2 + i] for i in range(len(FEATS))}
    return dict(X=X, logpm=A[:, F], ywin=A[:, F + 1], defs=defs,
                ridx=A[:, F + 7].astype(int), num=A[:, F + 8].astype(int),
                month=z["month"], rid=z["rid"])


# ── 条件付きロジット（offset=logpm固定） ────────────────────────────────
def cl_fit(Xc, logpm, ridx, ywin, iters=50):
    """P(i wins) = softmax(logpm + Xc @ b). returns b, se, ll, ll0."""
    n, k = Xc.shape
    order = np.argsort(ridx, kind="stable")
    Xs, off, ys, rs = Xc[order], logpm[order], ywin[order], ridx[order]
    starts = np.searchsorted(rs, np.unique(rs))
    bounds = np.append(starts, n)
    b = np.zeros(k)

    def ll_of(bv):
        eta = off + Xs @ bv
        ll = 0.0
        for a, z in zip(bounds[:-1], bounds[1:]):
            e = eta[a:z]
            m = e.max()
            ll += float(e[ys[a:z] == 1][0] - (m + np.log(np.exp(e - m).sum())))
        return ll

    ll0 = ll_of(np.zeros(k))
    H = np.eye(k)
    for _ in range(iters):
        eta = off + Xs @ b
        g = np.zeros(k)
        H = np.zeros((k, k))
        for a, z in zip(bounds[:-1], bounds[1:]):
            e = eta[a:z]
            m = e.max()
            p = np.exp(e - m)
            p /= p.sum()
            xr = Xs[a:z]
            xw = xr[ys[a:z] == 1][0]
            mu = p @ xr
            g += xw - mu
            H += (xr * p[:, None]).T @ xr - np.outer(mu, mu)
        H += np.eye(k) * 1e-9
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        b = b + step
        if np.abs(step).max() < 1e-10:
            break
    ll = ll_of(b)
    cov = np.linalg.inv(H)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    return b, se, ll, ll0, ll_of


def split_mask(ds, name):
    lo, hi = SPLITS[name]
    m = np.array([lo <= x <= hi for x in ds["month"]])
    return m[ds["ridx"]]


def test():
    ds = load()
    out = json.load(open(RESULT, encoding="utf-8"))
    masks = {s: split_mask(ds, s) for s in SPLITS}
    for s, m in masks.items():
        print(f"{s}: races={len(set(ds['ridx'][m].tolist()))} horses={int(m.sum())}")

    res = {}
    for fname in FEATS:
        cols = ([ds["X"]["c_wchg"], ds["X"]["c_ldays"], ds["X"]["wx"]]
                if fname == "wx" else [ds["X"][fname]])
        Xc = np.column_stack(cols)
        rec = {}
        fits = {}
        for s, m in masks.items():
            b, se, ll, ll0, _ = cl_fit(Xc[m], ds["logpm"][m], ds["ridx"][m],
                                       ds["ywin"][m])
            if fname == "wx":
                # 増分は主効果のみモデルとの差
                bm, _, llm, _, _ = cl_fit(Xc[m][:, :-1], ds["logpm"][m],
                                          ds["ridx"][m], ds["ywin"][m])
                dll = ll - llm
            else:
                dll = ll - ll0
            fits[s] = (b, ll, ll0)
            rec[s] = dict(coef=float(b[-1]), se=float(se[-1]),
                          z=float(b[-1] / se[-1]) if se[-1] > 0 else 0.0,
                          dll=float(dll),
                          races=int(len(set(ds["ridx"][m].tolist()))))
        bmine = fits["MINE"][0]
        if fname == "wx":
            mm = masks["MINE"]
            bmain = cl_fit(Xc[mm][:, :-1], ds["logpm"][mm], ds["ridx"][mm],
                           ds["ywin"][mm])[0]
            bbase = np.append(bmain, 0.0)
        else:
            bbase = np.zeros_like(bmine)
        for s in ("VALIDATE", "CONFIRM"):
            m = masks[s]
            _, _, _, _, ll_of = cl_fit(Xc[m], ds["logpm"][m], ds["ridx"][m],
                                       ds["ywin"][m], iters=0)
            rec[s]["oos_dll"] = float(ll_of(bmine) - ll_of(bbase))
        rec["mine_pass"] = bool(abs(rec["MINE"]["z"]) >= Z_MINE)
        rec["val_pass"] = bool(rec["mine_pass"] and rec["VALIDATE"]["oos_dll"] > 0)
        rec["conf_pass"] = bool(rec["val_pass"] and rec["CONFIRM"]["oos_dll"] > 0)
        res[fname] = rec

    out["features"] = res
    meas = out["build"]["measurable"]
    n_pass = sum(1 for k, v in res.items() if v["conf_pass"] and meas.get(k))
    out["summary"] = dict(trials=len(FEATS), z_mine=Z_MINE,
                          bonferroni_z=2.81, n_conf_pass=n_pass)
    print(f"\n{'特徴':<9}{'測定可':<5}{'MINE z':>8}{'MINE ΔLL':>10}"
          f"{'VAL oosΔLL':>11}{'CONF oosΔLL':>12}{'VAL z':>7}{'CONF z':>8}  判定")
    for k, v in res.items():
        mark = ("合格" if v["conf_pass"] else
                "VAL通過" if v["val_pass"] else
                "MINE通過" if v["mine_pass"] else "×")
        if not meas.get(k):
            mark = "測定不能(" + mark + ")"
        print(f"{k:<9}{str(meas.get(k)):<5}{v['MINE']['z']:>8.2f}"
              f"{v['MINE']['dll']:>10.2f}{v['VALIDATE']['oos_dll']:>11.2f}"
              f"{v['CONFIRM']['oos_dll']:>12.2f}{v['VALIDATE']['z']:>7.2f}"
              f"{v['CONFIRM']['z']:>8.2f}  {mark}")
    json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n→ {RESULT}")


def diag():
    ds = load()
    out = json.load(open(RESULT, encoding="utf-8"))
    # jchg×jexp クロス表（定義済み行のみ・記述統計）
    dj, de = ds["defs"]["jchg"] > 0, ds["defs"]["jexp"] > 0
    m = dj & de
    # 中心化済みなので生値は復元不能 → build時に別途保存していないため raw から再計算はせず
    # ここでは permutation 較正のみ実施
    masks = {s: split_mask(ds, s) for s in SPLITS}
    rng = np.random.default_rng(20260820)
    passed = [k for k, v in (out.get("features") or {}).items() if v.get("conf_pass")]
    perm = {}
    for fname in passed:
        x = ds["X"][fname]
        mm = masks["MINE"]
        Xc = x[mm][:, None]
        lp, ri, yw = ds["logpm"][mm], ds["ridx"][mm], ds["ywin"][mm]
        _, se, _, _, _ = cl_fit(Xc, lp, ri, yw)
        zs = []
        order = np.argsort(ri, kind="stable")
        for t in range(200):
            xp = x[mm].copy()
            # レース内シャッフル
            rs = ri[order]
            xs = xp[order]
            starts = np.searchsorted(rs, np.unique(rs))
            bounds = np.append(starts, len(rs))
            for a, z_ in zip(bounds[:-1], bounds[1:]):
                xs[a:z_] = rng.permutation(xs[a:z_])
            xp[order] = xs
            b, s_, _, _, _ = cl_fit(xp[:, None], lp, ri, yw, iters=20)
            zs.append(float(b[0] / s_[0]) if s_[0] > 0 else 0.0)
        perm[fname] = dict(perm_z_sd=float(np.std(zs)),
                           perm_z_p975=float(np.quantile(np.abs(zs), 0.975)))
        print(fname, perm[fname])
    out["permutation"] = perm
    json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "build":
        build()
    elif cmd == "test":
        test()
    elif cmd == "diag":
        diag()
    else:
        print(__doc__)
