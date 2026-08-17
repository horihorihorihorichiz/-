# -*- coding: utf-8 -*-
"""ワイド・三連複のEV検証（Harville歪みを較正した版）。

place_eval.py の素の版（モデル3着内確率 → PL強度 → 組合せ確率 をそのままEVに使う）は
**EV推定が壊れている**ことが実測で判明した（平均EV 4.0 に対し実ROI 39%）。
原因は place_eval.py が出力した Harville較正表そのもの:

    Harville 3着内確率 q   実際の3着内率
      0.039   →  0.052     （ロングショットを過小評価）
      0.937   →  0.877     （本命を過大評価）

「モデルの3着内確率 → それを再現するPL強度」の逆変換は、この歪みをそのまま裏返して
**ロングショット馬の勝ち強度を過大に**する。その強度を3頭かけ合わせる三連複では
歪みが3乗で効き、低確率の組合せの理論確率が桁で膨らむ。素の版で全組合せの約半数が
EV≥1.2 で発火したのはこのため（＝閾値が働いていない）。

そこで **同じ歪みが model 側にも market 側にも掛かっている** ことを利用し、
組合せ確率にレース内温度較正（p_cal ∝ p^γ, レース内で和1に再正規化）を掛ける。
γ は「その月より前の月の的中組」だけを使った最尤推定（月次WF・リークなし）。
判定基準（EV≥1.2 / VALIDATE n≥40・ROI≥110% / CONFIRM n≥25・ROI≥105%）は**一切変えない**。

出力: place_combo_result.json
usage: python3 place_combo.py --variants v3place,v8place
"""
import argparse, json
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize_scalar

import fit_place as FP
import place_eval as PE

EV_TH = 1.2
GAMMA_WINDOW = 1500      # γ最尤推定に使う直近レース数（計算量のため。全期間だと1推定に数分かかる）


def race_tables(r):
    """レース r の三連複テーブル（model / market の生Harville確率）を作る。"""
    n = len(r["ns"])
    if n < 4:
        return None
    tri, p3m = FP.trio_probs(r["w_model"])
    _, p3k = FP.trio_probs(r["p_market"])
    nums = np.array(r["ns"])
    keys = nums[tri]                       # (m,3) 馬番
    keys_sorted = np.sort(keys, axis=1)
    win = tuple(sorted(r["top3"]))
    hit = -1
    for i, k in enumerate(keys_sorted):
        if tuple(int(x) for x in k) == win:
            hit = i
            break
    # ワイド用: 各ペアがどの三連複組に含まれるか（三連複確率の集約で作る）
    iu = np.triu_indices(n, 1)
    pair_keys = [tuple(sorted((int(nums[i]), int(nums[j])))) for i, j in zip(*iu)]
    pidx = {}
    for a in range(n):
        for b in range(a + 1, n):
            pidx[(a, b)] = len(pidx)
    Amap = np.zeros((len(tri), 3), dtype=np.int64)
    for c, (i, j, k) in enumerate(tri):
        Amap[c] = [pidx[(i, j)], pidx[(i, k)], pidx[(j, k)]]
    # pair_keys の並びを pidx の並びに合わせ直す
    order_keys = [None] * len(pidx)
    for a in range(n):
        for b in range(a + 1, n):
            order_keys[pidx[(a, b)]] = tuple(sorted((int(nums[a]), int(nums[b]))))
    return dict(tri_keys=[tuple(int(x) for x in k) for k in keys_sorted],
                p3m=p3m, p3k=p3k, hit3=hit,
                pair_keys=order_keys, Amap=Amap, npair=len(pidx))


def temp_mle(rows):
    """p_cal ∝ p^γ（レース内で和1に再正規化）の γ を的中組の尤度で最尤推定。
       rows = [(log確率ベクトル, 的中index)]。計算量のため直近 GAMMA_WINDOW レースを使う。"""
    use = [(lp, h) for lp, h in rows if h >= 0]
    if len(use) < 50:
        return None

    def nll(g):
        s = 0.0
        for lp, h in use:
            x = g * lp
            mx = x.max()
            s -= (x[h] - mx - np.log(np.exp(x - mx).sum()))
        return s
    res = minimize_scalar(nll, bounds=(0.2, 3.0), method="bounded",
                          options={"xatol": 1e-4})
    return float(res.x)


def temp_apply(p, g, total=1.0):
    x = g * np.log(np.clip(p, 1e-300, None))
    x -= x.max()
    e = np.exp(x)
    return total * e / e.sum()


