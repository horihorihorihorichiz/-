# -*- coding: utf-8 -*-
"""ランク運用シミュレータ: day_board の判定(発火→ヒート→SS/S/A/B→配分)を
   WF2200R(統一データ版V3=本番エンジン)で再生し、実払戻で精算する。

   判定は本番と同じ patterns.classify / heat_of / tier_of を呼ぶ（統一原則）。
   p1(モデル1位の勝率)は v2_live と同じ softmax+30%cap で scores から復元する。

   usage:
     python3 sim_rank.py                  # 基準構成
     python3 sim_rank.py --all-fires      # 併発パターンにも均等に張る
     python3 sim_rank.py --boot 2000      # ブートストラップ付き
"""
import argparse, itertools, json, math, random
from collections import defaultdict

import course
import patterns as JP

JRA_CODE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
            "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def key_of(ns):
    return "-".join(str(x) for x in sorted(ns))


def p_from_scores(sc):
    """v2_live.rescore と同じ: softmax → 30%クリップ+再正規化"""
    mx = max(sc.values())
    e = {n: math.exp(v - mx) for n, v in sc.items()}
    Z = sum(e.values())
    p = {n: v/Z for n, v in e.items()}
    for _ in range(len(p)):
        over = {n: v for n, v in p.items() if v > 0.30 + 1e-12}
        if not over:
            break
        rest = {n: v for n, v in p.items() if n not in over}
        room = 1.0 - 0.30*len(over)
        sm = sum(rest.values())
        for n in over:
            p[n] = 0.30
        if sm > 0:
            for n in rest:
                p[n] = rest[n]/sm*room
    return p


def load(path="wf_preds_v3.jsonl"):
    rows = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        order = [int(x) for x in d["order"]]
        sc = d["scores"]
        sc = {n: float(v) for n, v in zip(order, sc)} if isinstance(sc, list) else \
             {int(k): float(v) for k, v in sc.items()}
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        rid = d["rid"]
        p = p_from_scores(sc)
        so = sorted(sc, key=lambda n: -sc[n])
        rows.append(dict(
            rid=rid, m=d["month"], order=order, odds=odds, pay=pay,
            g12=sc[so[0]]-sc[so[1]] if len(so) > 1 else 9,
            sp15=sc[so[0]]-sc[so[4]] if len(so) > 4 else None,
            p1=p[so[0]], tier=d.get("tier"), surface=d.get("surface"),
            dist=int(d.get("dist") or 0), field=int(d.get("field") or len(order)),
            day=int(rid[8:10]), baba=(d.get("baba") or "").strip(),
            venue=d.get("venue") or JRA_CODE.get(rid[4:6], "")))
    return rows


# ── 発火(パターン名)→実際の買い目→払戻 ────────────────────────────────
def settle_fire(r, name, desc):
    """1点=100円換算の (点数, 払戻合計) を返す。None=精算不能(未対応名)"""
    o = r["order"]
    pay = r["pay"]
    win = int(list(pay["単勝"].keys())[0])
    if "馬連モデル1-2位" in name or "馬連1-2位" in name:
        return 1, float((pay.get("馬連") or {}).get(key_of(o[:2]), 0))
    if "モデル2位" in name and "単勝" in name:
        t2 = o[1]
        return (1, float((pay.get("単勝") or {}).get(str(t2), 0))) if t2 == win else (1, 0.0)
    if "三連複軸ながし" in name:
        t1 = o[0]
        mtop = [n for n in sorted(r["odds"], key=lambda h: r["odds"][h]) if n != t1][:3]
        if len(mtop) < 3:
            return None
        pts = list(itertools.combinations(mtop, 2))
        ret = sum(float((pay.get("三連複") or {}).get(key_of([t1, *pp]), 0)) for pp in pts)
        return len(pts), ret
    if "ワイド1-2位" in name:
        return 1, float((pay.get("ワイド") or {}).get(key_of(o[:2]), 0))
    if "複勝1位" in name:
        return 1, float((pay.get("複勝") or {}).get(str(o[0]), 0))
    if "単勝" in name or "乖離" in name:      # 乖離単勝ファミリー・単勝1位系
        t1 = o[0]
        return (1, float((pay.get("単勝") or {}).get(str(t1), 0))) if t1 == win else (1, 0.0)
    return None


def classify_race(r):
    """day_board.eval_race と同じ引数で classify+heat を呼ぶ"""
    fld = r["field"]
    w2 = course.jra_waku(r["order"][1], fld) if len(r["order"]) > 1 else None
    fires = JP.classify(r["order"], r["odds"], fld, surface=r["surface"], dist=r["dist"],
                        tier=r["tier"], gap12=r["g12"], p1=r["p1"], day=r["day"],
                        venue=r["venue"], spread15=r["sp15"], waku2=w2, baba=r["baba"])
    buy = [f for f in fires if f[3].startswith("◎")]
    hn, hc, hroi, hsn = JP.heat_of(r["order"], r["odds"], fld, surface=r["surface"],
                                   dist=r["dist"], tier=r["tier"], p1=r["p1"],
                                   venue=r["venue"])
    return buy, hc


