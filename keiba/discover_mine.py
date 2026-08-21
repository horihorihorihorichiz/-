# -*- coding: utf-8 -*-
"""DISCOVER 段階1-2＋ヌル検査（DISCOVER_PROTOCOL.md §3-§4 の実装）。

市場log-oddsをオフセット固定した条件付きロジット(top3)に候補を1本ずつ入れ、
MINE（month<=202602）での増分ΔLLとzを測る。着順シャッフルの偽データでも同じ発掘を回す。
usage: python3 discover_mine.py
既存ファイルは変更しない。
"""
import json, math, pickle, sys
import numpy as np

import v99w_fit as V
import discover_feats as DF

MAXH = V.MAXH
SEEDS = [20260821, 20260822, 20260823]
COV_MIN = 0.40


# ───────── 市場オフセット ─────────
def build_market(races, grid):
    R = len(races)
    OFF = np.full((R, MAXH), -1e18)
    W = np.zeros((R, 3), dtype=int)
    ok = np.zeros(R, dtype=bool)
    drop_few = drop_missing = 0
    for i, r in enumerate(races):
        n = len(r["nums"])
        o = np.array([r["odds"].get(num) or 0.0 for num in r["nums"]], float)
        if (o <= 0).any():
            drop_missing += 1
            continue
        if n < 5:
            drop_few += 1
            continue
        inv = 1.0 / o
        p = inv / inv.sum()
        OFF[i, :n] = np.log(p)
        W[i] = r["top3"]
        ok[i] = True
    return OFF, W, ok, dict(drop_missing_odds=drop_missing, drop_few=drop_few)


# ───────── top3 条件付きロジット（β1本・Newton） ─────────
def _ll_g_h(beta, F, OFF, M, W):
    s = OFF + beta * F
    masks = M.copy()
    ar = np.arange(F.shape[0])
    ll = 0.0
    g = 0.0
    h = 0.0
    for pos in range(3):
        sm = np.where(masks, s, -1e18)
        mx = sm.max(1)
        e = np.exp(sm - mx[:, None]) * masks
        Z = e.sum(1)
        p = e / Z[:, None]
        win = W[:, pos]
        ll += (s[ar, win] - (mx + np.log(Z))).sum()
        Ef = (p * F).sum(1)
        Ef2 = (p * F * F).sum(1)
        g += (F[ar, win] - Ef).sum()
        h += -(Ef2 - Ef ** 2).sum()
        masks[ar, win] = False
    return ll, g, h


def fit_beta(F, OFF, M, W, iters=25):
    beta = 0.0
    ll0, _, _ = _ll_g_h(0.0, F, OFF, M, W)
    for _ in range(iters):
        ll, g, h = _ll_g_h(beta, F, OFF, M, W)
        if h > -1e-12:
            break
        step = -g / h
        step = float(np.clip(step, -1.0, 1.0))
        beta += step
        if abs(step) < 1e-9:
            break
    ll, g, h = _ll_g_h(beta, F, OFF, M, W)
    se = 1.0 / math.sqrt(max(-h, 1e-12))
    return beta, ll - ll0, (beta / se if se > 0 else 0.0), ll0


def null_W(W, M, ok_idx, seed):
    """レース内で1-3着の割り当てをシャッフルした偽データ"""
    rng = np.random.default_rng(seed)
    Wn = W.copy()
    n = M.sum(1)
    for i in ok_idx:
        Wn[i] = rng.choice(int(n[i]), size=3, replace=False)
    return Wn


