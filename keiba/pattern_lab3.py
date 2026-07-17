# -*- coding: utf-8 -*-
"""パターン研究所・第3弾: 「他の歪み」探索（7/14ユーザー指示）。
   視点を変えた歪み仮説を2段階規律で一斉測定:
   A. 1位以外の乖離馬(モデル上位×市場人気薄=穴馬ゾーン)の単勝/複勝
   B. 確率比の歪み(モデル確率/市場確率≥x倍の馬すべて)
   C. プール間の矛盾(ワイド/馬連の実売価格 vs 単勝市場からのHarville理論値)
   D. 文脈(最終R・道悪・少頭数など)×乖離
   usage: python3 pattern_lab3.py
"""
import itertools, json, math, os
from collections import defaultdict

DEV_END = "202605"
MIN_DEV_BETS = 60
MIN_CONF_BETS = 25


def softmax_probs(rec):
    sc = {int(k): v for k, v in rec["scores"].items()}
    mx = max(sc.values())
    e = {n: math.exp(v-mx) for n, v in sc.items()}
    Z = sum(e.values())
    return {n: v/Z for n, v in e.items()}


def market_probs(om):
    inv = {n: 1.0/o for n, o in om.items() if o > 0}
    s = sum(inv.values())
    return {n: v/s for n, v in inv.items()}


def harville_wide(p, i, j):
    t = 0.0
    for k in p:
        if k in (i, j):
            continue
        for x, y, z in itertools.permutations([i, j, k]):
            d1 = 1 - p[x]
            d2 = 1 - p[x] - p[y]
            if d1 <= 0 or d2 <= 0:
                continue
            t += p[x]*(p[y]/d1)*(p[z]/d2)
    return t


def pay(rec, kind, key):
    return rec["payout"].get(kind, {}).get(key, 0)


def main():
    preds = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]
    print(f"WF予測 {len(preds)}R")
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))

    def book(name, phase, st, ret):
        a = acc[name][phase]
        a[0] += st; a[1] += ret; a[2] += 1

    for rec in preds:
        phase = "dev" if rec["month"] < DEV_END else "conf"
        om = {int(k): v for k, v in rec["odds"].items()}
        order = rec["order"]
        mp = market_probs(om)
        sp = softmax_probs(rec)
        mrank = {n: i+1 for i, n in enumerate(sorted(om, key=lambda h: om[h]))}
        rn = int(rec["rid"][-2:])
        baba = rec.get("baba")
        fld = rec.get("field", len(order))

        # --- A. モデル上位×市場人気薄(1位に限らない) ---
        for mk in (2, 3):
            for mr_min in (6, 8, 10):
                for i, n in enumerate(order[:mk]):
                    if mrank.get(n, 0) >= mr_min:
                        book(f"A.単勝 model≤{mk}位×市場{mr_min}人気+", phase, 100, pay(rec, "単勝", str(n)))
                        book(f"A.複勝 model≤{mk}位×市場{mr_min}人気+", phase, 100, pay(rec, "複勝", str(n)))
        # --- B. 確率比の歪み(全馬) ---
        for ratio in (2.0, 3.0):
            for n in order:
                if n in mp and mp[n] > 0 and sp.get(n, 0)/mp[n] >= ratio and mrank.get(n, 99) >= 4:
                    book(f"B.単勝 モデル/市場≥{ratio}倍", phase, 100, pay(rec, "単勝", str(n)))
                    book(f"B.複勝 モデル/市場≥{ratio}倍", phase, 100, pay(rec, "複勝", str(n)))
        # --- C. プール間の矛盾(ワイド/馬連の売られすぎペア) ---
        op = os.path.join("hist_odds", f"{rec['rid']}.json")
        if os.path.exists(op):
            boards = json.load(open(op, encoding="utf-8"))
            wd = {k: v for k, v in boards.get("wide", {}).items() if v}
            um = {k: v for k, v in boards.get("umaren", {}).items() if v}
            for a_, b_ in itertools.combinations(order[:4], 2):
                key = "-".join(map(str, sorted((a_, b_))))
                pw = harville_wide(mp, a_, b_)
                if pw <= 0:
                    continue
                fair = 0.775/pw   # 控除率22.5%込みのフェア値
                if key in wd:
                    for ratio in (1.5, 2.0):
                        if wd[key] >= fair*ratio:
                            book(f"C.ワイド過小評価ペア≥{ratio}x", phase, 100, pay(rec, "ワイド", key))
                if key in um:
                    pu = 0.0
                    for x, y in ((a_, b_), (b_, a_)):
                        d = 1 - mp.get(x, 0)
                        if d > 0:
                            pu += mp.get(x, 0)*mp.get(y, 0)/d
                    if pu > 0:
                        fairu = 0.775/pu
                        for ratio in (1.5, 2.0):
                            if um[key] >= fairu*ratio:
                                book(f"C.馬連過小評価ペア≥{ratio}x", phase, 100, pay(rec, "馬連", key))
        # --- D. 文脈×乖離単勝 ---
        t1 = order[0]
        if mrank.get(t1, 0) >= 4:
            ctx = []
            if rn >= 11:
                ctx.append("終盤R(11-12)")
            if rn <= 6:
                ctx.append("前半R(1-6)")
            if baba in ("稍", "重", "不"):
                ctx.append("道悪")
            if fld <= 12:
                ctx.append("少頭数")
            if fld >= 15:
                ctx.append("フルゲート級(15+)")
            for c in ctx:
                book(f"D.乖離単勝×{c}", phase, 100, pay(rec, "単勝", str(t1)))

    survivors = []
    n_cand = 0
    for name, ph in acc.items():
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_BETS or dv[0] == 0:
            continue
        droi = dv[1]/dv[0]*100
        if droi < 103:
            continue
        n_cand += 1
        if cf[2] >= MIN_CONF_BETS and cf[0] > 0 and cf[1]/cf[0]*100 >= 100:
            survivors.append(dict(pattern=name,
                                  dev_roi=round(droi, 1), dev_n=dv[2],
                                  conf_roi=round(cf[1]/cf[0]*100, 1), conf_n=cf[2],
                                  total_roi=round((dv[1]+cf[1])/(dv[0]+cf[0])*100, 1),
                                  total_n=dv[2]+cf[2]))
    survivors.sort(key=lambda x: -x["total_roi"])
    print(f"発見通過: {n_cand}件 / 確認も通過: {len(survivors)}件\n")
    print("==== 「他の歪み」の生存者 ====")
    for s in survivors:
        print(f"  {s['pattern']}: 発見{s['dev_roi']}%({s['dev_n']}点) "
              f"確認{s['conf_roi']}%({s['conf_n']}点) 通算{s['total_roi']}%({s['total_n']}点)")
    json.dump(survivors, open("pattern_stats4.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ pattern_stats4.json")


if __name__ == "__main__":
    main()
