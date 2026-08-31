# -*- coding: utf-8 -*-
"""α_place の頑健性検査 — 「Harville近似のクセを直しているだけ」ではないかを潰す。

主指標の α_place は
    P(3着内_i) = σ( α·logit q_model_i + β·logit q_market_i + c )
で測るが、q_market は **単勝オッズのHarville近似**であり、それ自体が系統的に歪んでいる
（place_eval.py の較正表: q=0.039→実際0.052 / q=0.937→実際0.877）。
したがって α>0 は「モデルが市場を超える情報を持つ」ではなく
「モデルがHarvilleの歪みの形を代理している」だけかもしれない。

そこで市場側を **単勝オッズだけから作れる最も柔軟な形** に置き換えて再測定する:
    flex: β1·logit q_market + β2·(logit q_market)^2 + β3·(logit q_market)^3
          + β4·logit p_win + β5·z_field
（p_win = 控除率補正済み単勝勝率そのもの、z_field = (頭数-12)/4）
この下でも α>0 が残るなら、「単勝オッズのどんな変換でも作れない情報」を
モデルが持っていることになる（＝Harville歪みの代理では説明できない）。

併せて **out-of-sample の対数損失**（1頭あたり）を市場のみ / registered / flex で比較する。
α の符号ではなく、実際に予測が良くなっているかを直接測るため。

usage: python3 place_alpha_robust.py --variants v3place,v8place
"""
import argparse, json

import numpy as np

import place_eval as PE

SPECS = {
    "market_only": ["mkt", "one"],
    "registered": ["mdl", "mkt", "one"],
    "flex": ["mdl", "mkt", "mkt2", "mkt3", "pwin", "zf", "one"],
    "flex_nomodel": ["mkt", "mkt2", "mkt3", "pwin", "zf", "one"],
}


def feats(r, keys):
    lm = PE._logit(r["q_model"])
    lk = PE._logit(r["q_market"])
    lw = np.log(np.clip(r["p_market"], 1e-9, None))
    n = len(r["ns"])
    zf = np.full(n, (r["field"] - 12) / 4.0)
    tbl = dict(mdl=lm, mkt=lk, mkt2=lk ** 2, mkt3=lk ** 3, pwin=lw, zf=zf,
               one=np.ones(n))
    return np.stack([tbl[k] for k in keys], axis=1)


def stackx(races, keys):
    X = np.concatenate([feats(r, keys) for r in races])
    y = np.concatenate([r["y"] for r in races])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(races)])
    return X, y, g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--out", default="place_alpha_robust.json")
    a = ap.parse_args()
    out = {}
    for v in a.variants.split(","):
        print(f"\n{'='*72}\n{v}\n{'='*72}", flush=True)
        races, _ = PE.load_ledger(f"place_preds_{v}.jsonl")
        PE.prep(races)
        months = sorted({r["month"] for r in races})
        by_m = {m: [r for r in races if r["month"] == m] for m in months}
        res = dict(folds={}, oos={})
        ll = {k: {} for k in SPECS}
        nn = {}
        for mi, m in enumerate(months):
            tr = [r for mm in months[:mi] for r in by_m[mm]]
            if len(tr) < 200:
                continue
            ev = by_m[m]
            sp = PE.split_of(m)
            row = dict(train=len(tr), split=sp)
            for name, keys in SPECS.items():
                X, y, g = stackx(tr, keys)
                th = PE.fit_logit(X, y)
                if name in ("registered", "flex"):
                    se = PE.cluster_se(X, y, g, th)
                    row[f"{name}_alpha"] = round(float(th[0]), 4)
                    row[f"{name}_se"] = round(float(se[0]), 4)
                    row[f"{name}_z"] = round(float(th[0] / max(se[0], 1e-9)), 2)
                Xe, ye, _ = stackx(ev, keys)
                p = PE._sig(Xe @ th)
                l = -(ye * np.log(np.clip(p, 1e-12, None))
                      + (1 - ye) * np.log(np.clip(1 - p, 1e-12, None))).sum()
                ll[name][sp] = ll[name].get(sp, 0.0) + float(l)
                ll[name]["ALL"] = ll[name].get("ALL", 0.0) + float(l)
            nn[sp] = nn.get(sp, 0) + int(sum(len(r["ns"]) for r in ev))
            nn["ALL"] = nn.get("ALL", 0) + int(sum(len(r["ns"]) for r in ev))
            res["folds"][m] = row
            print(f"{m}[{sp}] train={len(tr):5d}R  registered α={row['registered_alpha']:+.4f}"
                  f"(z{row['registered_z']:+.2f})   flex α={row['flex_alpha']:+.4f}"
                  f"(z{row['flex_z']:+.2f})", flush=True)
        for sp in ("MINE", "VALIDATE", "CONFIRM", "ALL"):
            if sp not in nn:
                continue
            d = {k: round(ll[k][sp] / nn[sp], 6) for k in SPECS}
            d["n_horses"] = nn[sp]
            d["gain_registered_vs_market"] = round(d["market_only"] - d["registered"], 6)
            d["gain_flex_vs_flexnomodel"] = round(d["flex_nomodel"] - d["flex"], 6)
            res["oos"][sp] = d
        print("\n[out-of-sample 対数損失 / 1頭]")
        for sp, d in res["oos"].items():
            print(f"  {sp:9s} n={d['n_horses']:7d}  市場のみ {d['market_only']:.5f} | "
                  f"registered {d['registered']:.5f} (改善{d['gain_registered_vs_market']:+.6f}) | "
                  f"flex-no-model {d['flex_nomodel']:.5f} | flex {d['flex']:.5f} "
                  f"(改善{d['gain_flex_vs_flexnomodel']:+.6f})")
        # α>0 の連続数
        for name in ("registered", "flex"):
            xs = [res["folds"][m][f"{name}_alpha"] for m in sorted(res["folds"])]
            run = best = 0
            for x in xs:
                run = run + 1 if x > 0 else 0
                best = max(best, run)
            res[f"{name}_pos"] = sum(1 for x in xs if x > 0)
            res[f"{name}_n"] = len(xs)
            res[f"{name}_maxrun"] = best
            print(f"  {name}: α>0 {res[f'{name}_pos']}/{len(xs)}fold 最長連続={best}")
        out[v] = res
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
