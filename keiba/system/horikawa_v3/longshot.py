# -*- coding: utf-8 -*-
"""システム1位なのにオッズが高い馬だけを見る。

発想: システムがそのレースで一番強いと言っている馬を、市場が10倍以上に
放置している。両者の食い違いが最大になる点で、もし勝てる場所があるならここ。

これまでの断片:
  探索窓  10-20倍 n=47 回収率 93.0% / 20倍以上 n=14 291.4%
  未知期間 10倍以上 n=55 回収率 126.4%（backtest.py の事前登録した切り口）

両方の窓で100%を越えた唯一の場所。ただし本数が極端に少なく、的中も数本しかない。
ここでは本数・的中の内訳・ブートストラップ信頼区間・「何本ずれたら結論が変わるか」
まで出して、判断できる形にする。

窓は explore.py と同じ（未知期間には触れない）。

  python longshot.py
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

OUT = "weights/longshot.json"
RNG = np.random.default_rng(20260831)
NBOOT = 20000


def ci(a, lo=2.5, hi=97.5):
    idx = RNG.integers(0, len(a), size=(NBOOT, len(a)))
    means = a[idx].mean(1)
    return np.percentile(means, lo) * 100, np.percentile(means, hi) * 100


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
    lv, _ = F.choose_level(FIT, names)
    m = F.Model().fit(FIT, names, verbose=False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True, nf)
    print(f"学習 {len(FIT)}R / 探索 {len(EXP)}R / 段階 {lv}\n", flush=True)

    rows = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay:
            continue
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        i = int(np.argmax(sc))
        h = r["rows"][i]
        if h["odds"] <= 0:
            continue
        tan = dict(pay.get("単勝", []))
        fuk = dict(pay.get("複勝", []))
        rows.append({"odds": h["odds"], "pop": int(h["pop"] or 99),
                     "fin": _fin(h["fin"]),
                     "tan": tan.get(str(h["umaban"]), 0) / 100.0,
                     "fuku": fuk.get(str(h["umaban"]), 0) / 100.0})
    print(f"システム1位が採れたレース {len(rows)}R\n", flush=True)

    out = []
    for lab, lo in [("7倍以上", 7.0), ("10倍以上", 10.0), ("15倍以上", 15.0), ("20倍以上", 20.0)]:
        s = [d for d in rows if d["odds"] >= lo]
        if len(s) < 10:
            print(f"{lab}: n={len(s)} 少なすぎる")
            continue
        tan = np.array([d["tan"] for d in s])
        fuku = np.array([d["fuku"] for d in s])
        wins = [d for d in s if d["fin"] == 1]
        in3 = [d for d in s if d["fin"] is not None and d["fin"] <= 3]
        tlo, thi = ci(tan)
        flo, fhi = ci(fuku)
        need = 1.0 / np.mean([d["odds"] for d in s])
        print(f"── システム1位が {lab}")
        print(f"   レース数 {len(s)}　平均オッズ {np.mean([d['odds'] for d in s]):.1f}倍")
        print(f"   1着 {len(wins)}本（的中率 {len(wins)/len(s)*100:.1f}%／"
              f"損益分岐に要る的中率 {need*100:.1f}%）　3着内 {len(in3)}本")
        print(f"   単勝回収率 {tan.mean()*100:.1f}%　95%信頼区間 [{tlo:.0f}, {thi:.0f}]")
        print(f"   複勝回収率 {fuku.mean()*100:.1f}%　95%信頼区間 [{flo:.0f}, {fhi:.0f}]")
        if wins:
            paid = sorted((d["tan"] for d in wins), reverse=True)
            print(f"   的中の払戻: " + " / ".join(f"{p*100:.0f}円" for p in paid[:6]))
            drop = (tan.sum() - paid[0]) / len(s) * 100
            print(f"   いちばん大きい的中1本を外すと {drop:.1f}% に落ちる")
        out.append({"band": lab, "n": len(s), "wins": len(wins), "in3": len(in3),
                    "tan_roi": round(float(tan.mean() * 100), 1),
                    "tan_ci": [round(tlo), round(thi)],
                    "fuku_roi": round(float(fuku.mean() * 100), 1),
                    "fuku_ci": [round(flo), round(fhi)]})
        print()

    print("判断のしかた: 信頼区間の下端が100%を割っていれば、"
          "この本数では「勝てる」と言い切れない。")
    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "level": lv,
               "n_races": len(rows), "bands": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {OUT}")


if __name__ == "__main__":
    main()
