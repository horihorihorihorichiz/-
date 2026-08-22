# -*- coding: utf-8 -*-
"""少ない買い目で一番マシなのはどれか（2026-08-22・指示「できるだけ少ない買い目でいいよ」）。

1レースあたり1〜3点に絞った時の実回収率を、全券種×全条件で総当たりする。
理屈ではなく実測で決める。台帳13,194R・hist_odds(全券種の実オッズ)を使う。

測る買い方（すべてモデル順位ベース・点数が少ない順）:
  1点: 複勝1位 / 単勝1位 / ワイド1-2位 / 馬連1-2位 / 三連複1-2-3位
  2点: 複勝1-2位 / ワイド1-2,1-3 / 馬連1-2,1-3
  3点: 複勝1-2-3位 / ワイド1-2,1-3,2-3
条件（絞り）:
  全体 / 選別=予想可能(A∧B) / 1位オッズ帯5段階 / 頭数3段階 / 芝ダ
3分割厳守。
"""
import json, os, sys, itertools, collections
import numpy as np

LEDGER = "bsd16_races.jsonl"


def bets_of(order, pay):
    """(名前, 点数, 払戻合計) のリスト。payは払戻dict。"""
    a, b, c = order[0], order[1], order[2]
    def g(k, key):
        d = pay.get(k) or {}
        v = d.get(key)
        return float(v) if v else 0.0
    def uk(x, y): return "-".join(str(t) for t in sorted((x, y)))
    def tk(x, y, z): return "-".join(str(t) for t in sorted((x, y, z)))
    return [
        ("複勝1位",        1, g("複勝", str(a))),
        ("単勝1位",        1, g("単勝", str(a))),
        ("ワイド1-2位",    1, g("ワイド", uk(a, b))),
        ("馬連1-2位",      1, g("馬連", uk(a, b))),
        ("三連複1-2-3位",  1, g("三連複", tk(a, b, c))),
        ("複勝1-2位",      2, g("複勝", str(a)) + g("複勝", str(b))),
        ("ワイド1-2,1-3",  2, g("ワイド", uk(a, b)) + g("ワイド", uk(a, c))),
        ("馬連1-2,1-3",    2, g("馬連", uk(a, b)) + g("馬連", uk(a, c))),
        ("複勝1-2-3位",    3, g("複勝", str(a)) + g("複勝", str(b)) + g("複勝", str(c))),
        ("ワイド上位3頭BOX", 3, g("ワイド", uk(a, b)) + g("ワイド", uk(a, c)) + g("ワイド", uk(b, c))),
    ]


def conds(r):
    o1 = r["odds"].get(str(r["rank16"][0]))
    out = [("全体", "全体")]
    if o1:
        o1 = float(o1)
        ob = ("1位<2倍" if o1 < 2 else "1位2-3倍" if o1 < 3 else "1位3-5倍" if o1 < 5
              else "1位5-8倍" if o1 < 8 else "1位8倍+")
        out.append(("odds1", ob))
    f = r["field"]
    out.append(("field", "≤10頭" if f <= 10 else "11-14頭" if f <= 14 else "15頭+"))
    out.append(("sd", r["sd"][0]))
    # 選別(exclusion.pyの凍結値)
    ok = (r["fav_p"] >= 0.341) and (r["ent"] <= 1.904)
    out.append(("sel", "予想可能" if ok else "例外"))
    return out


def main():
    seg_of = lambda m: 0 if m <= '202602' else (1 if m <= '202605' else 2)
    SEGN = ["MINE", "VAL", "CONF"]
    names = [n for n, _, _ in bets_of([1, 2, 3], {})]
    pts = {n: p for n, p, _ in bets_of([1, 2, 3], {})}
    acc = collections.defaultdict(lambda: np.zeros((3, 3)))  # key=(cond,bet) → [n,hit,ret]
    nr = 0
    for line in open(LEDGER):
        r = json.loads(line)
        if len(r["rank16"]) < 3 or not r.get("payout"):
            continue
        s = seg_of(r["month"]); nr += 1
        bl = bets_of(r["rank16"], r["payout"])
        cs = conds(r)
        for nm, p, ret in bl:
            for fam, v in cs:
                a = acc[(v, nm)]
                a[s] += [1, 1 if ret else 0, ret]
    print(f"対象 {nr}R\n")
    # 条件ごとに、点数の少ない順で最良を出す
    condlist = ["全体", "予想可能", "1位<2倍", "1位2-3倍", "1位3-5倍", "1位5-8倍", "1位8倍+",
                "≤10頭", "11-14頭", "15頭+", "芝", "ダ"]
    print("=" * 100)
    print("1レースあたり1〜3点に絞った時の実回収率（複勝100円/点）")
    print("控除率: 複勝20.4% 単勝20.0% ワイド23.3% 馬連22.8% 三連複25.0%")
    print("=" * 100)
    for cond in condlist:
        rows = []
        for nm in names:
            a = acc.get((cond, nm))
            if a is None: continue
            n = a[:, 0].sum()
            if n < 300: continue
            p = pts[nm]
            roi_all = a[:, 2].sum() / (100 * p * n) * 100
            r3 = []
            for s in range(3):
                nn, hh, rr = a[s]
                r3.append(rr / (100 * p * nn) * 100 if nn >= 60 else None)
            rows.append((roi_all, nm, p, int(n), r3, a[:, 1].sum() / n * 100))
        if not rows: continue
        rows.sort(reverse=True)
        print(f"\n── {cond} ──")
        print(f"{'買い方':<18}{'点':>3}{'的中':>7}{'全体ROI':>8}{'MINE':>7}{'VAL':>7}{'CONF':>7}  n")
        for roi, nm, p, n, r3, hit in rows[:6]:
            f3 = "".join(f"{x:6.1f}%" if x else "     —" for x in r3)
            print(f"{nm:<18}{p:>3}{hit:6.1f}%{roi:7.1f}%{f3}  {n}")
    json.dump({str(k): v.tolist() for k, v in acc.items()}, open("minbet.json", "w"))


if __name__ == "__main__":
    main()
