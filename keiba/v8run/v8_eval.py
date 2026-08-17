# -*- coding: utf-8 -*-
"""V8 評価（V8_PROTOCOL_20260817.md の機械適用）。

1) 一次判定: V7二段構成(fit_v7.py の関数をそのまま使用)に各variantのV8スコアを載せ、
   市場オッズを条件にした α を月次WFで再推定 → α>0 が3フォールド連続か。
2) 二次判定: EV = p_blend×オッズ ≥1.2 の単勝flat100円が
   VALIDATE n≥40・ROI≥110% / CONFIRM n≥25・ROI≥105%。
3) 補助: モデル1位勝率・単勝flat ROI・NDCG@3 を3分割別に。

usage: python3 v8_eval.py v8base,v8f1,v8f2,v8f4,v8all
"""
import json, math, sys
import numpy as np
import fit_v7 as F7

SPLITS = {"MINE": ("000000", "202602"),
          "VALIDATE": ("202603", "202605"),
          "CONFIRM": ("202606", "202608")}
THRESHOLDS = [1.2, 1.3, 1.5]
MAIN_T = 1.2
IDCG3 = 7.0 / math.log2(2) + 3.0 / math.log2(3) + 1.0 / math.log2(4)


def split_of(m):
    for k, (lo, hi) in SPLITS.items():
        if lo <= m <= hi:
            return k
    return None


# ── 補助指標（台帳から直接・αとは独立） ─────────────────────────────
def aux_metrics(path):
    acc = {k: dict(n=0, win=0, imp=0.0, spend=0, ret=0.0, ndcg=0.0, hit3=0)
           for k in SPLITS}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        sp = split_of(d["month"])
        if sp is None:
            continue
        a = acc[sp]
        order = [int(x) for x in d["order"]]
        odds = {int(k): float(v) for k, v in d["odds"].items()}
        top3 = [int(x) for x in d["top3"]]
        win = top3[0]
        t1 = order[0]
        a["n"] += 1
        a["win"] += (t1 == win)
        if odds.get(t1):
            a["imp"] += 0.8 / odds[t1]
            a["spend"] += 100
            pay = (d.get("payout") or {}).get("単勝", {}).get(str(t1))
            a["ret"] += (float(pay) if pay else odds[t1] * 100) if t1 == win else 0.0
        rel = {top3[0]: 7.0, top3[1]: 3.0, top3[2]: 1.0}
        a["ndcg"] += sum(rel.get(h, 0.0) / math.log2(i + 2)
                         for i, h in enumerate(order[:3])) / IDCG3
        a["hit3"] += sum(1 for h in order[:3] if h in rel)
    out = {}
    for k, a in acc.items():
        n = max(a["n"], 1)
        out[k] = dict(n=a["n"],
                      win1=a["win"] / n * 100,
                      imp1=a["imp"] / n * 100,
                      diff=(a["win"] / n - a["imp"] / n) * 100,
                      tan_roi=(a["ret"] / a["spend"] * 100) if a["spend"] else 0.0,
                      ndcg3=a["ndcg"] / n,
                      cap3=a["hit3"] / (3 * n) * 100)
    return out


