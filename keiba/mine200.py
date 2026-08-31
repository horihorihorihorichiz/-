# -*- coding: utf-8 -*-
"""条件を絞ってROI200%超の買い方を総当たりで採掘する（2026-08-21 指示による）。

指示: 「条件絞ってROI200超えさせて」

やり方（RULES.mdの採掘規律に従う）:
  1. 9券種 × 条件セル（単独＋2条件の組み合わせ）を全部測る。
     券種: モデル1位単勝/2位単勝/1位複勝/2位複勝/馬連12/ワイド12/三連複123/馬単12/三連単123
     条件: 場(10) × 芝ダ距離(6) × tier(5) × 頭数(4) × 1位オッズ帯(5) × fav_p(3) × ent(2) × sgap(2)
  2. MINE(≤202602)で n≥40 かつ ROI≥200% のセルを拾う。
  3. 拾ったセルだけ VALIDATE / CONFIRM を各1回測る。
  4. null-sweep: モデル順位を乱数に差し替えて同じ採掘を20回。
     「実力ゼロでも何セルがMINE200超になり、何セルが未知2期も100超で生き残るか」を数える。
     実データの生き残りが null の期待値を超えない限り、それは偶然。
"""
import json, sys, itertools, collections
import numpy as np

LEDGER = "bsd16_races.jsonl"

BETS = ["単勝1位", "単勝2位", "複勝1位", "複勝2位", "馬連12", "ワイド12",
        "三連複123", "馬単12", "三連単123", "BOX5三連複", "軸1位流し26"]
# ユーザーの3目標: BOX5三連複(上位5頭・10点=1000円) / 軸1位流し26(1位軸-2〜6位・10点) / 単勝1位
COSTS = [100, 100, 100, 100, 100, 100, 100, 100, 100, 1000, 1000]


def load():
    races = []
    for line in open(LEDGER):
        r = json.loads(line)
        if len(r["rank16"]) < 3 or not r.get("payout"):
            continue
        races.append(r)
    return races


def bet_returns(r, order):
    """order=馬番リスト(モデル順)。全券種の払戻(1点=100円)を返す。BOX系は複数点の合計。"""
    pay = r["payout"]
    a, b, c = order[0], order[1], order[2]
    def g(k, key):
        d = pay.get(k) or {}
        v = d.get(key)
        return float(v) if v else 0.0
    uma = "-".join(str(x) for x in sorted((a, b)))
    trio = "-".join(str(x) for x in sorted((a, b, c)))
    top5 = order[:5]
    box5 = sum(g("三連複", "-".join(str(x) for x in sorted(cmb)))
               for cmb in itertools.combinations(top5, 3))
    ax = sum(g("三連複", "-".join(str(x) for x in sorted((order[0],) + cmb)))
             for cmb in itertools.combinations(order[1:6], 2))
    return [
        g("単勝", str(a)), g("単勝", str(b)),
        g("複勝", str(a)), g("複勝", str(b)),
        g("馬連", uma), g("ワイド", uma),
        g("三連複", trio), g("馬単", f"{a}→{b}"), g("三連単", f"{a}→{b}→{c}"),
        box5, ax,
    ]


def conditions(r):
    """このレースが属する条件値（家族名, 値）のリスト。"""
    o1 = r["odds"].get(str(r["rank16"][0]))
    ob = None
    if o1:
        o1 = float(o1)
        ob = ("1位<3倍" if o1 < 3 else "1位3-7倍" if o1 < 7 else
              "1位7-15倍" if o1 < 15 else "1位15倍+")
    f = r["field"]
    fb = "≤9頭" if f <= 9 else "10-12頭" if f <= 12 else "13-15頭" if f <= 15 else "16頭+"
    venue = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
             "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}.get(
             str(r["rid"])[4:6])
    out = [("sd", r["sd"]), ("tier", f"tier{r['tier']}"), ("field", fb),
           ("fav", "本命強" if r["fav_p"] >= 0.341 else "本命中" if r["fav_p"] >= 0.25 else "混戦"),
           ("ent", "堅そう" if r["ent"] <= 1.904 else "荒れ形"),
           ("gap", "点差大" if r["sgap16"] >= 0.066 else "点差小")]
    if ob:
        out.append(("odds1", ob))
    if venue:
        out.append(("venue", venue))
    return out


