# -*- coding: utf-8 -*-
"""mine200 の細分化版（2026-08-21 指示「細かくカテゴライズせえや」）。

粗い版(mine200.py)との違い:
  ・カテゴリ追加: 馬場(良/稍/重不良)・距離6段階・季節(1-3/4-6/7-9/10-12月)
  ・細分化: 頭数6段階 / 1位オッズ6段階 / 場は据え置き10場
  ・組み合わせ: 2条件 → **3条件まで**
  ・馬場と距離は台帳に無いので hist/{rid}.json から結合（初回のみ、mine200_meta.json にキャッシュ）

判定の作法は同じ:
  MINE(≤202602)で n≥40 かつ ROI≥200% → 未知2期(VALIDATE/CONFIRM)を各1回 →
  null-sweep(乱数順位×10回)で「実力ゼロが同じ採掘で何セル生き残るか」を併記。
ユーザー3目標(BOX5三連複/軸1位流し26/単勝1位)は的中率ランキングも出す(n≥60)。
"""
import json, os, sys, itertools, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine200 as M0

META = "mine200_meta.json"


def load_meta(races):
    if os.path.exists(META):
        return json.load(open(META))
    out = {}
    for r in races:
        rid = r["rid"]
        p = f"hist/{rid}.json"
        try:
            d = json.load(open(p, encoding="utf-8"))["race"]
            out[rid] = {"baba": d.get("baba"), "distance": d.get("distance"),
                        "venue": d.get("venue")}
        except Exception:
            out[rid] = {}
    json.dump(out, open(META, "w"), ensure_ascii=False)
    return out


def make_conditions(races, meta):
    """orders に依存しない条件（家族名, 値）を前計算。"""
    consts = []
    for r in races:
        mt = meta.get(r["rid"], {})
        f = r["field"]
        fb = ("≤8頭" if f <= 8 else "9-10頭" if f <= 10 else "11-12頭" if f <= 12
              else "13-14頭" if f <= 14 else "15-16頭" if f <= 16 else "17-18頭")
        mm = int(r["month"][4:6])
        season = "1-3月" if mm <= 3 else "4-6月" if mm <= 6 else "7-9月" if mm <= 9 else "10-12月"
        cs = [("sd", r["sd"]), ("tier", f"tier{r['tier']}"), ("field", fb),
              ("fav", "本命強" if r["fav_p"] >= 0.341 else "本命中" if r["fav_p"] >= 0.25 else "混戦"),
              ("ent", "堅そう" if r["ent"] <= 1.904 else "荒れ形"),
              ("gap", "点差大" if r["sgap16"] >= 0.066 else "点差小"),
              ("season", season)]
        if mt.get("venue"):
            cs.append(("venue", mt["venue"]))
        b = mt.get("baba")
        if b:
            cs.append(("baba", "良" if b == "良" else "稍重" if b == "稍" or b == "稍重" else "重不良"))
        d = mt.get("distance")
        if d:
            db = ("~1200m" if d <= 1200 else "1300-1400m" if d <= 1400 else
                  "1500-1600m" if d <= 1600 else "1700-1800m" if d <= 1800 else
                  "1900-2000m" if d <= 2000 else "2100m+")
            cs.append(("dist", db))
        consts.append(cs)
    return consts


def odds1_of(r, order):
    o1 = r["odds"].get(str(order[0]))
    if not o1:
        return None
    o1 = float(o1)
    return ("1位<2倍" if o1 < 2 else "1位2-3倍" if o1 < 3 else "1位3-5倍" if o1 < 5
            else "1位5-8倍" if o1 < 8 else "1位8-15倍" if o1 < 15 else "1位15倍+")


