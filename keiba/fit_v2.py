# -*- coding: utf-8 -*-
"""Ver.2モデル（Ver.101 B1）: 生特徴量の条件付きPlackett-Luceモデル。
   現行モデル(手作り点数の順位圧縮)が捨てている情報——自前指数の「実差」・騎手率・
   着差・通過位置など——をレース内z標準化してそのまま学習する。
   現行WAvgも1特徴量として含む(現行の知識を包含した上で上積みを測る)。

   ゲート: ホールドアウト(test)の3着内PL-NLLで現行スコアに勝った時だけ params_v2.json を書く。

   usage: python3 fit_v2.py [--test 20260704,20260705,20260711,20260712] [--l2 0.05] [--write]
"""
import argparse, glob, json, math, os, sys
import calc

FEATS = ["idx_mean3", "idx_last", "wavg", "j_top3", "fin_frac", "agari_best",
         "days_log", "kinryo", "wchg", "corner_frac", "dist_chg", "csi"]


def z_in_race(vals):
    """レース内z標準化。Noneは0(平均)扱い"""
    xs = [v for v in vals.values() if v is not None]
    if len(xs) < 2:
        return {k: 0.0 for k in vals}
    m = sum(xs)/len(xs)
    sd = (sum((x-m)**2 for x in xs)/len(xs))**0.5 or 1.0
    return {k: ((v-m)/sd if v is not None else 0.0) for k, v in vals.items()}


def horse_feats(h, race):
    rs = h.get("races", [])
    tsis = [r.get("tsi") for r in rs[:5] if r.get("tsi") is not None]
    tsis_sorted = sorted(tsis, reverse=True)
    f = {}
    f["idx_mean3"] = sum(tsis_sorted[:3])/len(tsis_sorted[:3]) if tsis_sorted else None
    f["idx_last"] = rs[0].get("tsi") if rs else None
    f["fin_frac"] = -(rs[0]["finish"]/max(rs[0]["field"], 1)) if rs else None
    ag = [r.get("agari") for r in rs[:3] if r.get("agari")]
    f["agari_best"] = -min(ag) if ag else None
    f["days_log"] = math.log1p(h.get("last_race_days", 30))
    f["kinryo"] = h.get("kinryo")
    f["wchg"] = h.get("weight_change") or 0
    cf = [r["corner4"]/max(r["field"], 1) for r in rs[:3] if r.get("corner4")]
    f["corner_frac"] = -sum(cf)/len(cf) if cf else None
    f["dist_chg"] = -abs(race.get("distance", 1600) - rs[0]["dist"])/race.get("distance", 1600) if rs else None
    f["csi"] = h.get("csi", 0)
    return f


def load_dataset(histdir, featdir):
    ds = []
    for f in sorted(glob.glob(os.path.join(histdir, "*.json"))):
        rid = os.path.basename(f)[:-5]
        try:
            d = json.load(open(f, encoding="utf-8"))
            res = calc.run(d["race"])
        except Exception:
            continue
        top3 = [o["num"] for o in d["result"].get("order", [])
                if o.get("rank") in ("1", "2", "3")]
        if len(top3) < 3:
            continue
        wavg = {r["num"]: r["wavg"] for r in res["rows"]}
        jf = {}
        fp = os.path.join(featdir, f"{rid}.json")
        if os.path.exists(fp):
            jf = json.load(open(fp, encoding="utf-8")).get("jockey", {})
        odds = {o["num"]: o["odds"] for o in d["result"].get("order", []) if o.get("odds")}
        raw = {}
        for h in d["race"]["horses"]:
            ff = horse_feats(h, d["race"])
            ff["wavg"] = wavg.get(h["num"])
            j = jf.get(str(h["num"]))
            ff["j_top3"] = j["j_top3"] if j else None
            raw[h["num"]] = ff
        if any(t not in raw for t in top3) or len(raw) < 5:
            continue
        X = {k: z_in_race({n: raw[n].get(k) for n in raw}) for k in FEATS}
        ds.append(dict(X=X, ns=list(raw.keys()), top3=top3, odds=odds,
                       date=d.get("date", ""), rid=rid))
    return ds


