# -*- coding: utf-8 -*-
"""スコア分布の「形」と買い方の相性を測る（2026-08-22・指示「2頭がずば抜けてる時とか色々調べて」）。

問い: モデルスコアの形（1強/2強/3強/混戦）によって、どの券種がどれだけ当たるかは変わるか。
     変わるなら「形を見て券種を選ぶ」が成立する。

形の定義（スコアはレース内SDで正規化した上位の段差）:
  g12 = (1位-2位)/SD, g23 = (2位-3位)/SD, g34 = (3位-4位)/SD
  1強: g12≥0.6                        → 単勝1位/複勝1位が締まるはず
  2強: g12<0.3 かつ g23≥0.6           → ワイド1-2/馬連1-2の形
  3強: g12,g23<0.3 かつ g34≥0.5       → 三連複123の形
  混戦: 上記以外でg12,g23,g34全部<0.3
  階段: 残り

測るもの（各形×各券種×3期間）: 的中率・ROI・n
加えて連続量でも: g12帯ごとの1位成績 / g23帯ごとのワイド1-2成績（しきい値に依存しない確認）
さらに「モデルは2強だが市場は2強と見ていない」（2位のオッズが高い）の分解。
これは記述統計（選択ではない）なので3期間まとめて出し、期間別も併記する。
"""
import json, os, sys, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

BETS = ["単勝1位", "複勝1位", "ワイド1-2", "馬連1-2", "三連複123"]

def main():
    races = V.load_races(); V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    rows = []
    for r in races:
        s = r["Z16"] @ wfn(r)
        sd = s.std() or 1.0
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        z = np.sort(s)[::-1] / sd
        g12 = float(z[0]-z[1]); g23 = float(z[1]-z[2]) if len(z) > 2 else 0
        g34 = float(z[2]-z[3]) if len(z) > 3 else 0
        order = [r["nums"][k] for k in o]
        pay = r.get("payout") or {}
        def g(k, key):
            d = pay.get(k) or {}
            v = d.get(key); return float(v) if v else 0.0
        a, b, c = order[0], order[1], order[2]
        uk = "-".join(str(x) for x in sorted((a, b)))
        tk = "-".join(str(x) for x in sorted((a, b, c)))
        rets = [g("単勝", str(a)), g("複勝", str(a)), g("ワイド", uk), g("馬連", uk), g("三連複", tk)]
        o2 = (r.get("odds") or {}).get(str(b))
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        rows.append((g12, g23, g34, rets, seg, float(o2) if o2 else None))

    g12a = np.array([x[0] for x in rows]); g23a = np.array([x[1] for x in rows])
    g34a = np.array([x[2] for x in rows])
    RET = np.array([x[3] for x in rows]); seg = np.array([x[4] for x in rows])
    o2a = np.array([x[5] if x[5] else np.nan for x in rows])
    n = len(rows)
    print(f"対象 {n}R\n")

    shape = np.full(n, "階段", dtype=object)
    shape[(g12a < 0.3) & (g23a < 0.3) & (g34a < 0.3)] = "混戦"
    shape[(g12a < 0.3) & (g23a < 0.3) & (g34a >= 0.5)] = "3強"
    shape[(g12a < 0.3) & (g23a >= 0.6)] = "2強"
    shape[g12a >= 0.6] = "1強"

    print("═ 形×券種（全期間・的中率/ROI）═")
    hdr = f"{'形':<5}{'n':>6}" + "".join(f"{b:^20}" for b in BETS)
    print(hdr)
    for sh in ("1強", "2強", "3強", "混戦", "階段"):
        m = shape == sh
        nn = int(m.sum())
        if nn < 50: continue
        line = f"{sh:<5}{nn:>6}"
        for bi in range(len(BETS)):
            hit = (RET[m, bi] > 0).mean()*100; roi = RET[m, bi].sum()/(100*nn)
            line += f"  {hit:5.1f}%/{roi:6.1f}%  "
        print(line)
    m = np.ones(n, bool)
    line = f"{'全体':<5}{n:>6}"
    for bi in range(len(BETS)):
        line += f"  {(RET[:,bi]>0).mean()*100:5.1f}%/{RET[:,bi].sum()/(100*n):6.1f}%  "
    print(line)

    print("\n═ 期間別（形×最も相性の良い券種の確認）═")
    for sh, bi in (("1強", 1), ("1強", 0), ("2強", 2), ("2強", 3), ("3強", 4), ("混戦", 4)):
        line = f"{sh}×{BETS[bi]:<8}"
        for si, nm in ((0, "MINE"), (1, "VAL"), (2, "CONF")):
            m = (shape == sh) & (seg == si); nn = int(m.sum())
            if nn < 30: line += f"  {nm}:n{nn}小 "; continue
            line += f"  {nm} {(RET[m,bi]>0).mean()*100:.0f}%/{RET[m,bi].sum()/(100*nn):.0f}% (n{nn})"
        print(line)

    print("\n═ 連続量: g12帯ごとの1位成績（しきい値に依存しない確認）═")
    print(f"{'g12帯':>10}{'n':>6}{'複勝1位 的中/ROI':^20}{'単勝1位 的中/ROI':^20}")
    for lo, hi in ((0,0.15),(0.15,0.3),(0.3,0.45),(0.45,0.6),(0.6,0.8),(0.8,1.2),(1.2,9)):
        m = (g12a >= lo) & (g12a < hi); nn = int(m.sum())
        if nn < 100: continue
        print(f"{f'{lo:.2f}-{hi:.2f}':>10}{nn:>6}"
              f"{(RET[m,1]>0).mean()*100:9.1f}%/{RET[m,1].sum()/(100*nn):6.1f}%"
              f"{(RET[m,0]>0).mean()*100:9.1f}%/{RET[m,0].sum()/(100*nn):6.1f}%")

    print("\n═ 連続量: 2強度(g12小×g23帯)ごとのワイド1-2成績 ═")
    print(f"{'g23帯':>10}{'n':>6}{'ワイド1-2 的中/ROI':^22}{'馬連1-2 的中/ROI':^20}")
    base = g12a < 0.3
    for lo, hi in ((0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.9),(0.9,9)):
        m = base & (g23a >= lo) & (g23a < hi); nn = int(m.sum())
        if nn < 100: continue
        print(f"{f'{lo:.1f}-{hi:.1f}':>10}{nn:>6}"
              f"{(RET[m,2]>0).mean()*100:10.1f}%/{RET[m,2].sum()/(100*nn):6.1f}%"
              f"{(RET[m,3]>0).mean()*100:9.1f}%/{RET[m,3].sum()/(100*nn):6.1f}%")

    print("\n═ 2強なのに市場が2位を安く見ていない場合（2位オッズ帯で分解・ワイド1-2）═")
    m2 = (shape == "2強") & ~np.isnan(o2a)
    for lo, hi in ((1,3),(3,5),(5,8),(8,15),(15,999)):
        m = m2 & (o2a >= lo) & (o2a < hi); nn = int(m.sum())
        if nn < 50: continue
        print(f"  2位オッズ{lo}-{hi}倍: n{nn}  ワイド的中{(RET[m,2]>0).mean()*100:.1f}% "
              f"ROI {RET[m,2].sum()/(100*nn):.1f}%  馬連ROI {RET[m,3].sum()/(100*nn):.1f}%")
    json.dump({"note": "shape study raw counts in stdout"}, open("shape_study.json","w"))


if __name__ == "__main__":
    main()
