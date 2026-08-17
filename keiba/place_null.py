# -*- coding: utf-8 -*-
"""α_place のヌル検査（RULES.md §偽陽性率の要求）。

モデルの3着内確率をレース内でシャッフルして情報を完全に破壊し、
同じ手順で α_place を推定する。実力ゼロのはずなので α≈0 でなければ
「手順そのものが正の α を作る」＝偽陽性であることになる。

usage: python3 place_null.py --variant v8place --seeds 8
"""
import argparse, json

import numpy as np

import place_eval as PE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="v8place")
    ap.add_argument("--fold", default="202608")
    ap.add_argument("--seeds", type=int, default=8)
    a = ap.parse_args()

    races, _ = PE.load_ledger(f"place_preds_{a.variant}.jsonl")
    PE.prep(races)
    tr = [r for r in races if r["month"] < a.fold]
    X, y, g = PE.stack(tr)
    th = PE.fit_logit(X, y)
    se = PE.cluster_se(X, y, g, th)
    print(f"[実データ] {a.variant} fold={a.fold} train={len(tr)}R  "
          f"α={th[0]:+.4f} (se {se[0]:.4f}, z {th[0]/se[0]:+.2f}) β={th[1]:+.4f}")

    q0 = [r["q_model"].copy() for r in tr]
    alphas = []
    for s in range(a.seeds):
        rng = np.random.default_rng(1000 + s)
        for r, q in zip(tr, q0):
            r["q_model"] = q[rng.permutation(len(q))]
        Xn, yn, gn = PE.stack(tr)
        thn = PE.fit_logit(Xn, yn)
        sen = PE.cluster_se(Xn, yn, gn, thn)
        alphas.append(float(thn[0]))
        print(f"  null seed{s}: α={thn[0]:+.4f} (se {sen[0]:.4f}, z {thn[0]/sen[0]:+.2f}) "
              f"β={thn[1]:+.4f}")
    for r, q in zip(tr, q0):
        r["q_model"] = q
    out = dict(variant=a.variant, fold=a.fold, train_races=len(tr),
               alpha_real=round(float(th[0]), 4), se_real=round(float(se[0]), 4),
               beta_real=round(float(th[1]), 4),
               alpha_null=[round(x, 4) for x in alphas],
               alpha_null_mean=round(float(np.mean(alphas)), 4),
               alpha_null_max=round(float(np.max(alphas)), 4),
               null_ge_real=int(sum(1 for x in alphas if x >= th[0])))
    print(f"→ ヌルの α: 平均{out['alpha_null_mean']:+.4f} 最大{out['alpha_null_max']:+.4f} / "
          f"実データ以上は {out['null_ge_real']}/{a.seeds}")
    json.dump(out, open("place_null_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
