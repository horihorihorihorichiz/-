# -*- coding: utf-8 -*-
"""今回の馬場と比べて「同等以上に悪い条件」での実績を成分にする。

いまの TAS は「過去1年の道悪での平均着順比」を 10/5/0 に丸めたもので、
今回の馬場を見ていない。稍重の日も不良の日も同じ物差しになる。
不良の日に、稍重を1回こなしただけの馬と、不良で勝った馬が同じ扱いになる。

そこで今回の馬場を基準にして作り直す。悪さの順は 良0 / 稍重1 / 重2 / 不良3。

  W1 今回以上の出走数     今回と同じかそれ以上に悪い馬場での出走数（過去1年）
  W2 今回以上の着順比     その平均（小さいほど good）
  W3 今回以上の3着内率    その割合
  W4 今回より悪い出走数    厳密に今回より悪い馬場での出走数
  W5 今回以上 − 今回未満   悪い条件でどれだけ落ちないか（負なら道悪で上げる馬）
  W6 今回以上での最高着順比  いちばん良かったときの着順比

良の日は「今回以上」が全レースと同じ意味になるので W1 は通算出走と重なる。
そこは木が馬場（CTX成分）と組み合わせて自分で使い分ける。

窓は explore.py と同じ。未知期間には触れない。

  python wet_record.py
"""
import json
import os
import sqlite3
import sys

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
from boost import XPARAMS, to_matrix  # noqa: E402

OUT = "weights/wet_record.json"
NAN = float("nan")
SEV = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
NEW = ["今回以上の出走数", "今回以上の着順比", "今回以上の3着内率",
       "今回より悪い出走数", "今回以上-今回未満", "今回以上の最高着順比"]


def wet(P, g):
    """今回の馬場の悪さ g を基準にした6成分。P はその馬の過去走。"""
    ge = [q for q in P if q["ago"] <= 365 and q["pos"]
          and SEV.get(q["r"]["ground"], 3) >= g]
    lt = [q for q in P if q["ago"] <= 365 and q["pos"]
          and SEV.get(q["r"]["ground"], 3) < g]
    worse = [q for q in P if q["ago"] <= 365 and q["pos"]
             and SEV.get(q["r"]["ground"], 3) > g]
    rge = [q["pos"] / q["r"]["n"] for q in ge]
    rlt = [q["pos"] / q["r"]["n"] for q in lt]
    return [
        float(len(ge)),
        float(np.mean(rge)) if rge else NAN,
        float(np.mean([q["pos"] <= 3 for q in ge])) if ge else NAN,
        float(len(worse)),
        float(np.mean(rge) - np.mean(rlt)) if (rge and rlt) else NAN,
        float(min(rge)) if rge else NAN,
    ]


def build(book, b, lo, hi, val, add):
    DS = []
    for ri, r in enumerate(book.races):
        if lo <= r["date"] < hi:
            d = b.build_wide(ri)
            Z = [list(x) for x in d["Z"]]
            mm = val.get(r["id"]) or {}
            col = train_eval.znorm_column(
                [mm.get(str(x["umaban"]), NAN) for x in r["rows"]])
            for row, x in zip(Z, col):
                row.append(x)
            if add:
                g = SEV.get(r["ground"], 3)
                for k, row in enumerate(Z):
                    row.extend(wet(book.past(ri, k, 9), g))
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS


def fit(TR, names):
    TRs = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=names); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=names); dv.set_group(gb)
    m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    n = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    d = xgb.DMatrix(X, label=y, feature_names=names); d.set_group(g)
    return xgb.train(XPARAMS, d, num_boost_round=n), n


def rep(label, DS, model, names, pays, only=None):
    n = w = i3 = 0
    tan, fuku = [], []
    for d in DS:
        r = d["race"]
        if only and not only(r):
            continue
        s = np.asarray(model.predict(
            xgb.DMatrix(np.asarray(d["Z"], np.float32)[:, :len(names)],
                        feature_names=names)), float)
        i = int(np.argmax(s))
        h = r["rows"][i]
        f = _fin(h["fin"])
        n += 1
        w += (f == 1)
        i3 += (f is not None and f <= 3)
        pay = pays.get(r["id"])
        if pay:
            tan.append(dict(pay.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0)
            fuku.append(dict(pay.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0)
    return {"label": label, "n": n, "win": w / n * 100, "in3": i3 / n * 100,
            "tan": float(np.mean(tan) * 100), "fuku": float(np.mean(fuku) * 100)}


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    base = list(b.wide_names) + [train_eval.NAME]
    full = base + NEW
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R\n", flush=True)

    nb = len(base)
    cutd = lambda DS: [dict(d, Z=np.asarray(d["Z"])[:, :nb]) for d in DS]
    m1, r1 = fit(cutd(FIT), base)
    m2, r2 = fit(FIT, full)

    wetonly = lambda r: r["ground"] != "良"
    res = [
        rep(f"木48成分（いまのもの・{r1}本）", cutd(EXP), m1, base, pays),
        rep(f"木54成分（今回以上の実績を足す・{r2}本）", EXP, m2, full, pays),
    ]
    resw = [
        rep("　うち道悪のレースだけ（現行）", cutd(EXP), m1, base, pays, wetonly),
        rep("　うち道悪のレースだけ（新）", EXP, m2, full, pays, wetonly),
    ]

    print(f'{"":<36}{"R":>6}{"1位が1着":>10}{"1位が3着内":>11}{"単勝ROI":>10}{"複勝ROI":>10}')
    for x in res + resw:
        print(f'{x["label"]:<36}{x["n"]:>6}{x["win"]:>9.2f}%{x["in3"]:>10.2f}%'
              f'{x["tan"]:>9.1f}%{x["fuku"]:>9.1f}%')

    imp = m2.get_score(importance_type="gain")
    tot = sum(imp.values()) or 1
    rank = {n: i + 1 for i, (n, _v) in enumerate(
        sorted(imp.items(), key=lambda x: -x[1]))}
    print(f"\n新しい6成分の順位（全{len(rank)}成分中）")
    for n in NEW:
        print(f"  {n:<16}" + (f"{rank[n]:>2}位   寄与 {imp[n]/tot*100:.2f}%"
                              if n in imp else "使われず"))
    print("参考: 元の TAS  " + (f"{rank['TAS']}位   寄与 {imp['TAS']/tot*100:.2f}%"
                              if "TAS" in imp else "使われず"))

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "results": [{k: (round(v, 2) if isinstance(v, float) else v)
                            for k, v in x.items()} for x in res + resw],
               "importance": {n: round(imp.get(n, 0) / tot * 100, 2) for n in NEW}},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
