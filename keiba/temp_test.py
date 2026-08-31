# -*- coding: utf-8 -*-
"""β1が負なのは「情報が逆」なのか「温度(分布の尖り)がずれている」だけなのかを切り分ける
（2026-08-23・外部助言の最優先切り分け）。

背景: cond_logit.py で β1(log p_model) = -0.0597 (t=-2.42)。
     ②の帯別較正でPWinは1-3倍帯を19.2%(実測38.0%)と大幅に過小、50倍超を2.8%(実測0.6%)と過大。
     ＝一方向にフラット過ぎる分布。原因の第一候補は **PWin変換に入っている30%クリップ**
     （上位馬の確率を人為的に頭打ちにする非線形歪み。まさに過小の出る場所）。

★事前に決めた測定（見てから足さない）: 次の4変種を各1回だけ測る。
  A) 現行PWin（softmax→30%クリップ→再正規化）  ← ①で測った基準
  B) クリップ無しの素のsoftmax（= 得点そのもの。条件付きロジットは尺度を自動で吸収するので
     β1が温度パラメータそのものになる）
  C) 得点を直接投入（Bと数学的に同値。実装差の確認用）
  D) 順位のみ（log(1/順位)）＝確率情報を捨て順序だけ残した対照

判定:
  Bでβ1が有意に正(t>3) → 「情報はあったがPWin変換(クリップ)で壊していた」＝設計修正で復活
  Bでもβ1≈0か負      → 温度では説明できない＝市場に対する上乗せは本当に無い

usage: python3 temp_test.py
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
from verify_export import scorer_from_artifact
from calib_check import pwin_from_scores
import cond_logit as CL

EPS = 1e-12


def variants(races, wfn):
    """4変種それぞれの (X[n,2], 勝者idx, seg) データを作る。"""
    out = {k: [] for k in "ABCD"}
    for r in races:
        od = r.get("odds") or {}
        o = np.array([float(od.get(n) or 0) for n in r["nums"]])
        if (o <= 1.0).any():
            continue
        s = r["Z16"] @ wfn(r)
        imp = 1.0 / o
        pk = imp / imp.sum()
        lm = np.log(pk + EPS)
        m = r["month"]
        seg = 0 if m <= "202602" else (1 if m <= "202605" else 2)
        w = int(r["top3"][0])

        pA = pwin_from_scores(s)                       # クリップあり(現行)
        e = np.exp(s - s.max()); pB = e / e.sum()      # クリップ無し素softmax
        rank = np.empty(len(s)); rank[np.argsort(-s)] = np.arange(1, len(s) + 1)
        feats = {"A": np.log(pA + EPS), "B": np.log(pB + EPS),
                 "C": s - s.mean(), "D": np.log(1.0 / rank)}
        for k, f in feats.items():
            out[k].append((np.column_stack([f, lm]), w, seg, None, pk, o, m))
    return out


def main():
    races = V.load_races()
    V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    var = variants(races, wfn)
    seg = np.array([d[2] for d in var["A"]])
    mine = np.where(seg == 0)[0]
    print(f"対象 {len(seg):,}レース / MINE {len(mine):,}")

    # 市場のみモデル（比較の基準線）
    d_mkt = [(d[0][:, 1:2], d[1], d[2], d[3], d[4], d[5], d[6]) for d in var["A"]]
    b_mkt, _ = CL.fit(d_mkt, mine, K=1)
    base = {}
    for si, nm in ((1, "VAL"), (2, "CONF")):
        idx = np.where(seg == si)[0]
        base[nm] = CL.loglik(b_mkt, d_mkt, idx) / len(idx)
    print(f"基準線: 市場のみ VAL {base['VAL']:.4f} / CONF {base['CONF']:.4f}\n")

    names = {"A": "A 現行PWin(30%クリップ)", "B": "B クリップ無しsoftmax",
             "C": "C 得点を直接", "D": "D 順位のみ(対照)"}
    print(f"{'変種':<26}{'β1(モデル)':>12}{'SE':>8}{'t値':>8}{'β2(市場)':>10}"
          f"{'VAL上乗せ':>11}{'CONF上乗せ':>11}")
    res = {}
    for k in "ABCD":
        data = var[k]
        beta, cov = CL.fit(data, mine)
        se = np.sqrt(np.diag(cov))
        t = beta[0] / se[0]
        ups = []
        for si, nm in ((1, "VAL"), (2, "CONF")):
            idx = np.where(seg == si)[0]
            ups.append(CL.loglik(beta, data, idx) / len(idx) - base[nm])
        res[k] = (beta, se, t, ups)
        print(f"{names[k]:<26}{beta[0]:>12.4f}{se[0]:>8.4f}{t:>8.2f}{beta[1]:>10.4f}"
              f"{ups[0]:>+11.4f}{ups[1]:>+11.4f}")

    bB = res["B"]
    print("\n═ 判定 ═")
    if bB[2] > 3.0:
        print(f"★Bのβ1={bB[0][0]:.4f} (t={bB[2]:.2f}) が正で有意 → "
              "『情報はあったがPWin変換(30%クリップ)が壊していた』。PWin生成の修正で復活する。")
    elif bB[2] > 0:
        print(f"Bのβ1={bB[0][0]:.4f} (t={bB[2]:.2f}) は正だがt<3.0 → "
              "温度ずれで符号は説明できるが、上乗せは規律R5のハードルに届かない。")
    else:
        print(f"Bのβ1={bB[0][0]:.4f} (t={bB[2]:.2f}) も非正 → "
              "温度では説明できない。市場に対する上乗せは本当に無い。")
    print(f"未知期間の上乗せ(対数尤度): B = VAL {bB[3][0]:+.4f} / CONF {bB[3][1]:+.4f}")
    json.dump({k: {"beta": list(map(float, v[0])), "t": float(v[2]),
                   "uplift": list(map(float, v[3]))} for k, v in res.items()},
              open("temp_test.json", "w"), ensure_ascii=False, indent=1)
    print("saved temp_test.json")


if __name__ == "__main__":
    main()