# ── 一次判定: V7二段構成の α 再推定（fit_v7 の関数をそのまま使う） ──────
def run_v7(path, tag):
    races, dropped, month_scale = F7.load_races(path)
    months = sorted({r["month"] for r in races})
    by_month = {m: [r for r in races if r["month"] == m] for m in months}
    folds, bets = {}, []
    for mi, m in enumerate(months):
        train = [r for mm in months[:mi] for r in by_month[mm]]
        if len(train) < 200:
            folds[m] = dict(skipped=True, train_races=len(train))
            continue
        S, Q, M_, ZF, ZM, W = F7.pad(train)
        tau = F7.fit_tau(S, M_, W)
        X = F7.stage2_features(S, Q, M_, ZF, ZM, tau)
        theta, nll = F7.fit_stage2(X, M_, W)
        alpha, beta, gf, gm = [float(t) for t in theta]
        folds[m] = dict(tau=round(tau, 4), alpha=round(alpha, 4), beta=round(beta, 4),
                        gamma_field=round(gf, 4), gamma_maiden=round(gm, 4),
                        train_races=len(train))
        ev = by_month[m]
        Se, Qe, Me, ZFe, ZMe, We = F7.pad(ev)
        Xe = F7.stage2_features(Se, Qe, Me, ZFe, ZMe, tau)
        Ue = np.tensordot(theta, Xe, axes=1)
        LPb = F7.log_softmax_masked(Ue, Me)
        LPm = F7.log_softmax_masked(tau * Se, Me)
        for i, r in enumerate(ev):
            k = len(r["ns"])
            pb = np.exp(LPb[i, :k]); pmod = np.exp(LPm[i, :k]); pmkt = np.exp(Qe[i, :k])
            for j, h in enumerate(r["ns"]):
                bets.append(dict(rid=r["rid"], month=m, horse=h,
                                 odds=float(r["odds"][j]),
                                 p_model=float(pmod[j]), p_market=float(pmkt[j]),
                                 p_blend=float(pb[j]), ev=float(pb[j] * r["odds"][j]),
                                 model_rank=j + 1, win=int(j == r["win_idx"]),
                                 pay=r["tan"].get(h, 0)))
    json.dump(folds, open(f"v8_folds_{tag}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return folds, bets, dropped


def ll_by_split(bets):
    """1レースあたり平均log尤度（勝者の確率）"""
    agg = {k: {"m": [], "mo": [], "b": []} for k in SPLITS}
    for b in bets:
        if not b["win"]:
            continue
        sp = split_of(b["month"])
        if sp is None:
            continue
        agg[sp]["m"].append(math.log(max(b["p_market"], 1e-12)))
        agg[sp]["mo"].append(math.log(max(b["p_model"], 1e-12)))
        agg[sp]["b"].append(math.log(max(b["p_blend"], 1e-12)))
    return {k: {kk: (float(np.mean(v[kk])) if v[kk] else float("nan"))
                for kk in ("m", "mo", "b")} for k, v in agg.items()}


def roi(bs):
    n = len(bs)
    spend = 100 * n
    ret = sum(b["pay"] for b in bs if b["win"])
    hits = sum(b["win"] for b in bs)
    return n, ret / spend * 100 if spend else 0.0, hits


def main():
    variants = sys.argv[1].split(",")
    summary = {}
    for v in variants:
        path = f"wf_preds_{v}.jsonl"
        print(f"\n{'='*70}\n### {v}\n{'='*70}", flush=True)
        aux = aux_metrics(path)
        for k in ("MINE", "VALIDATE", "CONFIRM"):
            a = aux[k]
            print(f"[{k:8s}] n={a['n']:4d}R 1位勝率{a['win1']:5.1f}% "
                  f"(市場implied{a['imp1']:5.1f}% → {a['diff']:+.1f}pt) "
                  f"単勝flatROI {a['tan_roi']:6.1f}%  NDCG@3 {a['ndcg3']:.4f} "
                  f"捕捉3 {a['cap3']:.1f}%")
        folds, bets, dropped = run_v7(path, v)
        ms = sorted(folds)
        print(f"-- α推移 (dropped={len(dropped)}) --")
        for m in ms:
            f = folds[m]
            if f.get("skipped"):
                print(f"  {m}: skip(train={f['train_races']}R)")
            else:
                print(f"  {m}[{split_of(m)[:1]}]: train={f['train_races']:5d}R "
                      f"τ={f['tau']:.3f} α={f['alpha']:+.4f} β={f['beta']:.3f} "
                      f"γf={f['gamma_field']:+.3f} γm={f['gamma_maiden']:+.3f}")
        alphas = [(m, folds[m]["alpha"]) for m in ms if not folds[m].get("skipped")]
        pos = [m for m, x in alphas if x > 0]
        streak = best = 0
        for m, x in alphas:
            streak = streak + 1 if x > 0 else 0
            best = max(best, streak)
        print(f"  α>0 のfold数 {len(pos)}/{len(alphas)} / 最長連続 {best} "
              f"→ 一次判定 {'合格(3連続以上)' if best >= 3 else '不合格'}")
        lls = ll_by_split(bets)
        for k in ("MINE", "VALIDATE", "CONFIRM"):
            L = lls[k]
            print(f"  logLik/R [{k:8s}] market {L['m']:.4f} / model {L['mo']:.4f} "
                  f"/ blend {L['b']:.4f}")
        print("-- EV閾値別 --")
        ev_res = {}
        for k in ("MINE", "VALIDATE", "CONFIRM"):
            row = []
            for t in THRESHOLDS:
                bs = [b for b in bets if split_of(b["month"]) == k and b["ev"] >= t]
                n, r, h = roi(bs)
                row.append((t, n, r, h))
            ev_res[k] = row
            print(f"  [{k:8s}] " + " | ".join(
                f"EV≥{t}: n={n} ROI={r:.1f}% 的中{h}" for t, n, r, h in row))
        evmax = {}
        for k in ("MINE", "VALIDATE", "CONFIRM"):
            per = {}
            for b in bets:
                if split_of(b["month"]) == k:
                    per[b["rid"]] = max(per.get(b["rid"], 0.0), b["ev"])
            vals = sorted(per.values())
            evmax[k] = dict(med=float(np.median(vals)) if vals else float("nan"),
                            p99=float(np.percentile(vals, 99)) if vals else float("nan"),
                            mx=max(vals) if vals else float("nan"))
            print(f"  レース内EV最大 [{k:8s}] 中央値{evmax[k]['med']:.3f} "
                  f"99%点{evmax[k]['p99']:.3f} 最大{evmax[k]['mx']:.3f}")
        summary[v] = dict(aux=aux, alphas=alphas, best_streak=best,
                          n_pos=len(pos), ll=lls, ev=ev_res, evmax=evmax)
    json.dump(summary, open("v8_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print("\nwrote v8_summary.json")


if __name__ == "__main__":
    main()