def scores(r, w):
    return {n: sum(w[i]*r["X"][k][n] for i, k in enumerate(FEATS)) for n in r["ns"]}


def pl_nll_grad(ds, w, l2):
    nll = 0.0
    g = [0.0]*len(FEATS)
    n_obs = 0
    for r in ds:
        s = scores(r, w)
        alive = list(s.keys())
        for pos in range(3):
            winner = r["top3"][pos]
            mx = max(s[n] for n in alive)
            e = {n: math.exp(s[n]-mx) for n in alive}
            Z = sum(e.values())
            p = {n: e[n]/Z for n in alive}
            nll += -math.log(max(p[winner], 1e-12))
            n_obs += 1
            for i, k in enumerate(FEATS):
                g[i] += -(r["X"][k][winner] - sum(p[n]*r["X"][k][n] for n in alive))
            alive.remove(winner)
    for i in range(len(FEATS)):
        g[i] = g[i]/n_obs + 2*l2*w[i]
    return nll/n_obs + l2*sum(x*x for x in w), g


def fit(train, l2, iters=300, lr=0.3):
    w = [0.0]*len(FEATS)
    m = [0.0]*len(FEATS)
    for it in range(iters):
        nll, g = pl_nll_grad(train, w, l2)
        for i in range(len(FEATS)):
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
        if it % 100 == 0:
            print(f"  iter{it}: NLL={nll:.4f}", file=sys.stderr)
    return w


def eval_nll(ds, prob_fn):
    tot = n = 0
    for r in ds:
        p = prob_fn(r)
        alive = dict(p)
        for pos in range(3):
            winner = r["top3"][pos]
            Z = sum(alive.values())
            tot += -math.log(max(alive[winner]/Z, 1e-12))
            n += 1
            alive.pop(winner)
    return tot/n if n else float("inf")


def probs_v2(r, w):
    s = scores(r, w)
    mx = max(s.values())
    e = {n: math.exp(s[n]-mx) for n in s}
    Z = sum(e.values())
    return {n: e[n]/Z for n in e}


def probs_v1(r, T):
    wv = {n: 0.0 for n in r["ns"]}
    # 現行スコア=wavg特徴量そのもの(z化前の生値はdatasetに残していないためz値×温度で代替)
    for n in r["ns"]:
        wv[n] = r["X"]["wavg"][n]
    e = {n: math.exp(wv[n]*T) for n in wv}
    Z = sum(e.values())
    return {n: e[n]/Z for n in e}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--featdir", default="hist_feat")
    ap.add_argument("--test", default="20260704,20260705,20260711,20260712")
    ap.add_argument("--l2", type=float, default=0.05)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_dataset(a.histdir, a.featdir)
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: 全{len(ds)}R (train {len(train)} / test {len(test)})")

    w = fit(train, a.l2)
    print("\n学習した重み（レース内z標準化後の生特徴量）:")
    for k, v in zip(FEATS, w):
        print(f"  {k:12s} {v:+.3f}")

    # 現行スコア(wavg単独)の最良温度をtrainで探して公平に比較
    bestT = min([0.4, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0],
                key=lambda T: eval_nll(train, lambda r, T=T: probs_v1(r, T)))
    print(f"\n── 3着内PL-NLL（小さいほど良い / 現行=wavg単独の最良温度{bestT}） ──")
    ok = True
    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        v1 = eval_nll(dset, lambda r: probs_v1(r, bestT))
        v2 = eval_nll(dset, lambda r: probs_v2(r, w))
        mark = "改善" if v2 < v1 else "改善なし"
        print(f"  {name}: 現行 {v1:.4f} → Ver.2 {v2:.4f} （{mark}）")
        if name == "test" and v2 >= v1:
            ok = False

    if a.write:
        if not ok:
            print("\n⚠️ ホールドアウトで改善しなかったため params_v2.json は書かない。")
            return
        json.dump(dict(feats=FEATS, weights=[round(x, 4) for x in w],
                       note="fit_v2 Ver.101 B1"),
                  open("params_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nparams_v2.json に保存した。")


if __name__ == "__main__":
    main()
