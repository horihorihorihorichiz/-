# -*- coding: utf-8 -*-
"""複勝とワイドで測る。このモデルが実際に狙っているのは3着以内。

単勝で測るのは的が違う。看板の数字は「1位が3着内 59.15%」と
「上位6頭で3着独占 42.77%」で、当てにいっているのは1着ではなく3着以内。
単勝は的中27%・分散が大きく、控除率も同じ20%なのに情報を捨てている。

窓は explore.py と同じ。未知期間（CUT_VAL 以降）には触れない。
払戻は harvest_payouts.py で取り込んだものを使う。

  python explore_place.py
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

OUT = "weights/explore_place.json"

# 買い方。返すのは (賭けた点数, 払戻円の合計)。払戻は100円あたり。
def bet_fuku(pick, pay):
    f = dict(pay.get("複勝", []))
    return len(pick), sum(f.get(str(u), 0) for u in pick)


def bet_wide(pick, pay):
    w = dict(pay.get("ワイド", []))
    hit = 0
    n = 0
    for i in range(len(pick)):
        for j in range(i + 1, len(pick)):
            n += 1
            a, b = sorted((int(pick[i]), int(pick[j])))
            hit += w.get(f"{a}-{b}", 0)
    return n, hit


BETS = [
    ("複勝 1位", lambda o: o[:1], bet_fuku),
    ("複勝 1〜2位", lambda o: o[:2], bet_fuku),
    ("複勝 1〜3位", lambda o: o[:3], bet_fuku),
    ("ワイド 1位-2位", lambda o: o[:2], bet_wide),
    ("ワイド 上位3頭ボックス", lambda o: o[:3], bet_wide),
]

# 事前に決めた切り口。後から足さない。
CUTS = [
    ("全体", lambda d: True),
    ("1位が1番人気", lambda d: d["pop1"] == 1),
    ("1位が2〜3番人気", lambda d: 2 <= d["pop1"] <= 3),
    ("1位が4番人気以下", lambda d: d["pop1"] >= 4),
    ("形 1強 (g12>=1.0)", lambda d: d["g12"] >= 1.0),
    ("形 混戦 (g12<0.5)", lambda d: d["g12"] < 0.5),
]


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    print(f"払戻を持っているレース {len(pays)}件")

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
    print(f"学習 {len(FIT)}R / 探索 {len(EXP)}R / 段階 {lv}\n")

    rows = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay or "複勝" not in pay:
            continue
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        um = [r["rows"][i]["umaban"] for i in o]
        top = r["rows"][o[0]]
        if not top["pop"]:
            continue
        sd = float(np.std(sc)) or 1.0
        # 人気順に買った場合を比べる相手にする
        byp = [h["umaban"] for h in sorted(r["rows"], key=lambda h: h["pop"] or 99)]
        rows.append({"um": um, "byp": byp, "pay": pay, "pop1": int(top["pop"]),
                     "g12": float((sc[o[0]] - sc[o[1]]) / sd) if len(sc) > 1 else 0.0})

    print(f"測れたレース {len(rows)}R")
    print("回収率は100円あたり。控除率20%なので、何もしなければ80%前後に落ちる。\n")

    out = []
    for bname, sel, fn in BETS:
        print(f"── {bname}")
        print(f'  {"切り口":<20}{"R":>6}{"回収率":>8}{"±1SE":>7}{"人気順で同じ買い方":>10}{"差":>8}{"t":>7}')
        for cname, f in CUTS:
            s = [d for d in rows if f(d)]
            if len(s) < 30:
                print(f"  {cname:<20}{len(s):>6}   （本数が足りないので測らない）")
                continue
            mine, mkt = [], []
            for d in s:
                n1, p1 = fn(sel(d["um"]), d["pay"])
                n2, p2 = fn(sel(d["byp"]), d["pay"])
                mine.append(p1 / (n1 * 100))
                mkt.append(p2 / (n2 * 100))
            a, bb = np.array(mine), np.array(mkt)
            diff = a - bb
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if diff.std(ddof=1) else 0.0
            se = a.std(ddof=1) / np.sqrt(len(a)) * 100
            print(f"  {cname:<20}{len(s):>6}{a.mean()*100:>7.1f}%{se:>7.1f}"
                  f"{bb.mean()*100:>9.1f}%{(a.mean()-bb.mean())*100:>+8.1f}{t:>7.2f}")
            out.append({"bet": bname, "cut": cname, "n": len(s),
                        "roi": round(a.mean() * 100, 1), "se": round(se, 1),
                        "market_roi": round(bb.mean() * 100, 1),
                        "t_vs_market": round(float(t), 2)})
        print()

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": {"fit": [config.CUT_HIST, CUT_EXPLORE],
                          "explore": [CUT_EXPLORE, config.CUT_EMBARGO]},
               "level": lv, "n": len(rows), "results": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {OUT}")
    print("ここは探索窓。採否は未知期間で一度だけ測って決めること。")


if __name__ == "__main__":
    main()
