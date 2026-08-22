# -*- coding: utf-8 -*-
"""「モデルが主張する期待値」は実際に当たるのか（2026-08-22・指示「ちゃんと調べて」）。

これを測らずに買い目の絞り方を論じても意味がない。核心の問い:
  モデル確率×実オッズで出した期待値が高い買い目ほど、本当に回収率が高いのか？
  高くないなら、期待値の計算そのものが飾りで、絞る/広げるの議論に意味はない。

方法:
  hist_odds/ に全券種の実オッズが14,031R分ある(tan/fuku/umaren/wide/sanrenpuku/…)。
  各レースで
    1. B-sd16のスコア→softmaxでモデル勝率p
    2. Harvilleでワイド(ペア3着内)確率へ展開
    3. 主張期待値 = モデル確率 × 実ワイドオッズ × 100
    4. 主張期待値の帯ごとに、**実際の払戻**で回収率を出す
  帯ごとの実回収率が主張どおり単調に増えるなら本物。
  全部77%前後(控除率23.3%の線)に潰れるなら、主張期待値はノイズ。

3分割を厳守（MINE ≤202602 / VALIDATE 202603-05 / CONFIRM 202606-08）。
"""
import json, os, sys, itertools, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEDGER = "bsd16_races.jsonl"
BANDS = [0, 50, 70, 85, 100, 120, 150, 200, 300, 10**9]


def harville_pair(p, nums):
    """ペアが両方3着以内の確率。p=dict(num->勝率)"""
    pair = collections.defaultdict(float)
    ks = nums
    for i in ks:
        d1 = 1 - p[i]
        if d1 <= 1e-9: continue
        for j in ks:
            if j == i: continue
            d2 = d1 - p[j]
            if d2 <= 1e-9: continue
            pij = p[i] * p[j] / d1
            for k in ks:
                if k in (i, j): continue
                q = pij * p[k] / d2
                a, b, c = sorted((i, j, k))
                pair[(a, b)] += q; pair[(a, c)] += q; pair[(b, c)] += q
    return pair


def band_of(ev):
    for i in range(len(BANDS) - 1):
        if BANDS[i] <= ev < BANDS[i + 1]:
            return i
    return len(BANDS) - 2


def main():
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    seg_of = lambda m: 0 if m <= '202602' else (1 if m <= '202605' else 2)
    SEGN = ["MINE", "VALIDATE", "CONFIRM"]
    # [点数, 的中, 払戻合計]
    acc = np.zeros((3, len(BANDS) - 1, 3))
    nr = 0
    for line in open(LEDGER):
        if nr >= lim: break
        r = json.loads(line)
        rid = r["rid"]
        po = f"hist_odds/{rid}.json"
        if not os.path.exists(po):
            continue
        try:
            od = json.load(open(po, encoding="utf-8"))
        except Exception:
            continue
        wide = od.get("wide") or {}
        if not wide:
            continue
        nums = [int(x) for x in r["nums"]]
        sc = np.array(r["score"], dtype=float)
        if len(sc) != len(nums):
            continue
        e = np.exp(sc - sc.max()); p = e / e.sum()
        pd = {n: float(p[i]) for i, n in enumerate(nums)}
        pair = harville_pair(pd, nums)
        # 実際の払戻(当たったペアだけ)
        payw = {}
        for k, v in ((r.get("payout") or {}).get("ワイド") or {}).items():
            a, b = sorted(int(x) for x in k.split("-"))
            payw[(a, b)] = float(v)
        s = seg_of(r["month"])
        nr += 1
        for (a, b), q in pair.items():
            k1, k2 = f"{a}-{b}", f"{b}-{a}"
            o = wide.get(k1) or wide.get(k2)
            if not o:
                continue
            ev = q * float(o) * 100
            bi = band_of(ev)
            ret = payw.get((a, b), 0.0)
            acc[s, bi] += [1, 1 if ret else 0, ret]

    print(f"対象 {nr}R")
    print("\n" + "=" * 92)
    print("モデルが主張する期待値の帯 → 実際の回収率（ワイド全ペア・1点100円）")
    print("控除率23.3% ⇒ 妙味ゼロなら全帯 76.7% 付近に潰れる")
    print("=" * 92)
    hdr = f"{'主張EV帯':>12}" + "".join(f"{n:^26}" for n in SEGN)
    print(hdr)
    print(f"{'':>12}" + "".join(f"{'点数   的中   実回収率':^26}" for _ in SEGN))
    for bi in range(len(BANDS) - 1):
        lo, hi = BANDS[bi], BANDS[bi + 1]
        lab = f"{lo}-{hi}円" if hi < 10**8 else f"{lo}円〜"
        line = f"{lab:>12}"
        skip = True
        for s in range(3):
            n, h, ret = acc[s, bi]
            if n >= 200:
                skip = False
                line += f"{int(n):8d} {h/n*100:5.2f}% {ret/(100*n)*100:7.1f}%  "
            else:
                line += f"{'—':^26}"
        if not skip:
            print(line)
    line = f"{'【全体】':>12}"
    for s in range(3):
        n, h, ret = acc[s].sum(0)
        line += f"{int(n):8d} {h/n*100:5.2f}% {ret/(100*n)*100:7.1f}%  "
    print(line)
    json.dump({"bands": BANDS, "acc": acc.tolist(), "races": nr},
              open("ev_backtest.json", "w"))


if __name__ == "__main__":
    main()
