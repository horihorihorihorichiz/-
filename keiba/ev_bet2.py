# -*- coding: utf-8 -*-
"""期待払戻モデル 第2版：モデル得点と市場のズレを特徴量に入れる（2026-08-21）。

ev_bet.py（第1版）の結果と、そこで分かった抜け:
  ・オッズ帯＋40ルールだけで単勝ROIは ベタ買い70.3% → 選択97.6% まで上がったが、
    **在サンプル(MINE 89,326頭)でさえ100%を超えない**。過学習を許してなお届かない＝壁。
  ・null control（ルールをデタラメな馬のものに差し替え）が CONFIRM で104.5%を出した。
    → CONFIRMの173%は運。少点数の高ROIは全部これで説明がつく。
  ・**決定的な抜け: モデル自身の得点が特徴量に入っていなかった。**
    RULES.mdの結論は「控除率を超える道は市場の価格ズレを突く以外にない」。
    ズレ＝(モデルの評価) −(市場の評価)。片方が無ければズレは測れない。

第2版で足すもの（すべてレース内で正規化）:
  msc  : Ver.99.27素点のレース内zスコア
  mrk  : モデル順位（1位=0）／頭数
  gap  : 1位との得点差 ÷ レース内SD
  imp  : 市場の勝率（1/オッズをレース内で正規化）
  div  : ズレ = モデル勝率(softmax) − 市場勝率     ★これが本命
  divr : ズレの順位（レース内で何番目に「モデルが市場より高く買っている」か）

評価の作法（第1版で学んだこと）:
  ・**在サンプル(MINE)のROIを必ず先に見る**。ここで100%を超えないものは本物ではない。
  ・**同じ点数のnull controlを必ず並べる**。少点数の高ROIは全部ノイズ。
  ・点数500未満のセルは判定に使わない。
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B
import bonus_fit as F

EDGES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 25.0, 40.0, 70.0, 120.0, 1e9]
NB = len(EDGES) - 1
CACHE = "ev2_cache.npz"
RAWW = np.zeros(22); RAWW[:11] = 1.0


def band_of(o):
    for i in range(NB):
        if EDGES[i] <= o < EDGES[i + 1]:
            return i
    return NB - 1


def build():
    races = B.load()
    RAW = json.load(open(F.RAWP))
    RL = F.RL; J = len(RL)
    TIERS = [3, 4, 5, 6, 10]
    EXTRA = ["msc", "mrk", "gap", "imp", "div", "divr", "頭数z", "log(odds)"]
    names = ([f"帯{EDGES[i]:g}-{EDGES[i+1]:g}" for i in range(NB)] + F.RN
             + [f"tier{t}" for t in TIERS] + EXTRA)
    D = NB + J + len(TIERS) + len(EXTRA)

    rows = []
    for r in races:
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        tn = {int(k): float(v) for k, v in (pay.get("単勝") or {}).items()}
        if not pl:
            continue
        odds = r.get("odds") or {}
        oo = np.array([float(odds.get(str(x)) or odds.get(x) or 0) for x in r["nums"]])
        if (oo <= 0).any():
            continue
        n = len(r["nums"])
        s = r["Z22"] @ RAWW
        sd = s.std() or 1.0
        z = (s - s.mean()) / sd
        rank = np.empty(n); rank[np.argsort(-s)] = np.arange(n)
        gap = (s.max() - s) / sd
        imp = (1.0 / oo); imp = imp / imp.sum()
        p_m = np.exp(z - z.max()); p_m = p_m / p_m.sum()
        div = p_m - imp
        divr = np.empty(n); divr[np.argsort(-div)] = np.arange(n)

        rec_all = RAW.get(r["rid"], {})
        rr = dict(distance=r["distance"], surface=r["surface"])
        for i, num in enumerate(r["nums"]):
            v = np.zeros(D, np.float32)
            v[band_of(oo[i])] = 1.0
            rec = rec_all.get(str(num)) or rec_all.get(num)
            if rec:
                for j, (_, fn) in enumerate(RL):
                    try:
                        if fn(rec, rr):
                            v[NB + j] = 1.0
                    except Exception:
                        pass
            t = r.get("tier")
            if t in TIERS:
                v[NB + J + TIERS.index(t)] = 1.0
            k = NB + J + len(TIERS)
            v[k:k + 8] = [z[i], rank[i] / n, gap[i], imp[i], div[i], divr[i] / n,
                          (n - 12) / 4.0, np.log(oo[i])]
            rows.append((r["month"], oo[i], v, pl.get(num, 0.0), tn.get(num, 0.0)))

    mon = np.array([x[0] for x in rows])
    od = np.array([x[1] for x in rows])
    X = np.stack([x[2] for x in rows])
    yp = np.array([x[3] for x in rows]); yw = np.array([x[4] for x in rows])
    np.savez_compressed(CACHE, mon=mon, od=od, X=X, yp=yp, yw=yw,
                        names=np.array(names, dtype=object))
    return mon, od, X, yp, yw, names


def load_cache():
    if os.path.exists(CACHE):
        z = np.load(CACHE, allow_pickle=True)
        return (z["mon"], z["od"], z["X"], z["yp"], z["yw"], [str(x) for x in z["names"]])
    return build()


def ridge(X, y, lam=30.0):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def sweep(pred, y, M, V, C, cost=100.0, label=""):
    """点数を揃えて比較する。閾値でなく『上位N点』で切る（null controlと同点数にするため）。"""
    out = []
    for frac in (0.30, 0.15, 0.08, 0.04, 0.02, 0.01, 0.005):
        thr = np.quantile(pred[M], 1 - frac)
        line = {}
        for nm, msk in (("MINE", M), ("VALIDATE", V), ("CONFIRM", C)):
            sel = msk & (pred >= thr); n = int(sel.sum())
            line[nm] = (dict(n=n, hit=float((y[sel] > 0).mean() * 100),
                             roi=float(y[sel].sum() / (cost * n) * 100),
                             pl=float(y[sel].sum() - cost * n)) if n else None)
        out.append((frac, thr, line))
    return out


def show(res, tag):
    print(f"  {'上位':>5} {'MINE(在サンプル)':^34} {'VALIDATE':^34} {'CONFIRM':^34}")
    for frac, thr, line in res:
        s = f"  {frac*100:4.1f}% "
        for nm in ("MINE", "VALIDATE", "CONFIRM"):
            d = line[nm]
            s += (f"{d['n']:6d}点 的中{d['hit']:5.1f}% ROI{d['roi']:6.1f}% {d['pl']:+8.0f}円 "
                  if d else f"{'—':^34}")
        print(s)


def main():
    mon, od, X, yp, yw, names = load_cache()
    J = len(F.RN)
    M = mon <= '202602'; V = (mon > '202602') & (mon <= '202605'); C = mon > '202605'
    print(f"頭数: MINE {M.sum()} / VALIDATE {V.sum()} / CONFIRM {C.sum()}")
    print(f"特徴量 {X.shape[1]}本\n")

    out = {}
    for tag, y in (("複勝", yp), ("単勝", yw)):
        print("=" * 118)
        print(f"■ {tag}  （ベタ買い MINE {y[M].mean():.1f}円 = ROI {y[M].mean():.1f}%）")
        print("=" * 118)
        w = ridge(X[M], y[M]); pred = X @ w
        res = sweep(pred, y, M, V, C)
        print("  ▼ 本物のモデル")
        show(res, tag)

        # null control: 同じ手順・同じ点数。ルール列＋モデル得点系の列をシャッフル
        rs = np.random.RandomState(3)
        perm = rs.permutation(len(X))
        Xn = X.copy()
        Xn[:, NB:NB + J] = X[perm, NB:NB + J]
        k = NB + J + 5
        Xn[:, k:k + 6] = X[perm, k:k + 6]      # msc/mrk/gap/imp/div/divr もデタラメに
        wn = ridge(Xn[M], y[M]); pn = Xn @ wn
        print("  ▼ null control（帯とオッズだけ本物、他はデタラメな馬のもの）")
        show(sweep(pn, y, M, V, C), tag)

        # 効いている特徴（上位/下位）
        idx = np.argsort(-np.abs(w))[:14]
        print("  ▼ 係数の大きい特徴（円）")
        for i in idx:
            print(f"      {w[i]:+8.2f}  {names[i]}")
        out[tag] = dict(w=[round(float(x), 4) for x in w], names=names,
                        res=[(f, float(t), l) for f, t, l in res])
        print()

    json.dump(out, open("ev_bet2.json", "w"), ensure_ascii=False, indent=1)
    print("saved ev_bet2.json")


if __name__ == "__main__":
    main()
