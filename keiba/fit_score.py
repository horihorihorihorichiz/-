# -*- coding: utf-8 -*-
"""得点システム(WAvg)の構成要素の重みをデータで学習する（Ver.100.1）。
   現行: s2 = tsi+lts+fsi+bonus+dsi+nsi+csi+was+tas+hcs+nrja（全部重み1）× 展開乗数
   本スクリプト: score = Σ w_k·feature_k を Plackett-Luce(上位3頭の並び)の尤度で学習。
   ホールドアウトで現行(等重み)に勝った時だけ params.json に score_weights を書く。

   usage: python3 fit_score.py [--test 20260711,20260712] [--l2 0.3] [--write]
"""
import argparse, glob, json, math, os, sys
import calc

FEATS = ["tsi", "lts", "fsi", "bonus", "dsi", "nsi", "csi",
         "was", "tas", "hcs", "nrja", "kankai"]


def load_dataset(histdir):
    ds = []
    for f in sorted(glob.glob(os.path.join(histdir, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
            res = calc.run(d["race"])
        except Exception:
            continue
        X = {}
        for r in res["rows"]:
            feat = {k: float(r.get(k, 0) or 0) for k in FEATS[:-1]}
            feat["kankai"] = (float(r["mult"]) - 1.0) * 100.0
            X[r["num"]] = feat
        top3 = [o["num"] for o in d["result"].get("order", [])
                if o.get("rank") in ("1", "2", "3")]
        odds = {o["num"]: o["odds"] for o in d["result"].get("order", [])
                if o.get("odds") and o["num"] in X}
        if len(top3) < 3 or any(t not in X for t in top3) or len(X) < 5:
            continue
        ds.append(dict(X=X, top3=top3, odds=odds, date=d.get("date", "")))
    return ds


def scores(X, w):
    return {n: sum(w[i]*X[n][k] for i, k in enumerate(FEATS)) for n in X}


def pl_nll_grad(ds, w, T, l2):
    """Plackett-Luce: -Σ log P(1着,2着,3着の並び)。返り値=(nll, grad)"""
    nll = 0.0
    g = [0.0]*len(FEATS)
    n_obs = 0
    for r in ds:
        s = scores(r["X"], w)
        alive = list(s.keys())
        for pos in range(3):
            winner = r["top3"][pos]
            mx = max(s[n] for n in alive)
            e = {n: math.exp((s[n]-mx)/T) for n in alive}
            Z = sum(e.values())
            p = {n: e[n]/Z for n in alive}
            nll += -math.log(max(p[winner], 1e-12))
            n_obs += 1
            for i, k in enumerate(FEATS):
                xw = r["X"][winner][k]
                ex = sum(p[n]*r["X"][n][k] for n in alive)
                g[i] += -(xw - ex)/T
            alive.remove(winner)
    for i in range(len(FEATS)):
        g[i] = g[i]/n_obs + 2*l2*(w[i]-1.0)   # 等重み(1.0)への正則化
    return nll/n_obs + l2*sum((x-1.0)**2 for x in w), g


def fit_weights(train, T, l2, iters=400, lr=0.5):
    w = [1.0]*len(FEATS)   # 等重み=現行から出発
    m = [0.0]*len(FEATS)
    for it in range(iters):
        nll, g = pl_nll_grad(train, w, T, l2)
        for i in range(len(FEATS)):
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
        if it % 100 == 0:
            print(f"  iter{it}: PL-NLL={nll:.4f}", file=sys.stderr)
    return w


def eval_nll(ds, w, T):
    tot = n = 0
    for r in ds:
        s = scores(r["X"], w)
        alive = list(s.keys())
        for pos in range(3):
            winner = r["top3"][pos]
            mx = max(s[x] for x in alive)
            e = {x: math.exp((s[x]-mx)/T) for x in alive}
            Z = sum(e.values())
            tot += -math.log(max(e[winner]/Z, 1e-12))
            n += 1
            alive.remove(winner)
    return tot/n if n else float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--test", default="20260711,20260712")
    ap.add_argument("--l2", type=float, default=0.3)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    T = calc.load_params().get("temp", 20.0)
    ds = load_dataset(a.histdir)
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: 全{len(ds)}R (train {len(train)} / test {len(test)}) T={T} L2={a.l2}")

    w = fit_weights(train, T, a.l2)
    print("\n学習した重み（1.0=現行の等重み）:")
    for k, v in zip(FEATS, w):
        print(f"  {k:8s} {v:+.3f}")

    print("\n── 3着内の並びPL-NLL（学習スコア vs 現行等重み, 小さいほど良い）──")
    w0 = [1.0]*len(FEATS)
    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        v0 = eval_nll(dset, w0, T)
        v1 = eval_nll(dset, w, T)
        verdict = "改善" if v1 < v0 else "改善なし"
        print(f"  {name}: 現行 {v0:.4f} → 学習後 {v1:.4f} （{verdict}）")

    if a.write:
        v0 = eval_nll(test, w0, T) if test else None
        v1 = eval_nll(test, w, T) if test else None
        if test and v1 >= v0:
            print("\n⚠️ ホールドアウトで改善しなかったため params.json には書かない（現状維持）。")
            return
        p = calc.load_params()
        p["score_weights"] = {k: round(v, 4) for k, v in zip(FEATS, w)}
        json.dump(p, open("params.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nparams.json に score_weights を保存した。")


if __name__ == "__main__":
    main()
