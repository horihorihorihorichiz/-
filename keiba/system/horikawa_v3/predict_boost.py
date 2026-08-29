# -*- coding: utf-8 -*-
"""木48成分 + 市場 の合成で、未発走のレースを採点する。

探索窓1,826Rでの実測（boost.py）:
  木48成分        1位が3着内 62.43% / 単勝83.9% / 複勝87.2%   対市場 -2.85pt
  市場(1番人気)     65.28% / 76.3% / 83.8%
  木48 + 市場 合成  70.04% / 96.0% / 94.5%   対市場 +4.76pt
                  対にした検定で 単勝 t=+6.98 / 複勝 t=+7.48

合成は「木の順位」と「市場の順位」を足して並べ直すだけ。片方だけでは市場に
負けるのに、足すと勝つ。誤差の出方が違うので互いの外し方が打ち消し合う。

寄与の内訳は木の SHAP 値（pred_contribs）で出す。線形の Z×重み より正確。

  python predict_boost.py ../../data/cards_20260830.json --date 20260830 \
      --md ../../predictions/20260830.md --viz ../../data/viz_20260830.json
"""
import json
import os
import sys

import numpy as np
import xgboost as xgb

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402
import predict_today as PT  # noqa: E402
from boost import XPARAMS, to_matrix  # noqa: E402

EVAL_RAW = "../../data/hk_train_raw.json"
NAN = float("nan")


def build_rows(book, b, val, want, date):
    """全レースを順に進めながら、対象レースの成分行列を作る。"""
    out = {}
    for ri, r in enumerate(book.races):
        take = r["id"] in want
        train = (config.CUT_HIST <= r["date"] < date) and not take
        if take or train:
            d = b.build_wide(ri)
            Z = [list(x) for x in d["Z"]]
            mm = val.get(r["id"]) or {}
            col = train_eval.znorm_column(
                [mm.get(str(x["umaban"]), NAN) for x in r["rows"]])
            for row, x in zip(Z, col):
                row.append(x)
            d["Z"] = np.array(Z, dtype=np.float32)
            d["race"] = r
            if take:
                out[r["id"]] = d
            elif 1 in d["ord"]:
                d["top"] = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
                out.setdefault("_TR", []).append(d)
        b.advance(r)
    return out


