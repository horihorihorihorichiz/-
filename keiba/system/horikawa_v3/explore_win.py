# -*- coding: utf-8 -*-
"""1着を当てにいく配点を作って、3着内狙いの配点と比べる。

いまの配点は Plackett-Luce の尤度を「1着・2着・3着の順」まで取って学習している
（fit.py の pl_fit は for k in range(3)）。つまり最初から3着以内を当てにいく設計で、
1着だけを当てるようには最適化されていない。

_prepare は top を -1 で詰めるので、top に1着の添字だけ渡せば
2着・3着の項が消えて「1着だけの尤度」になる。hk は一切触らずに作れる。

窓は explore.py と同じ。未知期間には触れない。

  python explore_win.py
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

OUT = "weights/explore_win.json"


def retarget(DS, k):
    """top を先頭 k 個に切る。k=1 なら1着だけの尤度になる。"""
    return [dict(d, top=d["top"][:k]) for d in DS]


def measure(m, lv, EXP, pays):
    """1位が1着 / 1位が3着内 / 上位6頭で3着独占 / 単勝ROI / 複勝1位ROI。"""
    win = top3 = box6 = 0
    tan, fuku = [], []
    n = nf_ = 0
    for d in EXP:
        r = d["race"]
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        fins = [_fin(h["fin"]) for h in r["rows"]]
        n += 1
        if fins[o[0]] == 1:
            win += 1
        if fins[o[0]] is not None and fins[o[0]] <= 3:
            top3 += 1
        got = {fins[i] for i in o[:6]}
        if {1, 2, 3} <= got:
            box6 += 1
        h = r["rows"][o[0]]
        if h["odds"] > 0:
            tan.append(h["odds"] if fins[o[0]] == 1 else 0.0)
        p = pays.get(r["id"])
        if p and "複勝" in p:
            nf_ += 1
            fuku.append(dict(p["複勝"]).get(str(h["umaban"]), 0) / 100.0)
    f = lambda a: (np.mean(a) * 100, np.std(a, ddof=1) / np.sqrt(len(a)) * 100) if a else (0, 0)
    return {"n": n, "1位が1着": win / n * 100, "1位が3着内": top3 / n * 100,
            "上位6頭で3着独占": box6 / n * 100,
            "単勝ROI": f(tan), "複勝1位ROI": f(fuku), "n_pay": nf_}


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
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 払戻あり {len(pays)}件\n")

    res = {}
    for k, label in [(3, "3着内狙い（いまの配点）"), (1, "1着狙い（単勝仕立て）")]:
        TR = retarget(FIT, k)
        lv, _t = F.choose_level(TR, names)
        m = F.Model().fit(TR, names, verbose=False)
        res[label] = (measure(m, lv, EXP, pays), lv, m)
        print(f"{label}: 段階 {lv}")

    print()
    hdr = ["1位が1着", "1位が3着内", "上位6頭で3着独占"]
    print(f'{"":<26}' + "".join(f"{h:>14}" for h in hdr) + f'{"単勝ROI":>12}{"複勝1位ROI":>14}')
    for label, (r, lv, _m) in res.items():
        print(f"{label:<26}" + "".join(f"{r[h]:>13.2f}%" for h in hdr)
              + f'{r["単勝ROI"][0]:>11.1f}%{r["複勝1位ROI"][0]:>13.1f}%')

    a = res["3着内狙い（いまの配点）"][0]
    bq = res["1着狙い（単勝仕立て）"][0]
    print("\n差（1着狙い − 3着内狙い）")
    for h in hdr:
        print(f"  {h:<16}{bq[h]-a[h]:+.2f}pt")
    print(f'  {"単勝ROI":<16}{bq["単勝ROI"][0]-a["単勝ROI"][0]:+.1f}pt '
          f'(±1SE {a["単勝ROI"][1]:.1f} / {bq["単勝ROI"][1]:.1f})')
    print(f'  {"複勝1位ROI":<16}{bq["複勝1位ROI"][0]-a["複勝1位ROI"][0]:+.1f}pt '
          f'(±1SE {a["複勝1位ROI"][1]:.1f} / {bq["複勝1位ROI"][1]:.1f})')

    os.makedirs("weights", exist_ok=True)
    json.dump({label: {k: v for k, v in r.items()} for label, (r, _l, _m) in res.items()},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=list)
    print(f"\n書き出しました → {OUT}")
    print("控除率20%。ここは探索窓で、採否は未知期間で一度だけ測って決めること。")


if __name__ == "__main__":
    main()
