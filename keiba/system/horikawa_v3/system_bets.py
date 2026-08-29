# -*- coding: utf-8 -*-
"""買う馬も、レースの選択も、システムだけで決めて測る。人気は一切使わない。

これまでの買い方の測定（patterns.py / restructure.py / system_first.py）は
2つとも古い:

  1 「穴」を人気で定義していた（4-9番人気の中から選ぶ、など）。
    それは市場の順序で先に絞ってからシステムを使うことになる。
  2 モデルが線形24成分だった。木48成分のほうが明確に強いと分かった後も
    測り直していない。

ここでは木48成分（と、木+市場の合成）だけで軸と相手を決める。レースの選択も
システム側の量（1位と2位の得点差など）だけで行う。

窓は explore.py と同じ。未知期間には触れない。

  python system_bets.py
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
from explore import CUT_EXPLORE, EVAL_RAW  # noqa: E402
from boost import XPARAMS, to_matrix, build  # noqa: E402

OUT = "weights/system_bets.json"


def k2(a, b):
    x, y = sorted((int(a), int(b)))
    return f"{x}-{y}"


def k3(a, b, c):
    x, y, z = sorted((int(a), int(b), int(c)))
    return f"{x}-{y}-{z}"


def bets(pay, um):
    """um は選択順（システム順）に並んだ馬番。100円あたりの回収額を返す。"""
    tan = dict(pay.get("単勝", []))
    fuk = dict(pay.get("複勝", []))
    wid = dict(pay.get("ワイド", []))
    san = dict(pay.get("三連複", []))
    w3 = [wid.get(k2(um[i], um[j]), 0) for i in range(3) for j in range(i + 1, 3)]
    return {
        "単勝1位": tan.get(str(um[0]), 0) / 100.0,
        "複勝1位": fuk.get(str(um[0]), 0) / 100.0,
        "複勝1-3位": sum(fuk.get(str(u), 0) for u in um[:3]) / 300.0,
        "ワイド1-2位": wid.get(k2(um[0], um[1]), 0) / 100.0,
        "ワイド上位3BOX": sum(w3) / 300.0,
        "三連複1-3位": san.get(k3(um[0], um[1], um[2]), 0) / 100.0,
    }


BETNAMES = ["単勝1位", "複勝1位", "複勝1-3位", "ワイド1-2位", "ワイド上位3BOX", "三連複1-3位"]


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}

    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)
    wide = list(b.wide_names) + [train_eval.NAME]
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, nf, False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, nf, False)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R", flush=True)

    TRs = sorted(FIT, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=wide); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=wide); dv.set_group(gb)
    mm = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    best = (mm.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    dall = xgb.DMatrix(X, label=y, feature_names=wide); dall.set_group(g)
    model = xgb.train(XPARAMS, dall, num_boost_round=best)
    print(f"木の本数 {best}本\n", flush=True)

    rows = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay:
            continue
        Z = np.asarray(d["Z"], np.float32)
        s = np.asarray(model.predict(xgb.DMatrix(Z, feature_names=wide)), float)
        trank = np.argsort(np.argsort(-s))
        pops = np.array([h["pop"] if h["pop"] else 99 for h in r["rows"]], float)
        if (pops >= 99).all():
            continue
        blend = trank + np.argsort(np.argsort(pops))
        tord = sorted(range(len(s)), key=lambda i: trank[i])
        bord = sorted(range(len(s)), key=lambda i: (blend[i], trank[i]))
        if len(tord) < 4:
            continue
        sd = float(np.std(s)) or 1.0
        o = [r["rows"][i]["odds"] for i in tord]
        rows.append({
            "tree": bets(pay, [r["rows"][i]["umaban"] for i in tord]),
            "blend": bets(pay, [r["rows"][i]["umaban"] for i in bord]),
            # 発走前に分かる量だけ。ワイドの払戻で絞ると結果を見て選ぶことになる
            "o1": o[0], "o2": o[1], "omul": o[0] * o[1], "omin": min(o[0], o[1]),
            # レースの選択に使う量。どれもシステム側だけで決まる
            "g12": float((s[tord[0]] - s[tord[1]]) / sd),
            "g13": float((s[tord[0]] - s[tord[2]]) / sd),
            "spread": float(s.max() - s.min()) / sd,
            "n": r["n"],
        })
    print(f"測れたレース {len(rows)}R", flush=True)
    print("回収率は100円あたり。控除率20%なので、何もしなければ80%前後に落ちる。\n")

    FILTERS = [
        ("全レース", lambda d: True),
        ("木の1-2位差 大 (g12>=1.0)", lambda d: d["g12"] >= 1.0),
        ("木の1-2位差 中 (0.4-1.0)", lambda d: 0.4 <= d["g12"] < 1.0),
        ("木の1-2位差 小 (<0.4)", lambda d: d["g12"] < 0.4),
        ("木の1-3位差 大 (g13>=1.5)", lambda d: d["g13"] >= 1.5),
        ("得点の広がり 大 (>=3.0)", lambda d: d["spread"] >= 3.0),
        ("少頭数 (<=12)", lambda d: d["n"] <= 12),
        ("多頭数 (>=15)", lambda d: d["n"] >= 15),
        # 木1位・2位の単勝オッズで絞る（ワイドの配当の代わり。発走前に分かる）
        ("木1-2位の単勝の積 >=20", lambda d: d["omul"] >= 20),
        ("木1-2位の単勝の積 >=50", lambda d: d["omul"] >= 50),
        ("木1-2位の単勝の積 >=100", lambda d: d["omul"] >= 100),
        ("木1-2位とも5倍以上", lambda d: d["omin"] >= 5),
        ("木1位が10倍以上", lambda d: d["o1"] >= 10),
    ]

    out = []
    for src in ("tree", "blend"):
        lab = "木48成分だけで選ぶ" if src == "tree" else "木48+市場 の合成で選ぶ"
        print(f"── {lab}")
        print(f'  {"レースの選択":<26}{"R":>5}' + "".join(f"{x:>15}" for x in BETNAMES))
        for fl, f in FILTERS:
            sel = [d for d in rows if f(d)]
            if len(sel) < 80:
                print(f"  {fl:<26}{len(sel):>5}   （レース数が足りない）")
                continue
            line = ""
            for bn in BETNAMES:
                a = np.array([d[src][bn] for d in sel])
                line += f"{a.mean()*100:>10.1f}%±{a.std(ddof=1)/np.sqrt(len(a))*100:<4.1f}"
                out.append({"select": lab, "filter": fl, "bet": bn, "races": len(sel),
                            "roi": round(float(a.mean() * 100), 1),
                            "se": round(float(a.std(ddof=1) / np.sqrt(len(a)) * 100), 1)})
            print(f"  {fl:<26}{len(sel):>5}{line}")
        print()

    best_ = max(out, key=lambda x: x["roi"])
    print(f'最良 {best_["roi"]}% ±{best_["se"]}  '
          f'（{best_["bet"]} / {best_["select"]} / {best_["filter"]} / {best_["races"]}R）')
    over = [x for x in out if x["roi"] >= 100]
    print(f'100%を越えたマス {len(over)}個 / {len(out)}通り中')
    for x in sorted(over, key=lambda x: -x["roi"])[:8]:
        print(f'  {x["roi"]:>6.1f}% ±{x["se"]:<4.1f} {x["bet"]:<14}{x["filter"]:<26}{x["select"]}')

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "n_races": len(rows),
               "rounds": best, "results": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")
    print("2通りの選び方 × 8つのレース選択 × 6券種 = 96通り。"
          "偶然の当たりが混じる数なので、100%超えが出ても単独では採用しないこと。")


if __name__ == "__main__":
    main()
