# -*- coding: utf-8 -*-
"""WIN5 が獲れる見込みを、過去のレースで測る。

netkeiba の win5.html は kaisai_date を渡しても当日分しか返さないので、
過去の対象5レースは取れなかった。ただ WIN5 の本質は「1着を5連続で当てる」で、
どの5レースが指定されたかは大きくは効かない。そこで探索窓の実レースを
同じ日の中で5つずつ束ねて、全部の1着を当てられた割合を数える。

買い方は2通り:
  1点  各レース1頭（合成1位）
  N点  各レースの上位N頭を流す。的中率は上がるが点数は N^5 で増える

控除率は WIN5 が27.5%（単勝・複勝は20%）。壁はこちらのほうが高い。

窓は explore.py と同じ。未知期間には触れない。

  python win5.py
"""
import json
import os
import sys
from collections import defaultdict
from itertools import combinations

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
from boost import XPARAMS, to_matrix, build  # noqa: E402

OUT = "weights/win5.json"
NLINES = [1, 2, 3, 5]          # 各レースで何頭に流すか


def main():
    st = Store(config.DB_PATH)
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)
    wide = list(b.wide_names) + [train_eval.NAME]
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, nf, False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, nf, False)

    TRs = sorted(FIT, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=wide); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=wide); dv.set_group(gb)
    m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    best = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    dall = xgb.DMatrix(X, label=y, feature_names=wide); dall.set_group(g)
    model = xgb.train(XPARAMS, dall, num_boost_round=best)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 木 {best}本\n", flush=True)

    # レースごとに「上位N頭の中に1着がいるか」を出す
    by_day = defaultdict(list)
    for d in EXP:
        r = d["race"]
        s = np.asarray(model.predict(
            xgb.DMatrix(np.asarray(d["Z"], np.float32), feature_names=wide)), float)
        trank = np.argsort(np.argsort(-s))
        pops = np.array([h["pop"] if h["pop"] else 99 for h in r["rows"]], float)
        if (pops >= 99).all():
            continue
        blend = trank + np.argsort(np.argsort(pops))
        winner = next((i for i, h in enumerate(r["rows"]) if _fin(h["fin"]) == 1), None)
        if winner is None:
            continue
        tord = sorted(range(len(s)), key=lambda i: trank[i])
        bord = sorted(range(len(s)), key=lambda i: (blend[i], trank[i]))
        mord = sorted(range(len(s)), key=lambda i: pops[i])
        by_day[r["date"]].append({
            "id": r["id"],
            "tree": {n: winner in tord[:n] for n in NLINES},
            "blend": {n: winner in bord[:n] for n in NLINES},
            "market": {n: winner in mord[:n] for n in NLINES},
        })

    days = {k: v for k, v in by_day.items() if len(v) >= 5}
    print(f"5レース以上ある開催日 {len(days)}日 / のべ {sum(len(v) for v in days.values())}R")

    # 同じ日の中で5レースの束を作る。連続する5つを窓でずらす
    sets = []
    for d, rs in sorted(days.items()):
        rs.sort(key=lambda x: x["id"])
        for i in range(len(rs) - 4):
            sets.append(rs[i:i + 5])
    print(f"5レースの束 {len(sets)}通り\n")

    print(f'{"買い方":<22}{"点数":>7}{"5連続の的中率":>14}{"損益分岐に要る配当":>18}')
    out = []
    for src, lab in [("market", "市場（人気順）"), ("tree", "木48成分"), ("blend", "木48+市場 の合成")]:
        for n in NLINES:
            hit = sum(1 for s5 in sets if all(r[src][n] for r in s5))
            p = hit / len(sets)
            lines = n ** 5
            cost = lines * 100
            need = cost / p if p > 0 else float("inf")
            print(f'{lab + " 各" + str(n) + "頭":<22}{lines:>7}{p*100:>13.3f}%'
                  f'{(format(round(need), ",") + "円") if p else "—":>18}')
            out.append({"select": lab, "per_race": n, "lines": lines,
                        "hit_rate_pct": round(p * 100, 4),
                        "breakeven_payout": (None if not p else round(need))})
    print(f"\n束の数 {len(sets)}。的中は「5レース全部の1着を、その点数の中に入れられた」回数。")
    print("損益分岐に要る配当＝その点数を買い続けて元を取るのに必要な平均払戻。")
    print("実際の WIN5 の配当は数十万〜数億円で振れ幅が大きく、"
          "人気どころで決まった日は10万円台まで落ちる。")
    print("控除率は WIN5 が27.5%。単勝・複勝の20%より壁は高い。")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "n_days": len(days), "n_sets": len(sets), "results": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
