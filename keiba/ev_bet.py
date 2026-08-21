# -*- coding: utf-8 -*-
"""1頭ごとの複勝/単勝の期待払戻を直接予測して、100%を超える馬だけ買う（2026-08-21）。

なぜ設計を変えたか（odds_band.py の実測から）:
  ① 複勝ベタ買いROIはオッズ帯で 98.1%(1.0〜1.5) 〜 47.0%(120倍〜) まで動く。
     控除率の理論線79.6%を大きく上回る帯（1.0〜7.0倍）と、大きく下回る帯（70倍〜）がある。
     = 人気馬-穴馬バイアスが巨大。まずこの地形を土台にする。
  ② オッズ帯を揃えた残差で見ると「直近3走すべて着外」が +6.49pt。
     生ROIが低いのは大穴だからで、同じ値段の馬と比べれば市場は負け馬を安く売っている。

  → 馬を並べ替える（順位モデル）のをやめる。
     「この馬の複勝100円は平均何円返ってくるか」を直接回帰し、100円を超える馬だけ買う。
     これは控除率を超える唯一の道（＝市場の価格ズレを突く）そのもの。

モデル: E[払戻] = オッズ帯ダミー（地形） + ルールダミー（残差） + 頭数/クラス
  線形回帰（解釈できる＝各項が「何円」か分かる）と LightGBM（非線形の確認）の両方。
検証: MINEで係数と閾値を決め、VALIDATE/CONFIRMは各1回だけ測る。
偽陽性対策: ルール列をレース内でシャッフルした偽データで同じ手順（null control）。
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B
import bonus_fit as F

# オッズ帯（odds_band.py と同じ切り方）
EDGES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 25.0, 40.0, 70.0, 120.0, 1e9]
NB = len(EDGES) - 1


def band_of(o):
    for i in range(NB):
        if EDGES[i] <= o < EDGES[i + 1]:
            return i
    return NB - 1


def build():
    """1行=1頭。X=[帯ダミー(14) + ルール(40) + 頭数z + tierダミー] , y=複勝払戻, y2=単勝払戻"""
    races = B.load()
    RAW = json.load(open(F.RAWP))
    RL = F.RL; J = len(RL)
    TIERS = [3, 4, 5, 6, 10]
    rows = []
    for r in races:
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        tn = {int(k): float(v) for k, v in (pay.get("単勝") or {}).items()}
        if not pl:
            continue
        rec_all = RAW.get(r["rid"], {})
        rr = dict(distance=r["distance"], surface=r["surface"])
        odds = r.get("odds") or {}
        n = len(r["nums"])
        for num in r["nums"]:
            o = odds.get(str(num)) or odds.get(num)
            if not o:
                continue
            o = float(o)
            v = np.zeros(NB + J + 1 + len(TIERS) + 1, np.float32)
            v[band_of(o)] = 1.0
            rec = rec_all.get(str(num)) or rec_all.get(num)
            if rec:
                for j, (_, fn) in enumerate(RL):
                    try:
                        if fn(rec, rr):
                            v[NB + j] = 1.0
                    except Exception:
                        pass
            v[NB + J] = (n - 12) / 4.0
            t = r.get("tier")
            if t in TIERS:
                v[NB + J + 1 + TIERS.index(t)] = 1.0
            v[-1] = np.log(o)
            rows.append((r["month"], r["rid"], num, o, v,
                         pl.get(num, 0.0), tn.get(num, 0.0)))
    return rows, TIERS


def fit_ridge(X, y, lam=30.0):
    """リッジ回帰。切片なし（帯ダミーが飽和しているので不要）。"""
    A = X.T @ X + lam * np.eye(X.shape[1])
    return np.linalg.solve(A, X.T @ y)


def report(name, sel, pay, cost=100.0):
    n = int(sel.sum())
    if n == 0:
        return f"{name:10s} 買い0点"
    ret = pay[sel].sum()
    hit = (pay[sel] > 0).mean() * 100
    return (f"{name:10s} {n:6d}点 的中{hit:5.1f}% ROI{ret/(cost*n)*100:6.1f}% "
            f"収支{ret-cost*n:+10.0f}円")


def main():
    rows, TIERS = build()
    mon = np.array([r[0] for r in rows])
    X = np.stack([r[4] for r in rows])
    yp = np.array([r[5] for r in rows])       # 複勝払戻(円, 外れ=0)
    yw = np.array([r[6] for r in rows])       # 単勝払戻
    od = np.array([r[3] for r in rows])
    names = ([f"帯{EDGES[i]:g}-{EDGES[i+1]:g}" for i in range(NB)] + F.RN
             + ["頭数z"] + [f"tier{t}" for t in TIERS] + ["log(odds)"])

    M = mon <= '202602'; V = (mon > '202602') & (mon <= '202605'); C = mon > '202605'
    print(f"頭数: MINE {M.sum()} / VALIDATE {V.sum()} / CONFIRM {C.sum()}\n")

    out = {}
    for tag, y, cost in (("複勝", yp, 100.0), ("単勝", yw, 100.0)):
        print("=" * 92)
        print(f"■ {tag}: 1頭100円の期待払戻を回帰して、閾値を超えた馬だけ買う")
        print("=" * 92)
        w = fit_ridge(X[M], y[M])
        pred = X @ w
        print(f"  MINE平均予測 {pred[M].mean():.1f}円 / 実績 {y[M].mean():.1f}円")

        # 帯の地形とルール残差（円）を表示
        print(f"\n  --- オッズ帯の基準（買って平均何円返るか）---")
        for i in range(NB):
            k = M & (X[:, i] == 1)
            if k.sum() < 50:
                continue
            print(f"    {EDGES[i]:6.1f}〜{EDGES[i+1]:<6.1f} 基準{w[i]:7.1f}円  "
                  f"実績{y[k].mean():6.1f}円  n={int(k.sum()):6d}")
        ridx = np.argsort(-w[NB:NB + len(F.RN)])
        print(f"\n  --- 加点/減点（帯を揃えた後の上乗せ、円）上位8/下位5 ---")
        for j in list(ridx[:8]) + list(ridx[-5:]):
            print(f"    {w[NB+j]:+7.2f}円  {F.RN[j]}")

        # 閾値をMINEで決める（100円=損益分岐）
        res = {"w": [round(float(x), 4) for x in w], "names": names, "thr": {}}
        print(f"\n  --- 予測閾値ごとの成績（MINEで決め、他は1回だけ確認）---")
        print(f"    {'閾値':>6}  {'MINE':^42} {'VALIDATE':^42} {'CONFIRM':^42}")
        for thr in (95, 100, 105, 110, 120, 140):
            line = f"    {thr:>4}円  "
            rec = {}
            for nm, msk in (("MINE", M), ("VALIDATE", V), ("CONFIRM", C)):
                sel = msk & (pred >= thr)
                n = int(sel.sum())
                if n:
                    ret = y[sel].sum()
                    rec[nm] = dict(n=n, hit=float((y[sel] > 0).mean() * 100),
                                   roi=float(ret / (cost * n) * 100), pl=float(ret - cost * n))
                    line += (f"{n:6d}点 的中{rec[nm]['hit']:5.1f}% "
                             f"ROI{rec[nm]['roi']:6.1f}% {rec[nm]['pl']:+9.0f}円 ")
                else:
                    rec[nm] = None; line += f"{'買い0点':^42}"
            res["thr"][thr] = rec
            print(line)

        # null control: ルール列をシャッフル（帯とオッズはそのまま）
        rs = np.random.RandomState(3)
        Xn = X.copy()
        perm = rs.permutation(len(X))
        Xn[:, NB:NB + len(F.RN)] = X[perm, NB:NB + len(F.RN)]
        wn = fit_ridge(Xn[M], y[M]); pn = Xn @ wn
        print(f"\n  --- null control（ルールを無関係な馬のものに差し替えて同じ手順）---")
        for thr in (100, 110):
            for nm, msk in (("MINE", M), ("CONFIRM", C)):
                sel = msk & (pn >= thr); n = int(sel.sum())
                if n:
                    print(f"    偽 {thr}円 {nm:9s} {n:6d}点 ROI{y[sel].sum()/(cost*n)*100:6.1f}%")
        out[tag] = res
        print()

    json.dump(out, open("ev_bet.json", "w"), ensure_ascii=False, indent=1)
    print("saved ev_bet.json")


if __name__ == "__main__":
    main()