def main():
    races = V.load_races()
    A, race_idx, num, keep, ctx, st = DF.load_ds()
    assert len(keep) == len(races), (len(keep), len(races))
    grid = DF.Grid(race_idx, len(races))
    D = DF.derive(A)

    OFF, W, ok, dstat = build_market(races, grid)
    month = np.array([r["month"] for r in races])
    mine = ok & (month <= "202602")
    vali = ok & (month >= "202603") & (month <= "202605")
    conf = ok & (month >= "202606") & (month <= "202608")
    print(f"as-of: 過去走 {int(st[1])}走 / days<=0 は {int(st[0])}件 / hist欠 {int(st[2])}R")
    print(f"除外: オッズ欠 {dstat['drop_missing_odds']}R / 5頭未満 {dstat['drop_few']}R")
    print(f"MINE={mine.sum()} VALIDATE={vali.sum()} CONFIRM={conf.sum()} "
          f"(全{len(races)}R)")

    Mm = grid.MASK[mine]
    OFFm, Wm = OFF[mine], W[mine]
    rows_mine = np.isin(race_idx, np.where(mine)[0])
    print(f"MINE 馬行 = {rows_mine.sum()}")

    # ヌル用の偽着順
    ok_idx = np.arange(Mm.shape[0])
    Wnulls = [null_W(Wm, Mm, ok_idx, s) for s in SEEDS]

    res = []
    dropped_cov, dropped_var = 0, 0
    ntest = 0
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        cov = float(np.isfinite(v[rows_mine]).mean())
        Zm = Z[mine]
        if cov < COV_MIN:
            dropped_cov += 1
            continue
        if Zm[Mm].std() < 1e-9:
            dropped_var += 1
            continue
        ntest += 1
        b, dll, z, ll0 = fit_beta(Zm, OFFm, Mm, Wm)
        row = dict(name=name, ja=ja, cov=round(cov, 4), beta=round(b, 5),
                   dll=round(dll, 3), z=round(z, 3))
        for si, Wn in enumerate(Wnulls):
            _, dn, zn, _ = fit_beta(Zm, OFFm, Mm, Wn)
            row[f"z_null{si}"] = round(zn, 3)
        res.append(row)
        if ntest % 100 == 0:
            print(f"  ... {ntest}本 検定済", flush=True)

    N = ntest
    from math import erf, sqrt
    # z_crit = Phi^-1(1 - 0.025/N)
    def phi_inv(p):
        # Acklam近似で十分（境界は下で数値補正）
        a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
             1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
             6.680131188771972e+01, -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
             -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
             3.754408661907416e+00]
        pl = 0.02425
        if p < pl:
            q = sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p > 1 - pl:
            q = sqrt(-2 * math.log(1 - p))
            return -((((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) /
                     ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

    zc = phi_inv(1 - 0.025 / N)
    passed = [r for r in res if abs(r["z"]) >= zc]
    nulls = [sum(1 for r in res if abs(r[f"z_null{si}"]) >= zc)
             for si in range(len(SEEDS))]
    print(f"\n候補総数 生成={870} / 検定={N} "
          f"(カバレッジ<40%で除外={dropped_cov} 分散0で除外={dropped_var})")
    print(f"Bonferroni z_crit = {zc:.3f} (両側α=0.05 / N={N})")
    print(f"実データ通過 = {len(passed)} 本")
    print(f"ヌル通過 = {nulls} (平均 {np.mean(nulls):.2f} 最大 {max(nulls)})")
    ok_null = len(passed) > max(nulls) and len(passed) > 3 * np.mean(nulls)
    print(f"ヌル判定: {'通過' if ok_null else '棄却'}")

    passed_sorted = sorted(passed, key=lambda r: -abs(r["z"]))
    print("\n── MINE通過（|z|降順・上位40） ──")
    for r in passed_sorted[:40]:
        print(f"  {r['name']:28s} z={r['z']:+7.2f} ΔLL={r['dll']:+8.1f} "
              f"cov={r['cov']:.2f}  {r['ja']}")

    out = dict(n_generated=870, n_tested=N, dropped_cov=dropped_cov,
               dropped_var=dropped_var, z_crit=zc,
               n_pass=len(passed), null_pass=nulls,
               null_ok=bool(ok_null), seeds=SEEDS,
               splits=dict(mine=int(mine.sum()), vali=int(vali.sum()),
                           conf=int(conf.sum())),
               asof=dict(runs=int(st[1]), days_le0=int(st[0])),
               drops=dstat, all=res)
    json.dump(out, open("discover_mine_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n→ discover_mine_result.json 保存")


if __name__ == "__main__":
    main()
