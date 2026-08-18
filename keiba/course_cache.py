# -*- coding: utf-8 -*-
"""course_system.py 用の特徴行列キャッシュ。

build_row(=fit_v2) は純関数なので、全レース分を一度だけ作って npz に固める。
これが無いと 1 fold の学習ごとに 10 分近く行生成に費やす（実測）ため、
方式3（全データ学習×コース重み）が計算量的に不可能になる。

出力: course_cache.npz  (X: float32[N,F], y_top3, y_win, race_idx, 他メタは pkl)
"""
import pickle
import time

import numpy as np

import fit_v2 as V2
import wf_compare as W

SPEC = dict(v4=False, v8="f1,f2,f4")     # = fit_place.PLACE_VARIANTS["v8place"] の特徴部
NPZ = "course_cache.npz"
META = "course_cache_meta.pkl"


def build():
    t0 = time.time()
    ds = W.load_ds(False, v8=True)
    ds = sorted(ds, key=lambda r: (r["date"], r["rid"]))
    print(f"dataset {len(ds)}R ({time.time()-t0:.0f}s)", flush=True)
    X, yw, yp, ridx = [], [], [], []
    meta = []
    for i, r in enumerate(ds):
        win = r["top3"][0]
        inm = set(r["top3"])
        for n in r["ns"]:
            X.append(V2.build_row(r, n, SPEC["v4"], False, False, SPEC["v8"]))
            yw.append(1.0 if n == win else 0.0)
            yp.append(1.0 if n in inm else 0.0)
            ridx.append(i)
        meta.append(dict(rid=r["rid"], date=r["date"], month=r["date"][:6],
                         venue=r["venue"], surface=r["surface"], dist=int(r["dist"] or 0),
                         tier=int(r["tier"] or 0), baba=r["baba"],
                         ns=list(r["ns"]), top3=list(r["top3"]),
                         odds={int(k): float(v) for k, v in r["odds"].items()},
                         payout=r.get("payout") or {}))
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(ds)} ({time.time()-t0:.0f}s)", flush=True)
    X = np.array(X, dtype=np.float32)
    np.savez_compressed(NPZ, X=X, y_win=np.array(yw, dtype=np.float32),
                        y_place=np.array(yp, dtype=np.float32),
                        ridx=np.array(ridx, dtype=np.int32))
    with open(META, "wb") as f:
        pickle.dump(meta, f)
    print(f"saved {NPZ} X={X.shape} / {META} {len(meta)}R ({(time.time()-t0)/60:.1f}min)")


def load():
    z = np.load(NPZ)
    with open(META, "rb") as f:
        meta = pickle.load(f)
    return z["X"], z["y_win"], z["y_place"], z["ridx"], meta


if __name__ == "__main__":
    build()