def mine(races, orders, min_n=40, roi_th=200.0):
    """orders[rid]=馬番順。セル(単独+2条件)ごとに9券種のROIを測り、MINE通過セルを返す。
       返り値: {(cell, bet): (nM, roiM)} と、要求があれば全セル集計。"""
    # レースごとの前計算
    R = len(races)
    ret = np.zeros((R, len(BETS)))
    seg = np.zeros(R, dtype=int)          # 0=MINE 1=VAL 2=CONF
    conds = []
    for i, r in enumerate(races):
        ret[i] = bet_returns(r, orders[r["rid"]])
        m = r["month"]
        seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        conds.append(conditions(r))
    # 条件値→マスク
    vals = collections.defaultdict(lambda: np.zeros(R, dtype=bool))
    for i, cs in enumerate(conds):
        for fam, v in cs:
            vals[(fam, v)][i] = True
    keys = sorted(vals.keys())
    segm = [seg == k for k in range(3)]
    hits = {}
    # 単独 + 2条件（別ファミリー）
    cells = [(k,) for k in keys] + [
        (k1, k2) for k1, k2 in itertools.combinations(keys, 2) if k1[0] != k2[0]]
    for cell in cells:
        m = vals[cell[0]].copy()
        for k in cell[1:]:
            m &= vals[k]
        mM = m & segm[0]
        nM = int(mM.sum())
        if nM < min_n:
            continue
        roiM = ret[mM].sum(0) / nM / (np.array(COSTS) / 100.0)   # ROI%
        for bi, roi in enumerate(roiM):
            if roi >= roi_th:
                hits[(cell, bi)] = (nM, float(roi))
    return hits, ret, seg, vals, segm


def evaluate(hits, ret, vals, segm):
    """MINE通過セルの VAL/CONF を測る。"""
    out = []
    for (cell, bi), (nM, roiM) in hits.items():
        m = vals[cell[0]].copy()
        for k in cell[1:]:
            m &= vals[k]
        mm0 = m & segm[0]
        row = {"cell": cell, "bet": BETS[bi], "nM": nM, "roiM": roiM,
               "hitM": float((ret[mm0, bi] > 0).mean() * 100)}
        for si, nm in ((1, "V"), (2, "C")):
            mm = m & segm[si]
            n = int(mm.sum())
            row[f"n{nm}"] = n
            row[f"roi{nm}"] = float(ret[mm, bi].sum() / n / (COSTS[bi] / 100.0)) if n else None
            hh = (ret[mm, bi] > 0)
            row[f"hit{nm}"] = float(hh.mean() * 100) if n else None
        out.append(row)
    return out


