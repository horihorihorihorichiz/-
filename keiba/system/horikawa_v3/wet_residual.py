# -*- coding: utf-8 -*-
"""道悪が苦手な馬の証拠が、モデルの残差に残っているかを先に調べる。

今日は成分を足す試みが5回続けて空振りした。作る前に「そもそも残す余地が
あるのか」を見る。木の予測順位と実際の着順の差＝残差を取り、道悪のレースで
「過去に道悪で негативな実績がある馬」がその残差の中で沈んでいるかを見る。

沈んでいれば、そこはまだモデルが読めていない領域。信号が無ければ、
どんな成分を作っても同じ結果になる。

見る証拠（すべて過去1年・今回が道悪のレースのみ）:
  A 道悪で人気を裏切った回数   道悪で（人気 − 着順）が -5 以下だった回数
  B 道悪での着順比 − 良での着順比   正なら道悪で落ちる馬
  C 道悪で二桁着順の回数
  D 道悪の経験が無い          今回道悪なのに道悪の出走がゼロ

窓は explore.py と同じ。未知期間には触れない。

  python wet_residual.py
"""
import json
import os
import sys

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
# build は explore にも boost にもあり、引数の意味が違う。
# ここは wide 47成分 + 調教評価 を返す boost 側を使う。
from boost import XPARAMS, to_matrix, build  # noqa: E402

OUT = "weights/wet_residual.json"
SEV = {"良": 0, "稍重": 1, "重": 2, "不良": 3}


def evidence(P):
    """過去1年の道悪での negative な証拠。"""
    wet = [q for q in P if q["ago"] <= 365 and q["pos"]
           and SEV.get(q["r"]["ground"], 3) >= 1]
    dry = [q for q in P if q["ago"] <= 365 and q["pos"]
           and SEV.get(q["r"]["ground"], 3) == 0]
    betray = sum(1 for q in wet
                 if q["h"]["pop"] and (q["h"]["pop"] - q["pos"]) <= -5)
    rw = [q["pos"] / q["r"]["n"] for q in wet]
    rd = [q["pos"] / q["r"]["n"] for q in dry]
    return {
        "wet_runs": len(wet),
        "betray": betray,
        "gap": (np.mean(rw) - np.mean(rd)) if (rw and rd) else None,
        "double": sum(1 for q in wet if q["pos"] >= 10),
    }


