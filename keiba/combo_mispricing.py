# -*- coding: utf-8 -*-
"""三連複・ワイドの「市場の値付けのズレ」を、モデル抜きで直接測る（2026-08-21）。

なぜこれをやるか（今日ここまでの実測から）:
  ・単勝オッズだけを土台に、40の加点ルール＋Ver.99.27の得点＋市場とのズレを全部入れて
    1頭ごとの期待払戻を回帰したが、**在サンプル(MINE 89,326頭)でさえROIは複勝89.5%/単勝94.3%止まり**。
    過学習を許してなお100%に届かない＝単勝・複勝には突く隙がない。
  ・一方で分かったのは「Harville近似は大穴の3着内率を構造的に過小評価する」こと
    （lift 1.535 が実払戻では消えた件）。
    → **単勝オッズから合成した三連複の理論確率も、同じ癖で歪んでいるはず。**
       日本の馬券市場は単勝・複勝ほど三連複を効率的に値付けできていない可能性がある。
       ここは「市場 vs 市場」の比較なので、モデルの当たり外れとは無関係に測れる。

測ること:
  各レースで単勝オッズ→勝率p_iを作り、Harvilleで全C(n,3)通りの三連複確率を合成。
  合成確率の帯ごとに「その帯の組を全部100円ずつ買ったときの実ROI」を出す。
  控除率25.0%なので、歪みが無ければどの帯も75%付近に並ぶはず。
  75%から大きく外れる帯があれば、そこが市場の値付けのズレ。

ワイドも同様（控除率23.3%）。
"""
import json, os, sys, itertools, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEDGER = "bsd16_races.jsonl"
# 合成確率の帯（実オッズに直すと 1/p。0.02 なら 50倍相当）
PEDGES = [0.0, 0.0005, 0.001, 0.002, 0.004, 0.007, 0.012, 0.02, 0.035,
          0.06, 0.10, 0.16, 0.25, 1.0]


def pidx(p):
    for i in range(len(PEDGES) - 1):
        if PEDGES[i] <= p < PEDGES[i + 1]:
            return i
    return len(PEDGES) - 2


def harville_top3(p):
    """全C(n,3)の『3頭とも3着以内』確率。順序6通りを合算。"""
    n = len(p)
    out = {}
    for a, b, c in itertools.combinations(range(n), 3):
        s = 0.0
        for i, j, k in itertools.permutations((a, b, c)):
            d1 = 1.0 - p[i]
            if d1 <= 1e-9:
                continue
            d2 = d1 - p[j]
            if d2 <= 1e-9:
                continue
            s += p[i] * (p[j] / d1) * (p[k] / d2)
        out[(a, b, c)] = s
    return out


def harville_top2(p):
    """『2頭とも3着以内』確率（ワイド）。= 1 - P(両方外) - P(片方だけ)... は面倒なので
       3頭目を全部積み上げる形で近似せず、順序で直接計算する。"""
    n = len(p)
    out = collections.defaultdict(float)
    # 3着以内の並び (i,j,k) を全列挙するとO(n^3)。n<=18なので許容。
    for i in range(n):
        d1 = 1.0 - p[i]
        if d1 <= 1e-9:
            continue
        for j in range(n):
            if j == i:
                continue
            d2 = d1 - p[j]
            if d2 <= 1e-9:
                continue
            pij = p[i] * p[j] / d1
            for k in range(n):
                if k == i or k == j:
                    continue
                q = pij * p[k] / d2
                a, b, c = sorted((i, j, k))
                out[(a, b)] += q; out[(a, c)] += q; out[(b, c)] += q
    return out


def main():
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 9
    # [組数, 的中, 払戻] を 帯 × 期間 で
    SEGS = ("MINE", "VALIDATE", "CONFIRM")
    NB = len(PEDGES) - 1
    S3 = {s: np.zeros((NB, 3)) for s in SEGS}
    SW = {s: np.zeros((NB, 3)) for s in SEGS}
    nr = 0
    for line in open(LEDGER):
        r = json.loads(line)
        if nr >= lim:
            break
        mon = r["month"]
        seg = "MINE" if mon <= '202602' else ("VALIDATE" if mon <= '202605' else "CONFIRM")
        odds = r.get("odds") or {}
        nums = r["nums"]
        oo = []
        ok = True
        for x in nums:
            v = odds.get(str(x)) or odds.get(x)
            if not v:
                ok = False; break
            oo.append(float(v))
        if not ok or len(nums) < 6:
            continue
        pay = r.get("payout") or {}
        s3 = {k: float(v) for k, v in (pay.get("三連複") or {}).items()}
        wd = {k: float(v) for k, v in (pay.get("ワイド") or {}).items()}
        if not s3:
            continue
        nr += 1
        p = 1.0 / np.array(oo); p = p / p.sum()

        H3 = harville_top3(p)
        for (a, b, c), q in H3.items():
            k = pidx(q)
            key = "-".join(str(x) for x in sorted((nums[a], nums[b], nums[c])))
            v = s3.get(key, 0.0)
            S3[seg][k] += [1, 1 if v else 0, v]

        if wd:
            H2 = harville_top2(p)
            for (a, b), q in H2.items():
                k = pidx(q)
                x, y = nums[a], nums[b]
                v = wd.get(f"{min(x,y)}-{max(x,y)}") or wd.get(f"{max(x,y)}-{min(x,y)}") or 0.0
                SW[seg][k] += [1, 1 if v else 0, v]

    def dump(tag, S, take):
        print("=" * 104)
        print(f"■ {tag}（控除率{take}% → 歪みが無ければどの帯も {100-take:.1f}% 付近に並ぶはず）")
        print("=" * 104)
        print(f"{'合成オッズ帯':>16} {'MINE':^26} {'VALIDATE':^26} {'CONFIRM':^26}")
        tot = {s: S[s].sum(0) for s in SEGS}
        for i in range(NB):
            lo, hi = PEDGES[i], PEDGES[i + 1]
            lab = f"{1/hi if hi else 0:.0f}〜{1/lo if lo else 99999:.0f}倍" if lo > 0 else f"{1/hi:.0f}倍〜"
            line = f"{lab:>16} "
            skip = True
            for s in SEGS:
                n, h, ret = S[s][i]
                if n >= 300:
                    skip = False
                    line += f"{int(n):8d}組 的中{h/n*100:5.2f}% ROI{ret/(100*n)*100:6.1f}% "
                else:
                    line += f"{'—':^26} "
            if not skip:
                print(line)
        line = f"{'【全帯】':>16} "
        for s in SEGS:
            n, h, ret = tot[s]
            line += f"{int(n):8d}組 的中{h/n*100:5.2f}% ROI{ret/(100*n)*100:6.1f}% " if n else ""
        print(line)
        print()

    print(f"対象レース {nr}R\n")
    dump("三連複（単勝オッズからHarvilleで合成）", S3, 25.0)
    dump("ワイド（単勝オッズからHarvilleで合成）", SW, 23.3)
    json.dump({"races": nr, "pedges": PEDGES,
               "trio": {s: S3[s].tolist() for s in SEGS},
               "wide": {s: SW[s].tolist() for s in SEGS}},
              open("combo_mispricing.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