def build(races, consts, orders):
    R = len(races)
    ret = np.zeros((R, len(M0.BETS))); seg = np.zeros(R, dtype=int)
    vals = collections.defaultdict(lambda: np.zeros(R, dtype=bool))
    for i, r in enumerate(races):
        ret[i] = M0.bet_returns(r, orders[r["rid"]])
        m = r["month"]
        seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        for fam, v in consts[i]:
            vals[(fam, v)][i] = True
        ob = odds1_of(r, orders[r["rid"]])
        if ob:
            vals[("odds1", ob)][i] = True
    segm = [seg == k for k in range(3)]
    return ret, vals, segm


def cells_iter(keys):
    yield from ((k,) for k in keys)
    for k1, k2 in itertools.combinations(keys, 2):
        if k1[0] != k2[0]:
            yield (k1, k2)
    for k1, k2, k3 in itertools.combinations(keys, 3):
        if k1[0] != k2[0] and k1[0] != k3[0] and k2[0] != k3[0]:
            yield (k1, k2, k3)


def mine(ret, vals, segm, min_n=40, roi_th=200.0):
    keys = sorted(vals.keys())
    costs = np.array(M0.COSTS) / 100.0
    hits = {}
    for cell in cells_iter(keys):
        m = vals[cell[0]]
        for k in cell[1:]:
            m = m & vals[k]
        mM = m & segm[0]
        nM = int(mM.sum())
        if nM < min_n:
            continue
        roiM = ret[mM].sum(0) / nM / costs
        for bi, roi in enumerate(roiM):
            if roi >= roi_th:
                hits[(cell, bi)] = (nM, float(roi), m)
    return hits


def judge(hits, ret, segm):
    rows = []
    for (cell, bi), (nM, roiM, m) in hits.items():
        c = M0.COSTS[bi] / 100.0
        row = {"cell": cell, "bet": M0.BETS[bi], "nM": nM, "roiM": roiM,
               "hitM": float((ret[m & segm[0], bi] > 0).mean() * 100)}
        for si, nm in ((1, "V"), (2, "C")):
            mm = m & segm[si]; n = int(mm.sum())
            row[f"n{nm}"] = n
            row[f"roi{nm}"] = float(ret[mm, bi].sum() / n / c) if n else None
            row[f"hit{nm}"] = float((ret[mm, bi] > 0).mean() * 100) if n else None
        rows.append(row)
    surv = [x for x in rows
            if x["roiV"] is not None and x["roiC"] is not None
            and x["nV"] >= 5 and x["nC"] >= 5
            and x["roiV"] >= 100 and x["roiC"] >= 100]
    return rows, surv