def main():
    races = load()
    print(f"対象 {len(races)}R", file=sys.stderr)
    real_orders = {r["rid"]: r["rank16"] for r in races}

    hits, ret, seg, vals, segm = mine(races, real_orders)
    rows = evaluate(hits, ret, vals, segm)
    # 生き残り = 未知2期とも100超（n≥5）
    surv = [x for x in rows
            if x["roiV"] is not None and x["roiC"] is not None
            and x["nV"] >= 5 and x["nC"] >= 5
            and x["roiV"] >= 100 and x["roiC"] >= 100]

    print(f"\nMINEでROI200%超(n≥40): {len(rows)}セル")
    print(f"うち未知2期間(VALIDATE/CONFIRM)とも100%超で生き残り: {len(surv)}セル")

    # null-sweep: モデル順位を乱数に差し替えて同じ採掘
    rs = np.random.RandomState(7)
    null_pass = []; null_surv = []
    for t in range(20):
        fake = {}
        for r in races:
            o = list(r["rank16"])
            rs.shuffle(o)
            fake[r["rid"]] = o
        h2, ret2, _, vals2, segm2 = mine(races, fake)
        rows2 = evaluate(h2, ret2, vals2, segm2)
        s2 = [x for x in rows2
              if x["roiV"] is not None and x["roiC"] is not None
              and x["nV"] >= 5 and x["nC"] >= 5
              and x["roiV"] >= 100 and x["roiC"] >= 100]
        null_pass.append(len(rows2)); null_surv.append(len(s2))
        print(f"  null#{t+1:02d}: MINE200超 {len(rows2)}セル / 生き残り {len(s2)}", file=sys.stderr)

    print(f"\nnull-sweep(実力ゼロの乱数モデル×20回):")
    print(f"  MINE200超セル数     平均 {np.mean(null_pass):.1f} (min{min(null_pass)} max{max(null_pass)})")
    print(f"  未知2期生き残り数   平均 {np.mean(null_surv):.1f} (min{min(null_surv)} max{max(null_surv)})")

    rows.sort(key=lambda x: -x["roiM"])
    print("\n─ 実データ: MINE ROI200超の上位30（→未知期間でどうなったか）─")
    print(f"{'条件':<38}{'券種':<9}{'nM':>5}{'MINE':>7}{'nV':>4}{'VAL':>7}{'nC':>4}{'CONF':>7}")
    for x in rows[:30]:
        cell = "×".join(v for _, v in x["cell"])
        rv = f"{x['roiV']:.0f}%" if x["roiV"] is not None else "—"
        rc = f"{x['roiC']:.0f}%" if x["roiC"] is not None else "—"
        print(f"{cell:<38}{x['bet']:<9}{x['nM']:>5}{x['roiM']:>6.0f}%{x['nV']:>4}{rv:>7}{x['nC']:>4}{rc:>7}")

    if surv:
        print("\n─ 生き残り（未知2期とも100%超）─")
        for x in sorted(surv, key=lambda y: -min(y["roiV"], y["roiC"])):
            cell = "×".join(v for _, v in x["cell"])
            print(f"{cell:<38}{x['bet']:<9}{x['nM']:>5}{x['roiM']:>6.0f}%"
                  f"{x['nV']:>4}{x['roiV']:>6.0f}%{x['nC']:>4}{x['roiC']:>6.0f}%")

    # ── ユーザー3目標の「的中しまくる条件」ランキング（MINEで決めて未知2期を併記）──
    tgt_idx = {"BOX5三連複": 9, "軸1位流し26": 10, "単勝1位": 0}
    print("\n═ 3目標が最も当たる条件（MINE的中率順・n≥60。未知2期の的中率とROIを併記）═")
    for tnm, bi in tgt_idx.items():
        cand = []
        for cell in [(k,) for k in sorted(vals.keys())] + [
                (k1, k2) for k1, k2 in itertools.combinations(sorted(vals.keys()), 2)
                if k1[0] != k2[0]]:
            m = vals[cell[0]].copy()
            for k in cell[1:]:
                m &= vals[k]
            mM = m & segm[0]
            nM = int(mM.sum())
            if nM < 60:
                continue
            hitM = float((ret[mM, bi] > 0).mean() * 100)
            roiM = float(ret[mM, bi].sum() / nM / (COSTS[bi] / 100.0))
            rec = dict(cell=cell, nM=nM, hitM=hitM, roiM=roiM)
            for si, nm2 in ((1, "V"), (2, "C")):
                mm = m & segm[si]; n = int(mm.sum())
                rec[f"n{nm2}"] = n
                rec[f"hit{nm2}"] = float((ret[mm, bi] > 0).mean() * 100) if n else None
                rec[f"roi{nm2}"] = float(ret[mm, bi].sum() / n / (COSTS[bi] / 100.0)) if n else None
            cand.append(rec)
        cand.sort(key=lambda x: -x["hitM"])
        print(f"\n── {tnm} ──")
        print(f"{'条件':<34}{'nM':>5}{'的中M':>7}{'ROI_M':>7}{'的中V':>7}{'ROI_V':>7}{'的中C':>7}{'ROI_C':>7}")
        for x in cand[:12]:
            cellnm = "×".join(v for _, v in x["cell"])
            hv = f"{x['hitV']:.0f}%" if x["hitV"] is not None and x["nV"] >= 5 else "—"
            rv = f"{x['roiV']:.0f}%" if x["roiV"] is not None and x["nV"] >= 5 else "—"
            hc = f"{x['hitC']:.0f}%" if x["hitC"] is not None and x["nC"] >= 5 else "—"
            rc = f"{x['roiC']:.0f}%" if x["roiC"] is not None and x["nC"] >= 5 else "—"
            print(f"{cellnm:<34}{x['nM']:>5}{x['hitM']:>6.1f}%{x['roiM']:>6.0f}%"
                  f"{hv:>7}{rv:>7}{hc:>7}{rc:>7}")
        # 全体基準
        allM = segm[0]
        print(f"{'【全レース基準】':<34}{int(allM.sum()):>5}"
              f"{float((ret[allM, bi] > 0).mean() * 100):>6.1f}%"
              f"{float(ret[allM, bi].sum() / allM.sum() / (COSTS[bi] / 100.0)):>6.0f}%")

    json.dump({"n_hits": len(rows), "n_surv": len(surv),
               "null_pass": null_pass, "null_surv": null_surv,
               "rows": [{**x, "cell": ["×".join(v for _, v in x["cell"])]} for x in rows[:200]],
               "surv": [{**x, "cell": ["×".join(v for _, v in x["cell"])]} for x in surv]},
              open("mine200.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved mine200.json")


if __name__ == "__main__":
    main()
