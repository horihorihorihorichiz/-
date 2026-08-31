# -*- coding: utf-8 -*-
"""course_group_exc.py — COURSE_GROUP_PROTOCOL.md 追補B の実装。

主目的:「コース類型は、発走前3指標(fav_p / ent / sgap)より良い『例外判定』になるか」

  モデルは汎用GEN据え置き。買い方は固定（複勝・市場上位2頭・各100円）。
  閾値・除外規則は **MINE のみ** で決め、VALIDATE / CONFIRM に **1回だけ** 適用する。

usage:
  python3 course_group_exc.py            # 全部（ベースライン再現・類型除外・独立性検証）
出力: course_group_exc.json / 標準出力の表
"""
import json
import math
import time
from collections import defaultdict

import numpy as np

import course_cache as CC
import course_group as CG
import place_eval as PE

BET_KIND = "複勝"
N_LEGS = 2                       # 市場上位2頭
Q_FAV, Q_ENT, Q_SGAP = 0.60, 0.40, 0.40   # MINE分位: fav_p上位40% / ent下位40% / sgap上位60%
PASS_ROI, PASS_N = 100.0, 80


def split_of(d):
    return CG.split_of_date(d)


# ── 1. レース台帳（GEN place 予測 + 確定オッズ + 実払戻 + 類型） ─────────
def build():
    X, yw, yp, ridx, meta = CC.load()
    RM = {m["rid"]: m for m in meta}
    races = []
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if d["obj"] != "place":
            continue
        m = RM[d["rid"]]
        ns = d["ns"]
        odds = np.array([m["odds"].get(n, 0.0) for n in ns], dtype=float)
        if np.any(odds <= 0) or len(ns) < 5:
            continue
        imp = 1.0 / odds
        imp = imp / imp.sum()
        q = PE.norm_place(np.array(d["scores"], dtype=float))
        qs = np.sort(q)[::-1]
        order = np.argsort(-imp)              # 市場人気順
        legs = [ns[i] for i in order[:N_LEGS]]
        pf = (m["payout"].get(BET_KIND) or {})
        pay = sum(float(pf.get(str(h), 0)) for h in legs)
        races.append(dict(
            rid=d["rid"], date=m["date"], split=split_of(m["date"]),
            venue=m["venue"], surface=m["surface"], dist=m["dist"],
            fav_p=float(imp.max()),
            ent=float(-(imp * np.log(np.clip(imp, 1e-12, None))).sum()),
            sgap=float(qs[0] - qs[1]),
            pay=pay, hit=1.0 if pay > 0 else 0.0,
            g1=CG.group_of(m["venue"], m["surface"], m["dist"], "g1") or "",
            g2=CG.group_of(m["venue"], m["surface"], m["dist"], "g2") or "",
            g3=CG.group_of(m["venue"], m["surface"], m["dist"], "g3") or "",
        ))
    return races


def stat(rs):
    n = len(rs)
    if not n:
        return dict(n=0, roi=None, hit=None, ci=None)
    pays = np.array([r["pay"] for r in rs])
    roi = pays.sum() / (100.0 * N_LEGS * n) * 100
    # ROI の95%CI（レース単位の収益 sd から正規近似）
    per = pays / (100.0 * N_LEGS) * 100
    se = per.std(ddof=1) / math.sqrt(n) if n > 1 else float("nan")
    return dict(n=n, roi=round(roi, 1), hit=round(np.mean([r["hit"] for r in rs]) * 100, 1),
                ci=(round(roi - 1.96 * se, 1), round(roi + 1.96 * se, 1)))


def by_split(rs):
    return {s: stat([r for r in rs if r["split"] == s])
            for s in ("MINE", "VALIDATE", "CONFIRM")}


# ── 2. 独立性検証のロジスティック回帰 ────────────────────────────────
def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def fit_logistic(X, y, l2=1e-6, iters=200):
    """IRLS（数値安定のため微小L2）"""
    th = np.zeros(X.shape[1])
    for _ in range(iters):
        p = _sig(X @ th)
        W = np.clip(p * (1 - p), 1e-9, None)
        g = X.T @ (y - p) - l2 * th
        H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        th = th + step
        if np.max(np.abs(step)) < 1e-9:
            break
    return th


