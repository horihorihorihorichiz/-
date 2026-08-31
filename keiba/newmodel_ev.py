# -*- coding: utf-8 -*-
"""新モデル(49分割2層)の順位で期待値100%超の買い場を探す（2026-08-22・指示「期待値プラスにしようぜ」）。

根拠のある仮説: 49分割は3着内率だけでなく複勝2点ROIも上げた(81.0→84.0)。
順位の改善がROIに波及しているなら、旧モデルで91.8%だった最良セルが
新順位では100%に近づく/超える可能性がある。

作法(RULES.md R2/R3を遵守):
 ・1点買いのみ(複勝1位/単勝1位/複勝2位/ワイド1-2位)
 ・条件セル: 単独+2条件、MINE n≥120
 ・合格 = MINE/VAL/CONFの3期間すべてROI≥100%(VAL/CONF n≥15)
 ・null = 順位を乱数化して同じ採掘を10回(同じ自由度)
 ・正直な留保: 重みはMINEで学習(MINEは在サンプル)。VAL/CONFも49分割の選択に
   使用済みなので軽度に汚染。ここで合格が出ても最終確定は9月新データ。
"""
import json, os, sys, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

OB = [0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.3, 2.6, 3.0, 3.5, 4.5, 6.0, 10**9]
def obl(o):
    for i in range(len(OB)-1):
        if OB[i] <= o < OB[i+1]:
            return f"1位{OB[i]:g}-{OB[i+1]:g}倍" if OB[i+1] < 10**8 else f"1位{OB[i]:g}倍+"
    return "?"

def main():
    races = V.load_races(); V2.attach_corner(races)
    art = json.load(open("hori52_w.json"))
    wfn = scorer_from_artifact(art)
    R = len(races)
    print(f"対象 {R}R（新モデルで全レース再ランキング）", file=sys.stderr)

    # 新順位・払戻・条件を前計算
    seg = np.zeros(R, int)
    orders = []
    for i, r in enumerate(races):
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        orders.append([r["nums"][k] for k in o])
        m = r["month"]
        seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
    segm = [seg == k for k in range(3)]

    BETS = ["複勝1位", "単勝1位", "複勝2位", "ワイド1-2位"]

    def build(orders_):
        ret = np.zeros((R, len(BETS)))
        vals = collections.defaultdict(lambda: np.zeros(R, bool))
        for i, r in enumerate(races):
            od = orders_[i]
            a, b = od[0], od[1]
            pay = r.get("payout") or {}
            def g(k, key):
                d = pay.get(k) or {}
                v = d.get(key); return float(v) if v else 0.0
            ret[i] = [g("複勝", str(a)), g("単勝", str(a)), g("複勝", str(b)),
                      g("ワイド", "-".join(str(x) for x in sorted((a, b))))]
            o1 = (r.get("odds") or {}).get(str(a))
            f = len(r["nums"])
            cs = [("sd", r["surface"]), ("sdd", f"{r['surface']}{r['dist_cat']}"),
                  ("field", "≤10頭" if f <= 10 else "11-14頭" if f <= 14 else "15頭+"),
                  ("tier", f"t{r['tier']}"),
                  ("venue", str(r.get("venue")))]
            if o1:
                cs.append(("odds1", obl(float(o1))))
            for fam, v in cs:
                vals[(fam, v)][i] = True
        return ret, vals

    def sweep(ret, vals, min_n=120):
        keys = sorted(vals)
        cells = [(k,) for k in keys] + [(a, b) for a, b in itertools.combinations(keys, 2)
                                        if a[0] != b[0]]
        hits = []
        for cell in cells:
            m = vals[cell[0]]
            for k in cell[1:]:
                m = m & vals[k]
            mM = m & segm[0]
            n = int(mM.sum())
            if n < min_n:
                continue
            for bi in range(len(BETS)):
                roiM = float(ret[mM, bi].sum() / n)
                if roiM < 100:
                    continue
                row = dict(cell="×".join(x for _, x in cell), bet=BETS[bi], nM=n, roiM=roiM)
                ok = True
                for si, nm in ((1, "V"), (2, "C")):
                    mm = m & segm[si]; nn = int(mm.sum())
                    row[f"n{nm}"] = nn
                    row[f"roi{nm}"] = float(ret[mm, bi].sum() / nn) if nn else None
                    if nn < 15 or (row[f"roi{nm}"] or 0) < 100:
                        ok = False
                row["pass"] = ok
                hits.append(row)
        return hits

    ret, vals = build(orders)
    hits = sweep(ret, vals)
    surv = [h for h in hits if h["pass"]]
    print(f"\n新モデル順位: MINEでROI100%超 {len(hits)}セル / 3期間すべて100%超 {len(surv)}セル")

    # 参照: 旧モデルで最良だった単純セルの新旧比較
    print("\n── 基準セルの新モデル成績（全期間） ──")
    for cond, bet_i in ((None, 0), (("odds1帯<2倍",), 0)):
        pass
    m_all = np.ones(R, bool)
    for nm, msk in (("全レース", m_all),):
        for bi, bn in enumerate(BETS):
            n = int(msk.sum())
            print(f"  {nm} {bn}: ROI {ret[msk, bi].sum()/n:.1f}% (n={n})")
    # 1位<2倍
    m2 = np.zeros(R, bool)
    for i, r in enumerate(races):
        o1 = (r.get("odds") or {}).get(str(orders[i][0]))
        if o1 and float(o1) < 2.0:
            m2[i] = True
    for si, nm in ((0, "MINE"), (1, "VAL"), (2, "CONF")):
        mm = m2 & segm[si]; n = int(mm.sum())
        if n:
            print(f"  1位<2倍×複勝1位 {nm}: ROI {ret[mm,0].sum()/n:.1f}% 的中"
                  f"{(ret[mm,0]>0).mean()*100 if n else 0:.1f}% (n={n})")

    # null: 順位乱数×10で同じ採掘
    rs = np.random.RandomState(71)
    n_surv = []
    for t in range(10):
        fake = []
        for r in races:
            o = list(r["nums"]); rs.shuffle(o); fake.append(o)
        ret2, vals2 = build(fake)
        h2 = sweep(ret2, vals2)
        s2 = [h for h in h2 if h["pass"]]
        n_surv.append(len(s2))
        print(f"  null#{t+1}: MINE通過{len(h2)} / 3期間合格{len(s2)}", file=sys.stderr)
    print(f"\nnull(順位乱数×10): 3期間合格 平均{np.mean(n_surv):.1f} (max{max(n_surv)})")

    if surv:
        surv.sort(key=lambda h: -min(h["roiV"], h["roiC"]))
        print("\n── ★3期間すべてROI100%超のセル ──")
        print(f"{'条件':<34}{'券種':<10}{'nM':>5}{'MINE':>7}{'nV':>4}{'VAL':>7}{'nC':>4}{'CONF':>7}")
        for h in surv[:20]:
            print(f"{h['cell']:<34}{h['bet']:<10}{h['nM']:>5}{h['roiM']:>6.1f}%"
                  f"{h['nV']:>4}{h['roiV']:>6.1f}%{h['nC']:>4}{h['roiC']:>6.1f}%")
    json.dump({"hits": hits[:200], "surv": surv, "null_surv": n_surv},
              open("newmodel_ev.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved newmodel_ev.json")


if __name__ == "__main__":
    main()
