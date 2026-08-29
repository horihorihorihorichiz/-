# -*- coding: utf-8 -*-
"""調教評価の成分を、ブラウザ保管庫の評価語から作る。

ブラウザの meta ストアには追い切りの生データ（コース・ラップ）が無く、
hk の _train() が要求する形にはできない。入っているのは

  evalcode  … 166語の評価語辞書 + レースごとの「馬番→語インデックス」
  trainfeat … レースごとの「馬番:縦断:?:?」

の2つ。このうち評価語だけを使う。

やること:
  1. 学習期間（date < CUT_VAL）のレースだけで、語ごとの3着内率を数える
     未知期間は一切見ない
  2. 出現の少ない語は全体平均へ経験ベイズで縮める。縮小定数 k は
     hk.fit.eb_k をそのまま使う（E[d^2] = tau^2 + sigma^2/n の分解、
     lambda = n/(n+k)）
  3. 縮めた3着内率を、その馬の調教評価の値とする

採らなかったもの:
  調教縦断  trainfeat の第2フィールド。範囲 -1084〜1209 で単位が不明。
            hk の縦断は「同種コースでの過去の自己ベストとの秒差」なので
            スケールが合う保証がない
  調教本数  trainfeat の第3フィールドは 0〜9 の1桁のみで、初出走 17% /
            経験あり 32% がゼロ。前走からの本数ならこの向きは逆になるはずで、
            本数ではなく符号なしの符号値と見られる。整数の本数ではないので採らない
"""
import json
import sqlite3
from collections import defaultdict

import numpy as np

from hk.fit import eb_k

NAME = "調教評価"


def _blocks(parts):
    out = {}
    for b in parts:
        c = b.find(",")
        if c < 0:
            continue
        out[b[:c]] = b[c + 1:]
    return out


def load_evalcode(path):
    """{レースID: {馬番: 語インデックス}} と語の一覧を返す。"""
    raw = json.load(open(path, encoding="utf-8"))
    parts = raw["evalcode"].split("|")
    if parts[0] != "HKEV1":
        raise SystemExit(f"{path}: evalcode の形式が想定と違います: {parts[0]}")
    words = json.loads(parts[1])
    per_race = {}
    for rid, body in _blocks(parts[2:]).items():
        m = {}
        for e in body.split(";"):
            if not e:
                continue
            um, wi = e.split(":", 1)
            if wi != "":
                k = int(wi)
                if 0 <= k < len(words):
                    m[um] = k
        per_race[rid] = m
    return words, per_race


def _fin(x):
    try:
        return int(x)
    except Exception:
        return None


def learn(db_path, words, per_race, cut_val):
    """語ごとの3着内率を学習期間だけで数え、経験ベイズで縮める。"""
    cnt = defaultdict(int)
    top3 = defaultdict(int)
    db = sqlite3.connect(db_path)
    n_races = 0
    for rid, date, body in db.execute("SELECT id,date,body FROM races ORDER BY date,id"):
        if date >= cut_val:
            continue                      # 未知期間は絶対に見ない
        m = per_race.get(rid)
        if not m:
            continue
        n_races += 1
        for h in json.loads(body)["rows"]:
            wi = m.get(str(h["umaban"]))
            if wi is None:
                continue
            f = _fin(h["fin"])
            if f is None:
                continue                  # 中止・除外は分母にも入れない
            cnt[wi] += 1
            if f <= 3:
                top3[wi] += 1

    tot_n = sum(cnt.values())
    tot_t = sum(top3.values())
    if tot_n == 0:
        raise SystemExit("学習期間に評価語が1件も見つかりません")
    base = tot_t / tot_n

    ks = sorted(cnt)
    p = np.array([top3[w] / cnt[w] for w in ks], float)
    ns = np.array([cnt[w] for w in ks], float)
    k = eb_k((p - base).reshape(-1, 1), ns)[0]
    lam = ns / (ns + k) if np.isfinite(k) else np.zeros_like(ns)
    shrunk = base + lam * (p - base)

    table = {int(w): float(s) for w, s in zip(ks, shrunk)}
    info = {
        "全体3着内率": base,
        "語数": len(ks),
        "延べ頭数": tot_n,
        "レース数": n_races,
        "k": (None if not np.isfinite(k) else float(k)),
        "words": [
            {"語": words[w], "件数": int(cnt[w]), "素の3着内率": float(top3[w] / cnt[w]),
             "縮小後": float(table[w]), "lambda": float(l)}
            for w, l in zip(ks, lam)
        ],
    }
    return table, info


def value_map(per_race, table):
    """{レースID: {馬番: 調教評価の値}}。語が無い馬は入れない（=NaN扱い）。"""
    out = {}
    for rid, m in per_race.items():
        out[rid] = {um: table[wi] for um, wi in m.items() if wi in table}
    return out


def znorm_column(vals):
    """hk の _znorm と同じ扱い。NaN はレース内平均で埋めてから標準化する。
       埋めた馬の値はちょうど 0 になる（情報が無い＝平均的）。"""
    ok = [v for v in vals if v == v]
    m = sum(ok) / len(ok) if ok else 0.0
    v = [m if x != x else x for x in vals]
    n = len(v)
    mm = sum(v) / n
    sd = (sum((x - mm) ** 2 for x in v) / n) ** 0.5 or 1.0
    return [(x - mm) / sd for x in v]
