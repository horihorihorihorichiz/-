# -*- coding: utf-8 -*-
"""V7「市場残差」予想システム（Benter型二段構成）— V7_PROTOCOL_20260817.md 準拠。

一段目: 台帳 wf_preds_v3ext2.jsonl の V3 生スコアをレース内 softmax(τ·s) で確率化。
        ※V3のWF月次モデルはスコアのスケールが月ごとに大きく異なる（レース内stdの
          月中央値が0.03〜0.86の30倍レンジ）ため、スコアは「その月のレース内stdの
          中央値」で除して正規化してから使う。この正規化は結果(着順)を一切使わず
          スコアだけから計算でき、実運用でも当月モデルのスコア分布から同様に得られる
          （リークなし）。全段やり直し1回目の修正（202412フォールドのEV暴発の原因）。
        τ は各フォールドで「当該月より前の評価月」の勝者尤度から最尤推定。
        （τ と二段目の α は softmax 内で積として縮退するため、τ は p_model の
          単体報告用キャリブレーション。p_blend には α·τ の積だけが効く。）
二段目: 条件付きロジット（レース内 softmax）
        u_i = α·log p_model_i + β·log p_market_i
              + γf·zf·log p_model_i + γm·zm·log p_model_i
        zf = (頭数-12)/4（固定定数で標準化・事前登録）
        zm = 1[tier==10]（未勝利新馬クラス・事前登録）
        p_market = (1/odds) をレース内で合計1に正規化（控除率補正）。
        係数は月次WF: 各評価月 m につき、台帳内の m より前の月のみで最尤推定。
買い:   EV = p_blend × 確定オッズ ≥ 1.3 の馬の単勝 flat100円（1.2/1.5は参考）。

出力:
  v7_bets.jsonl  … 全馬の p_model/p_market/p_blend/EV/払戻（評価月 202410 以降）
  v7_folds.json  … 月別の τ, α, β, γf, γm と学習レース数
注記:
  - 202409 は前月データが台帳に無いため評価から除外（プロトコルに記録）。
  - オッズ不完全レース（202604020412: 17頭中5頭分しか無い）は学習・評価とも除外。
"""
import json
import numpy as np
from scipy.optimize import minimize, minimize_scalar

LEDGER = "wf_preds_v3ext2.jsonl"
BETS_OUT = "v7_bets.jsonl"
FOLDS_OUT = "v7_folds.json"


def load_races(path=LEDGER):
    races, dropped = [], []
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        order = [int(x) for x in d["order"]]
        odds = {int(k): float(v) for k, v in d["odds"].items()}
        if any(h not in odds or odds[h] <= 0 for h in order):
            dropped.append(d["rid"])
            continue
        tan = d["payout"]["単勝"]
        winner = int(d["top3"][0])
        races.append(dict(
            rid=d["rid"], month=d["month"], ns=order,
            s=np.array(d["scores"], dtype=float),
            odds=np.array([odds[h] for h in order], dtype=float),
            win_idx=order.index(winner) if winner in order else -1,
            tan={int(k): int(v) for k, v in tan.items()},
            field=int(d["field"]), tier=int(d.get("tier") or 0),
        ))
    races = [r for r in races if r["win_idx"] >= 0]
    # 月別スケール正規化（スコアのみ使用・結果不使用＝リークなし）
    month_scale = {}
    stds = {}
    for r in races:
        stds.setdefault(r["month"], []).append(float(np.std(r["s"])))
    for m, v in stds.items():
        month_scale[m] = float(np.median(v)) or 1.0
    for r in races:
        r["s"] = r["s"] / month_scale[r["month"]]
    return races, dropped, month_scale


def pad(races):
    """レース群を (n, K) のパディング行列に。返り値: S, LQ(log p_market), M(mask), ZF, ZM, W"""
    n = len(races)
    K = max(len(r["ns"]) for r in races)
    S = np.zeros((n, K)); Q = np.zeros((n, K)); M = np.zeros((n, K), dtype=bool)
    ZF = np.zeros(n); ZM = np.zeros(n); W = np.zeros(n, dtype=int)
    for i, r in enumerate(races):
        k = len(r["ns"])
        S[i, :k] = r["s"]
        pm = 1.0 / r["odds"]
        Q[i, :k] = np.log(pm / pm.sum())      # 控除率補正済み log p_market
        M[i, :k] = True
        ZF[i] = (r["field"] - 12) / 4.0
        ZM[i] = 1.0 if r["tier"] == 10 else 0.0
        W[i] = r["win_idx"]
    return S, Q, M, ZF, ZM, W


