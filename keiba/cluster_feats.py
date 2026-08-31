# -*- coding: utf-8 -*-
"""cluster_feats.py — CLUSTER_PROTOCOL.md §3-1 のレースベクトル生成。

各レースを「そのレースの性質を表す19次元ベクトル」に変換する。
**全て発走前に知り得る量のみ。着順・払戻は一切入れない。**

入力:
  course_cache_meta.pkl  … 台帳メタ（頭数/距離/馬場/tier/オッズ）
  hist/<rid>.json        … 出馬表（脚質・キャリア・前走間隔）
  course_preds_gen.jsonl … 汎用モデルのOOSスコア（obj=place）※202403以降のみ存在

出力: cluster_feats.npz (F[N,19], rid, date, month) + cluster_feats_meta.pkl

usage: python3 cluster_feats.py
"""
import json
import os
import pickle
import time

import numpy as np

NPZ = "cluster_feats.npz"
META = "cluster_feats_meta.pkl"
GEN_PATH = "course_preds_gen.jsonl"

COLS = ["field", "dist", "is_dirt", "baba_idx", "tier", "day_no",
        "log_fav1_odds", "odds_sd", "top3_implied", "entropy",
        "score_gap12", "score_var_top5",
        "r_nige", "r_senko", "r_sashi", "r_oikomi",
        "mean_career", "log_mean_rest", "r_layoff"]

BABA_IDX = {"良": 0, "稍": 1, "稍重": 1, "重": 2, "不": 3, "不良": 3}
STYLE_KEY = {"逃": 12, "先": 13, "差": 14, "追": 15}


def load_gen_place():
    """{rid: {馬番: place score}}（汎用GENのOOSスコア・obj=place）"""
    g = {}
    with open(GEN_PATH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("obj") != "place" or d.get("method") != "GEN":
                continue
            g[d["rid"]] = dict(zip(d["ns"], d["scores"]))
    return g


def build():
    t0 = time.time()
    with open("course_cache_meta.pkl", "rb") as f:
        meta = pickle.load(f)
    meta = sorted(meta, key=lambda m: (m["date"], m["rid"]))
    gen = load_gen_place()
    print(f"meta {len(meta)}R / gen scores {len(gen)}R ({time.time()-t0:.0f}s)", flush=True)

    F, keep = [], []
    skipped = {"no_gen": 0, "no_hist": 0, "bad_odds": 0}
    for m in meta:
        rid = m["rid"]
        gs = gen.get(rid)
        if gs is None:
            skipped["no_gen"] += 1
            continue
        ns = list(m["ns"])
        odds = np.array([m["odds"].get(n, 0.0) for n in ns], dtype=float)
        if np.any(odds <= 0):
            skipped["bad_odds"] += 1
            continue
        hp = os.path.join("hist", f"{rid}.json")
        if not os.path.exists(hp):
            skipped["no_hist"] += 1
            continue
        with open(hp, encoding="utf-8") as f:
            hd = json.load(f)

        v = np.zeros(len(COLS), dtype=np.float64)
        v[0] = len(ns)
        v[1] = float(m["dist"] or 0)
        v[2] = 1.0 if m["surface"] == "ダ" else 0.0
        v[3] = float(BABA_IDX.get(m["baba"], 0))
        v[4] = float(m["tier"] or 0)
        v[5] = float(int(rid[8:10]))

        # ── 市場の分布形状
        imp = 1.0 / odds
        imp = imp / imp.sum()
        v[6] = float(np.log(odds.min()))
        v[7] = float(np.std(np.log10(odds)))
        v[8] = float(np.sort(imp)[::-1][:3].sum())
        v[9] = float(-(imp * np.log(imp)).sum())

        # ── モデルの分布形状（OOS汎用スコア・PLACE）
        s = np.array([gs.get(n, 0.0) for n in ns], dtype=float)
        ss = np.sort(s)[::-1]
        v[10] = float(ss[0] - ss[1]) if len(ss) >= 2 else 0.0
        v[11] = float(np.var(ss[:5])) if len(ss) >= 2 else 0.0

        # ── 出走馬の構成
        horses = hd["race"]["horses"]
        st = np.zeros(4)
        nst = 0
        careers, rests, lay = [], [], 0
        for h in horses:
            k = STYLE_KEY.get(h.get("paper_style"))
            if k is not None:
                st[k - 12] += 1
                nst += 1
            careers.append(len(h.get("races") or []))
            d = h.get("last_race_days")
            if d is not None:
                rests.append(float(d))
                lay += 1 if float(d) >= 90 else 0
        if nst:
            v[12:16] = st / nst
        v[16] = float(np.mean(careers)) if careers else 0.0
        v[17] = float(np.log1p(np.mean(rests))) if rests else 0.0
        v[18] = float(lay / len(rests)) if rests else 0.0

        F.append(v)
        keep.append(dict(rid=rid, date=m["date"], month=m["month"]))

    F = np.array(F, dtype=np.float64)
    np.savez_compressed(NPZ, F=F)
    with open(META, "wb") as f:
        pickle.dump(dict(cols=COLS, rows=keep), f)
    print(f"saved {NPZ} F={F.shape} skipped={skipped} ({time.time()-t0:.0f}s)")
    print("column means:", {c: round(float(F[:, i].mean()), 3) for i, c in enumerate(COLS)})


def load():
    z = np.load(NPZ)
    with open(META, "rb") as f:
        mm = pickle.load(f)
    return z["F"], mm["cols"], mm["rows"]


if __name__ == "__main__":
    build()
