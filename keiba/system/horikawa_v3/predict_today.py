# -*- coding: utf-8 -*-
"""未発走のレースを採点する。

hk の cmd_predict は保管庫にあるレース（＝着順が確定したレース）しか扱えない。
parse.py にも出馬表（発走前）のパーサが無い。ここはその穴を埋めるもので、
ブラウザから取った出馬表を仮のレコードにして保管庫の末尾に置き、
features.Builder にそのまま計算させる。

  python predict_today.py ../../data/today_cards.json
  python predict_today.py ../../data/today_cards.json --md ../../predictions/20260829.md
  python predict_today.py ../../data/cards_20260830.json --date 20260830       --md ../../predictions/20260830.md --viz ../../data/viz_20260830.json

出せるのは同一レース内の並びとスコアの内訳だけ。買い目や期待値は出さない
（logic.md「この配点の正しい使い方」参照）。
"""
import json
import os
import re
import sys
import unicodedata

import numpy as np

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk import features, fit as F  # noqa: E402
from hk.store import Store  # noqa: E402

import train_eval  # noqa: E402

W_PATH = "weights/hori_w.json"
EVAL_RAW = "../../data/hk_train_raw.json"

CLASSES = ((r"新馬|未勝利", "t10"), (r"1勝クラス|500万", "t6"),
           (r"2勝クラス|1000万", "t5"), (r"3勝クラス|1600万", "t4"),
           (r"オープン|ステークス|重賞|G[ⅠⅡⅢI]", "t3"))
GROUND = {"良": "良", "稍": "稍重", "稍重": "稍重", "重": "重", "不": "不良", "不良": "不良"}


def to_race(rid, card, date):
    """出馬表 → 保管庫の races と同じ形の仮レコード。"""
    # netkeiba の出馬表は全角混じり（「１勝クラス」など）。半角に寄せてから読む。
    nz = lambda x: unicodedata.normalize("NFKC", x or "")
    d01, d02 = nz(card["data01"]), nz(card["data02"])
    m = re.search(r"(芝|ダ|障)\s*(\d+)m\s*\(?\s*(右|左|直線)?\s*(外|内|[A-D])?", d01)
    if not m:
        raise SystemExit(f"{rid}: コースを読めません: {d01}")
    surf, dist, turn = m.group(1), int(m.group(2)), m.group(3) or ""
    io = m.group(4) if m.group(4) in ("外", "内") else ""
    mg = re.search(r"馬場\s*:\s*(\S+)", d01)
    mw = re.search(r"天候\s*:\s*(\S+)", d01)
    cls = ""
    for pat, name in CLASSES:
        if re.search(pat, d02):
            cls = name
            break
    if not cls:
        raise SystemExit(f"{rid}: クラスを読めません: {d02}")

    rows = []
    for h in card["rows"]:
        # 出馬表と同じ class を持つ別表（上がり最速など）の行が混ざる。
        # 馬番が数字で、性齢の列があるものだけを出走馬とみなす。
        if h["cancel"] or not str(h.get("umaban", "")).isdigit() or "sexage" not in h:
            continue
        ms = re.match(r"([牡牝セ騸])(\d+)", h["sexage"])
        bw = re.match(r"(\d+)", h["bw"] or "")
        rows.append({
            "fin": "", "waku": int(h["waku"] or 0), "umaban": int(h["umaban"]),
            "horse": h["horse"], "sex": ms.group(1) if ms else "",
            "age": int(ms.group(2)) if ms else 0,
            "kin": float(h["kin"] or 0), "jockey": h["jockey"],
            "sec": 0.0, "margin": "", "corner": "", "agari": 0.0,
            "odds": 0.0, "pop": 0,
            "bw": int(bw.group(1)) if bw else 0, "bwd": 0,
            "trainer": h["trainer"],
        })
    return {"id": rid, "date": date, "place": rid[4:6], "surf": surf,
            "turn": turn, "io": io, "dist": dist,
            "weather": mw.group(1) if mw else "",
            "ground": GROUND.get(mg.group(1) if mg else "", "良"),
            "cls": cls, "n": len(rows), "rows": rows, "tidx": []}


