# -*- coding: utf-8 -*-
"""実測ROIを期待値として使い、100%を超えるセルを探す（2026-08-22・指示「期待値優先ね」）。

★今日わかった前提:
   モデル確率×オッズの期待値は実回収率と逆相関(-0.925)＝使えない。
   代わりに「過去の実測ROI」そのものを期待値として使う。
   点数は少ないほど良い(1点81.3% > 3点80.0%)ので **1点買いのみ** を対象にする。
   最良は『モデル1位の単勝<2倍 → 複勝1点』で91.8%。ここをさらに刻んで100%超を探す。

探索:
   券種 = 複勝1位 / 単勝1位 / 複勝2位（1点のみ）
   条件 = 1位オッズを12段階に細分 × (場10 / 芝ダ / 頭数3 / クラス / 選別 / 馬場)
          単独 + 2条件 + 3条件
   MINEでn≥120かつROI≥100%を採掘 → VAL/CONFを各1回 → null-sweep(順位乱数×10)

★mine200との違い: あちらはROI≥200%を狙って必然的に大穴に寄り、独立データで全滅した。
   今回は「100%をわずかに超える人気サイド」を狙う。的中率が高い＝分散が小さいので、
   少ない標本でも偶然と実力を分離しやすい。
"""
import json, os, sys, itertools, collections
import numpy as np

LEDGER = "bsd16_races.jsonl"
OB = [0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.3, 2.6, 3.0, 3.5, 4.5, 6.0, 10**9]


def obl(o):
    for i in range(len(OB) - 1):
        if OB[i] <= o < OB[i + 1]:
            hi = OB[i + 1]
            return f"1位{OB[i]:g}-{hi:g}倍" if hi < 10**8 else f"1位{OB[i]:g}倍+"
    return "1位不明"


VEN = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
       "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def load():
    out = []
    for line in open(LEDGER):
        r = json.loads(line)
        if len(r["rank16"]) < 3 or not r.get("payout"):
            continue
        o1 = r["odds"].get(str(r["rank16"][0]))
        if not o1:
            continue
        r["_o1"] = float(o1)
        out.append(r)
    return out


def conds(r):
    f = r["field"]
    cs = [("odds1", obl(r["_o1"])),
          ("sd", r["sd"][0]),
          ("sdd", r["sd"]),
          ("field", "≤10頭" if f <= 10 else "11-14頭" if f <= 14 else "15頭+"),
          ("tier", f"tier{r['tier']}"),
          ("sel", "予想可能" if (r["fav_p"] >= 0.341 and r["ent"] <= 1.904) else "例外"),
          ("gap", "点差大" if r["sgap16"] >= 0.066 else "点差小")]
    v = VEN.get(str(r["rid"])[4:6])
    if v:
        cs.append(("venue", v))
    return cs


def rets(r):
    pay = r["payout"]
    a, b = r["rank16"][0], r["rank16"][1]
    def g(k, key):
        d = pay.get(k) or {}
        v = d.get(key)
        return float(v) if v else 0.0
    return [("複勝1位", g("複勝", str(a))),
            ("単勝1位", g("単勝", str(a))),
            ("複勝2位", g("複勝", str(b)))]


def sweep(races, orders=None, min_n=120, th=100.0):
    R = len(races)
    names = [n for n, _ in rets(races[0])]
    ret = np.zeros((R, len(names)))
    seg = np.zeros(R, int)
    vals = collections.defaultdict(lambda: np.zeros(R, bool))
    for i, r in enumerate(races):
        if orders is not None:
            r = dict(r); r["rank16"] = orders[r["rid"]]
        ret[i] = [v for _, v in rets(r)]
        m = r["month"]
        seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        for fam, v in conds(r):
            vals[(fam, v)][i] = True
    segm = [seg == k for k in range(3)]
    keys = sorted(vals)
    cells = [(k,) for k in keys]
    cells += [(a, b) for a, b in itertools.combinations(keys, 2) if a[0] != b[0]]
    cells += [(a, b, c) for a, b, c in itertools.combinations(keys, 3)
              if a[0] != b[0] and a[0] != c[0] and b[0] != c[0]]
    hits = []
    for cell in cells:
        m = vals[cell[0]]
        for k in cell[1:]:
            m = m & vals[k]
        mM = m & segm[0]
        n = int(mM.sum())
        if n < min_n:
            continue
        roi = ret[mM].sum(0) / n
        for bi, v in enumerate(roi):
            if v >= th:
                row = {"cell": "×".join(x for _, x in cell), "bet": names[bi],
                       "nM": n, "roiM": float(v),
                       "hitM": float((ret[mM, bi] > 0).mean() * 100)}
                for si, sn in ((1, "V"), (2, "C")):
                    mm = m & segm[si]; nn = int(mm.sum())
                    row[f"n{sn}"] = nn
                    row[f"roi{sn}"] = float(ret[mm, bi].sum() / nn) if nn else None
                hits.append(row)
    return hits


def main():
    races = load()
    print(f"対象 {len(races)}R")
    hits = sweep(races)
    surv = [h for h in hits if h["roiV"] is not None and h["roiC"] is not None
            and h["nV"] >= 15 and h["nC"] >= 15 and h["roiV"] >= 100 and h["roiC"] >= 100]
    print(f"MINEでROI100%超(n≥120): {len(hits)}セル / 未知2期とも100%超: {len(surv)}セル")

    rs = np.random.RandomState(31)
    npass, nsurv = [], []
    for t in range(10):
        fake = {}
        for r in races:
            o = list(r["rank16"]); rs.shuffle(o); fake[r["rid"]] = o
        h2 = sweep(races, orders=fake)
        s2 = [h for h in h2 if h["roiV"] is not None and h["roiC"] is not None
              and h["nV"] >= 15 and h["nC"] >= 15 and h["roiV"] >= 100 and h["roiC"] >= 100]
        npass.append(len(h2)); nsurv.append(len(s2))
    print(f"null(順位乱数×10): MINE通過 平均{np.mean(npass):.1f} / 生き残り 平均{np.mean(nsurv):.1f} (max{max(nsurv)})")

    hits.sort(key=lambda x: -x["roiM"])
    print("\n─ MINE ROI100%超の上位25 ─")
    print(f"{'条件':<40}{'券種':<9}{'nM':>5}{'的中':>7}{'MINE':>7}{'nV':>4}{'VAL':>7}{'nC':>4}{'CONF':>7}")
    for h in hits[:25]:
        rv = f"{h['roiV']:.0f}%" if h["roiV"] is not None else "—"
        rc = f"{h['roiC']:.0f}%" if h["roiC"] is not None else "—"
        print(f"{h['cell']:<40}{h['bet']:<9}{h['nM']:>5}{h['hitM']:6.1f}%{h['roiM']:6.0f}%"
              f"{h['nV']:>4}{rv:>7}{h['nC']:>4}{rc:>7}")
    if surv:
        print("\n─ ★生き残り（未知2期とも100%超）─")
        for h in sorted(surv, key=lambda x: -min(x["roiV"], x["roiC"])):
            print(f"{h['cell']:<40}{h['bet']:<9} nM{h['nM']} 的中{h['hitM']:.0f}% "
                  f"M{h['roiM']:.0f}% / V n{h['nV']} {h['roiV']:.0f}% / C n{h['nC']} {h['roiC']:.0f}%")
    json.dump({"hits": hits[:300], "surv": surv, "null_pass": npass, "null_surv": nsurv},
              open("ev_hunt.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved ev_hunt.json")


if __name__ == "__main__":
    main()
