# -*- coding: utf-8 -*-
"""線形の配点表を学習して weights/hori_w.json に書き出す。

`python -m hk.cli fit` の代わり。処理は cmd_fit と同じだが、線形モデルに
渡す成分を「16成分 + 実測で効いた7つ（+ 調教3つ）」に絞る点だけが違う。

なぜ絞るか:
  cmd_fit は _dataset() が返す wide_names（47個）をそのまま線形モデルに渡す。
  その中の RAW_NAMES（前走着順・休養日数など14個）は初出走馬で NaN になる
  設計で、NaN を扱える木の学習器のためのもの。fit.py に NaN の処理は無いため、
  線形モデルに入ると重みが全て NaN になる。
  cmd_gbdt は線形と比べるとき names[:26] と明示的に切っている（cli.py:130）。
  ここでも同じ切り方をする。

hk/ の中身は上流のまま触っていない。
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F, predict as P  # noqa: E402
from hk.store import Store  # noqa: E402

W_PATH = "weights/hori_w.json"


def dataset(st):
    races = st.all_races()
    book = features.Book(races, config.CUT_HIST)
    oik = st.all_oikiri()
    if oik:
        print(f"  追い切り {len(oik)}レース分を使います（調教3成分を足します）")
    else:
        print("  追い切りが未取得なので、調教3成分は作りません")

    lin_names = list(features.BASE_NAMES) + (list(features.TRAIN_NAMES) if oik else [])
    nf = len(lin_names)

    b = features.WideBuilder(book, oikiri=oik, market=False)
    assert b.wide_names[:nf] == lin_names, "成分の並びが想定と違う"

    DS = []
    for ri, r in enumerate(book.races):
        if r["date"] >= config.CUT_HIST:
            d = b.build_wide(ri)
            d["Z"] = np.array([row[:nf] for row in d["Z"]], dtype=np.float32)
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS, lin_names


def main():
    st = Store(config.DB_PATH)
    print("成分を作ります")
    DS, names = dataset(st)
    TR = [d for d in DS if d["date"] < config.CUT_EMBARGO]
    print(f"学習 {len(TR)}R / 成分 {len(names)}個")

    Z = np.vstack([d["Z"] for d in TR])
    nanc = [names[j] for j in range(len(names)) if np.isnan(Z[:, j]).any()]
    flat = [names[j] for j in range(len(names)) if np.nanstd(Z[:, j]) == 0]
    if nanc:
        print(f"  警告: NaN を含む成分: {nanc}")
    if flat:
        print(f"  警告: 全馬同値で情報が無い成分: {flat}")

    lv, tab = F.choose_level(TR, names)
    m = F.Model().fit(TR, names)
    cal = P.build_calibration(TR, m, level=lv)
    os.makedirs("weights", exist_ok=True)
    out = {"names": names, "G": list(map(float, m.G)),
           "L1": {k: list(map(float, v)) for k, v in m.L1.items()},
           "A": {k: list(map(float, v)) for k, v in m.A.items()},
           "B": {k: list(map(float, v)) for k, v in m.B.items()},
           "C": {k: list(map(float, v)) for k, v in m.C.items()},
           "rep": {k: v for k, v in m.rep.items()},
           "n": {k: v for k, v in m.n.items()},
           "K": {k: [None if np.isinf(x) else float(x) for x in v] for k, v in m.K.items()},
           "calib": cal, "level": lv, "inner": tab}
    # 上流の cmd_fit は open(W_PATH, "w") で書くため、Windows では CP932 に
    # なってしまい他の環境から読めない。成分名やセル名が日本語なので UTF-8 で書く。
    json.dump(out, open(W_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"書き出しました → {W_PATH}")

    def norm(w):
        w = np.asarray(w, float)
        s = np.abs(w).mean() or 1.0
        return np.round(w / s * 30, 1)

    cells = ["芝S", "芝M", "芝L", "ダS", "ダM", "ダL"]
    g = norm(m.G)
    ws = {c: norm(m.L1[c]) for c in cells if c in m.L1}
    print("\n実効配点（平均絶対値=30に正規化）")
    print("成分".ljust(10) + "全体".rjust(8) + "".join(c.rjust(8) for c in cells))
    for j, nm in enumerate(names):
        print(nm.ljust(10) + f"{g[j]:8.1f}" +
              "".join(f"{ws[c][j]:8.1f}" if c in ws else "       -" for c in cells))


if __name__ == "__main__":
    main()
