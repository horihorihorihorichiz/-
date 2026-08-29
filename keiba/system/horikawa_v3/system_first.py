# -*- coding: utf-8 -*-
"""買う馬はシステムだけで決める。人気は最後に「どのレースを買うか」でだけ使う。

これまでの試みは、馬を選ぶ段階に人気を混ぜていた（「4-9番人気の中から選ぶ」など）。
それは市場の順序で先に絞ってから system を使うことになり、system の順序を
評価していない。

システム順位ごとの3着内率は 59.5 / 47.6 / 40.4 / 31.7 / 27.4 / 23.5 / 18.2 / 12.9%
と完全に単調で、システム順位はそのレースでの強さの順序として機能している。
だったら買う馬はシステム順位で決めるのが筋。

ここでは:
  馬の選択  … システム順位のみ（人気を一切見ない）
  レースの選択 … 人気・オッズをここでだけ使う

  python system_first.py
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

OUT = "weights/system_first.json"


def k2(a, b):
    x, y = sorted((int(a), int(b)))
    return f"{x}-{y}"


def k3(a, b, c):
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
        hs = [{"um": r["rows"][i]["umaban"], "pop": int(r["rows"][i]["pop"] or 99),
               "odds": r["rows"][i]["odds"]} for i in o]
        if len(hs) < 8 or hs[0]["odds"] <= 0:
            continue
        sd = float(np.std(sc)) or 1.0
        R.append({
            "hs": hs, "pay": pay,
            "g12": float((sc[o[0]] - sc[o[1]]) / sd),
            "odds1": hs[0]["odds"], "pop1": hs[0]["pop"],
            "pop123": np.mean([h["pop"] for h in hs[:3]]),
            "favpop_srank": next((k + 1 for k, h in enumerate(hs) if h["pop"] == 1), 99),
        })
    print(f"測れたレース {len(R)}R\n", flush=True)

    # 買う馬はシステム順位だけで決める
    def fuku1(rc):
        d = dict(rc["pay"].get("複勝", []))
        return [d.get(str(rc["hs"][0]["um"]), 0) / 100.0]

    def fuku123(rc):
        d = dict(rc["pay"].get("複勝", []))
        return [d.get(str(h["um"]), 0) / 100.0 for h in rc["hs"][:3]]

    def wide12(rc):
        d = dict(rc["pay"].get("ワイド", []))
        return [d.get(k2(rc["hs"][0]["um"], rc["hs"][1]["um"]), 0) / 100.0]

    def wide_box3(rc):
        d = dict(rc["pay"].get("ワイド", []))
        h = rc["hs"][:3]
        return [d.get(k2(h[i]["um"], h[j]["um"]), 0) / 100.0
                for i in range(3) for j in range(i + 1, 3)]

    def san123(rc):
        d = dict(rc["pay"].get("三連複", []))
        h = rc["hs"][:3]
        return [d.get(k3(h[0]["um"], h[1]["um"], h[2]["um"]), 0) / 100.0]

    def tan1(rc):
        d = dict(rc["pay"].get("単勝", []))
        return [d.get(str(rc["hs"][0]["um"]), 0) / 100.0]

    BETS = [("単勝 システム1位", tan1), ("複勝 システム1位", fuku1),
            ("複勝 システム1-3位", fuku123), ("ワイド システム1-2位", wide12),
            ("ワイド システム上位3頭BOX", wide_box3), ("三連複 システム1-3位", san123)]

    # レースの選択にだけ人気・オッズを使う
    FILTERS = [
        ("全レース", lambda d: True),
        ("システム1位が1番人気でない", lambda d: d["pop1"] != 1),
        ("システム1位の単勝3倍以上", lambda d: d["odds1"] >= 3),
        ("システム1位の単勝5倍以上", lambda d: d["odds1"] >= 5),
        ("1番人気がシステム4位以下", lambda d: d["favpop_srank"] >= 4),
        ("システム上位3頭の平均人気5以上", lambda d: d["pop123"] >= 5),
        ("1強 (g12>=1.0)", lambda d: d["g12"] >= 1.0),
        ("1強 かつ 1位が1番人気でない", lambda d: d["g12"] >= 1.0 and d["pop1"] != 1),
    ]

    print(f'{"レースの選択":<28}{"R":>6}' + "".join(f'{n:>22}' for n, _ in BETS))
    out = []
    for fl, f in FILTERS:
        sel = [rc for rc in R if f(rc)]
        if len(sel) < 60:
            print(f"{fl:<28}{len(sel):>6}   （レース数が足りない）")
            continue
        line = ""
        for bn, fn in BETS:
            pay = []
            for rc in sel:
                pay.extend(fn(rc))
            a = np.array(pay)
            roi = a.mean() * 100
            se = a.std(ddof=1) / np.sqrt(len(a)) * 100
            line += f"{roi:>15.1f}%±{se:<5.1f}"
            out.append({"filter": fl, "bet": bn, "races": len(sel), "bets": len(a),
                        "roi": round(float(roi), 1), "se": round(float(se), 1)})
        print(f"{fl:<28}{len(sel):>6}{line}")

    best = max(out, key=lambda x: x["roi"])
    print(f'\n最良: {best["roi"]}% ± {best["se"]}  '
          f'（{best["bet"]} / {best["filter"]} / {best["races"]}R）')
    print("控除率20%。100%を越えなければ買う理由にならない。")
    print("組み合わせは 8フィルタ × 6券種 = 48通り。偶然の当たりが混じる数なので、"
          "100%超えが出ても単独では採用しないこと。")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "level": lv,
               "n_races": len(R), "results": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {OUT}")


if __name__ == "__main__":
    main()
