# -*- coding: utf-8 -*-
"""木の学習器を動かし、さらに新しい成分を足して、市場に届くか測る。

これまでの測定は全部 24成分の線形でやっていた。リポジトリが「本命」と呼ぶ
50成分の木（hk/gbdt.py）は lightgbm が入っておらず、一度も動かしていない。
そこが最大の未使用の手なので、まずそれを動かす。

そのうえで、リポジトリに無い成分を6つ足す。どれも「市場が完全には織り込み
にくい」類のものを選んだ。

  E1 乗り替わり      前走と騎手が替わったか。乗り替わり自体は公開情報だが、
                    良化/悪化の向きはオッズに一様には入らない
  E2 前走の上がり順位  上がり3Fのレース内順位。着順に出なかった脚を拾う
  E3 前走の人気−着順   人気以上に走ったか。前走の評価と結果のズレ
  E4 馬体重増減      仕上りの変化。絶対値ではなく差分
  E5 同コース3着内率   場×芝ダ×距離帯での過去実績
  E6 前走の4角位置比   4コーナーでどこにいたか（頭数で割る）。展開の受け方

比べるもの:
  線形24成分 / 木48成分 / 木54成分（新成分入り）/ 市場（1番人気）

窓は explore.py と同じ。未知期間には触れない。

  python boost.py
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
from explore import CUT_EXPLORE, EVAL_RAW, _fin  # noqa: E402

OUT = "weights/boost.json"

# lightgbm 4.7.0 は この環境（Python 3.14 / numpy 2.5）でラベル付き Dataset を
# 作ると必ずアクセス違反で落ちる。成分名や中身とは無関係で、ラベル無しなら通る。
# hk/gbdt.py は lightgbm 前提なので、木の学習だけ xgboost の rank:ndcg に
# 差し替える。目的関数（段階付き relevance の順位学習）と、内側の時系列分割で
# 本数を決める手順は hk/gbdt.py と同じにした。hk/ は触っていない。
import xgboost as xgb  # noqa: E402

XPARAMS = dict(objective="rank:ndcg", eval_metric="ndcg@3",
               lambdarank_num_pair_per_sample=6, lambdarank_pair_method="topk",
               learning_rate=0.05, max_depth=7, min_child_weight=40,
               reg_lambda=5.0, subsample=0.85, colsample_bytree=0.85,
               max_bin=63, verbosity=0, seed=7, nthread=0)


def to_matrix(DS):
    X = np.vstack([np.asarray(d["Z"], np.float32) for d in DS])
    grp = [len(d["Z"]) for d in DS]
    y = []
    for d in DS:
        for o in d["ord"]:
            y.append(3 if o == 1 else (2 if o == 2 else (1 if o == 3 else 0)))
    return X, np.array(y, np.float32), grp


def xfit(TR, names, inner_frac=0.2, max_rounds=600, verbose=True):
    """時系列で内側を切って木の本数を決め、そのあと全体で学習し直す。"""
    TR = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TR) * (1 - inner_frac))
    A, B = TR[:cut], TR[cut:]
    Xa, ya, ga = to_matrix(A)
    Xb, yb, gb = to_matrix(B)
    da = xgb.DMatrix(Xa, label=ya, feature_names=list(names)); da.set_group(ga)
    dbv = xgb.DMatrix(Xb, label=yb, feature_names=list(names)); dbv.set_group(gb)
    ev = {}
    m = xgb.train(XPARAMS, da, num_boost_round=max_rounds,
                  evals=[(dbv, "inner")], early_stopping_rounds=60,
                  evals_result=ev, verbose_eval=False)
    best = (m.best_iteration or max_rounds - 1) + 1
    if verbose:
        print(f"  内側検証 {len(B)}R で木の本数を決めました → {best}本")
    X, y, g = to_matrix(TR)
    d = xgb.DMatrix(X, label=y, feature_names=list(names)); d.set_group(g)
    full = xgb.train(XPARAMS, d, num_boost_round=best)
    if verbose:
        imp = full.get_score(importance_type="gain")
        tot = sum(imp.values()) or 1
        print("  効いた成分（上位12）")
        for nm, v in sorted(imp.items(), key=lambda x: -x[1])[:12]:
            print(f"    {nm:14s} {v / tot * 100:5.1f}%")
    return full, best


def xscore(model, DS, names):
    X, _, g = to_matrix(DS)
    d = xgb.DMatrix(X, feature_names=list(names))
    s = model.predict(d)
    out, p = [], 0
    for n in g:
        out.append(s[p:p + n]); p += n
    return out
NAN = float("nan")
EXTRA = ["乗り替わり", "前走上がり順位", "前走人気-着順", "馬体重増減",
         "同コース3着内率", "前走4角位置比"]


def extras(book, ri, hi):
    """リポジトリに無い6成分。過去走から作るので発走前に分かるものだけ。"""
    r = book.races[ri]
    h = r["rows"][hi]
    P = book.past(ri, hi, 9)
    last = P[0] if P else None

    e1 = NAN
    if last:
        e1 = 0.0 if last["h"]["jockey"] == h["jockey"] else 1.0

    e2 = NAN
    if last:
        ag = [x["agari"] for x in last["r"]["rows"] if x["agari"] > 0]
        if ag and last["h"]["agari"] > 0:
            e2 = sum(1 for a in ag if a < last["h"]["agari"]) / len(ag)

    e3 = NAN
    if last and last["pos"] and last["h"]["pop"]:
        e3 = float(last["h"]["pop"] - last["pos"])

    e4 = float(h["bwd"]) if h["bw"] > 0 else NAN

    key = r["place"] + r["surf"] + features.band(r["dist"])
    same = [q for q in P
            if q["r"]["place"] + q["r"]["surf"] + features.band(q["r"]["dist"]) == key]
    e5 = (sum(1 for q in same if q["pos"] and q["pos"] <= 3) / len(same)) if same else NAN

    e6 = NAN
    if last and last["cor"]:
        c = last["cor"][-1]
        if c and last["r"]["n"]:
            e6 = float(c) / last["r"]["n"]

    return [e1, e2, e3, e4, e5, e6]


def build(book, b, lo, hi, val, nf, with_extra):
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
            if with_extra:
                for k, row in enumerate(Z):
                    row.extend(extras(book, ri, k))
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                DS.append(d)
        b.advance(r)
    return DS


def report(label, DS, order_fn, pays):
    n = w = i3 = box = 0
    tan, fuku = [], []
    for d in DS:
        r = d["race"]
        o = order_fn(d)
        fins = [_fin(x["fin"]) for x in r["rows"]]
        n += 1
        p1 = fins[o[0]]
        w += (p1 == 1)
        i3 += (p1 is not None and p1 <= 3)
        box += {1, 2, 3} <= {fins[i] for i in o[:6]}
        pay = pays.get(r["id"])
        if pay:
            h = r["rows"][o[0]]
            tan.append(dict(pay.get("単勝", [])).get(str(h["umaban"]), 0) / 100.0)
            fuku.append(dict(pay.get("複勝", [])).get(str(h["umaban"]), 0) / 100.0)
    f = lambda a: (np.mean(a) * 100, np.std(a, ddof=1) / np.sqrt(len(a)) * 100)
    return {"label": label, "n": n, "win": w / n * 100, "in3": i3 / n * 100,
            "box6": box / n * 100, "tan": f(tan), "fuku": f(fuku)}


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
    full = wide + EXTRA

    FIT = build(book, b, config.CUT_HIST, CUT_EXPLORE, val, nf, True)
    EXP = build(book, b, CUT_EXPLORE, config.CUT_EMBARGO, val, nf, True)
    print(f"学習 {len(FIT)}R / 測定 {len(EXP)}R", flush=True)
    print(f"成分: 木={len(full)}個（wide {len(b.wide_names)} + 調教評価 + 新規{len(EXTRA)}）\n",
          flush=True)

    res = []

    # 1 線形24成分（これまでの基準）
    lin = list(features.BASE_NAMES) + [train_eval.NAME]
    nl = len(lin)
    cut = lambda DS: [dict(d, Z=np.asarray(d["Z"])[:, :nl]) for d in DS]
    lv, _ = F.choose_level(cut(FIT), lin)
    ml = F.Model().fit(cut(FIT), lin, verbose=False)
    def lin_order(d):
        s = np.asarray(d["Z"])[:, :nl].astype(float) @ ml.w(d["k"], lv)
        return list(np.argsort(-s))
    res.append(report(f"線形24成分（段階{lv}）", EXP, lin_order, pays))

    # 2 木48成分（wide + 調教評価）
    nw = len(wide)
    cutw = lambda DS: [dict(d, Z=np.asarray(d["Z"])[:, :nw]) for d in DS]
    print("木48成分を学習", flush=True)
    m48, _ = xfit(cutw(FIT), wide, verbose=True)
    s48 = {id(d): s for d, s in zip(EXP, xscore(m48, cutw(EXP), wide))}
    res.append(report("木48成分", EXP, lambda d: list(np.argsort(-np.asarray(s48[id(d)]))), pays))

    # 3 木54成分（新成分入り）
    print("\n木54成分（新成分入り）を学習", flush=True)
    m54, _ = xfit(FIT, full, verbose=True)
    s54 = {id(d): s for d, s in zip(EXP, xscore(m54, EXP, full))}
    res.append(report("木54成分（新成分入り）", EXP, lambda d: list(np.argsort(-np.asarray(s54[id(d)]))), pays))

    # 4 市場（人気順）
    def mkt(d):
        r = d["race"]
        return list(np.argsort([x["pop"] if x["pop"] else 99 for x in r["rows"]]))
    res.append(report("市場（1番人気）", EXP, mkt, pays))

    print(f'\n{"":<26}{"1位が1着":>11}{"1位が3着内":>12}{"上位6頭3着独占":>14}'
          f'{"単勝ROI":>11}{"複勝ROI":>11}')
    for x in res:
        print(f'{x["label"]:<26}{x["win"]:>10.2f}%{x["in3"]:>11.2f}%{x["box6"]:>13.2f}%'
              f'{x["tan"][0]:>10.1f}%{x["fuku"][0]:>10.1f}%')

    mk = res[-1]
    print(f'\n市場との差（3着内率）')
    for x in res[:-1]:
        print(f'  {x["label"]:<26}{x["in3"]-mk["in3"]:+7.2f}pt')

    # ── 同じレースで対にして検定する（回収率）
    def payvec(order_fn, kind):
        v = []
        for d in EXP:
            pay = pays.get(d["race"]["id"])
            if not pay:
                continue
            h = d["race"]["rows"][order_fn(d)[0]]
            v.append(dict(pay.get(kind, [])).get(str(h["umaban"]), 0) / 100.0)
        return np.array(v)

    o48 = lambda d: list(np.argsort(-np.asarray(s48[id(d)])))

    def blend(d):
        """木の順位と市場の順位を足して並べ直す。両方の言い分を半分ずつ。"""
        r = d["race"]
        a = np.argsort(np.argsort(-np.asarray(s48[id(d)])))
        pv = np.array([x["pop"] if x["pop"] else 99 for x in r["rows"]])
        return list(np.argsort(a + np.argsort(np.argsort(pv))))

    res.append(report("木48成分 + 市場 の合成", EXP, blend, pays))
    x = res[-1]
    print(f'\n{x["label"]:<26}{x["win"]:>10.2f}%{x["in3"]:>11.2f}%{x["box6"]:>13.2f}%'
          f'{x["tan"][0]:>10.1f}%{x["fuku"][0]:>10.1f}%   （対市場 {x["in3"]-mk["in3"]:+.2f}pt）')

    print("\n同じレースで対にした検定（相手は市場＝1番人気）")
    for lab, fn in [("木48成分", o48), ("木48+市場 合成", blend)]:
        for kind in ("単勝", "複勝"):
            a = payvec(fn, kind)
            c = payvec(mkt, kind)
            dd = a - c
            t = dd.mean() / (dd.std(ddof=1) / np.sqrt(len(dd)))
            print(f"  {lab:<16}{kind}  {a.mean()*100:6.1f}% 対 {c.mean()*100:6.1f}%"
                  f"   差 {dd.mean()*100:+6.1f}pt  t={t:+5.2f}  n={len(dd)}")
    print("\n控除率20%。100%を越えなければ買えないのは変わらない。")

    os.makedirs("weights", exist_ok=True)
    json.dump({"window": [CUT_EXPLORE, config.CUT_EMBARGO],
               "n_fit": len(FIT), "n_exp": len(EXP), "features": full,
               "results": [{k: (list(v) if isinstance(v, tuple) else v)
                            for k, v in x.items()} for x in res]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n書き出しました → {OUT}")


if __name__ == "__main__":
    main()
