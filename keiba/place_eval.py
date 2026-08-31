# -*- coding: utf-8 -*-
"""3着内(複勝圏)特化モデルの評価器 — PLACE_SYSTEM_20260817.md の事前登録どおり。

測るもの:
  (1) α_place  … 複勝市場(=単勝オッズのHarville近似)に対する付加情報。
                  主指標 = 3着内二値のロジスティック回帰
                     P(3着内_i) = σ( α·logit q_model_i + β·logit q_market_i + c )
                  副指標 = 上位3着の順序ロジット(Plackett-Luce・V7と同じ形)
                     u_i = α·log w_model_i + β·log p_market_i
                  どちらも月次WF(fold月 m の係数は m より前の月だけで推定)。
  (2) ワイド・三連複のEV … モデルの3着内確率 → PL強度 → 組合せ理論確率。
                  組合せの市場オッズは台帳に無いため、
                  「前月までの的中組の払戻 vs 市場Harville確率」の log線形回帰でWF推定する。
                  EV = p_model_combo × odds_est。的中時の払戻は **実払戻** を使う。
  (3) 複勝単体   … モデル3着内確率1位の複勝flat。ベンチマーク=市場1-3番人気の複勝flat。
  (4) Harville近似そのものの較正 … 事前複勝オッズを持たない事による限界の定量化。

usage: python3 place_eval.py --variants v3place,v8place
"""
import argparse, json, itertools
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

import fit_place as FP

SPLITS = [("MINE", "000000", "202602"),
          ("VALIDATE", "202603", "202605"),
          ("CONFIRM", "202606", "202608")]
EV_TH = 1.2          # 事前登録の閾値（事後変更禁止）
LOSE = 1e-9


def split_of(m):
    for name, lo, hi in SPLITS:
        if lo <= m <= hi:
            return name
    return None


# ── 台帳読み込み ──────────────────────────────────────────────────────
def load_ledger(path):
    races, dropped = [], []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        order = [int(x) for x in d["order"]]
        odds = {int(k): float(v) for k, v in d["odds"].items()}
        if any(h not in odds or odds[h] <= 0 for h in order):
            dropped.append(d["rid"])
            continue
        top3 = [int(x) for x in d["top3"]]
        if len(top3) < 3 or any(t not in order for t in top3):
            dropped.append(d["rid"])
            continue
        pay = d.get("payout") or {}
        races.append(dict(
            rid=d["rid"], month=d["month"], split=split_of(d["month"]),
            ns=order, s=np.array(d["scores"], dtype=float),
            odds=np.array([odds[h] for h in order], dtype=float),
            top3=top3, top3_idx=[order.index(t) for t in top3],
            pay_fuku={int(k): int(v) for k, v in (pay.get("複勝") or {}).items()},
            pay_wide={_key(k): int(v) for k, v in (pay.get("ワイド") or {}).items()},
            pay_trio={_key(k): int(v) for k, v in (pay.get("三連複") or {}).items()},
            field=int(d["field"]), tier=int(d.get("tier") or 0)))
    return races, dropped


def _key(k):
    return tuple(sorted(int(x) for x in k.replace("→", "-").split("-")))


# ── 確率の作り方 ──────────────────────────────────────────────────────
def _logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def norm_place(p, target=3.0):
    """確率の並び p を「ロジットの平行移動」で和=target に正規化する。
       単純なスケーリングと違い (0,1) を外れない・順序を保つ。"""
    l = _logit(np.asarray(p, dtype=float))
    n = len(l)
    if n <= target:
        return np.ones(n)
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _sig(l + mid).sum() > target:
            hi = mid
        else:
            lo = mid
    return np.clip(_sig(l + (lo + hi) / 2), 1e-9, 1 - 1e-9)


def market_probs(odds):
    """確定単勝オッズ -> 控除率補正済み勝率 pw(和1) と Harville の3着内確率 qm(和3)"""
    pw = 1.0 / np.asarray(odds, dtype=float)
    pw = pw / pw.sum()
    return pw, FP.harville_place(pw, 3)