def payout_calib(rows):
    """rows=[(log(1/p_cal), log(pay/100))] -> (a,b): log odds_est = a + b·log(1/p)"""
    if len(rows) < 30:
        return None
    x = np.array([r[0] for r in rows]); y = np.array([r[1] for r in rows])
    X = np.stack([np.ones_like(x), x], axis=1)
    c, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(c[0]), float(c[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--out", default="place_combo_result.json")
    a = ap.parse_args()
    out = {}

    for v in a.variants.split(","):
        print(f"\n{'='*72}\n{v}\n{'='*72}", flush=True)
        races, dropped = PE.load_ledger(f"place_preds_{v}.jsonl")
        PE.prep(races)
        months = sorted({r["month"] for r in races})
        by_m = {m: [r for r in races if r["month"] == m] for m in months}
        print(f"races={len(races)} months={months[0]}..{months[-1]}", flush=True)

        T = {}
        for r in races:
            t = race_tables(r)
            if t is not None:
                T[r["rid"]] = t
        print(f"組合せテーブル作成 {len(T)}R", flush=True)

        from collections import deque
        hist = dict(p3m=deque(maxlen=GAMMA_WINDOW), p3k=deque(maxlen=GAMMA_WINDOW),
                    pay3=[], pay2=[])
        bets = defaultdict(float)
        topk = defaultdict(float)
        gam_log, cal_log = {}, {}
        for mi, m in enumerate(months):
            # ── α_place の二段目を月次WFで再推定し、ブレンド3着内確率を作る ──
            tr = [r for mm in months[:mi] for r in by_m[mm]]
            th = None
            if len(tr) >= 200:
                X, y, _g = PE.stack(tr)
                th = PE.fit_logit(X, y)
            for r in by_m[m]:
                if th is None:
                    continue
                z = (th[0] * PE._logit(r["q_model"]) + th[1] * PE._logit(r["q_market"]) + th[2])
                r["q_blend"] = PE.norm_place(PE._sig(z))
                r["w_blend"] = FP.pl_from_place(r["q_blend"])
            gm = temp_mle(hist["p3m"])
            gk = temp_mle(hist["p3k"])
            c3 = payout_calib(hist["pay3"])
            c2 = payout_calib(hist["pay2"])
            gam_log[m] = dict(g_model=None if gm is None else round(gm, 4),
                              g_market=None if gk is None else round(gk, 4),
                              n_gamma=len(hist["p3m"]), n_pay3=len(hist["pay3"]))
            cal_log[m] = dict(trio=c3, wide=c2)
            for r in by_m[m]:
                t = T.get(r["rid"])
                if t is None:
                    continue
                if gm and gk:
                    p3m = temp_apply(t["p3m"], gm)
                    p3k = temp_apply(t["p3k"], gk)
                    p3b = (temp_apply(FP.trio_probs(r["w_blend"])[1], gm)
                           if "w_blend" in r else None)
                    # ワイド = 較正済み三連複確率をペアへ集約（和=3が自動で保たれる）
                    p2m = np.zeros(t["npair"]); p2k = np.zeros(t["npair"])
                    np.add.at(p2m, t["Amap"].ravel(), np.repeat(p3m, 3))
                    np.add.at(p2k, t["Amap"].ravel(), np.repeat(p3k, 3))
                    p2b = None
                    if p3b is not None:
                        p2b = np.zeros(t["npair"])
                        np.add.at(p2b, t["Amap"].ravel(), np.repeat(p3b, 3))
                    sp = r["split"]
                    # ── (A) 事前登録のEV検証（推定オッズが必要） ──
                    if c3 and c2:
                        srcs = [("", p3m, p2m)] + ([("bl_", p3b, p2b)] if p3b is not None else [])
                        for pref, q3, q2 in srcs:
                            for tag, keys, pm, pk, cc, paydict in (
                                    ("trio", t["tri_keys"], q3, p3k, c3, r["pay_trio"]),
                                    ("wide", t["pair_keys"], q2, p2k, c2, r["pay_wide"])):
                                a_, b_ = cc
                                o_est = np.exp(a_ + b_ * np.log(1.0 / np.clip(pk, 1e-300, None)))
                                ev = pm * o_est
                                bets[f"{sp}/{pref}{tag}_races"] += 1
                                bets[f"{sp}/{pref}{tag}_maxev"] = max(
                                    bets[f"{sp}/{pref}{tag}_maxev"], float(ev.max()))
                                for i in np.where(ev >= EV_TH)[0]:
                                    p = paydict.get(keys[i], 0)
                                    bets[f"{sp}/{pref}{tag}_n"] += 1
                                    bets[f"{sp}/{pref}{tag}_pay"] += p
                                    bets[f"{sp}/{pref}{tag}_hit"] += (1 if p else 0)
                                    bets[f"{sp}/{pref}{tag}_evsum"] += float(ev[i])
                                    bets[f"{sp}/{pref}{tag}_pmsum"] += float(pm[i])
                    # ── (B) オッズ推定を一切使わない top-k flat（払戻は実測のみ） ──
                    for src, q3, q2 in (("mdl", p3m, p2m), ("mkt", p3k, p2k),
                                        ("bl", p3b, p2b)):
                        if q3 is None:
                            continue
                        o3 = np.argsort(-q3)
                        for K in (1, 3, 5, 10, 20):
                            if K > len(o3):
                                continue
                            pay = sum(r["pay_trio"].get(t["tri_keys"][i], 0) for i in o3[:K])
                            topk[f"{sp}/{src}/trio{K}_n"] += K
                            topk[f"{sp}/{src}/trio{K}_pay"] += pay
                            topk[f"{sp}/{src}/trio{K}_hit"] += (1 if pay else 0)
                            topk[f"{sp}/{src}/trio{K}_R"] += 1
                        o2 = np.argsort(-q2)
                        for K in (1, 2, 3, 5):
                            if K > len(o2):
                                continue
                            pay = sum(r["pay_wide"].get(t["pair_keys"][i], 0) for i in o2[:K])
                            hits = sum(1 for i in o2[:K] if r["pay_wide"].get(t["pair_keys"][i], 0))
                            topk[f"{sp}/{src}/wide{K}_n"] += K
                            topk[f"{sp}/{src}/wide{K}_pay"] += pay
                            topk[f"{sp}/{src}/wide{K}_hit"] += hits
                            topk[f"{sp}/{src}/wide{K}_R"] += 1
                # 履歴へ追加（当月の結果は当月の判定に使っていない）
                if t["hit3"] >= 0:
                    hist["p3m"].append((np.log(np.clip(t["p3m"], 1e-300, None)), t["hit3"]))
                    hist["p3k"].append((np.log(np.clip(t["p3k"], 1e-300, None)), t["hit3"]))
                if gk and t["hit3"] >= 0:
                    pk_cal = temp_apply(t["p3k"], gk)
                    p2k_cal = np.zeros(t["npair"])
                    np.add.at(p2k_cal, t["Amap"].ravel(), np.repeat(pk_cal, 3))
                    pay = r["pay_trio"].get(tuple(sorted(r["top3"])), 0)
                    if pay:
                        hist["pay3"].append((float(np.log(1 / max(pk_cal[t["hit3"]], 1e-300))),
                                             float(np.log(pay / 100.0))))
                    for pr, pv in r["pay_wide"].items():
                        if pr in t["pair_keys"]:
                            i = t["pair_keys"].index(pr)
                            hist["pay2"].append((float(np.log(1 / max(p2k_cal[i], 1e-300))),
                                                 float(np.log(pv / 100.0))))
            print(f"{m}[{PE.split_of(m)}] γmodel={gm} γmarket={gk} "
                  f"trio_cal={None if not c3 else [round(x,3) for x in c3]} "
                  f"wide_cal={None if not c2 else [round(x,3) for x in c2]}", flush=True)

        res = dict(gamma=gam_log, payout_calib=cal_log, splits={}, topk={})
        for sp, _, _ in PE.SPLITS:
            d = {}
            for tag in ("trio", "wide", "bl_trio", "bl_wide"):
                n = bets[f"{sp}/{tag}_n"]
                d[tag] = dict(n=int(n), races=int(bets[f"{sp}/{tag}_races"]),
                              hits=int(bets[f"{sp}/{tag}_hit"]),
                              roi=round(bets[f"{sp}/{tag}_pay"] / (100 * n) * 100, 1) if n else None,
                              mean_ev=round(bets[f"{sp}/{tag}_evsum"] / n, 3) if n else None,
                              mean_p=round(bets[f"{sp}/{tag}_pmsum"] / n, 5) if n else None,
                              max_ev_seen=round(bets[f"{sp}/{tag}_maxev"], 3))
            res["splits"][sp] = d
        for sp, _, _ in PE.SPLITS:
            d = {}
            for src in ("mdl", "mkt", "bl"):
                for tag, Ks in (("trio", (1, 3, 5, 10, 20)), ("wide", (1, 2, 3, 5))):
                    for K in Ks:
                        n = topk[f"{sp}/{src}/{tag}{K}_n"]
                        if n:
                            d[f"{src}/{tag}{K}"] = dict(
                                n=int(n), races=int(topk[f"{sp}/{src}/{tag}{K}_R"]),
                                hits=int(topk[f"{sp}/{src}/{tag}{K}_hit"]),
                                roi=round(topk[f"{sp}/{src}/{tag}{K}_pay"] / (100 * n) * 100, 1))
            res["topk"][sp] = d

        print("\n[較正後 組合せEV≥1.2]")
        for sp, _, _ in PE.SPLITS:
            for tag, jp in (("trio", "三連複     "), ("wide", "ワイド     "),
                            ("bl_trio", "三連複blend"), ("bl_wide", "ワイドblend")):
                x = res["splits"][sp][tag]
                print(f"  {sp:9s} {jp} n={x['n']:6d} 的中{x['hits']:5d} "
                      f"ROI={x['roi'] if x['roi'] is not None else '—'}% "
                      f"平均EV={x['mean_ev']} 全組合せ中の最大EV={x['max_ev_seen']}")
        print("\n[オッズ推定なし top-k flat（実払戻のみ）]")
        for sp, _, _ in PE.SPLITS:
            for tag, Ks in (("trio", (1, 5, 20)), ("wide", (1, 3))):
                row = []
                for src, jp in (("mdl", "model"), ("bl", "blend"), ("mkt", "market")):
                    for K in Ks:
                        x = res["topk"][sp].get(f"{src}/{tag}{K}")
                        if x:
                            row.append(f"{jp}top{K} {x['roi']:5.1f}%({x['hits']}/{x['races']}R)")
                print(f"  {sp:9s} {tag:5s} " + " | ".join(row))
        out[v] = res

    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
