# -*- coding: utf-8 -*-
"""コース単位の配点を30パターン以上で掃引し直す（2026-08-22・指示「courseもありなさい 少なくとも30パターン作ったら」）。

★なぜやり直すか:
   前回コース単位を棄却した COURSE_SWEEP50_REPORT は **台帳8,002R** 時点の測定で、
   1コースあたり65Rしかなく null control(乱数重み)に8回負けた。
   その後の収穫で台帳が **14,476R** まで増えた(1コースあたり約1.5倍)。
   標本が増えれば結論が変わりうるので、同じ規律でやり直す。

パターン(31本):
   [基準] 素Ver.99.27 / 全体1本(学習) / 芝ダ×距離6群(現行)
   [コース単位] L2縮小を 0.05〜20 の8段階 × (全体1本へ縮小 / 6群へ縮小) = 16本
   [コース群] 場のみ / 場×芝ダ / 距離のみ / 距離帯×場 の4本
   [混合] コース重みと6群重みの線形ブレンド α=0.25/0.50/0.75 の3本
   [null] コース割当シャッフル(縮小3段階) の3本  ←偶然の目安
   [下限] 最小R数のしきい値を 30/60/120 に変えた3本
   合計 3+16+4+3+3+3 = 32本

判定:
   MINEで学習 → VALIDATE/CONFIRM を各1回だけ測定。
   **null control を上回らないパターンは、どれだけMINEで良くても採らない。**
"""
import json, os, sys, collections, pickle, itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2

NAMES16 = ["TSI", "LTS", "FSI", "Bonus", "DSI", "NSI", "CSI", "WAS", "TAS", "HCS",
           "NRJA", "展開乗数", "spd_res", "mgn_abs", "wide4c", "pos_gain"]


def course_key(r):
    return f"{r.get('venue')}{r['surface']}{r['distance']}"


def sd_key(r):
    return f"{r['surface']}{r['dist_cat']}"


def venue_key(r):
    return str(r.get("venue"))


def venue_sd_key(r):
    return f"{r.get('venue')}{r['surface']}"


def dist_key(r):
    return str(r["distance"])


def fit_by(races, keyfn, l2, w0, min_n=1):
    out = {}
    by = collections.defaultdict(list)
    for r in races:
        k = keyfn(r)
        if k:
            by[k].append(r)
    for k, sub in by.items():
        if len(sub) < min_n:
            continue
        X, M, W = V2.make_tensor(sub, key="Z16")
        out[k] = V2.fit(X, M, W, l2, w0=w0, wstart=w0)
    return out


def ev(races, wfn):
    n = len(races); win = t3 = 0; cost = ret = 0
    for r in races:
        w = wfn(r)
        s = r["Z16"] @ w
        o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
        fin = set(r["top3"])
        win += int(o[0] == r["top3"][0]); t3 += int(o[0] in fin)
        pl = {int(k): float(v) for k, v in ((r["payout"] or {}).get("複勝") or {}).items()}
        for i in o[:2]:
            cost += 100; ret += pl.get(r["nums"][i], 0.0)
    return (win / n * 100, t3 / n * 100, ret / cost * 100 if cost else 0)


