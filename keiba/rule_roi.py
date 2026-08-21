# -*- coding: utf-8 -*-
"""加点ルールごとの「実払戻ベタ買いROI」（2026-08-21）。

なぜこれを測るか:
  前回測った lift = 実際の3着内率 ÷ 市場想定3着内率 は、
  市場想定を単勝オッズ→Harville近似で作っている。Harvilleは**大穴の3着内率を構造的に
  過小評価する**ので、「直近3走着外 lift 1.535」が本物の妙味なのか近似の癖なのか区別できない。
  → 実際の複勝・ワイド払戻でベタ買いすれば一発で分かる。
     控除率は複勝20.4% → 妙味ゼロなら ROI≈79.6%。それを超えたルールだけが本物。

出力: ルールごとに 発火数 / 複勝的中率 / 複勝ROI / 平均オッズ帯 / 単勝ROI
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B
import bonus_fit as F


def main():
    races = B.load()
    RAW = json.load(open(F.RAWP))
    RL = F.RL
    J = len(RL)

    # 集計器: [発火, 複勝的中, 複勝払戻, 単勝的中, 単勝払戻, オッズ合計]
    A = np.zeros((J, 6))
    # 期間別（MINEで見つけてVAL/CONFで確認するため）
    per = {k: np.zeros((J, 6)) for k in ("MINE", "VALIDATE", "CONFIRM")}
    tot = np.zeros(6)

    for r in races:
        m = r["month"]
        seg = "MINE" if m <= '202602' else ("VALIDATE" if m <= '202605' else "CONFIRM")
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        tn = {int(k): float(v) for k, v in (pay.get("単勝") or {}).items()}
        if not pl:
            continue
        rec_all = RAW.get(r["rid"], {})
        rr = dict(distance=r["distance"], surface=r["surface"])
        odds = r.get("odds") or {}
        for i, num in enumerate(r["nums"]):
            rec = rec_all.get(str(num)) or rec_all.get(num)
            if not rec:
                continue
            o = float(odds.get(str(num)) or odds.get(num) or 0) or np.nan
            hitp = pl.get(num, 0.0); hitw = tn.get(num, 0.0)
            row = np.array([1.0, 1.0 if hitp else 0.0, hitp, 1.0 if hitw else 0.0, hitw,
                            o if o == o else 0.0])
            tot += row
            for j, (_, fn) in enumerate(RL):
                try:
                    if fn(rec, rr):
                        A[j] += row
                        per[seg][j] += row
                except Exception:
                    pass

    def fmt(v):
        n = v[0]
        if n < 30:
            return None
        return dict(n=int(n), plhit=v[1] / n * 100, plroi=v[2] / (100 * n) * 100,
                    wnhit=v[3] / n * 100, wnroi=v[4] / (100 * n) * 100,
                    avgodds=v[5] / n)

    out = {"total": fmt(tot), "rules": {}}
    rows = []
    for j, nm in enumerate(F.RN):
        d = fmt(A[j])
        if not d:
            continue
        d["seg"] = {k: fmt(per[k][j]) for k in per}
        out["rules"][nm] = d
        rows.append((d["plroi"], nm, d))

    print(f"{'複ROI':>7} {'複的中':>6} {'単ROI':>7} {'平均単勝':>8} {'n':>8}   ルール")
    print(f"{tot[2]/(100*tot[0])*100:7.1f} {tot[1]/tot[0]*100:6.1f} "
          f"{tot[4]/(100*tot[0])*100:7.1f} {tot[5]/tot[0]:8.1f} {int(tot[0]):8d}   【全馬】")
    print("-" * 90)
    for roi, nm, d in sorted(rows, reverse=True):
        s = d["seg"]
        tag = ""
        if all(s[k] for k in s):
            tag = f"  [M{s['MINE']['plroi']:.0f}/V{s['VALIDATE']['plroi']:.0f}/C{s['CONFIRM']['plroi']:.0f}]"
        print(f"{d['plroi']:7.1f} {d['plhit']:6.1f} {d['wnroi']:7.1f} {d['avgodds']:8.1f} "
              f"{d['n']:8d}   {nm}{tag}")

    json.dump(out, open("rule_roi.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved rule_roi.json", file=sys.stderr)


if __name__ == "__main__":
    main()