def eval_words(card, vocab):
    """追い切り表から 馬ID → 評価語。

    追い切り表には2つのレイアウトがある。ふつうのレースは1頭1行（評価語は
    右から3列目）だが、特別戦や重賞は1頭が2行に割れ、1行目に馬名と短評、
    2行目に時計と評価語が入る。列位置で拾うと後者で取りこぼす。

    そこで列位置ではなく、166語の辞書に載っている語かどうかで判定する。
    直前に出てきた馬IDにその語を結びつける。
    """
    out = {}
    cur = None
    for x in card["oikiri"]:
        if x["horse"]:
            cur = x["horse"]
        if cur is None:
            continue
        for c in x["cells"]:
            t = (c or "").strip()
            if t in vocab:
                out.setdefault(cur, t)
                break
    return out


PLACES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
          "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}
CLSNAME = {"t10": "新馬・未勝利", "t6": "1勝クラス", "t5": "2勝クラス",
           "t4": "3勝クラス", "t3": "オープン"}


def SHAPE(g12, g23, g34):
    """設計図の g12/g23/g34 による形。しきい値は設計図に無いので暫定値。"""
    if g12 >= 1.0:
        return "1強"
    if g23 >= 1.0:
        return "2強"
    if g34 >= 1.0:
        return "3強"
    if g12 >= 0.5 and g23 >= 0.5 and g34 >= 0.5:
        return "階段"
    return "混戦"


def render_md(results, cards, names, level, when):
    L = [f"# 予想 {when[:4]}-{when[4:6]}-{when[6:8]}", ""]
    L.append(f"配点表 `weights/hori_w.json`（{len(names)}成分・採用段階 {level}）による、")
    L.append("同一レース内の並びとスコアの内訳。**買い目と期待値は出していない。**")
    L.append("")
    L.append("> 点数が高い＝買い、ではない。未知期間1,707Rの実測で3着内率は 59.64%")
    L.append("> （市場 66.14%）、市場に条件付けた上乗せは控除率20%を越えるのに必要な")
    L.append("> 0.223 nats に対して最大 0.0019 nats。買う根拠とされる発火表")
    L.append("> `plus_fires.json` は未作成。詳しくは `system/logic.md`。")
    L.append("")
    for rid in sorted(results, key=lambda k: (results[k][7], k)):
        r, d, Z, wv, score, miss, ew, post, debut = results[rid]
        place = PLACES.get(r["place"], r["place"])
        title = cards[rid].get("name", "")
        L.append(f'## {place}{int(rid[10:12])}R　{post}発走　'
                 f'{title}　{r["surf"]}{r["dist"]}m {r["ground"]}　'
                 f'{CLSNAME.get(r["cls"], r["cls"])}　{r["n"]}頭')
        L.append("")
        L.append(f'`{rid}`　配点セル `{d["k"].get(level, d["k"]["L1"])}`')
        notes = []
        if debut == r["n"]:
            notes.append("**全馬が初出走。過去走から作る成分がほぼ空で、並びの根拠は薄い**")
        elif debut:
            notes.append(f"初出走 {debut}頭")
        if miss:
            notes.append(f"調教評価が引けなかった馬 {miss}頭（レース内平均で埋めたので寄与0）")
        if not any(h["bw"] > 0 for h in r["rows"]):
            notes.append("馬体重が未発表。成分「馬体重」は全馬同値で寄与0")
        for n in notes:
            L.append(f"　※ {n}")
        L.append("")
        L.append("| 順 | 馬番 | 馬名 | 得点 | 追い切り評価 | 効いた成分（上位3） |")
        L.append("|--:|--:|---|--:|---|---|")
        order = sorted(range(r["n"]), key=lambda i: -score[i])
        for k, i in enumerate(order):
            h = r["rows"][i]
            parts = sorted(((names[j], Z[i][j] * wv[j]) for j in range(len(names))),
                           key=lambda x: -abs(x[1]))[:3]
            nm = next((c["name"] for c in cards[rid]["rows"]
                       if c["horse"] == h["horse"]), h["horse"])
            top = " ".join(f'{a}{v:+.1f}' for a, v in parts)
            L.append(f'| {k+1} | {h["umaban"]} | {nm} | {score[i]:.1f} | '
                     f'{ew.get(h["horse"], "—")} | {top} |')
        sd = float(np.std(score)) or 1.0
        g = lambda a, bq: (score[order[a]] - score[order[bq]]) / sd
        L.append("")
        L.append(f'形: **{SHAPE(g(0,1), g(1,2), g(2,3))}**　'
                 f'g12={g(0,1):.2f} g23={g(1,2):.2f} g34={g(2,3):.2f}')
        L.append("")
    return "\n".join(L)


