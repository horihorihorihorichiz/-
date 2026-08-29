# -*- coding: utf-8 -*-
"""ブラウザ書き出し(hori_*.jsonl.gz)を SQLite の保管庫に取り込む。

hk 本体には harvest（netkeiba から自分で取る）しか入口が無く、
ブラウザ側の書き出しファイルを読む口が無い。これはその橋渡し。

  python import_export.py ../../data/hori_export.jsonl.gz
  python import_export.py ../../data/hori_races_20260829.jsonl.gz \
                          ../../data/hori_train_20260829.jsonl.gz

列の対応はファイル先頭のヘッダ行（rcols / hcols）に従うので、
書き出し側の列が増減しても取り違えない。ヘッダに無い列は補わない。
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

from hk.store import Store  # noqa: E402

# parse.race() が rows の各要素に入れるキー。書き出しの hcols がこれと
# 食い違っていたら取り込まない（列ずれのまま学習させないため）。
EXPECTED_H = ["fin", "waku", "umaban", "horse", "sex", "age", "kin", "jockey",
              "sec", "margin", "corner", "agari", "odds", "pop", "bw", "bwd", "trainer"]
# races テーブルが必要とする列。
NEEDED_R = ["id", "date", "place", "surf", "turn", "io", "dist",
            "weather", "ground", "cls", "n"]


def load_races(path, st):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        head = json.loads(f.readline())
        if head.get("_") != "horikawa-export":
            raise SystemExit(f"{path}: horikawa-export のファイルではありません")
        rcols, hcols = head["rcols"], head["hcols"]

        missing = [c for c in NEEDED_R if c not in rcols]
        if missing:
            raise SystemExit(f"{path}: レース側に必要な列がありません: {missing}")
        if hcols != EXPECTED_H:
            raise SystemExit(
                f"{path}: 出走馬の列が hk の想定と違います。\n"
                f"  書き出し: {hcols}\n  想定    : {EXPECTED_H}")

        n = 0
        n_tidx = 0
        dates = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            r = dict(zip(rcols, d["r"]))
            rows = [dict(zip(hcols, h)) for h in d["h"]]
            tidx = [float(x) if x else 0.0 for x in (d.get("t") or [])]
            n_tidx += sum(1 for x in tidx if x > 0)

            rec = {k: r.get(k) for k in NEEDED_R}
            for k in ("place", "surf", "turn", "io", "weather", "ground", "cls"):
                rec[k] = "" if rec[k] is None else str(rec[k])
            rec["dist"] = int(rec["dist"] or 0)
            rec["n"] = int(rec["n"] or len(rows))
            rec["rows"] = rows
            rec["tidx"] = tidx

            st.put_race(rec)
            dates.append(rec["date"])
            n += 1
            if n % 2000 == 0:
                st.commit()
                print(f"  {n}レース")
    st.commit()
    return n, dates, n_tidx


def load_train(path, st):
    """調教（meta）側。1行1レコードで、レースIDを持つものだけ取り込む。"""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        head = json.loads(f.readline())
        if head.get("_") != "horikawa-meta":
            raise SystemExit(f"{path}: horikawa-meta のファイルではありません")
        n = 0
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            rid = m.get("id") or m.get("race_id")
            rows = m.get("rows") or m.get("oikiri")
            if not rid or not rows:
                continue
            st.put_oikiri(str(rid), rows)
            n += 1
    st.commit()
    return n


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    st = Store(config.DB_PATH)

    n, dates, n_tidx = load_races(sys.argv[1], st)
    print(f"レース {n}件を取り込みました（保管庫: {config.DB_PATH}）")
    if dates:
        print(f"  期間 {min(dates)} 〜 {max(dates)}")
    if n_tidx == 0:
        print("  警告: タイム指数(tidx)が1件も入っていません。"
              "成分「公式指数」は作れません。")
    else:
        print(f"  タイム指数 {n_tidx}件")

    if len(sys.argv) > 2:
        m = load_train(sys.argv[2], st)
        print(f"調教 {m}レース分を取り込みました")
    else:
        print("  調教ファイルの指定なし。成分「調教縦断/調教本数/調教評価」は作れません。")


if __name__ == "__main__":
    main()