def log_softmax_masked(U, M):
    U = np.where(M, U, -1e30)
    mx = U.max(axis=1, keepdims=True)
    lse = mx + np.log(np.exp(U - mx).sum(axis=1, keepdims=True))
    return U - lse


def fit_tau(S, M, W):
    idx = np.arange(len(W))

    def nll(tau):
        lp = log_softmax_masked(tau * S, M)
        return -lp[idx, W].sum()

    res = minimize_scalar(nll, bounds=(0.05, 60.0), method="bounded",
                          options={"xatol": 1e-6})
    return float(res.x)


def stage2_features(S, Q, M, ZF, ZM, tau):
    """特徴行列 X (4, n, K): [log p_model, log p_market, zf·lpm, zm·lpm]"""
    L = log_softmax_masked(tau * S, M)          # log p_model
    X = np.stack([L, Q, ZF[:, None] * L, ZM[:, None] * L])
    return X


def fit_stage2(X, M, W):
    idx = np.arange(len(W))

    def f(theta):
        U = np.tensordot(theta, X, axes=1)
        lp = log_softmax_masked(U, M)
        nll = -lp[idx, W].sum()
        P = np.where(M, np.exp(lp), 0.0)
        # grad_k = Σ_i (E_p[X_k] − X_k[winner])
        g = (P[None] * X).sum(axis=2).sum(axis=1) - X[:, idx, W].sum(axis=1)
        return nll, g

    res = minimize(f, x0=np.array([1.0, 1.0, 0.0, 0.0]), jac=True,
                   method="L-BFGS-B")
    return res.x, float(res.fun)


def main():
    races, dropped, month_scale = load_races()
    months = sorted({r["month"] for r in races})
    by_month = {m: [r for r in races if r["month"] == m] for m in months}
    print(f"races={len(races)} dropped(odds不完全)={dropped} months={months[0]}..{months[-1]}")
    print("month_scale:", {m: round(month_scale[m], 3) for m in months})

    folds = {}
    bets_f = open(BETS_OUT, "w", encoding="utf-8")
    for mi, m in enumerate(months):
        train = [r for mm in months[:mi] for r in by_month[mm]]
        if not train:
            print(f"{m}: 学習データなし→評価スキップ（記録）")
            folds[m] = dict(skipped=True, train_races=0)
            continue
        S, Q, M_, ZF, ZM, W = pad(train)
        tau = fit_tau(S, M_, W)
        X = stage2_features(S, Q, M_, ZF, ZM, tau)
        theta, nll = fit_stage2(X, M_, W)
        alpha, beta, gf, gm = [float(t) for t in theta]
        folds[m] = dict(tau=round(tau, 4), alpha=round(alpha, 4),
                        beta=round(beta, 4), gamma_field=round(gf, 4),
                        gamma_maiden=round(gm, 4), train_races=len(train),
                        train_nll_per_race=round(nll / len(train), 4))
        # 当月レースへ適用
        ev = by_month[m]
        Se, Qe, Me, ZFe, ZMe, We = pad(ev)
        Xe = stage2_features(Se, Qe, Me, ZFe, ZMe, tau)
        Ue = np.tensordot(theta, Xe, axes=1)
        LPb = log_softmax_masked(Ue, Me)
        LPm = log_softmax_masked(tau * Se, Me)
        for i, r in enumerate(ev):
            k = len(r["ns"])
            pb = np.exp(LPb[i, :k]); pmod = np.exp(LPm[i, :k])
            pmkt = np.exp(Qe[i, :k])
            for j, h in enumerate(r["ns"]):
                evj = pb[j] * r["odds"][j]
                rec = dict(rid=r["rid"], month=m, horse=h,
                           odds=round(float(r["odds"][j]), 1),
                           p_model=round(float(pmod[j]), 5),
                           p_market=round(float(pmkt[j]), 5),
                           p_blend=round(float(pb[j]), 5),
                           ev=round(float(evj), 4),
                           model_rank=j + 1, field=r["field"], tier=r["tier"],
                           win=int(j == r["win_idx"]),
                           pay=r["tan"].get(h, 0))
                bets_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{m}: train={len(train):4d}R τ={tau:.3f} α={alpha:.3f} β={beta:.3f} "
              f"γf={gf:+.3f} γm={gm:+.3f}")
    bets_f.close()
    json.dump(folds, open(FOLDS_OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"wrote {BETS_OUT}, {FOLDS_OUT}")


if __name__ == "__main__":
    main()
