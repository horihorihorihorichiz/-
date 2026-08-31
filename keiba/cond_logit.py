# -*- coding: utf-8 -*-
"""エッジの有無を1本の検定で確定させる（2026-08-23・外部助言の最優先項目）。

問い: 堀川システムのPWinは、市場（単勝オッズ）が知らないことを知っているか。
     それとも市場の再現装置にすぎないか。較正の合格はこの問いに答えない
     （オッズを確率に直しただけの予測でも較正は満点になる）。

方法: Benter(1994)と同じ二段階の形。レース内の条件付きロジット（McFadden）で
      勝ち馬を説明する:
          P(i勝つ) = exp(β1·log p_model_i + β2·log p_market_i) / Σ_j exp(...)
      レース内定数は打ち消えるので切片は不要。
  β2≈1, β1≈0  → システムは市場の写し。回収60%はこれで説明がつく。
  β1が有意に正 → 市場が知らない情報を持っている。そこだけが唯一のエッジ。

出すもの:
  ① MINEで推定した β1/β2 と標準誤差・t値（規律R5: ハードルはt>3.0）
  ② VAL/CONFでの対数尤度比較（市場のみモデル vs 両方モデル）＝未知データでの上乗せ
  ③ 市場オッズ帯ごとの較正（全頭平均だと大穴帯の自明な予測が重みを占めるため）
  ④ 高確率帯(PWin25-35%)のずれの期間別安定性（符号が一貫するか）

usage: python3 cond_logit.py
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
from verify_export import scorer_from_artifact
from calib_check import pwin_from_scores

EPS = 1e-9


def build(races, wfn):
    """レースごとに (X[n,2], 勝者index, メタ) を作る。"""
    out = []
    for r in races:
        od = r.get("odds") or {}
        o = np.array([float(od.get(n) or 0) for n in r["nums"]])
        if (o <= 1.0).any():           # オッズ欠損レースは除外（推定を壊すため）
            continue
        s = r["Z16"] @ wfn(r)
        pm = pwin_from_scores(s)                    # モデル確率
        imp = 1.0 / o
        pk = imp / imp.sum()                        # 市場確率（控除を正規化で除去）
        X = np.column_stack([np.log(pm + EPS), np.log(pk + EPS)])
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        out.append((X, int(r["top3"][0]), seg, pm, pk, o, m))
    return out


def loglik(beta, data, idx=None):
    ll = 0.0
    for k in (idx if idx is not None else range(len(data))):
        X, w = data[k][0], data[k][1]
        u = X @ beta
        u -= u.max()
        e = np.exp(u)
        ll += u[w] - np.log(e.sum())
    return ll


def fit(data, idx, K=2, iters=60):
    """ニュートン法（条件付きロジットは凹なので安定）。返り値: beta, 分散共分散行列"""
    beta = np.zeros(K)
    for _ in range(iters):
        g = np.zeros(K); H = np.zeros((K, K))
        for k in idx:
            X, w = data[k][0], data[k][1]
            u = X @ beta; u -= u.max()
            p = np.exp(u); p /= p.sum()
            xbar = p @ X
            g += X[w] - xbar
            H -= (X * p[:, None]).T @ X - np.outer(xbar, xbar)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        beta -= step
        if np.abs(step).max() < 1e-10:
            break
    cov = -np.linalg.inv(H)
    return beta, cov


def main():
    races = V.load_races()
    V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    data = build(races, wfn)
    seg = np.array([d[2] for d in data])
    print(f"対象 {len(data):,}レース（オッズ完備のみ）"
          f" MINE {int((seg==0).sum())} / VAL {int((seg==1).sum())} / CONF {int((seg==2).sum())}")

    mine = np.where(seg == 0)[0]
    beta, cov = fit(data, mine)
    se = np.sqrt(np.diag(cov))
    print("\n═ ① 条件付きロジット（MINEで推定）═")
    print(f"{'説明変数':<22}{'係数':>9}{'SE':>8}{'t値':>8}   判定")
    for nm, b, s in (("log p_model (堀川)", beta[0], se[0]),
                     ("log p_market(オッズ)", beta[1], se[1])):
        t = b / s if s else 0
        verdict = "★エッジあり(t>3)" if (nm.startswith("log p_model") and t > 3.0) else (
                  "市場が支配的" if nm.startswith("log p_market") and t > 3 else "")
        print(f"{nm:<22}{b:>9.4f}{s:>8.4f}{t:>8.2f}   {verdict}")

    # 市場のみモデル(β1=0固定)との比較
    b1, c1 = fit([(d[0][:, 1:2], d[1], d[2], d[3], d[4], d[5], d[6]) for d in data], mine, K=1)
    print(f"\n参考: 市場のみモデルの係数 {b1[0]:.4f}")

    print("\n═ ② 未知データでの対数尤度（1頭あたり・大きいほど良い）═")
    d_mkt = [(d[0][:, 1:2], d[1], d[2], d[3], d[4], d[5], d[6]) for d in data]
    d_mdl = [(d[0][:, 0:1], d[1], d[2], d[3], d[4], d[5], d[6]) for d in data]
    b_mdl, _ = fit(d_mdl, mine, K=1)
    print(f"  （単独推定の係数: モデル {b_mdl[0]:.4f} / 市場 {b1[0]:.4f}）")
    for si, nm in ((1, "VALIDATE"), (2, "CONFIRM")):
        idx = np.where(seg == si)[0]
        ll_both = loglik(beta, data, idx) / len(idx)
        ll_mkt = loglik(b1, d_mkt, idx) / len(idx)
        # ★モデル単独は「単独で推定し直した係数」で測る（条件付き係数の流用は不当）
        ll_mdl = loglik(b_mdl, d_mdl, idx) / len(idx)
        unif = float(np.mean([-np.log(len(data[k][5])) for k in idx]))
        print(f"  {nm}: 一様 {unif:.4f} / モデル単独 {ll_mdl:.4f} / 市場単独 {ll_mkt:.4f} / "
              f"両方 {ll_both:.4f}  → 両方-市場単独 = {ll_both-ll_mkt:+.4f}")

    print("\n═ ③ 市場オッズ帯ごとの較正（全頭平均だと大穴帯が重みを占めるため分けて測る）═")
    print(f"{'市場オッズ帯':>14}{'n':>8}{'市場p平均':>10}{'PWin平均':>10}{'実測勝率':>10}"
          f"{'PWin-実測':>11}{'市場-実測':>11}")
    bands = [(1, 3), (3, 6), (6, 10), (10, 20), (20, 50), (50, 1e9)]
    for lo, hi in bands:
        ys, pms, pks = [], [], []
        for X, w, sg, pm, pk, o, m in data:
            if sg == 0:
                continue                       # 未知期間だけで測る
            msk = (o >= lo) & (o < hi)
            if not msk.any():
                continue
            y = np.zeros(len(o)); y[w] = 1
            ys.append(y[msk]); pms.append(pm[msk]); pks.append(pk[msk])
        if not ys:
            continue
        y = np.concatenate(ys); pm = np.concatenate(pms); pk = np.concatenate(pks)
        print(f"{f'{lo:g}-{hi:g}倍':>14}{len(y):>8,}{pk.mean():>9.1%}{pm.mean():>10.1%}"
              f"{y.mean():>10.1%}{pm.mean()-y.mean():>+10.1%}{pk.mean()-y.mean():>+10.1%}")

    print("\n═ ④ PWin25-35%帯のずれの期間別安定性（符号が一貫するか）═")
    per = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for X, w, sg, pm, pk, o, m in data:
        msk = (pm >= 0.25) & (pm < 0.35)
        if not msk.any():
            continue
        y = np.zeros(len(o)); y[w] = 1
        a = per[m[:6]]
        a[0] += int(msk.sum()); a[1] += float(pm[msk].sum()); a[2] += float(y[msk].sum())
    signs = []
    for mo in sorted(per):
        n, sp, sy = per[mo]
        if n < 50:
            continue
        d = sp / n - sy / n
        signs.append(np.sign(d))
        print(f"  {mo}: n{n:>4} 予測{sp/n:.1%} 実測{sy/n:.1%} ずれ{d:+.1%}")
    if signs:
        pos = sum(1 for s in signs if s > 0)
        print(f"  → 符号: 過大{pos} / 過小{len(signs)-pos} "
              f"({'一貫＝補正すべき' if pos in (0, len(signs)) else '揺れている＝推定が不安定。上位帯ほどケリー分数を絞る'})")

    json.dump({"beta_model": float(beta[0]), "beta_market": float(beta[1]),
               "se": [float(x) for x in se]}, open("cond_logit.json", "w"))
    print("\nsaved cond_logit.json")


if __name__ == "__main__":
    main()