def main():
    cards = json.load(open(sys.argv[1], encoding="utf-8"))
    opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    md_path, viz_path = opt("--md"), opt("--viz")
    date = opt("--date") or "20260829"
    w = json.load(open(W_PATH, encoding="utf-8"))
    names, level = w["names"], w.get("level", "L1")
    use_tev = train_eval.NAME in names

    tev_table = None
    if use_tev:
        words, per_race = train_eval.load_evalcode(EVAL_RAW)
        tev_table, info = train_eval.learn(config.DB_PATH, words, per_race, config.CUT_VAL)
        by_word = {words[i]: v for i, v in tev_table.items()}
        wcnt = {x["語"]: x for x in info["words"]}
        vocab = set(words)

    m = F.Model()
    m.names = names
    m.G = np.array(w["G"])
    for a in ("L1", "A", "B", "C"):
        setattr(m, a, {k: np.array(v) for k, v in w[a].items()})
    m.n, m.rep = w["n"], w["rep"]

    st = Store(config.DB_PATH)
    races = st.all_races()
    targets = {rid: to_race(rid, c, date) for rid, c in cards.items()}
    for rid in sorted(targets):
        races.append(targets[rid])

    book = features.Book(races, config.CUT_HIST)
    b = features.WideBuilder(book, oikiri={}, market=False)
    nf = len(features.BASE_NAMES)
    want = set(targets)
    results = {}

    for ri, r in enumerate(book.races):
        if r["id"] in want:
            d = b.build_wide(ri)
            Z = [list(row[:nf]) for row in d["Z"]]
            if use_tev:
                ew = eval_words(cards[r["id"]], vocab)
                col = train_eval.znorm_column(
                    [by_word.get(ew.get(h["horse"], ""), float("nan")) for h in r["rows"]])
                for row, x in zip(Z, col):
                    row.append(x)
                miss = sum(1 for h in r["rows"] if ew.get(h["horse"]) not in by_word)
            else:
                miss = None
            Z = np.array(Z, float)
            wv = m.w(d["k"], level)
            score = Z @ wv
            debut = sum(1 for h in r["rows"] if b.rec[h["horse"]]["n"] == 0)
            post = re.search(r"(\d{1,2}:\d{2})発走",
                             unicodedata.normalize("NFKC", cards[r["id"]]["data01"]))
            results[r["id"]] = (r, d, Z, wv, score, miss,
                                ew if use_tev else {}, post.group(1) if post else "", debut)
        b.advance(r)

    if md_path:
        os.makedirs(os.path.dirname(md_path), exist_ok=True)
        when = next(iter(results.values()))[0]["date"]
        io_open = open(md_path, "w", encoding="utf-8", newline="\n")
        io_open.write(render_md(results, cards, names, level, when) + "\n")
        io_open.close()
        print(f"書き出しました → {md_path}")

    if viz_path:
        out = {"names": names, "level": level, "date": date,
               "baseRate": round(info["全体3着内率"] * 100, 1),
               "evalTop": sorted(info["words"], key=lambda x: -x["縮小後"])[:6],
               "evalBottom": sorted(info["words"], key=lambda x: x["縮小後"])[:6],
               "races": []}
        for rid in sorted(results, key=lambda k: (results[k][7], k)):
            r, d, Z, wv, score, miss, ew, post, debut = results[rid]
            hs = []
            for i, h in enumerate(r["rows"]):
                c = next((c for c in cards[rid]["rows"] if c["horse"] == h["horse"]), {})
                wd = ew.get(h["horse"], "")
                hs.append({"umaban": h["umaban"], "waku": h["waku"],
                           "name": c.get("name", h["horse"]), "sexage": c.get("sexage", ""),
                           "kin": h["kin"], "jockey": c.get("jockeyName", ""),
                           "stable": c.get("stable", ""), "bw": h["bw"],
                           "score": round(float(score[i]), 3), "evalWord": wd,
                           "evalRate": round(by_word[wd] * 100, 1) if wd in by_word else None,
                           "evalN": wcnt.get(wd, {}).get("件数"),
                           "parts": [round(float(Z[i][j] * wv[j]), 3) for j in range(len(names))]})
            o = sorted(range(len(score)), key=lambda i: -score[i])
            sd = float(np.std(score)) or 1.0
            g = lambda a, bq: round(float((score[o[a]] - score[o[bq]]) / sd), 2)
            out["races"].append({
                "id": rid, "place": PLACES.get(r["place"], r["place"]),
                "r": int(rid[10:12]), "post": post,
                "title": cards[rid].get("name", ""),
                "surf": r["surf"], "dist": r["dist"], "ground": r["ground"],
                "turn": r["turn"], "cls": CLSNAME.get(r["cls"], r["cls"]), "n": r["n"],
                "cell": d["k"].get(level, d["k"]["L1"]), "debut": debut,
                "weights": [round(float(x), 2) for x in wv],
                "g12": g(0, 1), "g23": g(1, 2), "g34": g(2, 3),
                "shape": SHAPE(g(0, 1), g(1, 2), g(2, 3)), "horses": hs})
        json.dump(out, open(viz_path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"書き出しました → {viz_path}")

    for rid in sorted(results):
        r, d, Z, wv, score, miss, ew, post, debut = results[rid]
        place = PLACES.get(r["place"], r["place"])
        print(f'\n=== {place}{int(rid[10:12])}R  {r["surf"]}{r["dist"]}m {r["ground"]} '
              f'{r["cls"]} {r["n"]}頭  配点層={level} セル={d["k"][level if level in d["k"] else "L1"]} ===')
        if miss:
            print(f'  ※ 調教評価が引けなかった馬 {miss}頭（レース内平均で埋め、寄与0）')
        order = sorted(range(r["n"]), key=lambda i: -score[i])
        sd = float(np.std(score)) or 1.0
        print(f'  {"順":>2} {"馬番":>3} {"馬名":<14}{"得点":>7}  効いた成分（上位3）')
        for k, i in enumerate(order):
            h = r["rows"][i]
            parts = sorted(((names[j], Z[i][j] * wv[j]) for j in range(len(names))),
                           key=lambda x: -abs(x[1]))[:3]
            nm = next((c["name"] for c in cards[rid]["rows"]
                       if c["horse"] == h["horse"]), h["horse"])
            top = "  ".join(f'{a}{v:+.1f}' for a, v in parts)
            print(f'  {k+1:>2} {h["umaban"]:>3} {nm:<14}{score[i]:>7.1f}  {top}')
        g = lambda a, bq: (score[order[a]] - score[order[bq]]) / sd
        print(f'  形: g12={g(0,1):.2f} g23={g(1,2):.2f} g34={g(2,3):.2f}')


if __name__ == "__main__":
    main()
