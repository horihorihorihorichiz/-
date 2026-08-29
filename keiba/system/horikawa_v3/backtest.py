# -*- coding: utf-8 -*-
"""未知期間で、配点表の並びを単勝の回収率に換算して測る。

「どのレースを買うか」を決めるための足場。ここで測るのは
「モデルの1位を単勝で買い続けたらいくら戻るか」であって、買い目の推奨ではない。

  python backtest.py

注意: これは未知期間（date >= CUT_VAL）を覗く操作にあたる。
切り口を増やすほど、たまたま良く見えるものが混ざる。ここで測る切り口は
あらかじめ下の CUTS に固定してあり、思いついた条件を後から足さないこと。
足すなら、新しいデータで測り直す前提で足す。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402

W_PATH = "weights/hori_w.json"
EVAL_RAW = "../../data/hk_train_raw.json"

# 事前に決めた切り口。これ以外を後から足さない。
CUTS = [
    ("全体", lambda d: True),
    ("1位の単勝 3倍未満", lambda d: d["odds1"] < 3),
    ("1位の単勝 3〜10倍", lambda d: 3 <= d["odds1"] < 10),
    ("1位の単勝 10倍以上", lambda d: d["odds1"] >= 10),
    ("形 g12 < 0.5", lambda d: d["g12"] < 0.5),
    ("形 g12 0.5〜1.0", lambda d: 0.5 <= d["g12"] < 1.0),
    ("形 g12 >= 1.0", lambda d: d["g12"] >= 1.0),
]


def _fin(x):
    try:
        return int(x)
    except Exception:
        return None


def main():
    w = json.load(open(W_PATH, encoding="utf-8"))
    names, level = w["names"], w.get("level", "L1")
    use_tev = train_eval.NAME in names
    if use_tev:
        words, per_race = train_eval.load_evalcode(EVAL_RAW)
        tab, _info = train_eval.learn(config.DB_PATH, words, per_race, config.CUT_VAL)
        val = train_eval.value_map(per_race, tab)

    m = F.Model()
    m.names = names
    m.G = np.array(w["G"])
    for a in ("L1", "A", "B", "C"):
        setattr(m, a, {k: np.array(v) for k, v in w[a].items()})
    m.n, m.rep = w["n"], w["rep"]

    st = Store(config.DB_PATH)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)

    rows = []
    for ri, r in enumerate(book.races):
        if r["date"] >= config.CUT_VAL:
            d = b.build_wide(ri)
            Z = [list(x[:nf]) for x in d["Z"]]
            if use_tev:
                mm = val.get(r["id"]) or {}
                col = train_eval.znorm_column(
                    [mm.get(str(h["umaban"]), float("nan")) for h in r["rows"]])
                for row, x in zip(Z, col):
                    row.append(x)
            sc = np.array(Z, float) @ m.w(d["k"], level)
            o = sorted(range(len(sc)), key=lambda i: -sc[i])
            sd = float(np.std(sc)) or 1.0
            top = r["rows"][o[0]]
            if top["odds"] <= 0:
                continue
            fav = min(r["rows"], key=lambda h: h["odds"] if h["odds"] > 0 else 1e9)
            rows.append({
                "odds1": top["odds"], "win1": _fin(top["fin"]) == 1,
                "favodds": fav["odds"], "favwin": _fin(fav["fin"]) == 1,
                "sameAsFav": top["umaban"] == fav["umaban"],
                "g12": float((sc[o[0]] - sc[o[1]]) / sd) if len(sc) > 1 else 0.0,
            })
        b.advance(r)

    print(f"未知期間 {config.CUT_VAL} 以降 / 測れたレース {len(rows)}R\n")
    print(f'{"切り口":<20}{"R":>6}{"的中":>7}{"回収率":>8}{"±1SE":>8}{"市場":>8}{"差":>8}')
    for label, f in CUTS:
        s = [d for d in rows if f(d)]
        if not s:
            continue
        n = len(s)
        hit = sum(d["win1"] for d in s)
        pay = np.array([(d["odds1"] if d["win1"] else 0.0) for d in s])
        roi = pay.mean() * 100
        se = pay.std(ddof=1) / np.sqrt(n) * 100        # 回収率の標準誤差
        froi = np.mean([(d["favodds"] if d["favwin"] else 0.0) for d in s]) * 100
        print(f"{label:<20}{n:>6}{hit/n*100:>6.1f}%{roi:>7.1f}%{se:>7.1f}{froi:>7.1f}%{roi-froi:>+8.1f}")

    same = sum(d["sameAsFav"] for d in rows)
    print(f"\nモデルの1位が1番人気と同じだったレース: {same}/{len(rows)} ({same/len(rows)*100:.1f}%)")
    print("単勝の控除率は20%。回収率100%を越えて初めて買う意味がある。")


if __name__ == "__main__":
    main()
