# -*- coding: utf-8 -*-
"""オッズ帯別ROIと、「ルールはオッズ以上の情報を持つか」の分離測定（2026-08-21）。

分かったこと(rule_roi.py)の続き:
  40ルールの複勝ベタ買いROIの並びが、平均単勝オッズの並びとほぼ一致していた。
  = ルール固有の情報ではなく「人気馬を多く含むルールほどROIが高い」だけかもしれない。
  これを分離しないと、加点方式に意味があるのか判定できない。

測ること:
 (1) オッズ帯別の複勝/単勝ベタ買いROI（人気馬-穴馬バイアスの形と、100%を超える帯があるか）
 (2) 各ルールの「同じオッズ帯の馬と比べた」複勝ROI差 = 残差ROI
     → これが+ならオッズ以上の情報。ゼロ付近ならルールはオッズの言い換えに過ぎない。
 (3) ルールROI ~ log(平均オッズ) の回帰の決定係数 R^2
     → 1に近いほど「全部オッズで説明できる」
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B
import bonus_fit as F

BANDS = [(0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 4.0), (4.0, 5.0),
         (5.0, 7.0), (7.0, 10.0), (10.0, 15.0), (15.0, 25.0), (25.0, 40.0),
         (40.0, 70.0), (70.0, 120.0), (120.0, 1e9)]


def bidx(o):
    for i, (a, b) in enumerate(BANDS):
        if a <= o < b:
            return i
    return len(BANDS) - 1


def main():
    races = B.load()
    RAW = json.load(open(F.RAWP))
    RL = F.RL; J = len(RL)
    NB = len(BANDS)

    # 帯別: [n, 複的中, 複払戻, 単的中, 単払戻]
    band = np.zeros((NB, 5))
    # ルール×帯
    rb = np.zeros((J, NB, 3))    # [n, 複的中, 複払戻]

    for r in races:
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        tn = {int(k): float(v) for k, v in (pay.get("単勝") or {}).items()}
        if not pl:
            continue
        rec_all = RAW.get(r["rid"], {})
        rr = dict(distance=r["distance"], surface=r["surface"])
        odds = r.get("odds") or {}
        for num in r["nums"]:
            o = odds.get(str(num)) or odds.get(num)
            if not o:
                continue
            o = float(o)
            k = bidx(o)
            hp = pl.get(num, 0.0); hw = tn.get(num, 0.0)
            band[k] += [1, 1 if hp else 0, hp, 1 if hw else 0, hw]
            rec = rec_all.get(str(num)) or rec_all.get(num)
            if not rec:
                continue
            for j, (_, fn) in enumerate(RL):
                try:
                    if fn(rec, rr):
                        rb[j, k] += [1, 1 if hp else 0, hp]
                except Exception:
                    pass

    print("=" * 78)
    print("(1) オッズ帯別 ベタ買いROI（100円ずつ全馬に賭けた場合）")
    print("=" * 78)
    print(f"{'単勝オッズ帯':>14} {'頭数':>8} {'複勝的中':>8} {'複勝ROI':>8} {'単勝的中':>8} {'単勝ROI':>8}")
    for i, (a, b) in enumerate(BANDS):
        n = band[i, 0]
        if n < 50:
            continue
        lab = f"{a:.1f}〜{b:.1f}" if b < 1e8 else f"{a:.0f}〜"
        print(f"{lab:>14} {int(n):8d} {band[i,1]/n*100:7.1f}% {band[i,2]/(100*n)*100:7.1f}% "
              f"{band[i,3]/n*100:7.1f}% {band[i,4]/(100*n)*100:7.1f}%")

    # 帯ごとの基準複勝ROI
    base_roi = np.where(band[:, 0] > 0, band[:, 2] / np.maximum(100 * band[:, 0], 1), 0)

    print()
    print("=" * 78)
    print("(2) 残差ROI: 同じオッズ帯の馬と比べて、そのルールは何pt上か")
    print("    （+ならオッズ以上の情報。0付近ならルール＝オッズの言い換え）")
    print("=" * 78)
    rows = []
    for j, nm in enumerate(F.RN):
        n = rb[j, :, 0].sum()
        if n < 500:
            continue
        actual = rb[j, :, 2].sum() / (100 * n)
        expect = (rb[j, :, 0] * base_roi).sum() / n      # 帯構成をそろえた期待ROI
        rows.append((actual - expect, nm, int(n), actual * 100, expect * 100))
    print(f"{'残差pt':>7} {'実ROI':>7} {'帯期待':>7} {'n':>8}   ルール")
    for d, nm, n, a, e in sorted(rows, reverse=True):
        print(f"{d*100:+7.2f} {a:7.1f} {e:7.1f} {n:8d}   {nm}")

    # (3) ルールROI ~ log(平均オッズ) の回帰
    RR = json.load(open("rule_roi.json"))
    x = []; y = []
    for nm, d in RR["rules"].items():
        if d["avgodds"] > 0:
            x.append(np.log(d["avgodds"])); y.append(d["plroi"])
    x = np.array(x); y = np.array(y)
    A = np.vstack([x, np.ones_like(x)]).T
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print()
    print("=" * 78)
    print(f"(3) 40ルールの複勝ROI を log(平均単勝オッズ) だけで説明した回帰")
    print(f"    複勝ROI = {coef[0]:.2f} × log(平均オッズ) + {coef[1]:.1f}      R^2 = {r2:.3f}")
    print(f"    → R^2が1に近いほど『ルールはオッズの言い換えに過ぎない』")
    print("=" * 78)

    json.dump({"band": band.tolist(), "bands": BANDS,
               "resid": [(nm, d, n) for d, nm, n, a, e in sorted(rows, reverse=True)],
               "r2": float(r2), "coef": coef.tolist()},
              open("odds_band.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
