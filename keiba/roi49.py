# -*- coding: utf-8 -*-
"""49セルごとに「複勝1位ROIがプラスになる配点」を直接探索する（2026-08-22・指示）。

指示: 「ROIプラスになるような配点などを49パターン考えていくのがあなたの仕事」

設計（過去の失敗を全部避ける）:
 ・目的関数 = 複勝1位のROIそのもの（的中率にしない: BOX5の教訓=的中率最適化は市場に収束）
 ・ターゲット券種は複勝1位1点のみ（的中50%超で分散が小さく、ROI差が統計的に見える唯一の券種）
 ・セルのMINEを時系列で前半/後半に割る:
     前半 = CEMの探索に使う（ここのROIを最大化）
     後半 = 関門。探索中一度も見ない。ここでROI≥102%のセルだけ合格
 ・合格セルの配点をプールして VAL/CONF を各1回だけ測定
 ・null = 複勝払戻をセル内でシャッフルして同じ全パイプライン×3回
   （配点と結果の繋がりを切る。合格セル数と最終ROIの偶然水準が出る）
"""
import json, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

H = 20

def pack(rs):
    n = len(rs); K = rs[0]["Z16"].shape[1]
    X = np.zeros((n, H, K)); M = np.zeros((n, H), bool)
    PAY = np.zeros((n, H)); WA = np.zeros((n, H)); NU = np.zeros((n, H), int)
    for i, r in enumerate(rs):
        k = len(r["nums"])
        X[i, :k] = r["Z16"]; M[i, :k] = True
        WA[i, :k] = r["wavg"]; NU[i, :k] = r["nums"]
        pl = {int(a): float(b) for a, b in ((r.get("payout") or {}).get("複勝") or {}).items()}
        for j, num in enumerate(r["nums"]):
            PAY[i, j] = pl.get(num, 0.0)
    return X, M, PAY, WA, NU

def roi_of(w, P):
    X, M, PAY, WA, NU = P
    s = np.where(M, X @ w, -1e18)
    key = (-s) * 1e9 + (-WA) * 1e3 + NU
    key = np.where(M, key, 1e30)
    top = np.argmin(key, axis=1)
    ret = PAY[np.arange(len(top)), top]
    return ret.sum() / len(top), ret

def cem(P, w0, iters=14, pop=40, elite=0.15, seed=0):
    rs = np.random.RandomState(seed)
    mu = w0.copy(); sd = np.abs(w0) * 0.35 + 0.02
    best_w, best_v = w0.copy(), roi_of(w0, P)[0]
    for _ in range(iters):
        C = rs.randn(pop, len(mu)) * sd + mu
        C[0] = best_w
        vals = np.array([roi_of(C[i], P)[0] for i in range(pop)])
        idx = np.argsort(-vals)[:max(4, int(pop * elite))]
        mu = C[idx].mean(0); sd = C[idx].std(0) + 0.01
        if vals[idx[0]] > best_v:
            best_v, best_w = vals[idx[0]], C[idx[0]].copy()
    return best_w, best_v

def run_pipeline(cells, shuffle_pay=None, verbose=False):
    accepted = {}
    rows = []
    for lab, (mine, val, conf) in cells.items():
        if len(mine) < 120:
            rows.append((lab, len(mine), None, None, "標本不足")); continue
        half = len(mine) // 2
        A, B = mine[:half], mine[half:]
        PA, PB = pack(A), pack(B)
        if shuffle_pay is not None:
            for P in (PA, PB):
                rs = shuffle_pay
                for i in range(P[2].shape[0]):
                    k = int(P[1][i].sum())
                    P[2][i, :k] = P[2][i, rs.permutation(k)]
        w0 = np.mean([wfn_ctx[lab](r) for r in mine[:20]], axis=0)
        w, vA = cem(PA, w0, seed=7)
        vB = roi_of(w, PB)[0]
        ok = vB >= 102
        rows.append((lab, len(mine), vA, vB, "★合格" if ok else "不合格"))
        if ok:
            accepted[lab] = w
    # 合格セルのプールをVAL/CONFで測定
    res = {}
    for nm, key in (("VAL", 1), ("CONF", 2)):
        cost = ret = 0
        for lab, w in accepted.items():
            S = cells[lab][key]
            if not S: continue
            P = pack(S)
            if shuffle_pay is not None:
                rs = shuffle_pay
                for i in range(P[2].shape[0]):
                    k = int(P[1][i].sum())
                    P[2][i, :k] = P[2][i, rs.permutation(k)]
            _, r_ = roi_of(w, P)
            cost += 100 * len(S); ret += r_.sum()
        res[nm] = ret / cost * 100 if cost else None
    return rows, accepted, res

def main():
    global wfn_ctx
    races = V.load_races(); V2.attach_corner(races)
    art = json.load(open("hori52_w.json"))
    wfn = scorer_from_artifact(art)
    wfn_ctx = collections.defaultdict(lambda: (lambda r: r["Z16"].mean(0)))
    cells = collections.defaultdict(lambda: ([], [], []))
    for r in sorted(races, key=lambda x: x["month"]):
        lab = f"{r.get('venue')}{r['surface']}{r['dist_cat']}"
        idx = 0 if r["month"] <= "202602" else (1 if r["month"] <= "202605" else 2)
        cells[lab][idx].append(r)
    for lab in cells:
        wfn_ctx[lab] = wfn
    print(f"セル数 {len(cells)}")

    rows, accepted, res = run_pipeline(dict(cells))
    print(f"\n実データ: 合格 {len(accepted)}セル")
    print(f"合格セルのプール: VAL {res['VAL'] if res['VAL'] else '—'}% / CONF {res['CONF'] if res['CONF'] else '—'}%")
    print(f"\n{'セル':<10}{'nM':>5}{'探索半分ROI':>11}{'関門半分ROI':>11}  判定")
    for lab, n, vA, vB, verdict in sorted(rows, key=lambda x: -(x[3] or 0)):
        va = f"{vA:.1f}%" if vA else "—"
        vb = f"{vB:.1f}%" if vB else "—"
        print(f"{lab:<10}{n:>5}{va:>11}{vb:>11}  {verdict}")

    print("\nnull(払戻シャッフル×3・同じ全パイプライン):")
    for t in range(3):
        rs = np.random.RandomState(200 + t)
        r2, a2, res2 = run_pipeline(dict(cells), shuffle_pay=rs)
        print(f"  null#{t+1}: 合格{len(a2)}セル  VAL {res2['VAL'] if res2['VAL'] else '—'} / CONF {res2['CONF'] if res2['CONF'] else '—'}")
    json.dump({"accepted": list(accepted), "res": res,
               "rows": [(l, n, a, b, v) for l, n, a, b, v in rows]},
              open("roi49.json", "w"), ensure_ascii=False, indent=1, default=float)

if __name__ == "__main__":
    main()
