# -*- coding: utf-8 -*-
"""レースを細かく切ると当たるようになるのか、段階ごとに測る。

配点は4段ある。

    全体1本      1セル
    6群         芝ダ × 距離帯            6セル
    場+クラス    場 と クラスを足し合わせ    57 + 30セル
    コース単位    場 × 芝ダ × 距離帯 × クラス × 回り   266セル

細かくすればその条件に合った配点になるが、1セルあたりのレース数が減って
推定が荒くなる。どちらが勝つかは測らないと分からない。

explore.py と同じ窓を使う。未知期間（CUT_VAL 以降）には触れない。

  python check_levels.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
from explore import CUT_EXPLORE, EVAL_RAW, build, _fin  # noqa: E402

LEVELS = [("G", "全体1本"), ("L1", "6群"), ("mid", "場+クラス"), ("C", "コース単位")]


def main():
    st = Store(config.DB_PATH)
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    names = list(features.BASE_NAMES) + [train_eval.NAME]
    nf = len(features.BASE_NAMES)
    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)

    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True, nf)
    m = F.Model().fit(FIT, names, verbose=False)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True, nf)
    print(f"学習 {len(FIT)}R ({config.CUT_HIST}〜{CUT_EXPLORE}) / "
          f"測定 {len(EXP)}R ({CUT_EXPLORE}〜{config.CUT_EMBARGO})")
    print(f"セル数: 6群 {len(m.L1)} / 場 {len(m.A)} / クラス {len(m.B)} / コース単位 {len(m.C)}\n")

    rows, per, roi = {}, {}, {}
    for lv, nm in LEVELS:
        rows[nm], per[nm] = F.evaluate(EXP, m, lv)
        pay = []
        for d in EXP:
            sc = np.asarray(d["Z"], float) @ m.w(d["k"], lv)
            top = d["race"]["rows"][int(np.argmax(sc))]
            if top["odds"] > 0:
                pay.append(top["odds"] if _fin(top["fin"]) == 1 else 0.0)
        roi[nm] = (np.mean(pay) * 100, np.std(pay, ddof=1) / np.sqrt(len(pay)) * 100)

    print(f'{"段階":<12}{"セル":>6}{"1位が1着":>10}{"1位が3着内":>11}'
          f'{"上位6頭で3着独占":>14}{"単勝回収率":>11}')
    ncell = {"全体1本": 1, "6群": len(m.L1), "場+クラス": len(m.A) + len(m.B), "コース単位": len(m.C)}
    for lv, nm in LEVELS:
        r = rows[nm]
        vals = [v for k, v in r.items() if k != "n"]
        print(f'{nm:<12}{ncell[nm]:>6}' + "".join(f"{v:>10.2f}%" for v in vals[:3])
              + f'{roi[nm][0]:>10.1f}%')

    print("\n全体1本との差（対応のある検定・規律は t>3.0 で採用）")
    for lv, nm in LEVELS[1:]:
        line = []
        for i, lab in enumerate(["1位が1着", "1位が3着内", "上位6頭で3着独占"]):
            d = F.mcnemar(per[nm], per["全体1本"], i)
            line.append(f'{lab} {d["差pt"]:+.2f}pt (t={d["t"]:.2f})')
        print(f"  {nm:<10} " + " / ".join(line))

    print("\n単勝回収率（±1SE）")
    for lv, nm in LEVELS:
        print(f"  {nm:<10} {roi[nm][0]:>6.1f}% ± {roi[nm][1]:.1f}")


if __name__ == "__main__":
    main()