def logloss(X, y, th):
    p = np.clip(_sig(X @ th), 1e-12, 1 - 1e-12)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def loglik(X, y, th):
    p = np.clip(_sig(X @ th), 1e-12, 1 - 1e-12)
    return float((y * np.log(p) + (1 - y) * np.log(1 - p)).sum())


def chi2_sf(x, df):
    """χ²上側確率（正則化不完全ガンマの連分数を使わず級数＋補完で十分な精度）"""
    from math import exp, lgamma, log
    if x <= 0:
        return 1.0
    a = df / 2.0
    xx = x / 2.0
    if xx < a + 1:                     # 級数展開 P(a,x)
        term = 1.0 / a
        s = term
        n = 0
        while n < 10000:
            n += 1
            term *= xx / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        p = s * exp(-xx + a * log(xx) - lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))
    # 連分数（Lentz）で Q(a,x)
    tiny = 1e-300
    b = xx + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    q = exp(-xx + a * log(xx) - lgamma(a)) * h
    return max(0.0, min(1.0, q))


def main():
    t0 = time.time()
    races = build()
    OUT = dict(n_races=len(races), bet=f"{BET_KIND}・市場上位{N_LEGS}頭・各100円")
    mine = [r for r in races if r["split"] == "MINE"]
    print(f"races={len(races)}  MINE={len(mine)} "
          f"VAL={sum(1 for r in races if r['split']=='VALIDATE')} "
          f"CONF={sum(1 for r in races if r['split']=='CONFIRM')}", flush=True)

    # ── 0. 無選別ベンチマーク ──────────────────────────────────
    OUT["all"] = by_split(races)
    print("\n[0] 無選別（全レース）")
    for s, v in OUT["all"].items():
        print(f"   {s:<9} n={v['n']:>5} ROI={v['roi']:>6}%  hit={v['hit']:>5}%  CI={v['ci']}")

    # ── 1. 3指標ベースライン（MINEのみで閾値決定） ────────────────
    th_fav = float(np.quantile([r["fav_p"] for r in mine], Q_FAV))
    th_ent = float(np.quantile([r["ent"] for r in mine], Q_ENT))
    th_sgap = float(np.quantile([r["sgap"] for r in mine], Q_SGAP))
    OUT["thresholds"] = dict(fav_p=round(th_fav, 4), ent=round(th_ent, 4),
                             sgap=round(th_sgap, 4))
    print(f"\n[1] 3指標の閾値（MINEのみ・分位は EXCLUSION から流用）: "
          f"fav_p>={th_fav:.4f} / ent<={th_ent:.4f} / sgap>={th_sgap:.4f}")

    def abc(r):
        return r["fav_p"] >= th_fav and r["ent"] <= th_ent and r["sgap"] >= th_sgap

    sel_abc = [r for r in races if abc(r)]
    OUT["abc"] = by_split(sel_abc)
    OUT["abc_survival"] = {s: round(len([r for r in sel_abc if r["split"] == s])
                                    / max(len([r for r in races if r["split"] == s]), 1) * 100, 1)
                           for s in ("MINE", "VALIDATE", "CONFIRM")}
    print("   A∧B∧C:")
    for s, v in OUT["abc"].items():
        print(f"   {s:<9} n={v['n']:>5} ROI={v['roi']:>6}%  hit={v['hit']:>5}%  CI={v['ci']}"
              f"  残存={OUT['abc_survival'][s]}%")

    # 単独指標の5分位（診断）
    OUT["quintiles"] = {}
    for key in ("fav_p", "ent", "sgap"):
        qs = np.quantile([r[key] for r in mine], [0.2, 0.4, 0.6, 0.8])
        rows = []
        for k in range(5):
            lo = -np.inf if k == 0 else qs[k - 1]
            hi = np.inf if k == 4 else qs[k]
            rows.append(stat([r for r in races if lo <= r[key] < hi]))
        OUT["quintiles"][key] = rows

    # ── 2. 類型による除外規則（MINEのみ・全体ROI未満を除外） ─────────
    mine_roi = stat(mine)["roi"]
    OUT["mine_roi_all"] = mine_roi
    OUT["levels"] = {}
    n_decisions = 0
    for lv in ("g1", "g2", "g3"):
        tab = {}
        gs = sorted({r[lv] for r in races if r[lv]})
        for g in gs:
            gm = [r for r in mine if r[lv] == g]
            if len(gm) < 30:                 # MINE 30R未満は判断材料にならない→除外側
                tab[g] = dict(mine=stat(gm), keep=False, reason="MINE<30R")
                continue
            st = stat(gm)
            tab[g] = dict(mine=st, keep=bool(st["roi"] >= mine_roi), reason="ROI>=全体")
            n_decisions += 1
        keep = {g for g, v in tab.items() if v["keep"]}
        sel = [r for r in races if r[lv] in keep]
        sel_both = [r for r in sel if abc(r)]
        OUT["levels"][lv] = dict(
            groups=tab, keep=sorted(keep), n_groups=len(gs),
            typology_only=by_split(sel),
            typology_and_abc=by_split(sel_both),
            survival={s: round(len([r for r in sel if r["split"] == s])
                               / max(len([r for r in races if r["split"] == s]), 1) * 100, 1)
                      for s in ("MINE", "VALIDATE", "CONFIRM")})
        print(f"\n[2-{lv}] 類型除外（MINE全体ROI {mine_roi}% 以上のグループのみ残す）"
              f" -> 残 {len(keep)}/{len(gs)} グループ")
        for nm in ("typology_only", "typology_and_abc"):
            print(f"   {nm}:")
            for s, v in OUT["levels"][lv][nm].items():
                print(f"     {s:<9} n={v['n']:>5} ROI={v['roi']:>6}%  hit={v['hit']:>5}%"
                      f"  CI={v['ci']}")
    OUT["n_decisions"] = n_decisions

    # ── 3. 合格判定（7系列） ────────────────────────────────────
    series = {"3指標のみ(A∧B∧C)": OUT["abc"]}
    for lv in ("g1", "g2", "g3"):
        series[f"類型のみ({lv})"] = OUT["levels"][lv]["typology_only"]
        series[f"3指標∧類型({lv})"] = OUT["levels"][lv]["typology_and_abc"]
    verdict = {}
    for nm, v in series.items():
        V, C = v["VALIDATE"], v["CONFIRM"]
        verdict[nm] = dict(
            val=V, conf=C,
            passed=bool(V["n"] >= PASS_N and C["n"] >= PASS_N
                        and (V["roi"] or 0) > PASS_ROI and (C["roi"] or 0) > PASS_ROI))
    OUT["verdict"] = verdict
    print(f"\n[3] 合格ライン: VALIDATE と CONFIRM の両方で 複勝ROI>{PASS_ROI}% かつ n>={PASS_N}")
    print(f"{'系列':<22}{'VAL n':>7}{'VAL ROI':>9}{'CONF n':>8}{'CONF ROI':>10}{'合否':>6}")
    for nm, v in verdict.items():
        print(f"{nm:<22}{v['val']['n']:>7}{str(v['val']['roi']):>9}"
              f"{v['conf']['n']:>8}{str(v['conf']['roi']):>10}{'○' if v['passed'] else '×':>6}")
    OUT["n_series"] = len(series)
    OUT["n_passed"] = sum(1 for v in verdict.values() if v["passed"])

    # ── 4. 独立性検証 ───────────────────────────────────────────
    print("\n[4] 独立性検証")
    ind = {}
    # 4-1 相関
    for lv in ("g1", "g2", "g3"):
        gs = [g for g in sorted({r[lv] for r in races if r[lv]})
              if len([r for r in mine if r[lv] == g]) >= 30]
        rows = []
        for g in gs:
            gm = [r for r in mine if r[lv] == g]
            rows.append(dict(g=g, n=len(gm), roi=stat(gm)["roi"], hit=stat(gm)["hit"],
                             fav_p=float(np.mean([r["fav_p"] for r in gm])),
                             ent=float(np.mean([r["ent"] for r in gm])),
                             sgap=float(np.mean([r["sgap"] for r in gm]))))
        cor = {}
        for k in ("fav_p", "ent", "sgap"):
            for tgt in ("hit", "roi"):
                a = np.array([r[k] for r in rows])
                b = np.array([r[tgt] for r in rows])
                cor[f"{tgt}~{k}"] = round(float(np.corrcoef(a, b)[0, 1]), 3) if len(a) > 2 else None
        ind[lv] = dict(group_rows=rows, corr=cor)
        print(f"   {lv}: グループ数={len(rows)}  MINEグループ平均の相関 {cor}")

    # 4-2 増分寄与（尤度比 + OOS logloss）
    def design(rs, lv=None, gs=None):
        base = np.stack([np.array([r["fav_p"] for r in rs]),
                         np.array([r["ent"] for r in rs]),
                         np.array([r["sgap"] for r in rs]),
                         np.ones(len(rs))], axis=1)
        if lv is None:
            return base
        D = np.zeros((len(rs), len(gs)))
        idx = {g: i for i, g in enumerate(gs)}
        for i, r in enumerate(rs):
            j = idx.get(r[lv])
            if j is not None and j > 0:      # 先頭グループを基準に
                D[i, j] = 1.0
        return np.hstack([base, D[:, 1:]])

    y_m = np.array([r["hit"] for r in mine])
    X0 = design(mine)
    th0 = fit_logistic(X0, y_m)
    ll0 = loglik(X0, y_m, th0)
    inc = {}
    for lv in ("g1", "g2", "g3"):
        gs = sorted({r[lv] for r in races if r[lv]})
        X1 = design(mine, lv, gs)
        th1 = fit_logistic(X1, y_m)
        ll1 = loglik(X1, y_m, th1)
        lr = 2 * (ll1 - ll0)
        df = X1.shape[1] - X0.shape[1]
        oos = {}
        for s in ("VALIDATE", "CONFIRM"):
            rs = [r for r in races if r["split"] == s]
            ys = np.array([r["hit"] for r in rs])
            oos[s] = dict(ll_base=round(logloss(design(rs), ys, th0), 6),
                          ll_grp=round(logloss(design(rs, lv, gs), ys, th1), 6))
            oos[s]["improve"] = round(oos[s]["ll_base"] - oos[s]["ll_grp"], 6)
        inc[lv] = dict(lr_chi2=round(lr, 2), df=df, p=round(chi2_sf(max(lr, 0), df), 5), oos=oos)
        print(f"   {lv}: LRχ²={lr:.2f} df={df} p={inc[lv]['p']}  "
              f"OOS logloss改善 VAL={oos['VALIDATE']['improve']:+.6f} "
              f"CONF={oos['CONFIRM']['improve']:+.6f}")
    ind["incremental"] = inc

    # 4-3 A∧B∧C 残存内でのグループ差（MINE・χ²）
    cond = {}
    mine_abc = [r for r in mine if abc(r)]
    for lv in ("g1", "g2", "g3"):
        cnt = defaultdict(lambda: [0, 0])
        for r in mine_abc:
            c = cnt[r[lv]]
            c[0] += 1
            c[1] += r["hit"]
        rows = {g: dict(n=v[0], hit=round(v[1] / v[0] * 100, 1)) for g, v in cnt.items()
                if v[0] >= 20}
        p_bar = sum(v[1] for v in cnt.values()) / max(sum(v[0] for v in cnt.values()), 1)
        chi = sum((cnt[g][1] - cnt[g][0] * p_bar) ** 2
                  / max(cnt[g][0] * p_bar * (1 - p_bar), 1e-9)
                  for g in rows)
        df = max(len(rows) - 1, 1)
        cond[lv] = dict(n=len(mine_abc), groups=rows, chi2=round(chi, 2), df=df,
                        p=round(chi2_sf(chi, df), 5), base_hit=round(p_bar * 100, 1))
        print(f"   {lv}: A∧B∧C残存 MINE {len(mine_abc)}R の的中率 χ²={chi:.2f} "
              f"df={df} p={cond[lv]['p']} (全体 {cond[lv]['base_hit']}%)")
    ind["conditional"] = cond
    OUT["independence"] = ind

    json.dump(OUT, open("course_group_exc.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(f"\nsaved course_group_exc.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()


# ══════════════════════════════════════════════════════════════════════
# 追加のヌル検査（事前登録の判定基準は一切変えない・保守側にしか働かない）
#   「グループラベルをシャッフルした偽の類型」で同じ手順を繰り返し、
#   観測された 3指標∧類型 の CONFIRM ROI が偶然どれくらい出るかを測る。
# ══════════════════════════════════════════════════════════════════════
def nullsweep(iters=1000, seed=20260818):
    races = build()
    mine = [r for r in races if r["split"] == "MINE"]
    th_fav = float(np.quantile([r["fav_p"] for r in mine], Q_FAV))
    th_ent = float(np.quantile([r["ent"] for r in mine], Q_ENT))
    th_sgap = float(np.quantile([r["sgap"] for r in mine], Q_SGAP))

    def abc(r):
        return r["fav_p"] >= th_fav and r["ent"] <= th_ent and r["sgap"] >= th_sgap
    mine_roi = stat(mine)["roi"]
    rng = np.random.default_rng(seed)
    obs = json.load(open("course_group_exc.json", encoding="utf-8"))
    out = {}
    for lv in ("g1", "g2", "g3"):
        labels = np.array([r[lv] for r in races])
        idx_all = np.arange(len(races))
        hits = dict(val=0, conf=0, both=0, both100=0)
        o_v = obs["levels"][lv]["typology_and_abc"]["VALIDATE"]["roi"]
        o_c = obs["levels"][lv]["typology_and_abc"]["CONFIRM"]["roi"]
        ns = []
        for _ in range(iters):
            fake = labels[rng.permutation(idx_all)]
            for r, f in zip(races, fake):
                r["_f"] = f
            keep = set()
            for g in set(fake):
                if not g:
                    continue
                gm = [r for r in mine if r["_f"] == g]
                if len(gm) >= 30 and stat(gm)["roi"] >= mine_roi:
                    keep.add(g)
            sel = [r for r in races if r["_f"] in keep and abc(r)]
            v = stat([r for r in sel if r["split"] == "VALIDATE"])
            c = stat([r for r in sel if r["split"] == "CONFIRM"])
            ns.append((v["n"], c["n"]))
            if v["n"] and v["roi"] >= o_v:
                hits["val"] += 1
            if c["n"] and c["roi"] >= o_c:
                hits["conf"] += 1
            if v["n"] and c["n"] and v["roi"] >= o_v and c["roi"] >= o_c:
                hits["both"] += 1
            if v["n"] >= PASS_N and c["n"] >= PASS_N and (v["roi"] or 0) > 100 and (c["roi"] or 0) > 100:
                hits["both100"] += 1
        out[lv] = dict(iters=iters, obs_val=o_v, obs_conf=o_c,
                       p_val=hits["val"] / iters, p_conf=hits["conf"] / iters,
                       p_both=hits["both"] / iters, p_pass100=hits["both100"] / iters,
                       median_n=(float(np.median([a for a, _ in ns])),
                                 float(np.median([b for _, b in ns]))))
        print(f"[null {lv}] 観測 VAL={o_v}% CONF={o_c}% -> 偽類型で同等以上: "
              f"VAL {out[lv]['p_val']:.3f} / CONF {out[lv]['p_conf']:.3f} / "
              f"両方 {out[lv]['p_both']:.3f} / 合格ライン到達 {out[lv]['p_pass100']:.3f} "
              f"(n中央値 {out[lv]['median_n']})", flush=True)
    o = json.load(open("course_group_exc.json", encoding="utf-8"))
    o["nullsweep"] = out
    json.dump(o, open("course_group_exc.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print("saved (nullsweep merged)")