def main():
    races = V.load_races()
    V2.attach_corner(races)
    K = races[0]["Z16"].shape[1]
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    print(f"台帳 {len(races)}R / MINE {len(MINE)} VAL {len(VAL)} CONF {len(CONF)}", file=sys.stderr)
    cc = collections.Counter(course_key(r) for r in MINE)
    print(f"コース数 {len(cc)} / 1コース平均 {np.mean(list(cc.values())):.1f}R / "
          f"100R以上のコース {sum(1 for v in cc.values() if v >= 100)}", file=sys.stderr)

    X, M, W = V2.make_tensor(MINE, key="Z16")
    w_all = V2.fit(X, M, W, 1.0, w0=np.zeros(K), wstart=np.zeros(K))
    raw = np.zeros(K); raw[:11] = 1.0
    w_sd = fit_by(MINE, sd_key, 0.2, w_all)

    pats = []
    pats.append(("①素Ver.99.27", lambda r: raw, "base"))
    pats.append(("②全体1本(学習)", lambda r: w_all, "base"))
    pats.append(("③芝ダ×距離6群(現行)", lambda r: w_sd.get(sd_key(r), w_all), "base"))

    # コース単位: 縮小先=全体1本 / 6群、L2を8段階
    L2S = [0.05, 0.1, 0.3, 0.6, 1.0, 3.0, 8.0, 20.0]
    for lam in L2S:
        wc = fit_by(MINE, course_key, lam, w_all)
        pats.append((f"course→全体 λ={lam:g}",
                     (lambda r, wc=wc: wc.get(course_key(r), w_all)), "course"))
    for lam in L2S:
        # 6群重みへ縮小（コースごとに、その群の重みを起点にする）
        wc2 = {}
        by = collections.defaultdict(list)
        for r in MINE:
            by[course_key(r)].append(r)
        for k, sub in by.items():
            base = w_sd.get(sd_key(sub[0]), w_all)
            Xc, Mc, Wc = V2.make_tensor(sub, key="Z16")
            wc2[k] = V2.fit(Xc, Mc, Wc, lam, w0=base, wstart=base)
        pats.append((f"course→6群 λ={lam:g}",
                     (lambda r, wc2=wc2: wc2.get(course_key(r), w_sd.get(sd_key(r), w_all))),
                     "course"))

    # コース群（粗い分け）
    for nm, fn in (("場のみ", venue_key), ("場×芝ダ", venue_sd_key), ("距離のみ", dist_key)):
        wg = fit_by(MINE, fn, 0.3, w_all)
        pats.append((f"{nm} λ=0.3", (lambda r, wg=wg, fn=fn: wg.get(fn(r), w_all)), "group"))
    wvs = fit_by(MINE, lambda r: f"{r.get('venue')}{r['dist_cat']}", 0.3, w_all)
    pats.append(("場×距離帯 λ=0.3",
                 (lambda r, wvs=wvs: wvs.get(f"{r.get('venue')}{r['dist_cat']}", w_all)), "group"))

    # 混合（コース重みと6群重みのブレンド）
    wc_best = fit_by(MINE, course_key, 0.3, w_all)
    for a in (0.25, 0.5, 0.75):
        def mk(a=a):
            def f(r):
                c = wc_best.get(course_key(r))
                s = w_sd.get(sd_key(r), w_all)
                return s if c is None else a * c + (1 - a) * s
            return f
        pats.append((f"混合 course{a:.0%}+6群", mk(), "mix"))

    # 最小R数しきい値
    for mn in (30, 60, 120):
        wcm = fit_by(MINE, course_key, 0.3, w_all, min_n=mn)
        pats.append((f"course λ=0.3 最小{mn}R",
                     (lambda r, wcm=wcm: wcm.get(course_key(r), w_sd.get(sd_key(r), w_all))),
                     "course"))

    # null control: コース割当をシャッフル
    rs = np.random.RandomState(23)
    keys = sorted({course_key(r) for r in MINE})
    fake = {r["rid"]: keys[rs.randint(len(keys))] for r in races}
    for lam in (0.1, 0.3, 1.0):
        wn = fit_by(MINE, lambda r: fake[r["rid"]], lam, w_all)
        pats.append((f"null(course割当乱数) λ={lam:g}",
                     (lambda r, wn=wn: wn.get(fake[r["rid"]], w_all)), "null"))

    print(f"\nパターン数 {len(pats)}")
    print("=" * 104)
    print(f"{'パターン':<26}" + "".join(f"{s:^25}" for s in ("MINE", "VALIDATE", "CONFIRM")))
    print(f"{'':<26}" + "".join(f"{'1位勝率 3着内 複2ROI':^25}" for _ in range(3)))
    out = {}
    for nm, fn, kind in pats:
        line = f"{nm:<26}"
        rec = {}
        for sn, S in (("MINE", MINE), ("VALIDATE", VAL), ("CONFIRM", CONF)):
            a, b, c = ev(S, fn); rec[sn] = (a, b, c)
            line += f"{a:7.1f}%{b:7.1f}%{c:8.1f}%"
        out[nm] = {"kind": kind, **{k: list(v) for k, v in rec.items()}}
        print(line)

    # 判定: null の最良を上回るか
    nulls = [v for k, v in out.items() if v["kind"] == "null"]
    for metric, idx in (("VAL 3着内", 1), ("CONF 3着内", 1)):
        pass
    nb_v = max(n["VALIDATE"][1] for n in nulls)
    nb_c = max(n["CONFIRM"][1] for n in nulls)
    print("\n" + "=" * 104)
    print(f"null control の最良: VALIDATE 3着内 {nb_v:.1f}% / CONFIRM 3着内 {nb_c:.1f}%")
    print("★これを未知2期間**とも**上回ったパターンだけが本物:")
    winners = [(k, v) for k, v in out.items()
               if v["kind"] not in ("null",)
               and v["VALIDATE"][1] > nb_v and v["CONFIRM"][1] > nb_c]
    if winners:
        for k, v in sorted(winners, key=lambda x: -(x[1]["VALIDATE"][1] + x[1]["CONFIRM"][1])):
            print(f"  ○ {k:<26} VAL {v['VALIDATE'][1]:.1f}% / CONF {v['CONFIRM'][1]:.1f}%")
    else:
        print("  該当なし＝コース単位を含め、どの分け方も乱数を超えなかった")
    json.dump(out, open("course_sweep30.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved course_sweep30.json")


if __name__ == "__main__":
    main()
