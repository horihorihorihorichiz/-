# -*- coding: utf-8 -*-
"""役割を分けて組み替える。頭は市場、紐はシステム。

decompose.py で分かったこと（探索窓1,826R・25,206頭）:

  同じ人気の馬をシステム評価で3等分したときの3着内率の差（上位1/3 − 下位1/3）
    1番人気 +4.7pt(t=1.69) / 2番人気 -2.9pt / 3番人気 -0.4pt
    4-6番人気 +5.9pt(t=4.00) / 7-9番人気 +5.7pt(t=5.12) / 10番人気以下 +3.8pt(t=7.51)

  つまりシステムは、人気馬については市場に何も足していないが、
  市場が見放した馬の中では明確に強い馬を選べている。

だったら役割を分けるのが筋になる。**頭（軸）は市場の言う通りに取り、
相手（紐）だけシステムに選ばせる。** 両方の得意分野だけを使う形。

比較のため「市場だけ」の組み合わせも並べる。システムで紐を選ぶことが
人気で紐を選ぶより良いかどうかが、この組み替えの成否になる。

窓は explore.py と同じ。未知期間には触れない。

  python restructure.py
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

OUT = "weights/restructure.json"


def key2(a, b):
    x, y = sorted((int(a), int(b)))
    return f"{x}-{y}"


def key3(a, b, c):
    x, y, z = sorted((int(a), int(b), int(c)))
    return f"{x}-{y}-{z}"


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

    R = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay:
            continue
        sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        hs = []
        for k, i in enumerate(o):
            h = r["rows"][i]
            if not h["pop"] or h["odds"] <= 0:
                continue
            hs.append({"um": h["umaban"], "pop": int(h["pop"]), "srank": k + 1})
        if len(hs) < 8:
            continue
        bypop = sorted(hs, key=lambda x: x["pop"])
        R.append({"hs": hs, "bypop": bypop, "pay": pay})
    print(f"測れたレース {len(R)}R\n", flush=True)

    def sys_hole(rc, lo=4, hi=9):
        """人気 lo〜hi の中で、システム順位がいちばん上の馬。"""
        c = [h for h in rc["hs"] if lo <= h["pop"] <= hi]
        return min(c, key=lambda x: x["srank"]) if c else None

    def pop_hole(rc, lo=4, hi=9):
        """同じ帯から、人気がいちばん上の馬（市場だけで選ぶ対照）。"""
        c = [h for h in rc["hs"] if lo <= h["pop"] <= hi]
        return min(c, key=lambda x: x["pop"]) if c else None

    def rnd_hole(rc, lo=4, hi=9, rng=np.random.default_rng(7)):
        c = [h for h in rc["hs"] if lo <= h["pop"] <= hi]
        return c[int(rng.integers(len(c)))] if c else None

    def wide(rc, a, bq):
        return dict(rc["pay"].get("ワイド", [])).get(key2(a["um"], bq["um"]), 0) / 100.0

    def uren(rc, a, bq):
        return dict(rc["pay"].get("馬連", [])).get(key2(a["um"], bq["um"]), 0) / 100.0

    def sanfuku(rc, a, bq, c):
        return dict(rc["pay"].get("三連複", [])).get(key3(a["um"], bq["um"], c["um"]), 0) / 100.0

    def fuku(rc, a):
        return dict(rc["pay"].get("複勝", [])).get(str(a["um"]), 0) / 100.0

    PLANS = []

    def plan(label, fn):
        PLANS.append((label, fn))

    plan("ワイド 1番人気 × システムの穴(4-9人気)",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][0], h)] if h else None)(sys_hole(rc)))
    plan("ワイド 1番人気 × 人気の穴(4-9人気)  ※対照",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][0], h)] if h else None)(pop_hole(rc)))
    plan("ワイド 1番人気 × 無作為の穴(4-9人気) ※対照",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][0], h)] if h else None)(rnd_hole(rc)))
    plan("ワイド 2番人気 × システムの穴(4-9人気)",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][1], h)] if h else None)(sys_hole(rc)))
    plan("馬連 1番人気 × システムの穴(4-9人気)",
         lambda rc: (lambda h: [uren(rc, rc["bypop"][0], h)] if h else None)(sys_hole(rc)))
    plan("馬連 1番人気 × 人気の穴(4-9人気)   ※対照",
         lambda rc: (lambda h: [uren(rc, rc["bypop"][0], h)] if h else None)(pop_hole(rc)))
    plan("三連複 1・2番人気 × システムの穴(4-9人気)",
         lambda rc: (lambda h: [sanfuku(rc, rc["bypop"][0], rc["bypop"][1], h)] if h else None)(sys_hole(rc)))
    plan("三連複 1・2番人気 × 人気の穴(4-9人気) ※対照",
         lambda rc: (lambda h: [sanfuku(rc, rc["bypop"][0], rc["bypop"][1], h)] if h else None)(pop_hole(rc)))
    plan("複勝 システムの穴(4-9人気) 単体",
         lambda rc: (lambda h: [fuku(rc, h)] if h else None)(sys_hole(rc)))
    plan("複勝 人気の穴(4-9人気) 単体      ※対照",
         lambda rc: (lambda h: [fuku(rc, h)] if h else None)(pop_hole(rc)))
    plan("ワイド 1番人気 × システムの穴(10人気以下)",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][0], h)] if h else None)(sys_hole(rc, 10, 99)))
    plan("ワイド 1番人気 × 無作為の穴(10人気以下) ※対照",
         lambda rc: (lambda h: [wide(rc, rc["bypop"][0], h)] if h else None)(rnd_hole(rc, 10, 99)))

    print(f'{"買い方":<44}{"R":>6}{"的中":>8}{"回収率":>9}{"±1SE":>8}')
    out = []
    for label, fn in PLANS:
        pay = []
        for rc in R:
            v = fn(rc)
            if v is None:
                continue
            pay.extend(v)
        if len(pay) < 100:
            print(f"{label:<44}{len(pay):>6}   （本数が足りない）")
            continue
        a = np.array(pay)
        print(f"{label:<44}{len(a):>6}{(a > 0).mean()*100:>7.1f}%"
              f"{a.mean()*100:>8.1f}%{a.std(ddof=1)/np.sqrt(len(a))*100:>8.1f}")
        out.append({"plan": label, "n": len(a), "hit": round(float((a > 0).mean() * 100), 1),
                    "roi": round(float(a.mean() * 100), 1),
                    "se": round(float(a.std(ddof=1) / np.sqrt(len(a)) * 100), 1)})

    print("\n※対照 と比べて、システムで紐を選ぶほうが良いかどうかが組み替えの成否。")
    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "level": lv,
               "n_races": len(R), "plans": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {OUT}")


if __name__ == "__main__":
    main()