def prep(races):
    """各レースに q_model(和3)・q_market(和3)・w_model(PL強度)・p_market を付ける。"""
    for r in races:
        # 二値モデルの生出力(=P(3着内)の粗い推定)をレース内で和3に正規化
        r["q_model"] = norm_place(r["s"])
        pw, qm = market_probs(r["odds"])
        r["p_market"] = pw
        r["q_market"] = qm
        r["w_model"] = FP.pl_from_place(r["q_model"])
        r["y"] = np.zeros(len(r["ns"]))
        for i in r["top3_idx"]:
            r["y"][i] = 1.0


# ── (1a) 主指標: 3着内二値ロジスティック(クラスタ頑健SE) ────────────────
def stack(races):
    X = np.concatenate([np.stack([_logit(r["q_model"]), _logit(r["q_market"]),
                                  np.ones(len(r["ns"]))], axis=1) for r in races])
    y = np.concatenate([r["y"] for r in races])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(races)])
    return X, y, g


def fit_logit(X, y):
    def f(th):
        z = X @ th
        p = _sig(z)
        nll = -(y * np.log(np.clip(p, 1e-12, None))
                + (1 - y) * np.log(np.clip(1 - p, 1e-12, None))).sum()
        return nll, X.T @ (p - y)
    res = minimize(f, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B")
    return res.x


def cluster_se(X, y, g, th):
    p = _sig(X @ th)
    W = p * (1 - p)
    A = X.T @ (X * W[:, None])
    Ai = np.linalg.pinv(A)
    u = (y - p)[:, None] * X
    B = np.zeros_like(A)
    for gi in np.unique(g):
        s = u[g == gi].sum(axis=0)
        B += np.outer(s, s)
    V = Ai @ B @ Ai
    return np.sqrt(np.clip(np.diag(V), 0, None))


# ── (1b) 副指標: 上位3着の順序ロジット(Plackett-Luce) ──────────────────
def fit_pl_stage2(races):
    """u_i = α·log w_model_i + β·log p_market_i を 1着→2着→3着 の逐次選択尤度で最尤推定。"""
    A = [np.log(np.clip(r["w_model"], 1e-12, None)) for r in races]
    Bm = [np.log(np.clip(r["p_market"], 1e-12, None)) for r in races]
    idx = [r["top3_idx"] for r in races]

    def f(th):
        a, b = th
        nll = 0.0
        ga = np.zeros(2)
        for A_, B_, ix in zip(A, Bm, idx):
            u = a * A_ + b * B_
            alive = np.ones(len(u), dtype=bool)
            for t in ix:
                uu = np.where(alive, u, -1e30)
                mx = uu.max()
                e = np.exp(uu - mx)
                Z = e.sum()
                p = e / Z
                nll -= (u[t] - mx - np.log(Z))
                ga[0] -= A_[t] - float(p @ A_)
                ga[1] -= B_[t] - float(p @ B_)
                alive[t] = False
        return nll, ga
    res = minimize(f, np.array([1.0, 1.0]), jac=True, method="L-BFGS-B")
    return res.x, float(res.fun)


# ── (2) 組合せオッズのWF較正 ────────────────────────────────────────
def calib_fit(rows):
    """rows = [(log(1/p_mkt_combo), log(pay/100)), ...] (的中組のみ) -> (a,b)
       log odds_est = a + b·log(1/p)。b=1・a=log(1-控除率) が理想Harville。"""
    if len(rows) < 30:
        return None
    x = np.array([r[0] for r in rows])
    y = np.array([r[1] for r in rows])
    Xd = np.stack([np.ones_like(x), x], axis=1)
    coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    return float(coef[0]), float(coef[1])


def combo_tables(r):
    """レース r について三連複・ワイドの (組合せ, p_model, p_market) を返す。"""
    n = len(r["ns"])
    if n < 4:
        return None
    tri, pmod = FP.trio_probs(r["w_model"])
    _, pmkt = FP.trio_probs(r["p_market"])
    nums = np.array(r["ns"])
    keys3 = [tuple(sorted(nums[t])) for t in tri]
    Wmod = FP.wide_probs(tri, pmod, n)
    Wmkt = FP.wide_probs(tri, pmkt, n)
    iu = np.triu_indices(n, 1)
    keys2 = [tuple(sorted((int(nums[i]), int(nums[j])))) for i, j in zip(*iu)]
    return dict(k3=keys3, p3m=pmod, p3k=pmkt,
                k2=keys2, p2m=Wmod[iu] + Wmod.T[iu], p2k=Wmkt[iu] + Wmkt.T[iu])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--out", default="place_eval_result.json")
    a = ap.parse_args()
    out = {}

    for v in a.variants.split(","):
        print(f"\n{'='*70}\n{v}\n{'='*70}", flush=True)
        races, dropped = load_ledger(f"place_preds_{v}.jsonl")
        prep(races)
        months = sorted({r["month"] for r in races})
        by_m = {m: [r for r in races if r["month"] == m] for m in months}
        print(f"races={len(races)} dropped={len(dropped)} months={months[0]}..{months[-1]}")
        res = dict(n_races=len(races), dropped=len(dropped), months=months)

        # ── (1) α_place の月次WF ──
        folds = {}
        for mi, m in enumerate(months):
            tr = [r for mm in months[:mi] for r in by_m[mm]]
            if len(tr) < 200:
                folds[m] = dict(skipped=True, train=len(tr))
                continue
            X, y, g = stack(tr)
            th = fit_logit(X, y)
            se = cluster_se(X, y, g, th)
            thpl, _ = fit_pl_stage2(tr)
            folds[m] = dict(train=len(tr), split=split_of(m),
                            alpha=round(float(th[0]), 4), beta=round(float(th[1]), 4),
                            const=round(float(th[2]), 4),
                            se_alpha=round(float(se[0]), 4),
                            z_alpha=round(float(th[0] / max(se[0], 1e-9)), 2),
                            pl_alpha=round(float(thpl[0]), 4),
                            pl_beta=round(float(thpl[1]), 4))
            # 当月へ適用してブレンド確率を保存
            for r in by_m[m]:
                z = (th[0] * _logit(r["q_model"]) + th[1] * _logit(r["q_market"]) + th[2])
                r["q_blend"] = norm_place(_sig(z))
            print(f"{m}[{split_of(m)}] train={len(tr):5d}R  α={th[0]:+.4f}(se{se[0]:.4f}"
                  f" z{th[0]/max(se[0],1e-9):+.2f}) β={th[1]:+.4f} c={th[2]:+.3f}"
                  f" | PL α={thpl[0]:+.4f} β={thpl[1]:+.4f}", flush=True)
        res["folds"] = folds
        al = [(m, folds[m]["alpha"]) for m in months if not folds[m].get("skipped")]
        run = best = 0
        for _, x in al:
            run = run + 1 if x > 0 else 0
            best = max(best, run)
        res["alpha_pos_folds"] = sum(1 for _, x in al if x > 0)
        res["alpha_folds"] = len(al)
        res["alpha_max_run"] = best
        plal = [(m, folds[m]["pl_alpha"]) for m in months if not folds[m].get("skipped")]
        run = bestpl = 0
        for _, x in plal:
            run = run + 1 if x > 0 else 0
            bestpl = max(bestpl, run)
        res["pl_alpha_pos_folds"] = sum(1 for _, x in plal if x > 0)
        res["pl_alpha_max_run"] = bestpl
        print(f"→ α_place>0: {res['alpha_pos_folds']}/{res['alpha_folds']}fold"
              f" 最長連続={best}  | PL版 {res['pl_alpha_pos_folds']}/{res['alpha_folds']} 連続{bestpl}")

        ev_races = [r for r in races if "q_blend" in r]

        # ── (3) 複勝単体 + Harville較正 ──
        acc = defaultdict(float)
        cal = defaultdict(lambda: [0.0, 0.0, 0])     # bin -> [Σq, Σy, n]
        for r in ev_races:
            sp = r["split"]
            # モデル1位(3着内確率最大)の複勝flat
            i = int(np.argmax(r["q_model"]))
            h = r["ns"][i]
            acc[f"{sp}/mdl_n"] += 1
            acc[f"{sp}/mdl_pay"] += r["pay_fuku"].get(h, 0)
            acc[f"{sp}/mdl_hit"] += (h in r["top3"])
            # ブレンド1位
            j = int(np.argmax(r["q_blend"]))
            hb = r["ns"][j]
            acc[f"{sp}/bl_n"] += 1
            acc[f"{sp}/bl_pay"] += r["pay_fuku"].get(hb, 0)
            acc[f"{sp}/bl_hit"] += (hb in r["top3"])
            # 市場1-3番人気の複勝flat(ベンチマーク)
            pop = np.argsort(r["odds"])
            for k in range(min(3, len(pop))):
                hp = r["ns"][int(pop[k])]
                acc[f"{sp}/mkt{k+1}_n"] += 1
                acc[f"{sp}/mkt{k+1}_pay"] += r["pay_fuku"].get(hp, 0)
                acc[f"{sp}/mkt{k+1}_hit"] += (hp in r["top3"])
                acc[f"{sp}/mkt13_n"] += 1
                acc[f"{sp}/mkt13_pay"] += r["pay_fuku"].get(hp, 0)
                acc[f"{sp}/mkt13_hit"] += (hp in r["top3"])
            # Harville近似の較正(市場側 q_market vs 実際の3着内)
            for i2 in range(len(r["ns"])):
                b = min(9, int(r["q_market"][i2] * 10))
                cal[b][0] += r["q_market"][i2]
                cal[b][1] += r["y"][i2]
                cal[b][2] += 1
            # 複勝払戻 vs Harville含みオッズ(3着内馬のみ)
            for i2 in r["top3_idx"]:
                p = r["pay_fuku"].get(r["ns"][i2], 0)
                if p:
                    acc["fuk_pay"] += p / 100.0
                    acc["fuk_hv"] += 0.8 / max(r["q_market"][i2], 1e-6)
                    acc["fuk_n"] += 1
        res["fukusho"] = {}
        for sp, _, _ in SPLITS:
            d = {}
            for tag in ("mdl", "bl", "mkt1", "mkt2", "mkt3", "mkt13"):
                n = acc[f"{sp}/{tag}_n"]
                if n:
                    d[tag] = dict(n=int(n), roi=round(acc[f"{sp}/{tag}_pay"] / (100 * n) * 100, 1),
                                  hit=round(acc[f"{sp}/{tag}_hit"] / n * 100, 1))
            res["fukusho"][sp] = d
        res["harville_calib"] = {str(b): dict(q=round(cal[b][0] / cal[b][2], 4),
                                              actual=round(cal[b][1] / cal[b][2], 4),
                                              n=int(cal[b][2]))
                                 for b in sorted(cal) if cal[b][2]}
        res["fuku_pay_vs_harville"] = dict(
            n=int(acc["fuk_n"]),
            mean_pay=round(acc["fuk_pay"] / max(acc["fuk_n"], 1), 3),
            mean_harville_odds=round(acc["fuk_hv"] / max(acc["fuk_n"], 1), 3),
            ratio=round(acc["fuk_pay"] / max(acc["fuk_hv"], 1e-9), 3))
        print("\n[複勝flat]")
        for sp, _, _ in SPLITS:
            d = res["fukusho"][sp]
            print(f"  {sp:9s} model1位 n={d['mdl']['n']:4d} 的中{d['mdl']['hit']:5.1f}% ROI{d['mdl']['roi']:6.1f}%"
                  f" | blend1位 ROI{d['bl']['roi']:6.1f}%"
                  f" | 市場1-3人気 n={d['mkt13']['n']:4d} 的中{d['mkt13']['hit']:5.1f}% ROI{d['mkt13']['roi']:6.1f}%"
                  f" (1人気 ROI{d['mkt1']['roi']:6.1f}%)")
        print(f"  Harville較正(3着内馬の複勝): 実払戻平均{res['fuku_pay_vs_harville']['mean_pay']:.3f}倍"
              f" vs Harville含みオッズ{res['fuku_pay_vs_harville']['mean_harville_odds']:.3f}倍"
              f" → 比 {res['fuku_pay_vs_harville']['ratio']:.3f}")

        # ── (2) ワイド・三連複のEV ──
        # 月次WF: fold月 m のオッズ較正は m より前の月の的中組だけで推定
        hist3, hist2 = [], []
        bets = defaultdict(float)
        calib_log = {}
        for m in months:
            cal3 = calib_fit(hist3)
            cal2 = calib_fit(hist2)
            for r in by_m[m]:
                T = combo_tables(r)
                if T is None:
                    continue
                w3 = tuple(sorted(r["top3"]))
                pay3 = r["pay_trio"].get(w3, 0)
                if pay3:
                    i3 = T["k3"].index(w3) if w3 in T["k3"] else -1
                    if i3 >= 0:
                        hist3.append((float(np.log(1.0 / max(T["p3k"][i3], 1e-12))),
                                      float(np.log(pay3 / 100.0))))
                for pr, pv in r["pay_wide"].items():
                    if pr in T["k2"]:
                        i2 = T["k2"].index(pr)
                        hist2.append((float(np.log(1.0 / max(T["p2k"][i2], 1e-12))),
                                      float(np.log(pv / 100.0))))
                if cal3 is None or cal2 is None or "q_blend" not in r:
                    continue
                sp = r["split"]
                for tag, keys, pmod, pmkt, calc_, paydict, srcname in (
                        ("trio", T["k3"], T["p3m"], T["p3k"], cal3, r["pay_trio"], "三連複"),
                        ("wide", T["k2"], T["p2m"], T["p2k"], cal2, r["pay_wide"], "ワイド")):
                    a_, b_ = calc_
                    o_est = np.exp(a_ + b_ * np.log(1.0 / np.clip(pmkt, 1e-12, None)))
                    ev = pmod * o_est
                    sel = np.where(ev >= EV_TH)[0]
                    for i4 in sel:
                        k = keys[i4]
                        p = paydict.get(k, 0)
                        bets[f"{sp}/{tag}_n"] += 1
                        bets[f"{sp}/{tag}_pay"] += p
                        bets[f"{sp}/{tag}_hit"] += (1 if p else 0)
                        bets[f"{sp}/{tag}_evsum"] += float(ev[i4])
                    if len(ev):
                        bets[f"{sp}/{tag}_maxev"] = max(bets[f"{sp}/{tag}_maxev"], float(ev.max()))
                        bets[f"{sp}/{tag}_races"] += 1
            calib_log[m] = dict(trio=cal3, wide=cal2, n3=len(hist3), n2=len(hist2))
        res["combo"] = {}
        for sp, _, _ in SPLITS:
            d = {}
            for tag in ("trio", "wide"):
                n = bets[f"{sp}/{tag}_n"]
                d[tag] = dict(n=int(n), races=int(bets[f"{sp}/{tag}_races"]),
                              roi=round(bets[f"{sp}/{tag}_pay"] / (100 * n) * 100, 1) if n else None,
                              hits=int(bets[f"{sp}/{tag}_hit"]),
                              mean_ev=round(bets[f"{sp}/{tag}_evsum"] / n, 3) if n else None,
                              max_ev_seen=round(bets[f"{sp}/{tag}_maxev"], 3))
            res["combo"][sp] = d
        res["combo_calib"] = {m: dict(trio=calib_log[m]["trio"], wide=calib_log[m]["wide"])
                              for m in months if calib_log[m]["trio"]}
        print("\n[組合せEV≥1.2]")
        for sp, _, _ in SPLITS:
            d = res["combo"][sp]
            for tag, jp in (("trio", "三連複"), ("wide", "ワイド")):
                x = d[tag]
                print(f"  {sp:9s} {jp} n={x['n']:6d} 的中{x['hits']:4d} "
                      f"ROI={x['roi'] if x['roi'] is not None else '—'}% "
                      f"平均EV={x['mean_ev']} 最大EV(全組合せ中)={x['max_ev_seen']}")

        out[v] = res

    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