def main():
    races = M0.load()
    meta = load_meta(races)
    consts = make_conditions(races, meta)
    real = {r["rid"]: r["rank16"] for r in races}
    print(f"対象 {len(races)}R / カテゴリ細分化+3条件版", file=sys.stderr)

    ret, vals, segm = build(races, consts, real)
    print(f"条件値 {len(vals)}種", file=sys.stderr)
    hits = mine(ret, vals, segm)
    rows, surv = judge(hits, ret, segm)
    print(f"\nMINEでROI200%超(n≥40): {len(rows)}セル")
    print(f"うち未知2期間とも100%超で生き残り: {len(surv)}セル")

    rs = np.random.RandomState(11)
    np_, ns_ = [], []
    for t in range(10):
        fake = {}
        for r in races:
            o = list(r["rank16"]); rs.shuffle(o); fake[r["rid"]] = o
        ret2, vals2, segm2 = build(races, consts, fake)
        h2 = mine(ret2, vals2, segm2)
        r2, s2 = judge(h2, ret2, segm2)
        np_.append(len(r2)); ns_.append(len(s2))
        print(f"  null#{t+1:02d}: MINE200超 {len(r2)} / 生き残り {len(s2)}", file=sys.stderr)
    print(f"\nnull-sweep(乱数モデル×10): MINE200超 平均{np.mean(np_):.0f}セル / "
          f"生き残り 平均{np.mean(ns_):.1f} (max{max(ns_)})")

    rows.sort(key=lambda x: -x["roiM"])
    print("\n─ 実データ: MINE ROI200超の上位40 ─")
    print(f"{'条件':<44}{'券種':<9}{'nM':>5}{'MINE':>7}{'nV':>4}{'VAL':>7}{'nC':>4}{'CONF':>7}")
    for x in rows[:40]:
        cell = "×".join(v for _, v in x["cell"])
        rv = f"{x['roiV']:.0f}%" if x["roiV"] is not None else "—"
        rc = f"{x['roiC']:.0f}%" if x["roiC"] is not None else "—"
        print(f"{cell:<44}{x['bet']:<9}{x['nM']:>5}{x['roiM']:>6.0f}%{x['nV']:>4}{rv:>7}{x['nC']:>4}{rc:>7}")
    if surv:
        print("\n─ 生き残り（未知2期とも100%超）─")
        for x in sorted(surv, key=lambda y: -min(y["roiV"], y["roiC"])):
            cell = "×".join(v for _, v in x["cell"])
            print(f"{cell:<44}{x['bet']:<9} nM{x['nM']} M{x['roiM']:.0f}% "
                  f"V n{x['nV']} {x['roiV']:.0f}% / C n{x['nC']} {x['roiC']:.0f}%")

    # ── 3目標の的中率ランキング（細分化セル・n≥60）──
    tgt = {"BOX5三連複": 9, "軸1位流し26": 10, "単勝1位": 0}
    keys = sorted(vals.keys())
    out3 = {}
    for tnm, bi in tgt.items():
        c = M0.COSTS[bi] / 100.0
        cand = []
        for cell in cells_iter(keys):
            m = vals[cell[0]]
            for k in cell[1:]:
                m = m & vals[k]
            mM = m & segm[0]; nM = int(mM.sum())
            if nM < 60:
                continue
            rec = dict(cell=cell, nM=nM,
                       hitM=float((ret[mM, bi] > 0).mean() * 100),
                       roiM=float(ret[mM, bi].sum() / nM / c))
            for si, nm2 in ((1, "V"), (2, "C")):
                mm = m & segm[si]; n = int(mm.sum())
                rec[f"n{nm2}"] = n
                rec[f"hit{nm2}"] = float((ret[mm, bi] > 0).mean() * 100) if n else None
                rec[f"roi{nm2}"] = float(ret[mm, bi].sum() / n / c) if n else None
            cand.append(rec)
        cand.sort(key=lambda x: -x["hitM"])
        out3[tnm] = cand[:40]
        print(f"\n── {tnm}: 当たりまくる条件 上位15（MINE的中率順・n≥60）──")
        print(f"{'条件':<44}{'nM':>5}{'的中M':>7}{'ROI_M':>7}{'的中V':>7}{'ROI_V':>7}{'的中C':>7}{'ROI_C':>7}")
        for x in cand[:15]:
            cellnm = "×".join(v for _, v in x["cell"])
            def fmt(k, n):
                v = x[k]
                return f"{v:.0f}%" if v is not None and x[n] >= 5 else "—"
            print(f"{cellnm:<44}{x['nM']:>5}{x['hitM']:>6.1f}%{x['roiM']:>6.0f}%"
                  f"{fmt('hitV','nV'):>7}{fmt('roiV','nV'):>7}{fmt('hitC','nC'):>7}{fmt('roiC','nC'):>7}")
        allM = segm[0]
        print(f"{'【全レース基準】':<44}{int(allM.sum()):>5}"
              f"{float((ret[allM, bi] > 0).mean() * 100):>6.1f}%"
              f"{float(ret[allM, bi].sum() / allM.sum() / c):>6.0f}%")

    json.dump({"rows": [{**x, "cell": "×".join(v for _, v in x["cell"])} for x in rows[:300]],
               "surv": [{**x, "cell": "×".join(v for _, v in x["cell"])} for x in surv],
               "null_pass": np_, "null_surv": ns_,
               "targets": {k: [{**x, "cell": "×".join(v for _, v in x["cell"])} for x in v]
                           for k, v in out3.items()}},
              open("mine200f.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved mine200f.json")


if __name__ == "__main__":
    main()
