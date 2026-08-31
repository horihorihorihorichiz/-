# -*- coding: utf-8 -*-
"""PWin較正の検証（2026-08-23・外部調査報告の「段階0最優先項目」を実装）。

問い: システムが出す勝率PWinは、実際の勝率と一致しているか。
     一致していない(較正がずれている)状態でケリー配分を使うと、勝率の過大評価が
     そのまま賭け過ぎ→破産に直結する。だから実弾より先にここを測る。

出すもの:
  ① 信頼度図(数値版): PWin帯ごとの [予測平均 vs 実測勝率 vs n]
  ② Brierスコア: 確率予測の二乗誤差(低いほど良い)。比較対象=「全馬に1/頭数」の素朴予測
  ③ 較正誤差ECE(重み付き平均絶対ずれ)と、系統的な過大/過小の方向
  ④ 等調整回帰(isotonic)で補正した場合にBrier/ECEがどれだけ改善するか
     ※isotonicはMINEで学習しVAL/CONFで評価(自己採点を避ける)

usage: python3 calib_check.py
"""
import json, os, sys, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
from verify_export import scorer_from_artifact


def pwin_from_scores(s):
    """sim_rank.p_from_scores と同一仕様(softmax→30%クリップ→再正規化)のベクトル版。"""
    e = np.exp(s - s.max())
    p = e / e.sum()
    for _ in range(len(p)):
        over = p > 0.30 + 1e-12
        if not over.any():
            break
        rest = ~over
        room = 1.0 - 0.30 * over.sum()
        sm = p[rest].sum()
        p[over] = 0.30
        if sm > 0:
            p[rest] = p[rest] / sm * room
    return p


def isotonic(x, y, w):
    """重み付きPAVA(pool adjacent violators)。xの昇順に単調な当てはめ値を返す。"""
    order = np.argsort(x)
    xs, ys, ws = x[order], y[order], w[order]
    val = list(ys); wt = list(ws); idx = [[i] for i in range(len(ys))]
    i = 0
    while i < len(val) - 1:
        if val[i] <= val[i + 1] + 1e-15:
            i += 1
            continue
        nv = (val[i] * wt[i] + val[i + 1] * wt[i + 1]) / (wt[i] + wt[i + 1])
        val[i] = nv; wt[i] += wt[i + 1]; idx[i] += idx[i + 1]
        del val[i + 1], wt[i + 1], idx[i + 1]
        if i > 0:
            i -= 1
    fit = np.zeros(len(ys))
    for v, ii in zip(val, idx):
        fit[ii] = v
    knots_x = xs.copy(); knots_y = fit
    return knots_x, knots_y


def apply_iso(kx, ky, x):
    return np.interp(x, kx, ky, left=ky[0], right=ky[-1])


def report(name, p, y):
    """帯別の信頼度・Brier・ECEを出す。"""
    bins = [0, .02, .05, .08, .12, .18, .25, .35, 1.01]
    print(f"\n═ {name}（n={len(p):,}頭）═")
    print(f"{'PWin帯':>12}{'n':>8}{'予測平均':>10}{'実測勝率':>10}{'ずれ':>9}")
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() < 30:
            continue
        pm, ym = p[m].mean(), y[m].mean()
        ece += m.sum() / len(p) * abs(pm - ym)
        flag = "過大" if pm > ym + 0.005 else ("過小" if ym > pm + 0.005 else "一致")
        print(f"{f'{lo:.0%}-{hi:.0%}':>12}{m.sum():>8,}{pm:>9.1%}{ym:>10.1%}"
              f"{pm-ym:>+8.1%} {flag}")
    brier = float(np.mean((p - y) ** 2))
    print(f"  Brier {brier:.5f} / ECE {ece:.4f}")
    return brier, ece


def main():
    races = V.load_races()
    V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    P, Y, SEG, NAIVE = [], [], [], []
    for r in races:
        s = r["Z16"] @ wfn(r)
        p = pwin_from_scores(s)
        # ★注意: r["top3"] は馬番ではなく nums のインデックス(0始まり)。
        #   ここを馬番と誤ると全帯が base rate に潰れて「較正が全く効いていない」偽の絵が出る。
        y = np.zeros(len(r["nums"]))
        y[r["top3"][0]] = 1.0
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        P.append(p); Y.append(y); SEG.append(np.full(len(p), seg))
        NAIVE.append(np.full(len(p), 1.0 / len(p)))
    P = np.concatenate(P); Y = np.concatenate(Y)
    SEG = np.concatenate(SEG); NAIVE = np.concatenate(NAIVE)
    print(f"対象 {len(races):,}レース / {len(P):,}頭")

    nb = float(np.mean((NAIVE - Y) ** 2))
    print(f"\n素朴予測(全馬1/頭数)のBrier: {nb:.5f}  ←これを下回れば情報がある")

    b_all, e_all = report("全期間・生のPWin", P, Y)
    print(f"  → 素朴比 {(nb-b_all)/nb*100:+.1f}% 改善")
    for si, nm in ((1, "VALIDATE"), (2, "CONFIRM")):
        m = SEG == si
        report(f"{nm}・生のPWin", P[m], Y[m])

    # 等調整回帰: MINEで学習 → VAL/CONFで評価（自己採点を避ける）
    mine = SEG == 0
    kx, ky = isotonic(P[mine], Y[mine], np.ones(mine.sum()))
    print("\n" + "=" * 60)
    print("等調整回帰(MINEで学習)を当てた場合の未知2期間:")
    for si, nm in ((1, "VALIDATE"), (2, "CONFIRM")):
        m = SEG == si
        praw, y = P[m], Y[m]
        pcal = apply_iso(kx, ky, praw)
        pcal = np.clip(pcal, 1e-6, 1 - 1e-6)
        b0 = float(np.mean((praw - y) ** 2)); b1 = float(np.mean((pcal - y) ** 2))
        print(f"  {nm}: Brier 生{b0:.5f} → 補正{b1:.5f} ({(b0-b1)/b0*100:+.2f}%)")
    json.dump({"brier_raw": b_all, "ece_raw": e_all, "brier_naive": nb},
              open("calib_check.json", "w"))
    print("\nsaved calib_check.json")
    print("判定基準: ずれが系統的(同じ方向に連続)なら較正不良＝ケリー封印。"
          "帯ごとのずれが±1pt以内なら実用上OK。")


if __name__ == "__main__":
    main()
