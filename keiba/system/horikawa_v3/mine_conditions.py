# -*- coding: utf-8 -*-
"""条件を総当たりして、プラスの部分集合が本当にあるのかを判定する。

「特定の条件に絞ればプラス」は、探せば必ず見つかる。3,000マスも切れば、
控除率20%の世界でも100%超えのマスは何十個も出る。問題は、見つけたものが
本物か、切り刻んだ残りかを区別する手続きが無いことだった。

ここでやること:

  1. 条件を10軸に分け、1軸単体と2軸の組み合わせを全部作る（n>=50 のものだけ）
  2. 券種6通り × 全マスで回収率を出す
  3. **同じマスの切り方のまま、レースと払戻の対応をシャッフルして**
     「腕が無いときの最大回収率」の分布を作る（並べ替え検定）
     マスが多いほど、また小さいマスほど、偶然の最大値は高く出る。
     その分を込みで基準線が引ける
  4. 実測の最大値が、その基準線を越えたかどうかで判定する

越えなければ「プラスのマスは見つかったが、偶然と区別がつかない」が結論になる。
越えれば、それが未知期間で一度だけ試す価値のある候補になる。

窓は explore.py と同じ。未知期間には触れない。

  python mine_conditions.py
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

OUT = "weights/mine_conditions.json"
MIN_N = 50
NPERM = 2000
RNG = np.random.default_rng(20260829)

PLACES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
          "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def bet_payouts(pay, picks, kind):
    """100円あたりの回収額。買えない券種なら None。"""
    if kind == "単勝":
        d = dict(pay.get("単勝", []))
        return d.get(str(picks[0]), 0) / 100.0
    if kind.startswith("複勝"):
        d = dict(pay.get("複勝", []))
        k = int(kind[-1])
        return sum(d.get(str(u), 0) for u in picks[:k]) / (k * 100.0)
    if kind.startswith("ワイド"):
        d = dict(pay.get("ワイド", []))
        k = int(kind[-1])
        sel, tot, cnt = picks[:k], 0, 0
        for i in range(len(sel)):
            for j in range(i + 1, len(sel)):
                a, b = sorted((int(sel[i]), int(sel[j])))
                tot += d.get(f"{a}-{b}", 0)
                cnt += 1
        return tot / (cnt * 100.0) if cnt else None
    return None


BETS = ["単勝", "複勝1", "複勝2", "複勝3", "ワイド2", "ワイド3"]


def dims(r, pick, g12, tev):
    """1レースを10軸で表す。値は文字列。"""
    n = r["n"]
    return {
        "場": PLACES.get(r["place"], r["place"]),
        "芝ダ": r["surf"],
        "距離帯": features.band(r["dist"]),
        "クラス": r["cls"],
        "頭数": "少頭数(〜10)" if n <= 10 else ("中(11-14)" if n <= 14 else "多頭数(15〜)"),
        "馬場": r["ground"],
        "形": "1強" if g12 >= 1.0 else ("差あり" if g12 >= 0.5 else "混戦"),
        "1位の人気": ("1番人気" if pick["pop"] == 1 else
                   ("2-3番人気" if pick["pop"] <= 3 else
                    ("4-6番人気" if pick["pop"] <= 6 else "7番人気以下"))),
        "1位の調教評価": ("高" if tev >= 0.5 else ("低" if tev <= -0.5 else "中")),
        "月": r["date"][4:6] + "月",
    }


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
    print(f"学習 {len(FIT)}R / 探索 {len(EXP)}R / 段階 {lv}", flush=True)

    rows = []
    for d in EXP:
        r = d["race"]
        pay = pays.get(r["id"])
        if not pay:
            continue
        Z = np.asarray(d["Z"], float)
        sc = Z @ m.w(d["k"], lv)
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        pick = r["rows"][o[0]]
        if not pick["pop"]:
            continue
        sd = float(np.std(sc)) or 1.0
        g12 = float((sc[o[0]] - sc[o[1]]) / sd) if len(sc) > 1 else 0.0
        picks = [r["rows"][i]["umaban"] for i in o[:3]]
        pv = {k: bet_payouts(pay, picks, k) for k in BETS}
        if any(v is None for v in pv.values()):
            continue
        rows.append({"dim": dims(r, pick, g12, float(Z[o[0]][-1])), "pay": pv,
                     "odds1": pick["odds"]})

    N = len(rows)
    print(f"測れたレース {N}R\n", flush=True)

    # ── マスを作る（1軸単体 + 2軸の組み合わせ）
    axes = list(rows[0]["dim"].keys())
    cells = {}
    for i, a in enumerate(axes):
        for va in {d["dim"][a] for d in rows}:
            mask = np.array([d["dim"][a] == va for d in rows])
            if mask.sum() >= MIN_N:
                cells[f"{a}={va}"] = mask
        for bx in axes[i + 1:]:
            for va in {d["dim"][a] for d in rows}:
                for vb in {d["dim"][bx] for d in rows}:
                    mask = np.array([d["dim"][a] == va and d["dim"][bx] == vb for d in rows])
                    if mask.sum() >= MIN_N:
                        cells[f"{a}={va} & {bx}={vb}"] = mask
    keys = list(cells)
    M = np.array([cells[k] for k in keys], float)
    M = M / M.sum(1, keepdims=True)          # 各マスの平均を取る行列
    ns = np.array([cells[k].sum() for k in keys])
    print(f"条件のマス {len(keys)}個（n>={MIN_N}）× 券種{len(BETS)} = "
          f"{len(keys)*len(BETS)}通りを総当たり", flush=True)

    results = []
    null_max = []
    null_over = []
    for kind in BETS:
        p = np.array([d["pay"][kind] for d in rows])
        roi = M @ p * 100
        for k, r_, n_ in zip(keys, roi, ns):
            results.append({"bet": kind, "cell": k, "n": int(n_), "roi": round(float(r_), 1)})
        # 並べ替え: 払戻をレース間でシャッフルし、同じマスで最大回収率を取る
        P = np.stack([RNG.permutation(p) for _ in range(NPERM)], axis=1)   # (N, NPERM)
        R = M @ P * 100                                                    # (cells, NPERM)
        null_max.append(R.max(0))
        null_over.append((R >= 100).sum(0))                                # 100%超えのマス数
        print(f"  {kind}: 実測の最大 {roi.max():.1f}% / 並べ替えの最大 中央値 "
              f"{np.median(null_max[-1]):.1f}%", flush=True)

    allnull = np.max(np.stack(null_max), axis=0)      # 券種もまたいだ最大
    line95 = float(np.percentile(allnull, 95))
    line99 = float(np.percentile(allnull, 99))
    results.sort(key=lambda x: -x["roi"])
    best = results[0]

    print(f"\n── 実測の上位10マス（{len(results)}通り中）")
    print(f'  {"券種":<7}{"条件":<44}{"R":>5}{"回収率":>8}')
    for x in results[:10]:
        print(f'  {x["bet"]:<7}{x["cell"]:<44}{x["n"]:>5}{x["roi"]:>7.1f}%')

    print(f"\n── 偶然だけで出る最大回収率（払戻をシャッフルして{NPERM}回）")
    print(f"  中央値 {np.median(allnull):.1f}% / 95パーセンタイル {line95:.1f}% / "
          f"99パーセンタイル {line99:.1f}%")
    pval = float((allnull >= best["roi"]).mean())
    print(f"\n  実測の最大 {best['roi']:.1f}%（{best['bet']} / {best['cell']} / n={best['n']}）")
    print(f"  この値以上が偶然で出る確率 p = {pval:.3f}")
    print("  → " + ("基準線を越えた。未知期間で一度だけ試す価値がある。"
                    if pval < 0.05 else
                    "基準線を越えない。プラスのマスはあるが、偶然と区別がつかない。"))

    over = [x for x in results if x["roi"] >= 100]
    nover = np.stack(null_over).sum(0)          # 並べ替え1回あたりの100%超えマス数
    print(f"\n  100%を越えたマス: 実測 {len(over)}個 / 偶然でも中央 {np.median(nover):.0f}個"
          f"（5〜95パーセンタイル {np.percentile(nover, 5):.0f}〜{np.percentile(nover, 95):.0f}個）")
    print(f"  実測がこれ以上になる確率 p = {(nover >= len(over)).mean():.3f}")

    # ── 「的中率27.8%なら5倍以上で単勝プラスでは」を直接確かめる
    print("\n── モデル1位の単勝オッズ帯ごと（的中率は帯によって変わる）")
    print(f'  {"オッズ帯":<12}{"R":>5}{"平均オッズ":>10}{"的中率":>8}'
          f'{"損益分岐に要る的中率":>14}{"回収率":>8}')
    bands = [("1.0-2.0倍", 1.0, 2.0), ("2.0-3.0倍", 2.0, 3.0), ("3.0-5.0倍", 3.0, 5.0),
             ("5.0-10倍", 5.0, 10.0), ("10-20倍", 10.0, 20.0), ("20倍以上", 20.0, 1e9)]
    for lab, lo, hi in bands:
        s = [d for d in rows if lo <= d["odds1"] < hi]
        if not s:
            continue
        o_ = np.array([d["odds1"] for d in s])
        w_ = np.array([d["pay"]["単勝"] > 0 for d in s], float)
        need = 1.0 / o_.mean()
        print(f'  {lab:<12}{len(s):>5}{o_.mean():>10.1f}{w_.mean()*100:>7.1f}%'
              f'{need*100:>13.1f}%{np.mean([d["pay"]["単勝"] for d in s])*100:>8.1f}%')

    os.makedirs("weights", exist_ok=True)
    json.dump({"n_races": N, "n_cells": len(keys), "n_tests": len(results),
               "null_median": round(float(np.median(allnull)), 1),
               "null_p95": round(line95, 1), "null_p99": round(line99, 1),
               "best": best, "p_value": pval,
               "n_over100": len(over), "null_over100_median": float(np.median(nover)),
               "p_over100": float((nover >= len(over)).mean()),
               "top50": results[:50]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
