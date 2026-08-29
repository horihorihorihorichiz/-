# -*- coding: utf-8 -*-
"""49セル(場×芝ダ×距離帯)ごとに6型から最良の買い方を決める（2026-08-22・指示「各52ごとに決めて」）。

型: 単勝1位/複勝1位/ワイド1-2位/三連複軸流し4頭(6点)/同5頭(10点)/三連複5頭BOX(10点)
決め方: セルのMINE n≥80なら6型のMINE ROI最大を採用。n<80は6群(芝ダ×距離帯)の選択へ
フォールバック。★=そのセルの最良型がMINE ROI≥100(期待値プラス方針の対象)。
検証: ★セル集合の合計ROIをVAL/CONFで各1回。null=順位乱数で全パイプライン10回。
"""
import json, os, sys, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

FORMS = ["単勝1位", "複勝1位", "ワイド1-2", "三連複流し4頭6点", "三連複流し5頭10点", "三連複5頭BOX10点"]
COSTS = np.array([100.0, 100.0, 100.0, 600.0, 1000.0, 1000.0])

def main():
    races = V.load_races(); V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    R = len(races)
    seg = np.zeros(R, int); orders = []
    k52 = []; k6 = []
    for i, r in enumerate(races):
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        orders.append([r["nums"][k] for k in o])
        m = r["month"]; seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        k52.append(f"{r.get('venue')}{r['surface']}{r['dist_cat']}")
        k6.append(f"{r['surface']}{r['dist_cat']}")
    segm = [seg == k for k in range(3)]
    k52 = np.array(k52); k6 = np.array(k6)

    def rets_of(order_list):
        RET = np.zeros((R, len(FORMS)))
        for i, r in enumerate(races):
            od = order_list[i]; pay = r.get("payout") or {}
            def g(k, key):
                d = pay.get(k) or {}
                v = d.get(key); return float(v) if v else 0.0
            a = od[0]; b = od[1] if len(od) > 1 else None
            tri = pay.get("三連複") or {}
            def combo(par, axis=True):
                t = 0.0
                it = (itertools.combinations(par, 2) if axis else itertools.combinations(par, 3))
                for c in it:
                    hs = sorted((a,) + c) if axis else sorted(c)
                    v = tri.get("-".join(str(x) for x in hs))
                    if v: t += float(v)
                return t
            RET[i] = [g("単勝", str(a)), g("複勝", str(a)),
                      g("ワイド", "-".join(str(x) for x in sorted((a, b)))) if b else 0.0,
                      combo(od[1:5]), combo(od[1:6]), combo(od[:5], axis=False)]
        return RET

    def run(order_list):
        RET = rets_of(order_list)
        # 6群のフォールバック選択
        pol6 = {}
        for lab in set(k6):
            m = (k6 == lab) & segm[0]; n = int(m.sum())
            rois = RET[m].sum(0) / (COSTS * n) * 100 if n else np.zeros(len(FORMS))
            pol6[lab] = (int(np.argmax(rois)), float(np.max(rois)))
        # 49セルの選択
        table = {}
        for lab in sorted(set(k52)):
            m = (k52 == lab) & segm[0]; n = int(m.sum())
            if n >= 80:
                rois = RET[m].sum(0) / (COSTS * n) * 100
                bi = int(np.argmax(rois)); mroi = float(rois[bi]); src = "セル"
            else:
                bi, mroi = pol6[k6[np.where(k52 == lab)[0][0]]]; src = "6群FB"
            table[lab] = dict(form=bi, mine=mroi, n=n, src=src, star=mroi >= 100)
        # ★集合の3期間評価
        res = {}
        for si, nm in ((0, "MINE"), (1, "VAL"), (2, "CONF")):
            cost = ret = 0.0; nb = 0
            for lab, t in table.items():
                if not t["star"]: continue
                m = (k52 == lab) & segm[si]; n = int(m.sum())
                cost += COSTS[t["form"]] * n; ret += RET[m, t["form"]].sum(); nb += n
            res[nm] = dict(roi=ret / cost * 100 if cost else 0, n=nb)
        return table, res

    table, res = run(orders)
    stars = [l for l, t in table.items() if t["star"]]
    print(f"★セル(最良型がMINE100%超): {len(stars)}個 / 49")
    print(f"★集合の成績: MINE {res['MINE']['roi']:.1f}%(n{res['MINE']['n']}) / "
          f"VAL {res['VAL']['roi']:.1f}%(n{res['VAL']['n']}) / "
          f"CONF {res['CONF']['roi']:.1f}%(n{res['CONF']['n']})")

    rs = np.random.RandomState(89)
    nv, nc = [], []
    for t in range(10):
        fake = []
        for r in races:
            o = list(r["nums"]); rs.shuffle(o); fake.append(o)
        _, r2 = run(fake)
        nv.append(r2["VAL"]["roi"]); nc.append(r2["CONF"]["roi"])
        print(f"  null#{t+1}: ★集合 VAL {r2['VAL']['roi']:.1f}% / CONF {r2['CONF']['roi']:.1f}%", file=sys.stderr)
    print(f"null(×10): VAL 平均{np.mean(nv):.1f}% 最大{max(nv):.1f}% / CONF 平均{np.mean(nc):.1f}% 最大{max(nc):.1f}%")

    print("\n─ 49セルの選択表 ─")
    print(f"{'セル':<10}{'n':>6}{'選んだ型':<18}{'MINE ROI':>9}  印")
    ven = ["札幌","函館","福島","新潟","東京","中山","中京","京都","阪神","小倉"]
    for lab in sorted(table, key=lambda x: (ven.index(x[:2]) if x[:2] in ven else 99, x)):
        t = table[lab]
        print(f"{lab:<10}{t['n']:>6}{FORMS[t['form']]:<18}{t['mine']:>8.1f}%  "
              f"{'★' if t['star'] else ''}{'(6群FB)' if t['src']=='6群FB' else ''}")
    json.dump({"table": table, "res": res, "null_v": nv, "null_c": nc},
              open("policy52.json", "w"), ensure_ascii=False, indent=1)
    print("saved policy52.json")


if __name__ == "__main__":
    main()
