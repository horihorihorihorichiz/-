# -*- coding: utf-8 -*-
"""3着内の「並び」の質を市場と直接比較する（V8報告の NDCG@3 と同じ土俵）。

指標:
  捕捉3    … 予測上位3頭のうち実際に3着内だった頭数 / 3
  NDCG@3   … 3着内=利得1（着順は区別しない）の NDCG@3
  Brier    … 3着内確率の Brier スコア（1頭あたり・小さいほど良い）
比較対象: model（3着内特化モデル単体） / market（単勝オッズのHarville） / blend（α_place二段目）
差の不確実性はレース対応のペアード・ブートストラップ（10,000回）で出す。

usage: python3 place_rank.py --variants v3place,v8place
"""
import argparse, json

import numpy as np

import fit_place as FP
import place_eval as PE

DISC = 1.0 / np.log2(np.arange(2, 5))          # 1位,2位,3位の割引
IDCG = DISC.sum()


def ndcg3(q, yset, ns):
    o = np.argsort(-q)[:3]
    g = np.array([1.0 if ns[i] in yset else 0.0 for i in o])
    return float((g * DISC[:len(g)]).sum() / IDCG)


def boot(diff, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    d = np.asarray(diff, dtype=float)
    idx = rng.integers(0, len(d), size=(n, len(d)))
    ms = d[idx].mean(axis=1)
    return float(d.mean()), float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5)), \
        float((ms > 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--out", default="place_rank_result.json")
    a = ap.parse_args()
    out = {}
    for v in a.variants.split(","):
        print(f"\n{'='*72}\n{v}\n{'='*72}", flush=True)
        races, _ = PE.load_ledger(f"place_preds_{v}.jsonl")
        PE.prep(races)
        months = sorted({r["month"] for r in races})
        by_m = {m: [r for r in races if r["month"] == m] for m in months}
        rows = []
        for mi, m in enumerate(months):
            tr = [r for mm in months[:mi] for r in by_m[mm]]
            if len(tr) < 200:
                continue
            X, y, _g = PE.stack(tr)
            th = PE.fit_logit(X, y)
            for r in by_m[m]:
                z = th[0] * PE._logit(r["q_model"]) + th[1] * PE._logit(r["q_market"]) + th[2]
                qb = PE.norm_place(PE._sig(z))
                ys = set(r["top3"])
                rec = dict(split=r["split"], month=m)
                for name, q in (("mdl", r["q_model"]), ("mkt", r["q_market"]), ("bl", qb)):
                    o = np.argsort(-q)[:3]
                    rec[f"{name}_cap"] = sum(1 for i in o if r["ns"][i] in ys) / 3.0
                    rec[f"{name}_ndcg"] = ndcg3(q, ys, r["ns"])
                    rec[f"{name}_brier"] = float(np.mean((q - r["y"]) ** 2))
                rows.append(rec)
        res = {}
        for sp in ("MINE", "VALIDATE", "CONFIRM", "V+C"):
            sub = [r for r in rows if (r["split"] == sp if sp != "V+C"
                                       else r["split"] in ("VALIDATE", "CONFIRM"))]
            if not sub:
                continue
            d = dict(n=len(sub))
            for name in ("mdl", "mkt", "bl"):
                d[name] = {k: round(float(np.mean([r[f"{name}_{k}"] for r in sub])), 5)
                           for k in ("cap", "ndcg", "brier")}
            for tag, aa, bb in (("mdl-mkt", "mdl", "mkt"), ("bl-mkt", "bl", "mkt")):
                for k in ("cap", "ndcg", "brier"):
                    mu, lo, hi, p = boot([r[f"{aa}_{k}"] - r[f"{bb}_{k}"] for r in sub])
                    d[f"{tag}/{k}"] = dict(mean=round(mu, 5), lo=round(lo, 5),
                                           hi=round(hi, 5), p_gt0=round(p, 3))
            res[sp] = d
            print(f"[{sp}] n={d['n']}")
            for name in ("mdl", "mkt", "bl"):
                print(f"   {name:4s} 捕捉3={d[name]['cap']*100:.2f}% NDCG@3={d[name]['ndcg']:.4f} "
                      f"Brier={d[name]['brier']:.4f}")
            for tag in ("mdl-mkt", "bl-mkt"):
                x = d[f"{tag}/ndcg"]; c = d[f"{tag}/cap"]; b = d[f"{tag}/brier"]
                print(f"   Δ{tag}: NDCG {x['mean']:+.4f} [{x['lo']:+.4f},{x['hi']:+.4f}] "
                      f"P(>0)={x['p_gt0']} | 捕捉3 {c['mean']*100:+.2f}pt P(>0)={c['p_gt0']}"
                      f" | Brier {b['mean']:+.5f} P(>0)={b['p_gt0']}")
        out[v] = res
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
