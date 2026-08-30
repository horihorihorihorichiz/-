# -*- coding: utf-8 -*-
"""前走人気（市場由来）を抜いた木を、入れた木と比べる。

ユーザーの指針: 市場をメイン評価にすると市場次第になる。過去走・タイムの
事実で高めたい。木が使う市場由来の成分は「前走人気」ただ1つなので、
それを抜けば木は完全に市場非依存になる。的中率だけでなく安定性（月ごとの
3着内率のばらつき）でも比べる。

窓は explore.py と同じ。未知期間には触れない。

  python test_nopop.py
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
from boost import XPARAMS, build  # noqa: E402


def main():
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)
    st = Store(config.DB_PATH)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)
    names = list(b.wide_names) + [train_eval.NAME]
    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, nf, False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, nf, False)
    pop_idx = names.index("前走人気")

    def run(drop_pop):
        keep = [i for i in range(len(names)) if not (drop_pop and i == pop_idx)]
        nm = [names[i] for i in keep]

        def mat(DS):
            X = np.vstack([np.asarray(d["Z"], np.float32)[:, keep] for d in DS])
            g = [len(d["Z"]) for d in DS]
            y = []
            for d in DS:
                for o in d["ord"]:
                    y.append(3 if o == 1 else (2 if o == 2 else (1 if o == 3 else 0)))
            return X, np.array(y, np.float32), g

        TRs = sorted(FIT, key=lambda d: d["date"])
        X, y, g = mat(TRs)
        dm = xgb.DMatrix(X, label=y, feature_names=nm)
        dm.set_group(g)
        m = xgb.train(XPARAMS, dm, num_boost_round=74)

        by_month = defaultdict(lambda: [0, 0])
        win = i3 = n = 0
        tan, fuku = [], []
        for d in EXP:
            r = d["race"]
            s = m.predict(xgb.DMatrix(np.asarray(d["Z"], np.float32)[:, keep],
                                      feature_names=nm))
            i = int(np.argmax(s))
            h = r["rows"][i]
            f = _fin(h["fin"])
            n += 1
            win += (f == 1)
            i3 += (f is not None and f <= 3)
            mo = r["date"][4:6]
            by_month[mo][1] += 1
            by_month[mo][0] += (f is not None and f <= 3)
            p = pays.get(r["id"])
            if p:
                tan.append(dict(p.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0)
                fuku.append(dict(p.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0)
        rates = [c[0] / c[1] * 100 for c in by_month.values() if c[1] >= 30]
        return {"n_feat": len(nm), "win": win / n * 100, "in3": i3 / n * 100,
                "tan": np.mean(tan) * 100, "fuku": np.mean(fuku) * 100,
                "m_mean": np.mean(rates), "m_sd": np.std(rates), "m_min": min(rates)}

    print("=== 前走人気を入れる vs 抜く（探索窓1,826R）===\n")
    for drop in (False, True):
        r = run(drop)
        lab = "抜く（市場に一切依存しない木）" if drop else "入れる（現状の木）"
        print(f"{lab}")
        print(f"  成分 {r['n_feat']}個   1着 {r['win']:.2f}%   3着内 {r['in3']:.2f}%"
              f"   単勝 {r['tan']:.1f}%   複勝 {r['fuku']:.1f}%")
        print(f"  月ごとの3着内率: 平均 {r['m_mean']:.1f}%  ばらつき(SD) {r['m_sd']:.2f}"
              f"  最低の月 {r['m_min']:.1f}%\n")
    print("市場(1番人気)の3着内率は 65.28%。SDが小さいほど、月によってブレない＝揺るがない。")


if __name__ == "__main__":
    main()
