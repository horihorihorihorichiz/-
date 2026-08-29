# -*- coding: utf-8 -*-
"""未踏の「買い方の構造×シグナル」総当たり最終掃引（2026-08-22深夜・指示:
「ズバ抜けたリードならワイドの方が期待値高い等に加え、評価を超えた大穴馬を軸で買う
三連複とか、君がまだやってない世界をやりきってほしい」）。

★仮説は実行前にここに凍結する（見てから足さない・消さない）。

[A] 穴軸系: モデルが高評価なのに市場が嫌う馬（単勝しきい値 8/12/16/25倍）を軸に
    複勝1点 / ワイド2点(モデル上位2頭へ) / 三連複6点(モデル上位4頭へ流し)。
    軸定義は「モデル1位が穴」と「モデル上位3位内で最上位の穴」の2通り。
[B] 乖離系: モデル順位≤3 かつ (市場人気順位−モデル順位)≥4/6/8 の馬に
    複勝 / 1番人気とのワイド / モデル最上位他馬とのワイド。
[C] 形×オッズ文脈: 2強で両頭≥3/5/8倍のワイド・馬連、2強で2位≥8/15倍、
    1強で1位≥5/8/12倍の単勝・複勝、3強で上位3頭平均≥5/8倍の三連複、
    参照セル=1強×1位2倍未満の複勝（既知91.8%）。
[D] 形で券種を切替える固定ポートフォリオ（採掘ではなく事前登録した1本の方針）:
    1強→複勝1位 / 2強→ワイド1-2 / 3強→三連複123 / 階段→複勝1位 / 混戦→見送り。
    変種: 階段も見送る「厳格版」。

判定規律（RULES.md R1-R4）:
  ゲート = MINEでROI≥105% かつ n≥100 のセルだけ VAL/CONF を各1回測る。
  勝者 = VALとCONF両方でROI>100%。
  null = モデルスコアを乱数に置換して**同じ掃引と選択**を8回反復（同一自由度）。
  ROIはSE併記（per-bet収益の標準偏差/√n）。
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
from verify_export import scorer_from_artifact

rng = np.random.RandomState(20260822)


def prep(races, wfn, null_seed=None):
    """レースごとの文脈（順位・オッズ・形・払戻取得関数）を前計算する。"""
    rs = np.random.RandomState(null_seed) if null_seed is not None else None
    ctx = []
    for r in races:
        if rs is None:
            s = r["Z16"] @ wfn(r)
        else:
            s = rs.randn(len(r["nums"]))
        sd = s.std() or 1.0
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        order = [r["nums"][k] for k in o]           # モデル順位順の馬番
        od = {n: float(v) for n, v in (r.get("odds") or {}).items() if v}
        mrank = {n: i + 1 for i, n in enumerate(
            sorted(od, key=lambda n: (od[n], n)))}   # 市場人気順位
        z = np.sort(s)[::-1] / sd
        g12 = float(z[0] - z[1])
        g23 = float(z[1] - z[2]) if len(z) > 2 else 0.0
        g34 = float(z[2] - z[3]) if len(z) > 3 else 0.0
        if g12 >= 0.6:
            shape = "1強"
        elif g12 < 0.3 and g23 >= 0.6:
            shape = "2強"
        elif g12 < 0.3 and g23 < 0.3 and g34 >= 0.5:
            shape = "3強"
        elif g12 < 0.3 and g23 < 0.3 and g34 < 0.3:
            shape = "混戦"
        else:
            shape = "階段"
        pay = r.get("payout") or {}

        def mk(pay=pay):
            def g(kind, *nums):
                d = pay.get(kind) or {}
                if kind in ("単勝", "複勝"):
                    v = d.get(str(nums[0]))
                else:
                    v = d.get("-".join(str(x) for x in sorted(nums)))
                return float(v) if v else 0.0
            return g
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        ctx.append(dict(order=order, od=od, mrank=mrank, shape=shape,
                        g=(g12, g23, g34), pay=mk(), seg=seg))
    return ctx


# ── 買い方の構造（cost, ret を返す。発火しないなら None）──────────────

def bet_fuku(c, num):
    return (100, c["pay"]("複勝", num))


def bet_tan(c, num):
    return (100, c["pay"]("単勝", num))


def bet_wide_axis(c, axis, mates):
    mates = [m for m in mates if m != axis][:2]
    if not mates:
        return None
    return (100 * len(mates), sum(c["pay"]("ワイド", axis, m) for m in mates))


def bet_trio_axis(c, axis, mates):
    mates = [m for m in mates if m != axis][:4]
    if len(mates) < 2:
        return None
    import itertools
    combos = list(itertools.combinations(mates, 2))
    return (100 * len(combos), sum(c["pay"]("三連複", axis, a, b) for a, b in combos))


def axis_rank1(c, t):
    n = c["order"][0]
    o = c["od"].get(n)
    return n if (o and o >= t) else None


def axis_top3(c, t):
    for n in c["order"][:3]:
        o = c["od"].get(n)
        if o and o >= t:
            return n
    return None


def build_cells():
    """(名前, 発火関数) のリスト。発火関数は ctx→(cost,ret)|None。"""
    cells = []
    # [A] 穴軸
    for t in (8, 12, 16, 25):
        for anm, afn in (("軸=1位穴", axis_rank1), ("軸=上位3内穴", axis_top3)):
            def mkA(afn=afn, t=t, kind="複勝"):
                def f(c):
                    a = afn(c, t)
                    return None if a is None else bet_fuku(c, a)
                return f
            cells.append((f"A {anm}≥{t}倍 複勝", mkA()))

            def mkW(afn=afn, t=t):
                def f(c):
                    a = afn(c, t)
                    if a is None:
                        return None
                    return bet_wide_axis(c, a, c["order"][:3])
                return f
            cells.append((f"A {anm}≥{t}倍 ワイド2点", mkW()))

            def mkT(afn=afn, t=t):
                def f(c):
                    a = afn(c, t)
                    if a is None:
                        return None
                    return bet_trio_axis(c, a, c["order"][:5])
                return f
            cells.append((f"A {anm}≥{t}倍 三連複6点", mkT()))
    # [B] 乖離
    for D in (4, 6, 8):
        def pick(c, D=D):
            best = None
            for i, n in enumerate(c["order"][:3]):
                mr = c["mrank"].get(n)
                if mr and mr - (i + 1) >= D:
                    if best is None:
                        best = n
            return best

        def mkBf(pick=pick):
            def f(c):
                n = pick(c)
                return None if n is None else bet_fuku(c, n)
            return f
        cells.append((f"B 乖離≥{D} 複勝", mkBf()))

        def mkBw1(pick=pick):
            def f(c):
                n = pick(c)
                if n is None:
                    return None
                fav = min(c["od"], key=lambda k: c["od"][k]) if c["od"] else None
                if fav is None or fav == n:
                    return None
                return (100, c["pay"]("ワイド", n, fav))
            return f
        cells.append((f"B 乖離≥{D} ワイド×1人気", mkBw1()))

        def mkBw2(pick=pick):
            def f(c):
                n = pick(c)
                if n is None:
                    return None
                mate = next((m for m in c["order"] if m != n), None)
                if mate is None:
                    return None
                return (100, c["pay"]("ワイド", n, mate))
            return f
        cells.append((f"B 乖離≥{D} ワイド×モデル最上位", mkBw2()))
    # [C] 形×オッズ文脈
    def wide12(c):
        return (100, c["pay"]("ワイド", c["order"][0], c["order"][1]))

    def uma12(c):
        return (100, c["pay"]("馬連", c["order"][0], c["order"][1]))

    def trio123(c):
        return (100, c["pay"]("三連複", *c["order"][:3]))
    for b in (3, 5, 8):
        for bnm, bfn in (("ワイド1-2", wide12), ("馬連1-2", uma12)):
            def mkC(b=b, bfn=bfn):
                def f(c):
                    if c["shape"] != "2強":
                        return None
                    o1 = c["od"].get(c["order"][0]); o2 = c["od"].get(c["order"][1])
                    if not (o1 and o2 and o1 >= b and o2 >= b):
                        return None
                    return bfn(c)
                return f
            cells.append((f"C 2強両頭≥{b}倍 {bnm}", mkC()))
    for b in (8, 15):
        for bnm, bfn in (("ワイド1-2", wide12), ("馬連1-2", uma12)):
            def mkC2(b=b, bfn=bfn):
                def f(c):
                    if c["shape"] != "2強":
                        return None
                    o2 = c["od"].get(c["order"][1])
                    return bfn(c) if (o2 and o2 >= b) else None
                return f
            cells.append((f"C 2強2位≥{b}倍 {bnm}", mkC2()))
    for b in (5, 8, 12):
        for bnm, bfn in (("単勝1位", None), ("複勝1位", None)):
            def mkC3(b=b, tan=(bnm == "単勝1位")):
                def f(c):
                    if c["shape"] != "1強":
                        return None
                    o1 = c["od"].get(c["order"][0])
                    if not (o1 and o1 >= b):
                        return None
                    return bet_tan(c, c["order"][0]) if tan else bet_fuku(c, c["order"][0])
                return f
            cells.append((f"C 1強1位≥{b}倍 {bnm}", mkC3()))
    for b in (5, 8):
        def mkC4(b=b):
            def f(c):
                if c["shape"] != "3強":
                    return None
                os_ = [c["od"].get(n) for n in c["order"][:3]]
                if not all(os_) or np.mean(os_) < b:
                    return None
                return trio123(c)
            return f
        cells.append((f"C 3強平均≥{b}倍 三連複123", mkC4()))

    def ref(c):
        o1 = c["od"].get(c["order"][0])
        if c["shape"] == "1強" and o1 and o1 < 2.0:
            return bet_fuku(c, c["order"][0])
        return None
    cells.append(("C 参照:1強1位<2倍 複勝", ref))
    # [D] 形で券種を切替えるポートフォリオ（事前登録の1本）
    def policy(c, strict):
        sh = c["shape"]
        if sh == "1強":
            return bet_fuku(c, c["order"][0])
        if sh == "2強":
            return wide12(c)
        if sh == "3強":
            return trio123(c)
        if sh == "階段" and not strict:
            return bet_fuku(c, c["order"][0])
        return None
    cells.append(("D 形→券種ポートフォリオ", lambda c: policy(c, False)))
    cells.append(("D 形→券種(厳格=混戦階段見送り)", lambda c: policy(c, True)))
    return cells


def run_sweep(ctx, cells):
    """全セル×3期間の (n, cost, ret, per-bet ROI配列) を返す。"""
    out = {}
    for nm, fn in cells:
        stats = [[0, 0.0, 0.0, []] for _ in range(3)]
        for c in ctx:
            r = fn(c)
            if r is None:
                continue
            cost, ret = r
            st = stats[c["seg"]]
            st[0] += 1; st[1] += cost; st[2] += ret
            st[3].append(ret / cost * 100.0)
        out[nm] = stats
    return out


def fmt(st):
    n, cost, ret, per = st
    if not cost:
        return f"{'—':>22}"
    roi = ret / cost * 100
    se = np.std(per) / np.sqrt(len(per)) if len(per) > 1 else 0
    hit = np.mean([p > 0 for p in per]) * 100
    return f"n{n:>5} {hit:5.1f}% {roi:6.1f}±{se:4.1f}"


def gate_and_judge(res, tag=""):
    """ゲート(MINE ROI≥105, n≥100)→VAL/CONF両方100超を勝者とする。"""
    passed, winners = [], []
    for nm, st in res.items():
        nM, cM, rM, _ = st[0]
        if nM >= 100 and cM and rM / cM * 100 >= 105:
            passed.append(nm)
            v = st[1][2] / st[1][1] * 100 if st[1][1] else 0
            c = st[2][2] / st[2][1] * 100 if st[2][1] else 0
            if v > 100 and c > 100:
                winners.append((nm, v, c))
    return passed, winners


def main():
    races = V.load_races()
    V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    cells = build_cells()
    print(f"台帳 {len(races)}R / セル数 {len(cells)}（実行前に凍結済み）\n")

    ctx = prep(races, wfn)
    res = run_sweep(ctx, cells)

    print(f"{'セル':<34}{'MINE':^24}{'VALIDATE':^24}{'CONFIRM':^24}")
    print(f"{'':<34}" + "".join(f"{'n 的中 ROI±SE':^24}" for _ in range(3)))
    for nm, st in res.items():
        print(f"{nm:<34}" + "".join(f"{fmt(s):>24}" for s in st))

    passed, winners = gate_and_judge(res)
    print(f"\nゲート通過(MINE ROI≥105・n≥100): {len(passed)}本 → {passed}")
    print(f"勝者(VAL/CONF両方ROI>100): {len(winners)}本")
    for nm, v, c in winners:
        print(f"  ○ {nm}: VAL {v:.1f}% / CONF {c:.1f}%")

    # null: 乱数スコアで同じ掃引+同じ選択を8回
    print("\n═ null（乱数スコア×8反復・同一自由度）═")
    null_pass, null_win = [], []
    for i in range(8):
        nctx = prep(races, wfn, null_seed=1000 + i)
        nres = run_sweep(nctx, cells)
        p, w = gate_and_judge(nres)
        null_pass.append(len(p)); null_win.append(len(w))
        print(f"  null#{i+1}: ゲート通過{len(p)}本 勝者{len(w)}本"
              + (f" {[x[0] for x in w]}" if w else ""))
    print(f"\nnull平均: ゲート通過 {np.mean(null_pass):.1f}本 / 勝者 {np.mean(null_win):.1f}本")
    print(f"実データ: ゲート通過 {len(passed)}本 / 勝者 {len(winners)}本")
    print("→ 実データの勝者数がnull分布の中に収まるなら、その勝者は偶然と区別できない")

    json.dump({nm: [[s[0], s[1], s[2]] for s in st] for nm, st in res.items()},
              open("final_sweep.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved final_sweep.json")


if __name__ == "__main__":
    main()
