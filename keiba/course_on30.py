# -*- coding: utf-8 -*-
"""コースを30分割の上に重ねる（2026-08-22・指示「コースも分けろって」）。

★経緯と訂正:
   split30.py で「コース120はnullに勝っていない」と報告したが、比較相手が
   **30セル乱数** だった。120セルの分け方には120セル乱数を当てるのが公平で、
   course_sweep30.py（120セル乱数が相手）ではコースは明確に勝っていた。
   訂正した上で、正しい形＝「30分割を土台にコースを重ねる」で測り直す。

階層:
   全体1本 → 芝ダ×距離帯(6) → 芝ダ×距離帯×クラス(30) → コース(120)
   各段は前の段の重みへ縮小する(L2 shrinkage)。薄いセルは自動的に前段へ戻る。

比較:
   ①30分割のみ / ②30分割+コース(λ4段階) / ③30分割とコースの混合(α3段階)
   ④コースをクラスで割った course×tier も試す
   null: 120セル乱数・30セル乱数の両方を並べる（どちらとも比較できるように）
"""
import json, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2


def sd(r):   return f"{r['surface']}{r['dist_cat']}"
def k30(r):  return f"{r['surface']}{r['dist_cat']}/t{r['tier']}"
def kc(r):   return f"{r.get('venue')}{r['surface']}{r['distance']}"
def kct(r):  return f"{r.get('venue')}{r['surface']}{r['distance']}/t{r['tier']}"


def fit_by(races, keyfn, l2, base_of, min_n):
    out = {}
    by = collections.defaultdict(list)
    for r in races:
        by[keyfn(r)].append(r)
    for k, sub in by.items():
        if len(sub) < min_n:
            continue
        b = base_of(sub[0])
        X, M, W = V2.make_tensor(sub, key="Z16")
        out[k] = V2.fit(X, M, W, l2, w0=b, wstart=b)
    return out


def ev(races, wfn):
    n = len(races); win = t3 = 0; cost = ret = 0
    for r in races:
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
        win += int(o[0] == r["top3"][0]); t3 += int(o[0] in set(r["top3"]))
        pl = {int(k): float(v) for k, v in ((r["payout"] or {}).get("複勝") or {}).items()}
        for i in o[:2]:
            cost += 100; ret += pl.get(r["nums"][i], 0.0)
    return (win / n * 100, t3 / n * 100, ret / cost * 100 if cost else 0)


def main():
    races = V.load_races(); V2.attach_corner(races)
    K = races[0]["Z16"].shape[1]
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    X, M, W = V2.make_tensor(MINE, key="Z16")
    w_all = V2.fit(X, M, W, 1.0, w0=np.zeros(K), wstart=np.zeros(K))
    w6 = fit_by(MINE, sd, 0.2, lambda r: w_all, 1)
    b6 = lambda r: w6.get(sd(r), w_all)
    w30 = fit_by(MINE, k30, 0.3, b6, 40)
    b30 = lambda r: w30.get(k30(r), b6(r))
    ncourse = len({kc(r) for r in MINE})
    print(f"MINE {len(MINE)} / 30セル {len(w30)} / コース {ncourse}", file=sys.stderr)

    res = {}
    res["①6群(6)"] = (6, ev(MINE, b6), ev(VAL, b6), ev(CONF, b6))
    res["②30分割(30)"] = (30, ev(MINE, b30), ev(VAL, b30), ev(CONF, b30))

    # ③ 30分割 + コース
    for lam in (0.3, 1.0, 3.0, 8.0):
        wc = fit_by(MINE, kc, lam, b30, 40)
        f = lambda r, wc=wc: wc.get(kc(r), b30(r))
        res[f"③30+コース λ={lam:g}"] = (ncourse, ev(MINE, f), ev(VAL, f), ev(CONF, f))
    # 混合
    wc = fit_by(MINE, kc, 0.3, b30, 40)
    for a in (0.3, 0.5, 0.7):
        def mk(a=a, wc=wc):
            def g(r):
                c = wc.get(kc(r)); b = b30(r)
                return b if c is None else a * c + (1 - a) * b
            return g
        f = mk()
        res[f"③30+コース混合{a:.0%}"] = (ncourse, ev(MINE, f), ev(VAL, f), ev(CONF, f))
    # ④ コース×クラス
    for lam in (0.3, 1.0):
        wct = fit_by(MINE, kct, lam, b30, 30)
        f = lambda r, wct=wct: wct.get(kct(r), b30(r))
        res[f"④コース×クラス λ={lam:g}"] = (len(wct), ev(MINE, f), ev(VAL, f), ev(CONF, f))

    # null: 120セル乱数 と 30セル乱数
    rs = np.random.RandomState(53)
    for nc in (30, 120):
        fk = {r["rid"]: f"N{rs.randint(nc)}" for r in races}
        for lam in (0.3, 1.0):
            wn = fit_by(MINE, lambda r: fk[r["rid"]], lam, b30, 40)
            f = lambda r, wn=wn, fk=fk: wn.get(fk[r["rid"]], b30(r))
            res[f"null{nc}セル λ={lam:g}"] = (nc, ev(MINE, f), ev(VAL, f), ev(CONF, f))

    n120v = max(v[2][1] for k, v in res.items() if k.startswith("null120"))
    n120c = max(v[3][1] for k, v in res.items() if k.startswith("null120"))
    n30v = max(v[2][1] for k, v in res.items() if k.startswith("null30"))
    n30c = max(v[3][1] for k, v in res.items() if k.startswith("null30"))
    print(f"\nnull最良  120セル: VAL {n120v:.1f}% / CONF {n120c:.1f}%"
          f"   30セル: VAL {n30v:.1f}% / CONF {n30c:.1f}%")
    print("=" * 96)
    print(f"{'構成':<24}{'セル':>5}{'MINE 3着内':>11}{'VAL':>8}{'CONF':>8}{'VAL複2':>8}{'CONF複2':>8}  判定")
    for k, (nc, m, v, c) in sorted(res.items(), key=lambda kv: -(kv[1][2][1] + kv[1][3][1])):
        if k.startswith("null"):
            mark = "null"
        else:
            nv, nc2 = (n120v, n120c) if nc > 60 else (n30v, n30c)
            mark = "○" if (v[1] > nv and c[1] > nc2) else "×"
        print(f"{k:<24}{nc:>5}{m[1]:>10.1f}%{v[1]:>7.1f}%{c[1]:>7.1f}%{v[2]:>7.1f}%{c[2]:>7.1f}%  {mark}")
    json.dump({k: {"cells": v[0], "MINE": v[1], "VAL": v[2], "CONF": v[3]}
               for k, v in res.items()}, open("course_on30.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved course_on30.json")


if __name__ == "__main__":
    main()
