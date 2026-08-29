# -*- coding: utf-8 -*-
"""展開と馬場を、合成する前の生の値で木に渡してみる。馬場ごとの学習も試す。

いまの作り方は情報を潰している:

  展開乗数 = PACE_TAB[ペース-1][脚質]
    ペース5段階 × 脚質4段階 を、作る側が決めた20個の定数に畳んでいる。
    木は組み合わせを自分で学べるので、畳んでから渡す意味が無い。
    しかも脚質が不明な馬（通過順の履歴なし）は丸ごと欠測になる。

  TAS = 道悪での平均着順比を 10 / 5 / 0 の3段階に丸めたもの
    何走分の実績かも、良馬場のときと比べてどうかも消えている。

そこで生の値に分解して足す:

  P1 脚質rr      過去5走の4角通過順 ÷ 頭数 の平均（連続値）
  P2 脚質バケツ    0=逃げ 1=先行 2=差し 3=追込（不明は欠測）
  P3 想定ペース    レース単位。先行馬の多さから5段階
  P4 先行馬率     レース単位。連続値。P3 の元
  G1 道悪の出走数   過去1年、良馬場以外
  G2 道悪の着順比   その平均
  G3 良馬場の着順比  比較の土台
  G4 道悪−良      小さいほど道悪で走る馬

そのうえで、馬場ごとに別々の木を作る案も測る。

窓は explore.py と同じ。未知期間には触れない。

  python pace_going.py
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
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402
from boost import XPARAMS, to_matrix  # noqa: E402

OUT = "weights/pace_going.json"
NAN = float("nan")
NEW = ["脚質rr", "脚質バケツ", "想定ペース", "先行馬率",
       "道悪出走数", "道悪の着順比", "良馬場の着順比", "道悪-良"]


def race_pace(book, ri):
    """レース単位の先行馬率とペース。features.build と同じ決め方。"""
    r = book.races[ri]
    P = [book.past(ri, hi) for hi in range(r["n"])]
    ST = [features.Book.style(p) for p in P]
    front = sum(1 for s in ST if isinstance(s, int) and s <= 1) / r["n"]
    pace = 1 if front < .20 else (2 if front < .30 else
           (3 if front < .40 else (4 if front < .50 else 5)))
    return front, pace, P, ST


def horse_new(P, st, front, pace):
    """1頭ぶんの新しい8成分。"""
    # 脚質の生の値
    s = c = 0.0
    for q in P[:5]:
        if q["cor"]:
            s += q["cor"][0] / q["r"]["n"]
            c += 1
    rr = (s / c) if c else NAN
    bucket = float(st) if isinstance(st, int) else NAN

    # 馬場ごとの実績（過去1年）
    bad = [q for q in P if q["ago"] <= 365 and q["r"]["ground"] != "良" and q["pos"]]
    good = [q for q in P if q["ago"] <= 365 and q["r"]["ground"] == "良" and q["pos"]]
    gb = (sum(q["pos"] / q["r"]["n"] for q in bad) / len(bad)) if bad else NAN
    gg = (sum(q["pos"] / q["r"]["n"] for q in good) / len(good)) if good else NAN
    diff = (gb - gg) if (bad and good) else NAN
    return [rr, bucket, float(pace), float(front),
            float(len(bad)), gb, gg, diff]


def build(book, b, lo, hi, val, add_new):
    DS = []
    for ri, r in enumerate(book.races):
        if lo <= r["date"] < hi:
            d = b.build_wide(ri)
            Z = [list(x) for x in d["Z"]]
            mm = val.get(r["id"]) or {}
            col = train_eval.znorm_column(
                [mm.get(str(x["umaban"]), NAN) for x in r["rows"]])
            for row, x in zip(Z, col):
                row.append(x)
            if add_new:
                front, pace, P, ST = race_pace(book, ri)
                for k, row in enumerate(Z):
                    row.extend(horse_new(P[k], ST[k], front, pace))
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS


def fit(TR, names, rounds=None):
    TRs = sorted(TR, key=lambda d: d["date"])
    if rounds is None:
        cut = int(len(TRs) * 0.8)
        Xa, ya, ga = to_matrix(TRs[:cut])
        Xb, yb, gb = to_matrix(TRs[cut:])
        da = xgb.DMatrix(Xa, label=ya, feature_names=names); da.set_group(ga)
        dv = xgb.DMatrix(Xb, label=yb, feature_names=names); dv.set_group(gb)
        m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                       early_stopping_rounds=60, verbose_eval=False)
        rounds = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    d = xgb.DMatrix(X, label=y, feature_names=names); d.set_group(g)
    return xgb.train(XPARAMS, d, num_boost_round=rounds), rounds


def score_order(model, DS, names):
    out = {}
    for d in DS:
        s = np.asarray(model.predict(
            xgb.DMatrix(np.asarray(d["Z"], np.float32), feature_names=names)), float)
        out[d["race"]["id"]] = s
    return out


def report(label, DS, scores, pays):
    n = w = i3 = 0
    tan, fuku = [], []
    for d in DS:
        r = d["race"]
        s = scores.get(r["id"])
        if s is None:
            continue
        i = int(np.argmax(s))
        h = r["rows"][i]
        f = _fin(h["fin"])
        n += 1
        w += (f == 1)
        i3 += (f is not None and f <= 3)
        pay = pays.get(r["id"])
        if pay:
            tan.append(dict(pay.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0)
            fuku.append(dict(pay.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0)
    return {"label": label, "n": n, "win": w / n * 100, "in3": i3 / n * 100,
            "tan": np.mean(tan) * 100, "fuku": np.mean(fuku) * 100}


def main():
    st = Store(config.DB_PATH)
    db = sqlite3.connect(config.DB_PATH)
    pays = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM payouts")}
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tab, _ = train_eval.learn(config.DB_PATH, words, per_race, CUT_EXPLORE)
    val = train_eval.value_map(per_race, tab)

    book = features.Book(st.all_races(), config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    base = list(b.wide_names) + [train_eval.NAME]
    full = base + NEW

    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, True)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, True)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 成分 {len(full)}個\n", flush=True)

    res = []
    nb = len(base)
    cut = lambda DS: [dict(d, Z=np.asarray(d["Z"])[:, :nb]) for d in DS]

    m1, r1 = fit(cut(FIT), base)
    res.append(report(f"木48成分（いまのもの・{r1}本）", EXP, score_order(m1, cut(EXP), base), pays))

    m2, r2 = fit(FIT, full)
    res.append(report(f"木56成分（展開・馬場を生で足す・{r2}本）", EXP,
                      score_order(m2, EXP, full), pays))

    # 馬場ごとに別の木
    def gsplit(DS, good):
        return [d for d in DS if (d["race"]["ground"] == "良") == good]
    sc = {}
    for good in (True, False):
        f, e = gsplit(FIT, good), gsplit(EXP, good)
        if len(f) < 300 or not e:
            continue
        mm, rr = fit(f, full)
        sc.update(score_order(mm, e, full))
        print(f"  馬場{'良' if good else '良以外'}: 学習{len(f)}R / 測定{len(e)}R / {rr}本",
              flush=True)
    res.append(report("木56成分・馬場ごとに別の木", EXP, sc, pays))

    print(f'\n{"":<34}{"R":>6}{"1位が1着":>10}{"1位が3着内":>11}{"単勝ROI":>10}{"複勝ROI":>10}')
    for x in res:
        print(f'{x["label"]:<34}{x["n"]:>6}{x["win"]:>9.2f}%{x["in3"]:>10.2f}%'
              f'{x["tan"]:>9.1f}%{x["fuku"]:>9.1f}%')

    imp = m2.get_score(importance_type="gain")
    tot = sum(imp.values()) or 1
    rank = {n: i + 1 for i, (n, _v) in enumerate(
        sorted(imp.items(), key=lambda x: -x[1]))}
    print(f"\n新しい8成分が木の中で何位に入ったか（全{len(rank)}成分中）")
    for n in NEW:
        if n in imp:
            print(f"  {n:<12} {rank[n]:>2}位   寄与 {imp[n]/tot*100:.2f}%")
        else:
            print(f"  {n:<12} 使われず")
    print("\n参考: 元の合成値")
    for n in ("展開乗数", "TAS", "馬場", "FSI"):
        if n in imp:
            print(f"  {n:<12} {rank[n]:>2}位   寄与 {imp[n]/tot*100:.2f}%")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "results": [{k: (round(v, 2) if isinstance(v, float) else v)
                            for k, v in x.items()} for x in res],
               "new_importance": {n: round(imp.get(n, 0) / tot * 100, 2) for n in NEW}},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
