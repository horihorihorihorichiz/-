# -*- coding: utf-8 -*-
"""木の1位が「ダントツ」のとき、本当に当たりやすいのかを測る。

system_bets.py では g12>=1.0 で切ったが69レースしか無く測れなかった。
しきい値を先に決めると本数が偏るので、ここは分位で5等分する。
各グループが同じ本数になるので比べやすい。

見るもの:
  木の1位と2位の得点差（生の差と、レース内SDで割った差）を5等分し、
  各グループの 1着的中率 / 3着内率 / 単勝ROI / 複勝ROI を出す。
  比較のため市場（1番人気のオッズ帯）でも同じことをする。

窓は explore.py と同じ。未知期間には触れない。

  python dominance.py
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
from boost import XPARAMS, to_matrix, build  # noqa: E402

OUT = "weights/dominance.json"
NB = 5


def show(title, rows, key, fmt="{:.2f}"):
    """rows を key の分位で5等分して並べる。"""
    v = np.array([d[key] for d in rows])
    qs = np.quantile(v, np.linspace(0, 1, NB + 1))
    print(f"\n── {title}")
    print(f'  {"区間":<22}{"R":>6}{"1着":>8}{"3着内":>8}{"単勝ROI":>10}{"複勝ROI":>10}'
          f'{"1位の平均人気":>12}')
    out = []
    for i in range(NB):
        lo, hi = qs[i], qs[i + 1]
        s = [d for d in rows if (lo <= d[key] < hi or (i == NB - 1 and d[key] == hi))]
        if not s:
            continue
        w = np.mean([d["win"] for d in s]) * 100
        i3 = np.mean([d["in3"] for d in s]) * 100
        tr = np.mean([d["tan"] for d in s]) * 100
        fr = np.mean([d["fuku"] for d in s]) * 100
        tse = np.std([d["tan"] for d in s], ddof=1) / np.sqrt(len(s)) * 100
        pop = np.mean([d["pop1"] for d in s])
        lab = f"{fmt.format(lo)} 〜 {fmt.format(hi)}"
        print(f'  {lab:<22}{len(s):>6}{w:>7.1f}%{i3:>7.1f}%{tr:>9.1f}%{fr:>9.1f}%{pop:>12.1f}')
        out.append({"band": lab, "n": len(s), "win": round(w, 1), "in3": round(i3, 1),
                    "tan_roi": round(tr, 1), "tan_se": round(tse, 1),
                    "fuku_roi": round(fr, 1), "pop1": round(pop, 1)})
    return out


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

    TRs = sorted(FIT, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=wide); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=wide); dv.set_group(gb)
    m0 = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    bestn = (m0.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    dall = xgb.DMatrix(X, label=y, feature_names=wide); dall.set_group(g)
    model = xgb.train(XPARAMS, dall, num_boost_round=bestn)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R / 木 {bestn}本", flush=True)

    rows = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay:
            continue
        s = np.asarray(model.predict(
            xgb.DMatrix(np.asarray(d["Z"], np.float32), feature_names=wide)), float)
        o = sorted(range(len(s)), key=lambda i: -s[i])
        h = r["rows"][o[0]]
        if not h["pop"] or h["odds"] <= 0:
            continue
        f = _fin(h["fin"])
        sd = float(np.std(s)) or 1.0
        h2 = r["rows"][o[1]]
        f2 = _fin(h2["fin"])
        wid = dict(pay.get("ワイド", []))
        ure = dict(pay.get("馬連", []))
        a, bq = sorted((int(h["umaban"]), int(h2["umaban"])))
        rows.append({
            # 上位2頭がどれだけ後続を離しているか（2位と3位の差）
            "gap23": float(s[o[1]] - s[o[2]]) if len(o) > 2 else 0.0,
            "wide12": wid.get(f"{a}-{bq}", 0) / 100.0,
            "uren12": ure.get(f"{a}-{bq}", 0) / 100.0,
            "both3": (f is not None and f <= 3) and (f2 is not None and f2 <= 3),
            "odds2": h2["odds"],
            "gap_raw": float(s[o[0]] - s[o[1]]),          # 生の得点差
            "gap_sd": float((s[o[0]] - s[o[1]]) / sd),    # レース内SDで割った差
            "odds1": h["odds"], "pop1": int(h["pop"]),
            "win": f == 1, "in3": f is not None and f <= 3,
            "tan": dict(pay.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0,
            "fuku": dict(pay.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0,
        })
    print(f"測れたレース {len(rows)}R")
    print("回収率は100円あたり。控除率20%なので何もしなければ80%前後。")

    res = {}
    res["gap_raw"] = show("木の1位と2位の得点差（生）＝小さいほど僅差", rows, "gap_raw")
    res["gap_sd"] = show("木の1位と2位の得点差（レース内SDで割ったもの）", rows, "gap_sd")
    res["odds1"] = show("比較用: 木1位の単勝オッズ", rows, "odds1", "{:.1f}")

    # ── 上位2頭が抜けているとき
    print("\n── 木の2位と3位の得点差＝大きいほど上位2頭が抜けている")
    print(f'  {"区間":<22}{"R":>6}{"1-2着とも3着内":>14}{"ワイドROI":>11}'
          f'{"馬連ROI":>10}{"単勝1位ROI":>12}{"2頭の平均人気":>13}')
    v = np.array([d["gap23"] for d in rows])
    qs = np.quantile(v, np.linspace(0, 1, NB + 1))
    res["gap23"] = []
    for i in range(NB):
        lo, hi = qs[i], qs[i + 1]
        sset = [d for d in rows
                if (lo <= d["gap23"] < hi or (i == NB - 1 and d["gap23"] == hi))]
        if not sset:
            continue
        b3 = np.mean([d["both3"] for d in sset]) * 100
        wr = np.mean([d["wide12"] for d in sset]) * 100
        wse = np.std([d["wide12"] for d in sset], ddof=1) / np.sqrt(len(sset)) * 100
        ur = np.mean([d["uren12"] for d in sset]) * 100
        tr = np.mean([d["tan"] for d in sset]) * 100
        pp = np.mean([(d["pop1"] + 0.0) for d in sset])
        lab = f"{lo:.2f} 〜 {hi:.2f}"
        print(f'  {lab:<22}{len(sset):>6}{b3:>13.1f}%{wr:>10.1f}%{ur:>9.1f}%'
              f'{tr:>11.1f}%{pp:>13.1f}')
        res["gap23"].append({"band": lab, "n": len(sset), "both_in3": round(b3, 1),
                             "wide_roi": round(wr, 1), "wide_se": round(wse, 1),
                             "uren_roi": round(ur, 1), "tan_roi": round(tr, 1)})

    a = res["gap_raw"]
    print(f"\n最も僅差の群 {a[0]['n']}R: 1着 {a[0]['win']}% / 単勝 {a[0]['tan_roi']}%")
    print(f"最もダントツの群 {a[-1]['n']}R: 1着 {a[-1]['win']}% / 単勝 {a[-1]['tan_roi']}%")
    print("差が当たりやすさに効くなら、上から下へ 1着率が単調に伸びるはず。")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO], "n": len(rows),
               "bands": res}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