def simulate(rows, tier_fn=None, budgets=None, all_fires=False, collect=False):
    """returns per-tier stats + race-level pnl list"""
    tier_fn = tier_fn or JP.tier_of
    budgets = budgets or dict(JP.TIER_BUDGET)
    agg = defaultdict(lambda: defaultdict(float))
    pnl = []      # (m, tier, stake, ret)
    unmapped = defaultdict(int)
    for r in rows:
        buy, hc = classify_race(r)
        if not buy:
            continue
        best = max(buy, key=lambda f: f[2])
        try:
            tier, yen, _ = tier_fn(best[2], hc, best[0])
        except TypeError:
            tier, yen, _ = tier_fn(best[2], hc)
        if yen <= 0:
            continue
        targets = buy if all_fires else [best]
        stake_ret = []
        for f in targets:
            s = settle_fire(r, f[0], f[1])
            if s is None:
                unmapped[f[0]] += 1
                continue
            npts, ret100 = s
            stake_ret.append((npts, ret100))
        if not stake_ret:
            continue
        # 配分: 階級予算を対象パターンに均等割り→各パターン内で点数割り
        per = yen / len(stake_ret)
        stake = ret = 0.0
        for npts, ret100 in stake_ret:
            unit = per / npts
            stake += per
            ret += ret100/100.0 * unit
        a = agg[tier]
        a["n"] += 1
        a["stake"] += stake
        a["ret"] += ret
        a["hit"] += ret > 0
        pnl.append((r["m"], tier, stake, ret))
    return agg, pnl, unmapped


def report(agg, pnl, label):
    print(f"\n━━ {label} ━━")
    order = ["SS", "S", "A", "B"]
    tot_s = tot_r = 0.0
    print(f"  {'階級':4s} {'R数':>4s} {'的中率':>6s} {'投下':>10s} {'回収':>10s} {'ROI':>7s} {'損益':>10s}")
    for t in order:
        a = agg.get(t)
        if not a:
            continue
        roi = a["ret"]/a["stake"]*100
        tot_s += a["stake"]
        tot_r += a["ret"]
        print(f"  {t:4s} {int(a['n']):4d} {a['hit']/a['n']*100:5.1f}% "
              f"{a['stake']:10,.0f} {a['ret']:10,.0f} {roi:6.1f}% {a['ret']-a['stake']:+10,.0f}")
    if tot_s:
        print(f"  {'計':4s} {'':4s} {'':6s} {tot_s:10,.0f} {tot_r:10,.0f} "
              f"{tot_r/tot_s*100:6.1f}% {tot_r-tot_s:+10,.0f}")
    # 月次
    bym = defaultdict(lambda: [0.0, 0.0])
    for m, t, s, r_ in pnl:
        bym[m][0] += s
        bym[m][1] += r_
    ms = sorted(bym)
    line = " ".join(f"{m[-2:]}月{(bym[m][1]-bym[m][0])/1000:+.0f}k" for m in ms)
    neg = sum(1 for m in ms if bym[m][1] < bym[m][0])
    print(f"  月次: {line}  (負け月 {neg}/{len(ms)})")
    # 最大ドローダウン(レース時系列)
    cum = peak = dd = 0.0
    for m, t, s, r_ in pnl:
        cum += r_ - s
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    dv=[(s,r_) for m,t,s,r_ in pnl if m<="202603"]; cf=[(s,r_) for m,t,s,r_ in pnl if m>"202603"]
    drs=sum(s for s,_ in dv); drr=sum(r_ for _,r_ in dv)
    crs=sum(s for s,_ in cf); crr=sum(r_ for _,r_ in cf)
    print(f"  dev(11-03月) ROI {drr/max(drs,1)*100:.1f}% / conf(04-07月) ROI {crr/max(crs,1)*100:.1f}%")
    print(f"  最終損益 {tot_r-tot_s:+,.0f}円 / 最大DD {dd:,.0f}円")
    return tot_r - tot_s, dd


def bootstrap(pnl, B=2000, seed=1):
    rnd = random.Random(seed)
    outs = []
    n = len(pnl)
    for _ in range(B):
        s = r = 0.0
        for _ in range(n):
            _, _, st, rt = pnl[rnd.randrange(n)]
            s += st
            r += rt
        outs.append(r - s)
    outs.sort()
    lo, med, hi = outs[int(B*0.05)], outs[B//2], outs[int(B*0.95)]
    p_loss = sum(1 for x in outs if x < 0)/B
    print(f"  ブートストラップ{B}回: 損益中央値{med:+,.0f}円 90%区間[{lo:+,.0f}, {hi:+,.0f}] "
          f"P(損失)={p_loss*100:.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="wf_preds_v3.jsonl")
    ap.add_argument("--all-fires", action="store_true")
    ap.add_argument("--boot", type=int, default=0)
    a = ap.parse_args()
    rows = load(a.path)
    print(f"{len(rows)}R 読み込み ({a.path}) / 判定=本番patterns.py")

    agg, pnl, unmapped = simulate(rows, all_fires=a.all_fires)
    report(agg, pnl, "基準構成(最上位パターンに階級予算)" + ("+併発均等" if a.all_fires else ""))
    if unmapped:
        print("  ⚠精算未対応の発火:", dict(unmapped))
    if a.boot:
        bootstrap(pnl, a.boot)


if __name__ == "__main__":
    main()
