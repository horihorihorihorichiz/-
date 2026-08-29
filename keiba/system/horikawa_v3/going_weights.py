# -*- coding: utf-8 -*-
"""配点を馬場ごとに変える。モデルを分けるのではなく、重みだけ差し替える。

前の試み（pace_going.py）は馬場ごとに別の木を作って失敗した。良以外が799Rしか
無く、推定が荒れたため。だが hk が場やクラスでやっているのは「別のモデル」では
なく「配点だけ層で切って、薄いセルは経験ベイズで親へ縮める」形。
同じことを馬場の軸でやる。薄いセルは自動的に全体の配点へ寄るので壊れない。

層の切り方は3通り試す:
  馬場        良 / 稍重 / 重 / 不良
  芝ダ×馬場    芝良 / 芝道悪 / ダ良 / ダ道悪
  馬場2値      良 / 良以外

比較の相手は「全体1本」（馬場を見ない配点）。

窓は explore.py と同じ。未知期間には触れない。

  python going_weights.py
"""
import json
import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, build, _fin  # noqa: E402

OUT = "weights/going_weights.json"

WET = {"稍重", "重", "不良"}
KEYS = {
    "馬場4分割": lambda r: r["ground"],
    "芝ダ×馬場": lambda r: r["surf"] + ("良" if r["ground"] == "良" else "道悪"),
    "馬場2値": lambda r: "良" if r["ground"] == "良" else "良以外",
}


def evaluate(DS, wof, pays):
    """wof(race) が返す配点で採点する。"""
    n = w = i3 = 0
    tan, fuku = [], []
    for d in DS:
        r = d["race"]
        s = np.asarray(d["Z"], float) @ wof(r)
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
    return {"n": n, "win": w / n * 100, "in3": i3 / n * 100,
            "tan": float(np.mean(tan) * 100), "fuku": float(np.mean(fuku) * 100),
            "tan_se": float(np.std(tan, ddof=1) / np.sqrt(len(tan)) * 100)}


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    names = list(features.BASE_NAMES) + [train_eval.NAME]
    nf = len(features.BASE_NAMES)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True, nf)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True, nf)
    for d in FIT + EXP:
        d["Z"] = np.asarray(d["Z"])[:, :len(names)]
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 成分 {len(names)}個\n", flush=True)

    G, _ = F.pl_fit(FIT, iters=300)
    res = [{"layer": "全体1本（馬場を見ない）", "cells": 1,
            **evaluate(EXP, lambda r: G, pays)}]

    tables = {}
    for lab, keyf in KEYS.items():
        groups = {}
        for d in FIT:
            groups.setdefault(keyf(d["race"]), []).append(d)
        cnt = {k: len(v) for k, v in groups.items()}
        W, K, ns, _raw = F.fit_level(groups, lambda c: G)
        print(f"── {lab}: " + " / ".join(f"{k} {v}R" for k, v in sorted(cnt.items())))
        res.append({"layer": lab, "cells": len(W),
                    **evaluate(EXP, lambda r: W.get(keyf(r), G), pays)})
        tables[lab] = {k: [round(float(x), 3) for x in v] for k, v in W.items()}

    print(f'\n{"配点の層":<22}{"セル":>5}{"R":>6}{"1位が1着":>10}{"1位が3着内":>11}'
          f'{"単勝ROI":>10}{"複勝ROI":>10}')
    for x in res:
        print(f'{x["layer"]:<22}{x["cells"]:>5}{x["n"]:>6}{x["win"]:>9.2f}%'
              f'{x["in3"]:>10.2f}%{x["tan"]:>9.1f}%{x["fuku"]:>9.1f}%')

    # どの成分が馬場で入れ替わるかを見る
    W2 = tables["馬場2値"]
    if "良" in W2 and "良以外" in W2:
        a, c = np.array(W2["良"]), np.array(W2["良以外"])
        norm = lambda v: v / (np.abs(v).mean() or 1) * 30
        na, nc = norm(a), norm(c)
        dd = sorted(zip(names, na, nc, nc - na), key=lambda x: -abs(x[3]))
        print("\n良 と 良以外 で配点がどれだけ動くか（平均絶対値=30に正規化）")
        print(f'  {"成分":<10}{"良":>8}{"良以外":>9}{"差":>9}')
        for n_, x, y, z in dd[:10]:
            print(f'  {n_:<10}{x:>8.1f}{y:>9.1f}{z:>+9.1f}')

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "names": names,
               "results": [{k: (round(v, 2) if isinstance(v, float) else v)
                            for k, v in x.items()} for x in res],
               "tables": tables},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