def main():
    st = Store(config.DB_PATH)
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)
    names = list(b.wide_names) + [train_eval.NAME]
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, nf, False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, nf, False)

    TRs = sorted(FIT, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=names); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=names); dv.set_group(gb)
    m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    n0 = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    dall = xgb.DMatrix(X, label=y, feature_names=names); dall.set_group(g)
    model = xgb.train(XPARAMS, dall, num_boost_round=n0)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 木 {n0}本\n", flush=True)

    # 道悪のレースだけ、馬ごとの残差を集める
    H = []
    for d in EXP:
        r = d["race"]
        if SEV.get(r["ground"], 3) == 0:
            continue
        s = np.asarray(model.predict(
            xgb.DMatrix(np.asarray(d["Z"], np.float32), feature_names=names)), float)
        pred = np.argsort(np.argsort(-s)) + 1        # モデルの予測順位
        for i, h in enumerate(r["rows"]):
            f = _fin(h["fin"])
            if f is None:
                continue
            H.append({"i": i, "race": r, "ri": d, "pred": int(pred[i]), "fin": f,
                      "n": r["n"], "horse": h})
    print(f"道悪のレース {len({id(x['race']) for x in H})}R / 延べ {len(H)}頭", flush=True)

    # 証拠は past が要るので、レースを走査し直して付ける
    idx = {r["id"]: ri for ri, r in enumerate(book.races)}
    for x in H:
        ri = idx[x["race"]["id"]]
        x["ev"] = evidence(book.past(ri, x["i"], 9))

    # 残差 = 実際の着順比 − 予測順位比。正なら「モデルの想定より負けた」
    for x in H:
        x["resid"] = x["fin"] / x["n"] - x["pred"] / x["n"]

    def cmp(label, f):
        a = [x["resid"] for x in H if f(x)]
        c = [x["resid"] for x in H if not f(x)]
        if len(a) < 50:
            print(f"  {label:<32}{len(a):>6}   （頭数が足りない）")
            return None
        se = np.sqrt(np.var(a, ddof=1) / len(a) + np.var(c, ddof=1) / len(c))
        t = (np.mean(a) - np.mean(c)) / se
        print(f"  {label:<32}{len(a):>6}{np.mean(a):>+9.4f}{np.mean(c):>+10.4f}"
              f"{np.mean(a)-np.mean(c):>+10.4f}{t:>8.2f}")
        return {"label": label, "n": len(a), "resid": round(float(np.mean(a)), 4),
                "other": round(float(np.mean(c)), 4), "t": round(float(t), 2)}

    print("\n残差（実際の着順比 − 予測順位比）。正なら想定より負けている。")
    print(f'  {"証拠":<32}{"頭数":>6}{"該当":>9}{"それ以外":>10}{"差":>10}{"t":>8}')
    out = []
    for lab, f in [
        ("道悪で人気を裏切った 1回以上", lambda x: x["ev"]["betray"] >= 1),
        ("道悪で人気を裏切った 2回以上", lambda x: x["ev"]["betray"] >= 2),
        ("道悪で二桁着順 1回以上", lambda x: x["ev"]["double"] >= 1),
        ("道悪で二桁着順 2回以上", lambda x: x["ev"]["double"] >= 2),
        ("道悪のほうが着順比が悪い", lambda x: x["ev"]["gap"] is not None and x["ev"]["gap"] > 0),
        ("道悪のほうが着順比が0.2以上悪い",
         lambda x: x["ev"]["gap"] is not None and x["ev"]["gap"] > 0.2),
        ("道悪の経験が無い", lambda x: x["ev"]["wet_runs"] == 0),
    ]:
        r_ = cmp(lab, f)
        if r_:
            out.append(r_)

    # ── 交絡を切り分ける。道悪経験のある馬だけで比べ直す
    WE = [x for x in H if x["ev"]["wet_runs"] >= 1]

    def cmp2(label, f, pool):
        a = [x["resid"] for x in pool if f(x)]
        c = [x["resid"] for x in pool if not f(x)]
        if len(a) < 50 or len(c) < 50:
            print(f"  {label:<32}{len(a):>6}   （頭数が足りない）")
            return None
        se = np.sqrt(np.var(a, ddof=1) / len(a) + np.var(c, ddof=1) / len(c))
        t = (np.mean(a) - np.mean(c)) / se
        print(f"  {label:<32}{len(a):>6}{np.mean(a):>+9.4f}{np.mean(c):>+10.4f}"
              f"{np.mean(a) - np.mean(c):>+10.4f}{t:>8.2f}")
        return {"label": label + "（道悪経験ありの中で）", "n": len(a),
                "resid": round(float(np.mean(a)), 4),
                "other": round(float(np.mean(c)), 4), "t": round(float(t), 2)}

    print(f"\n道悪経験のある馬 {len(WE)}頭だけで比べ直す（経験の有無との交絡を外す）")
    print(f'  {"証拠":<32}{"頭数":>6}{"該当":>9}{"それ以外":>10}{"差":>10}{"t":>8}')
    for lab, f in [("道悪で二桁着順 1回以上", lambda x: x["ev"]["double"] >= 1),
                   ("道悪で二桁着順 2回以上", lambda x: x["ev"]["double"] >= 2),
                   ("道悪で人気を裏切った 1回以上", lambda x: x["ev"]["betray"] >= 1)]:
        r2 = cmp2(lab, f, WE)
        if r2:
            out.append(r2)

    print("\n道悪の出走数ごとの残差（経験そのものが効いていないかを見る）")
    print(f'  {"道悪出走数":<32}{"頭数":>6}{"残差":>9}')
    for lo, hi, lab in [(0, 0, "0回"), (1, 1, "1回"), (2, 3, "2-3回"), (4, 99, "4回以上")]:
        a = [x["resid"] for x in H if lo <= x["ev"]["wet_runs"] <= hi]
        if len(a) >= 50:
            print(f'  {lab:<32}{len(a):>6}{np.mean(a):>+9.4f}')
            out.append({"label": f"道悪出走数 {lab}", "n": len(a),
                        "resid": round(float(np.mean(a)), 4), "other": None, "t": None})

    print("\nt が +3 を越えていれば、その証拠はモデルがまだ読めていない。")
    print("どれも小さければ、道悪の不得手は既に他の成分に織り込まれている。")
    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "n_horses": len(H), "results": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