def main():
    cards = json.load(open(sys.argv[1], encoding="utf-8"))
    opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    date = opt("--date") or "20260830"
    md_path, viz_path = opt("--md"), opt("--viz")

    st = Store(config.DB_PATH)
    words, per_race = train_eval.load_evalcode(EVAL_RAW)
    tabw, info = train_eval.learn(config.DB_PATH, words, per_race, date)
    by_word = {words[i]: v for i, v in tabw.items()}
    wcnt = {x["語"]: x for x in info["words"]}
    vocab = set(words)
    print(f"調教評価: {info['語数']}語 / 学習{info['レース数']}R (date<{date})", flush=True)

    races = st.all_races()
    targets = {rid: PT.to_race(rid, c, date) for rid, c in cards.items()}
    for rid in sorted(targets):
        races.append(targets[rid])

    book = features.Book(races, config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    wide = list(b.wide_names) + [train_eval.NAME]
    got = build_rows(book, b, val=train_eval.value_map(per_race, tabw),
                     want=set(targets), date=date)
    TR = got.pop("_TR", [])
    print(f"学習 {len(TR)}R / 対象 {len(got)}R / 成分 {len(wide)}個", flush=True)

    # 木を学習（本数は内側の時系列分割で決める）
    TRs = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TRs) * 0.8)
    Xa, ya, ga = to_matrix(TRs[:cut])
    Xb, yb, gb = to_matrix(TRs[cut:])
    da = xgb.DMatrix(Xa, label=ya, feature_names=wide); da.set_group(ga)
    dv = xgb.DMatrix(Xb, label=yb, feature_names=wide); dv.set_group(gb)
    mm = xgb.train(XPARAMS, da, num_boost_round=600, evals=[(dv, "inner")],
                   early_stopping_rounds=60, verbose_eval=False)
    best = (mm.best_iteration or 599) + 1
    X, y, g = to_matrix(TRs)
    dall = xgb.DMatrix(X, label=y, feature_names=wide); dall.set_group(g)
    model = xgb.train(XPARAMS, dall, num_boost_round=best)
    print(f"木の本数 {best}本", flush=True)

    results = {}
    for rid, d in got.items():
        r = d["race"]
        Z = np.asarray(d["Z"], np.float32)
        dm = xgb.DMatrix(Z, feature_names=wide)
        s = np.asarray(model.predict(dm), float)
        contrib = np.asarray(model.predict(dm, pred_contribs=True), float)  # (n, F+1)
        pops = np.array([h["pop"] if h["pop"] else 99 for h in r["rows"]], float)
        # 順位を足す（0始まり）。同点は木の得点で割る
        trank = np.argsort(np.argsort(-s))
        mrank = np.argsort(np.argsort(pops))
        blend = trank + mrank
        order = sorted(range(len(s)), key=lambda i: (blend[i], trank[i]))
        sd = float(np.std(-blend.astype(float))) or 1.0
        g12 = float((blend[order[1]] - blend[order[0]]) / sd) if len(order) > 1 else 0.0
        results[rid] = {"race": r, "s": s, "contrib": contrib, "trank": trank,
                        "order": order, "blend": blend, "g12": g12,
                        "ew": PT.eval_words(cards[rid], vocab)}

    # ── 出力
    lines = [f"# 予想 {date[:4]}-{date[4:6]}-{date[6:8]}", "",
             "木48成分（xgboost rank:ndcg）と市場（人気順）の順位を足した合成。",
             "探索窓1,826Rの実測で 1位が3着内 70.04%（市場65.28%）、",
             "単勝ROI 96.0%（市場76.3%, t=+6.98）、複勝ROI 94.5%（市場83.8%, t=+7.48）。", "",
             "> それでも100%は越えていない。控除率20%に対し単勝で4pt、複勝で5.5pt足りない。",
             "> 未知期間での確認はまだ。買い目と期待値は出していない。", ""]
    viz = {"names": wide, "level": "木48+市場", "date": date,
           "baseRate": round(info["全体3着内率"] * 100, 1),
           "evalTop": sorted(info["words"], key=lambda x: -x["縮小後"])[:6],
           "evalBottom": sorted(info["words"], key=lambda x: x["縮小後"])[:6],
           "races": []}

    for rid in sorted(results, key=lambda k: (results[k]["race"]["id"],)):
        R = results[rid]
        r, order = R["race"], R["order"]
        c = cards[rid]
        post = PT.re.search(r"(\d{1,2}:\d{2})発走",
                            PT.unicodedata.normalize("NFKC", c["data01"]))
        post = post.group(1) if post else ""
        place = PT.PLACES.get(r["place"], r["place"])
        title = c.get("name", "")
        lines.append(f'## {place}{int(rid[10:12])}R　{post}発走　{title}　'
                     f'{r["surf"]}{r["dist"]}m {r["ground"]}　'
                     f'{PT.CLSNAME.get(r["cls"], r["cls"])}　{r["n"]}頭')
        lines.append("")
        lines.append("| 順 | 馬番 | 馬名 | 人気 | 木の順位 | 追い切り評価 | 効いた成分（上位3） |")
        lines.append("|--:|--:|---|--:|--:|---|---|")
        hs = []
        for k, i in enumerate(order):
            h = r["rows"][i]
            cs = sorted(((wide[j], float(R["contrib"][i][j])) for j in range(len(wide))),
                        key=lambda x: -abs(x[1]))[:3]
            nm = next((x["name"] for x in c["rows"] if x["horse"] == h["horse"]), h["horse"])
            wd = R["ew"].get(h["horse"], "")
            lines.append(f'| {k+1} | {h["umaban"]} | {nm} | {h["pop"] or "—"} | '
                         f'{int(R["trank"][i])+1} | {wd or "—"} | '
                         + " ".join(f"{a}{v:+.2f}" for a, v in cs) + " |")
            hs.append({
                "umaban": h["umaban"], "waku": h["waku"], "name": nm,
                "sexage": next((x["sexage"] for x in c["rows"] if x["horse"] == h["horse"]), ""),
                "kin": h["kin"],
                "jockey": next((x["jockeyName"] for x in c["rows"] if x["horse"] == h["horse"]), ""),
                "stable": next((x["stable"] for x in c["rows"] if x["horse"] == h["horse"]), ""),
                "bw": h["bw"], "pop": h["pop"], "odds": h["odds"],
                "trank": int(R["trank"][i]) + 1, "blend": int(R["blend"][i]),
                "score": round(float(-R["blend"][i]), 3),
                "evalWord": wd,
                "evalRate": round(by_word[wd] * 100, 1) if wd in by_word else None,
                "evalN": wcnt.get(wd, {}).get("件数"),
                "parts": [round(float(x), 4) for x in R["contrib"][i][:len(wide)]],
            })
        lines.append("")
        viz["races"].append({
            "id": rid, "place": place, "r": int(rid[10:12]), "post": post, "title": title,
            "surf": r["surf"], "dist": r["dist"], "ground": r["ground"], "turn": r["turn"],
            "cls": PT.CLSNAME.get(r["cls"], r["cls"]), "n": r["n"],
            "cell": "木48+市場", "debut": 0,
            "weights": [1.0] * len(wide),
            "g12": round(R["g12"], 2), "g23": 0.0, "g34": 0.0,
            "shape": "—", "horses": sorted(hs, key=lambda x: -x["score"])})

    viz["races"].sort(key=lambda x: x["post"])
    if md_path:
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        open(md_path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        print(f"書き出しました → {md_path}")
    if viz_path:
        json.dump(viz, open(viz_path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"書き出しました → {viz_path}")


if __name__ == "__main__":
    main()
