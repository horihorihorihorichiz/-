# -*- coding: utf-8 -*-
"""確率キャリブレーションのフィット（Ver.100）。
   hist/*.json（harvest.py産: race+確定結果+全頭単勝オッズ）から
   ①温度T ②展開スケールks ③市場ブレンド(α,β) を勝者の対数尤度で推定する。

   usage: python3 fit.py [--histdir hist] [--test 20260704,20260705] [--write]
   --write で params.json に保存（calc.py/predict.pyが自動で読む）。
"""
import argparse, glob, json, math, os, sys
import calc


def clip_renorm(p, cap=0.30):
    """上限capで切り、超過分を残りへ再正規化（総和1を保つ）"""
    p = dict(p)
    for _ in range(len(p)):
        over = [n for n, v in p.items() if v > cap + 1e-12]
        if not over:
            return p
        rest = {n: v for n, v in p.items() if n not in over}
        room = 1.0 - cap*len(over)
        s = sum(rest.values())
        for n in over: p[n] = cap
        if s > 0:
            for n in rest: p[n] = rest[n]/s*room
    return p


def load_dataset(histdir):
    """各レース → dict(s2, mult, win_odds, winner, top3, date, rid)"""
    ds = []
    for f in sorted(glob.glob(os.path.join(histdir, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
            race, result = d["race"], d["result"]
            res = calc.run(race)
        except Exception as e:
            print(f"  skip {os.path.basename(f)}: {e}", file=sys.stderr)
            continue
        s2 = {r["num"]: r["s2"] for r in res["rows"]}
        mult = {r["num"]: r["mult"] for r in res["rows"]}
        odds = {o["num"]: o["odds"] for o in result.get("order", [])
                if o.get("odds") and o["num"] in s2}
        top3 = [o["num"] for o in result.get("order", [])
                if o.get("rank") in ("1", "2", "3")]
        winner = next((o["num"] for o in result.get("order", [])
                       if o.get("rank") == "1"), None)
        if winner is None or winner not in s2 or len(odds) < len(s2)*0.8:
            continue
        ds.append(dict(s2=s2, mult=mult, odds=odds, winner=winner,
                       top3=top3, date=d.get("date", ""), rid=race.get("race_id", "")))
    return ds


def p_model(r, T, ks, cap=0.30):
    w = {n: r["s2"][n]*(1.0 + (r["mult"][n] - 1.0)*ks) for n in r["s2"]}
    mx = max(w.values())
    e = {n: math.exp((w[n]-mx)/T) for n in w}
    s = sum(e.values())
    return clip_renorm({n: e[n]/s for n in e}, cap)


def p_market(r):
    inv = {n: 1.0/o for n, o in r["odds"].items() if o and o > 0}
    s = sum(inv.values())
    return {n: v/s for n, v in inv.items()}


def p_blend(pm, q, alpha, beta):
    ns = [n for n in pm if n in q]
    lg = {n: alpha*math.log(max(pm[n], 1e-9)) + beta*math.log(max(q[n], 1e-9)) for n in ns}
    mx = max(lg.values())
    e = {n: math.exp(lg[n]-mx) for n in ns}
    s = sum(e.values())
    return {n: e[n]/s for n in ns}


def nll(ds, prob_fn):
    tot = n = 0
    for r in ds:
        p = prob_fn(r)
        if r["winner"] not in p:
            continue
        tot += -math.log(max(p[r["winner"]], 1e-9))
        n += 1
    return tot/n if n else float("inf"), n


def fit(train):
    # ① 温度T × 展開スケールks（モデル単体の勝者NLL最小化）
    best = (float("inf"), 14.0, 1.0)
    for T in [6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 50]:
        for ks in [0.0, 0.25, 0.5, 0.75, 1.0]:
            v, _ = nll(train, lambda r, T=T, ks=ks: p_model(r, T, ks))
            if v < best[0]:
                best = (v, T, ks)
    # 温度の細分化
    _, T0, ks0 = best
    for T in [T0-3, T0-2, T0-1, T0+1, T0+2, T0+3]:
        if T <= 2: continue
        for ks in [max(0.0, ks0-0.15), ks0, min(1.0, ks0+0.15)]:
            v, _ = nll(train, lambda r, T=T, ks=ks: p_model(r, T, ks))
            if v < best[0]:
                best = (v, T, ks)
    _, T, ks = best

    # ② 市場ブレンド（α=モデル重み, β=市場重み）
    bestb = (float("inf"), 0.0, 1.0)
    for a in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.1]:
        for b in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]:
            v, _ = nll(train, lambda r, a=a, b=b:
                       p_blend(p_model(r, T, ks), p_market(r), a, b))
            if v < bestb[0]:
                bestb = (v, a, b)
    _, alpha, beta = bestb
    return T, ks, alpha, beta


def calibration_table(ds, prob_fn, edges=(0.0, 0.03, 0.06, 0.12, 0.20, 1.01)):
    buck = [[0, 0.0, 0] for _ in range(len(edges)-1)]  # n, sum_p, wins
    for r in ds:
        p = prob_fn(r)
        for n_, v in p.items():
            for i in range(len(edges)-1):
                if edges[i] <= v < edges[i+1]:
                    buck[i][0] += 1
                    buck[i][1] += v
                    buck[i][2] += (1 if n_ == r["winner"] else 0)
    out = []
    for i, (n_, sp, w) in enumerate(buck):
        if n_:
            out.append((f"{edges[i]*100:.0f}-{edges[i+1]*100:.0f}%", n_,
                        sp/n_*100, w/n_*100))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--test", default="", help="テストに回す日付(カンマ区切りYYYYMMDD)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_dataset(a.histdir)
    test_days = set(a.test.split(",")) if a.test else set()
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: 全{len(ds)}R (train {len(train)} / test {len(test)})")
    if len(train) < 30:
        print("trainが少なすぎる。収穫を増やして再実行を。")
        return

    T, ks, alpha, beta = fit(train)
    print(f"\nフィット結果: 温度T={T} 展開スケールks={ks} ブレンド α(モデル)={alpha} β(市場)={beta}")

    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        rows = [
            ("市場のみ(最終単勝)", lambda r: p_market(r)),
            ("旧モデル(T=14,ks=1)", lambda r: p_model(r, 14, 1.0)),
            (f"新モデル(T={T},ks={ks})", lambda r: p_model(r, T, ks)),
            (f"ブレンド(α={alpha},β={beta})", lambda r: p_blend(p_model(r, T, ks), p_market(r), alpha, beta)),
        ]
        print(f"\n── 勝者NLL ({name}, 小さいほど良い) ──")
        for nm, fn in rows:
            v, n = nll(dset, fn)
            print(f"  {nm:28s} {v:.4f} (n={n})")

    if test:
        print("\n── ブレンドのキャリブレーション (test) ──")
        for label, n, pred, act in calibration_table(
                test, lambda r: p_blend(p_model(r, T, ks), p_market(r), alpha, beta)):
            print(f"  {label:8s} n={n:4d} 予測{pred:5.1f}% 実際{act:5.1f}%")

    # 3着内(複勝)の較正も確認: ブレンド確率のHarville P(top3) vs 実際
    if test:
        import predict as PRD
        buck = [[0, 0.0, 0] for _ in range(4)]
        edges3 = (0.0, 0.15, 0.30, 0.50, 1.01)
        for r in test:
            pb = p_blend(p_model(r, T, ks), p_market(r), alpha, beta)
            for n_, v in pb.items():
                p3 = PRD.p_place3(pb, n_)
                for i in range(4):
                    if edges3[i] <= p3 < edges3[i+1]:
                        buck[i][0] += 1; buck[i][1] += p3
                        buck[i][2] += (1 if n_ in r["top3"] else 0)
        print("\n── 3着内確率(Harville)のキャリブレーション (test) ──")
        for i, (n_, sp, w) in enumerate(buck):
            if n_:
                print(f"  {edges3[i]*100:.0f}-{edges3[i+1]*100:.0f}%: n={n_:4d} "
                      f"予測{sp/n_*100:5.1f}% 実際{w/n_*100:5.1f}%")

    if a.write:
        params = dict(temp=T, kankai_scale=ks, cap=30.0,
                      blend=dict(alpha=alpha, beta=beta),
                      fitted_on=len(train), note="fit.py Ver.100")
        json.dump(params, open("params.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nparams.json に保存した（calc/predictが次回から使う）")


if __name__ == "__main__":
    main()
