# -*- coding: utf-8 -*-
"""反芻ラウンド2: KPI「3着内馬がモデル5位以内」を直接狙うペアワイズ学習。
   目的: 各レースで(3着内馬, 非3着内馬)の全ペアについて 3着内馬が上に来るよう
   ロジスティック損失で学習(AUC最大化≒捕捉率最大化)。市場情報は不使用。
   参考として市場(オッズ順)の捕捉率も表示=事実上の天井の目安。

   usage: python3 fit_v2cap.py [--l2 0.03] [--write]
"""
import argparse, json, math, sys
import fit_v2 as V2
from fit_v2win import winner_metrics

FEATS = V2.FEATS


def pair_nll_grad(ds, w, l2):
    nll = 0.0
    g = [0.0]*len(FEATS)
    n_obs = 0
    for r in ds:
        s = V2.scores(r, w)
        t3 = set(r["top3"])
        outs = [n for n in r["ns"] if n not in t3]
        for f in r["top3"]:
            for o in outs:
                d = s[f] - s[o]
                pl = 1.0/(1.0 + math.exp(-d))   # P(正しい順)
                nll += -math.log(max(pl, 1e-12))
                n_obs += 1
                coef = -(1.0 - pl)
                for i, k in enumerate(FEATS):
                    g[i] += coef*(r["X"][k][f] - r["X"][k][o])
    for i in range(len(FEATS)):
        g[i] = g[i]/n_obs + 2*l2*w[i]
    return nll/n_obs + l2*sum(x*x for x in w), g


def fit(train, l2, iters=250, lr=0.5):
    w = [0.0]*len(FEATS)
    m = [0.0]*len(FEATS)
    for it in range(iters):
        nll, g = pair_nll_grad(train, w, l2)
        for i in range(len(FEATS)):
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
        if it % 50 == 0:
            print(f"  iter{it}: pairNLL={nll:.4f}", file=sys.stderr)
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="20260704,20260705,20260711,20260712")
    ap.add_argument("--l2", type=float, default=0.03)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = V2.load_dataset("hist", "hist_feat")
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: train {len(train)} / test {len(test)}")

    w = fit(train, a.l2)
    print("\n学習した重み（捕捉ペアワイズ・市場情報なし）:")
    for k, v in zip(FEATS, w):
        print(f"  {k:12s} {v:+.3f}")

    pv = json.load(open("params_v2.json", encoding="utf-8"))
    for name, dset in (("train", train), ("test", test)):
        print(f"\n── {name} ──")
        winner_metrics(dset, lambda r: {n: -sorted(r['odds'], key=lambda h: r['odds'][h]).index(n)
                                        if n in r['odds'] else -99 for n in r['ns']},
                       "市場(最終オッズ順)=参考天井")
        winner_metrics(dset, lambda r: V2.scores(r, pv["weights_win"]), "Ver.2-WIN")
        winner_metrics(dset, lambda r: V2.scores(r, w), "Ver.2-CAP(捕捉ペアワイズ)")

    if a.write:
        pv["weights_cap"] = [round(x, 4) for x in w]
        json.dump(pv, open("params_v2.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nparams_v2.json に weights_cap を保存した。")


if __name__ == "__main__":
    main()
