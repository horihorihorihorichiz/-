# -*- coding: utf-8 -*-
"""G1候補『ダM×三連複1位軸→2-5位流し6点』の再判定（2026-08-22・事前凍結）。

判定基準（実行前に凍結。結果を見てからの変更は全破棄）:
  A. 年別ROI(2022/2023/2024/2025/2026)の過半数が100%超
  B. 全期間プールのブートストラップ2000回で P(ROI>100%) ≥ 0.8
  C. null(順位乱数×10)の同条件ROIの最大を、実データのプールROIが上回る
  3つすべて満たしたら G1発火=紙上運用へ昇格。1つでも欠けたら凍結継続。
順位はhori52(検証済み2層)。
"""
import json, os, sys, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

def trio6_ret(order, pay):
    tri = pay.get("三連複") or {}
    a = order[0]; t = 0.0
    for c1, c2 in itertools.combinations(order[1:5], 2):
        v = tri.get("-".join(str(x) for x in sorted((a, c1, c2))))
        if v: t += float(v)
    return t

def main():
    races = V.load_races(); V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    dam = []
    for r in races:
        if f"{r['surface']}{r['dist_cat']}" != "ダM":
            continue
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        order = [r["nums"][k] for k in o]
        dam.append((r["month"][:4], trio6_ret(order, r.get("payout") or {}), r))
    n = len(dam)
    print(f"ダM 標本 {n}R")
    rets = np.array([x[1] for x in dam])
    pooled = rets.sum() / (600 * n) * 100
    print(f"プールROI: {pooled:.1f}%  的中率 {(rets>0).mean()*100:.1f}%")

    print("\nA. 年別ROI:")
    ok_years = 0; total_years = 0
    for y in sorted({x[0] for x in dam}):
        m = [x[1] for x in dam if x[0] == y]
        roi = sum(m) / (600 * len(m)) * 100
        total_years += 1; ok_years += roi > 100
        print(f"  {y}: {roi:6.1f}% (n={len(m)})")
    passA = ok_years > total_years / 2
    print(f"  → 過半数100%超: {ok_years}/{total_years}  {'✓' if passA else '✗'}")

    rs = np.random.RandomState(101)
    boots = []
    for _ in range(2000):
        idx = rs.randint(0, n, n)
        boots.append(rets[idx].sum() / (600 * n) * 100)
    p_plus = float(np.mean(np.array(boots) > 100))
    passB = p_plus >= 0.8
    print(f"\nB. ブートストラップ2000回: P(ROI>100%) = {p_plus:.3f}  {'✓' if passB else '✗'}")

    null_rois = []
    for t in range(10):
        tot = 0.0
        for _, _, r in dam:
            o = list(r["nums"]); rs.shuffle(o)
            tot += trio6_ret(o, r.get("payout") or {})
        null_rois.append(tot / (600 * n) * 100)
    passC = pooled > max(null_rois)
    print(f"C. null(順位乱数×10): 平均{np.mean(null_rois):.1f}% 最大{max(null_rois):.1f}%  "
          f"実データ{pooled:.1f}%  {'✓' if passC else '✗'}")

    verdict = passA and passB and passC
    print(f"\n判定: {'★G1昇格=紙上運用へ' if verdict else '凍結継続(発火させない)'}")
    json.dump(dict(n=n, pooled=pooled, hit=float((rets>0).mean()*100),
                   passA=bool(passA), passB=bool(passB), passC=bool(passC),
                   p_plus=p_plus, null=null_rois, verdict=bool(verdict)),
              open("dam_retest.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
