#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workout.py — netkeibaプレミアム「調教タイム生値」パーサ + 特徴量生成 (v0.2 / 2026-08-17)

■ 入力フォーマット (premium_workout_YYYYMMDD.txt)
    $<race_id> <場R>                      … レース見出し行
    馬番,追切日(MM/DD),コース,馬場,乗り役,タイム列,位置,脚色

■ タイム列の仕様（検算済み。詳細は WORKOUT_NOTES_20260817.md / verify_file()）
    スラッシュ区切りで「累計タイム / 次カラムまでのラップ」を **交互** に並べたもの。
    ラップは常に「その累計 − 次の累計」（最後は「1F − 0」＝ラスト1F）。
    これは全行・全ラップで残差 0.0（完全一致）で確認済み。

    ただし **累計カラムのハロン割り当てはコース種別で2系統ある**（v0.2の最重要修正）:

      (A) 周回コース系（W/ダ/芝/CW/プール）… netkeibaの [6F,5F,4F,3F,1F] に末尾そろえ
            要素数10 → 6F,5F,4F,3F,1F   要素数8 → 5F,4F,3F,1F
            要素数 6 → 4F,3F,1F         要素数4 → 3F,1F
          2Fカラムが存在しないため、**3Fの直後のラップだけ2ハロン分**になる。
            例: 41.6/29.0/12.6/12.6 → 41.6-12.6 = 29.0 ✔（依頼文の仮説どおり）

      (B) 坂路系（栗坂/美坂 等）… [4F,3F,2F,1F] に末尾そろえ。全ラップが1ハロン分。
            例: 56.9/17.1/39.8/14.4/25.4/13.0/12.4/12.4
                → 4F56.9 / 3F39.8 / 2F25.4 / 1F12.4、ラップ 17.1・14.4・13.0・12.4
          坂路は800m＝4ハロンしかないので (A) を当てると 3F=25.4秒（8.5秒/F）という
          物理的にあり得ない値になる。判別は「最後から2番目のラップ ÷ ラスト1F」:
            (A) 2.1〜2.5（2F区間）  /  (B) 0.9〜1.2（1F区間）
          本モジュールはコース名から (A)/(B) を決め、上記比と 秒/F レンジで自動検算する。

■ 使い方
    python3 workout.py verify   premium_workout_20260816.txt
    python3 workout.py features premium_workout_20260816.txt [--csv out.csv]
    python3 workout.py validate premium_workout_20260816.txt   # 初期検証(要 hist/*.json)

    from workout import parse_file, build_features
    feats = build_features(parse_file("premium_workout_20260816.txt"))  # 1行=1頭
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
HIST_DIR = os.path.join(HERE, "hist")

# ---------------------------------------------------------------- 定数・辞書

#: 周回コース系の累計カラム（ハロン）。末尾そろえで切り出す。2Fカラムが無い。
COLS_TRACK = [6, 5, 4, 3, 1]
#: 坂路系の累計カラム。800m=4Fで、2Fカラムがある。
COLS_SLOPE = [4, 3, 2, 1]

#: 秒/ハロンの許容レンジ（この外に出たらカラム割り当てを疑う）
SPF_MIN, SPF_MAX = 10.0, 23.0

#: 脚色係数。「馬なりで速い＝余力あり」を高得点にする方向で **事前に固定** した値。
#: 一杯に追ってようやく出した時計は額面どおり評価しない、という減点思想。
EFFORT_COEF = {
    "馬也": 1.00,   # 馬なり（追わずにその時計）＝余力最大
    "G強": 0.90,    # ゴール前だけ強め
    "直強": 0.90,   # 直線だけ強め
    "仕掛": 0.85,   # 仕掛けた（暫定: 強め相当。要検証）
    "強め": 0.85,   # 強めに追った
    "一杯": 0.70,   # 一杯に追った＝余力なし
}
DEFAULT_EFFORT_COEF = 0.85

#: 加算版（推奨）。乗算版は z<0 の馬で符号が反転する病理があるため併記する。
EFFORT_BONUS = {"馬也": 0.30, "G強": 0.10, "直強": 0.10,
                "仕掛": 0.00, "強め": 0.00, "一杯": -0.30}
DEFAULT_EFFORT_BONUS = 0.00

#: 乗り役の種別。騎手名が入っていれば "jockey"。
RIDER_NONJOCKEY = {
    "助手": "assistant",     # 調教助手
    "調教師": "trainer", "師": "trainer",
    "見習": "apprentice",    # 見習騎手
}

#: 明示的に判っているコース表記 → (競馬場/トレセン, 種別, レイアウト)
COURSE_TABLE = {
    "栗坂": ("栗東", "slope", "slope"),
    "美坂": ("美浦", "slope", "slope"),
    "南坂": ("美浦", "slope", "slope"),
    "北坂": ("美浦", "slope", "slope"),
    "坂路": ("不明", "slope", "slope"),
    "CW":  ("栗東", "wood", "track"),   # 栗東CWコース
    "DW":  ("栗東", "dirt", "track"),
    "DP":  ("栗東", "dirt", "track"),
    "南W": ("美浦", "wood", "track"),
    "北C": ("美浦", "wood", "track"),
    "美W": ("美浦", "wood", "track"),
    "栗W": ("栗東", "wood", "track"),
}

#: 場コードの先頭1文字 → 競馬場
VENUE_PREFIX = {
    "札": "札幌", "函": "函館", "福": "福島", "新": "新潟", "東": "東京",
    "中": "中山", "京": "京都", "阪": "阪神", "小": "小倉",
    "美": "美浦", "栗": "栗東",
}
#: 種別を表す文字
KIND_CHARS = [("坂", "slope"), ("W", "wood"), ("ダ", "dirt"), ("芝", "turf"),
              ("プ", "pool"), ("P", "pool"), ("C", "wood")]

#: コース欄の末尾に付く注記（コース名ではないので剥がしてフラグ化する）
COURSE_NOTES = {"一番時計": "best_of_day", "併せ": "paired"}

BABA_ORDER = {"良": 0, "稍": 1, "重": 2, "不": 3}


# ---------------------------------------------------------------- パース

class ParseError(ValueError):
    pass


def parse_course(c: str) -> dict:
    """'函W' / '栗坂' / 'CW一番時計' → 場・種別・レイアウト・注記フラグ。"""
    c = c.strip()
    notes = {}
    for note, flag in COURSE_NOTES.items():
        if c.endswith(note):
            notes[flag] = 1
            c = c[: -len(note)]
    c = c.strip()

    if c in COURSE_TABLE:
        venue, kind, layout = COURSE_TABLE[c]
    else:
        venue = VENUE_PREFIX.get(c[:1], c[:1] or "不明")
        kind = "unknown"
        for ch, k in KIND_CHARS:
            if ch in c[1:] or (len(c) == 1 and ch == c):
                kind = k
                break
        layout = "slope" if kind == "slope" else "track"

    out = {"course": c, "venue": venue, "kind": kind, "layout": layout,
           "best_of_day": 0, "paired": 0}
    out.update(notes)
    return out


def parse_times(s: str, layout: str = "track") -> dict:
    """タイム列文字列 → 累計/ラップ。layout は 'track' か 'slope'。

    Returns:
      cum      : {ハロン: 累計秒}   例 {5:72.0, 4:56.1, 3:41.6, 1:12.6}
      lap      : {"5-4": 14.5, ...} 記載どおりのラップ
      start_f  : 開始ハロン
      residual : 検算残差の最大絶対値（累計差 − 記載ラップ）。0.0 が正常。
      spf_min/spf_max : 秒/ハロンの最小・最大（カラム割り当ての妥当性チェック用）
      tail_ratio      : 最後から2番目のラップ ÷ ラスト1F（track≈2.1-2.5 / slope≈1.0）
      layout_flag     : 'ok' / 'suspect'（レイアウトを疑う）
    """
    toks = [t for t in s.strip().split("/") if t != ""]
    try:
        vals = [float(t) for t in toks]
    except ValueError as e:
        raise ParseError(f"非数値トークン: {s!r}") from e
    if len(vals) % 2 != 0:
        raise ParseError(f"要素数が奇数（累計/ラップの対にならない）: {s!r}")

    base = COLS_SLOPE if layout == "slope" else COLS_TRACK
    ncum = len(vals) // 2
    if ncum < 1 or ncum > len(base):
        raise ParseError(f"要素数 {len(vals)} は layout={layout} では想定外: {s!r}")

    cols = base[len(base) - ncum:]           # 末尾そろえ
    cum_vals, lap_vals = vals[0::2], vals[1::2]

    cum, lap, residual = {}, {}, 0.0
    for i, f in enumerate(cols):
        cum[f] = cum_vals[i]
        nxt_f = cols[i + 1] if i + 1 < ncum else 0
        nxt_v = cum_vals[i + 1] if i + 1 < ncum else 0.0
        lap[f"{f}-{nxt_f}"] = lap_vals[i]
        residual = max(residual, abs(cum_vals[i] - nxt_v - lap_vals[i]))

    spf = [cum[f] / f for f in cols]
    tail_ratio = (lap_vals[-2] / lap_vals[-1]) if ncum >= 2 and lap_vals[-1] else None
    flag = "ok"
    if min(spf) < SPF_MIN or max(spf) > SPF_MAX:
        flag = "suspect"
    if tail_ratio is not None:
        want2f = 3 in cols and 2 not in cols      # 3F直後が2F区間になる並び
        if want2f and tail_ratio < 1.6:
            flag = "suspect"
        if (not want2f) and tail_ratio > 1.6:
            flag = "suspect"

    return {"cum": cum, "lap": lap, "start_f": cols[0], "n_tokens": len(vals),
            "residual": round(residual, 4), "spf_min": round(min(spf), 2),
            "spf_max": round(max(spf), 2),
            "tail_ratio": round(tail_ratio, 3) if tail_ratio else None,
            "layout_flag": flag}


def parse_rider(r: str) -> dict:
    """乗り役 → 種別と騎手フラグ。名前が入っていれば騎手扱い。"""
    r = r.strip()
    typ = RIDER_NONJOCKEY.get(r)
    if typ is None:
        typ = "jockey" if r else "unknown"
    return {"rider": r, "rider_type": typ, "jockey_ride": 1 if typ == "jockey" else 0}


def parse_line(line: str, race_id: str | None = None) -> dict:
    """データ1行 → レコード辞書。"""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 8:
        raise ParseError(f"カラム数不足({len(parts)}): {line!r}")
    num, mmdd, course, baba, rider, times, pos, effort = parts[:8]

    rec = {"race_id": race_id, "num": int(num), "wk_date_md": mmdd,
           "baba": baba, "baba_idx": BABA_ORDER.get(baba), "effort": effort,
           "position": int(pos) if re.fullmatch(r"\d+", pos) else None,
           "has_partner": 1 if re.fullmatch(r"\d+", pos) else 0,
           "raw_times": times}
    rec.update(parse_course(course))
    rec.update(parse_times(times, rec["layout"]))
    rec.update(parse_rider(rider))
    return rec


def parse_file(path: str) -> "dict[str, list[dict]]":
    """ファイル → {race_id: [レコード,...]}（記載順を保持）"""
    races: dict[str, list[dict]] = {}
    rid = None
    for i, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("$"):
            rid = line[1:].split()[0]
            races.setdefault(rid, [])
            continue
        if rid is None:
            raise ParseError(f"{path}:{i} レース見出し($race_id)より前にデータ行がある")
        try:
            races[rid].append(parse_line(line, rid))
        except ParseError as e:
            raise ParseError(f"{path}:{i} {e}") from e
    return races


def verify_file(path: str) -> dict:
    """検算: ①累計差 vs 記載ラップ ②秒/ハロンの妥当性 ③未知語彙。"""
    races = parse_file(path)
    n_rows = n_laps = 0
    max_res = 0.0
    worst = None
    dist, suspects = defaultdict(int), []
    unknown_effort, unknown_kind = set(), set()
    spf_lo, spf_hi = 99.0, 0.0
    for rid, rows in races.items():
        for r in rows:
            n_rows += 1
            n_laps += len(r["lap"])
            dist[f'{r["layout"]}/{r["n_tokens"]}'] += 1
            spf_lo, spf_hi = min(spf_lo, r["spf_min"]), max(spf_hi, r["spf_max"])
            if r["effort"] not in EFFORT_COEF:
                unknown_effort.add(r["effort"])
            if r["kind"] == "unknown":
                unknown_kind.add(r["course"])
            if r["layout_flag"] != "ok":
                suspects.append((rid, r["num"], r["course"], r["raw_times"]))
            if r["residual"] > max_res:
                max_res, worst = r["residual"], (rid, r["num"], r["raw_times"])
    return {"races": len(races), "rows": n_rows, "laps": n_laps,
            "max_residual": max_res, "worst_residual_row": worst,
            "layout_token_dist": dict(dist),
            "sec_per_furlong_range": [spf_lo, spf_hi],
            "layout_suspect_rows": suspects,
            "unknown_effort": sorted(unknown_effort),
            "unknown_course": sorted(unknown_kind)}


# ---------------------------------------------------------------- 特徴量

def _mean_sd(xs):
    n = len(xs)
    if n == 0:
        return None, None
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / n)   # 母分散(ddof=0)


def _add_derived(r: dict) -> None:
    """1頭分の素性（コース差をまだ吸収していない生の量）。

    坂路/周回で共通に取れるのは 4F・3F・1F の累計。ここから先は
    「(f3 - f1)/2」のように **カラム構成に依存しない形** で組み立てる。
    """
    cum, lap = r["cum"], r["lap"]
    for f in (6, 5, 4, 3, 2, 1):
        r[f"f{f}"] = cum.get(f)
    r["last_1f"] = cum.get(1)
    r["last_3f"] = cum.get(3)
    r["last_4f"] = cum.get(4)

    f3, f1 = cum.get(3), cum.get(1)
    # 3F地点→1F地点（2ハロン）。坂路は2Fカラムがあるが、周回と揃えるため差で作る。
    r["mid_2f"] = (f3 - f1) if (f3 is not None and f1 is not None) else None
    r["mid_2f_per_f"] = r["mid_2f"] / 2.0 if r["mid_2f"] is not None else None
    r["f3_per_f"] = f3 / 3.0 if f3 is not None else None
    r["f4_per_f"] = cum[4] / 4.0 if cum.get(4) is not None else None

    # 終い加速度: 3F平均ラップ ÷ ラスト1F。>1 なら終いに向けて加速している。
    r["accel_1f_vs_3f"] = (r["f3_per_f"] / f1) if (r["f3_per_f"] and f1) else None
    # 直前2F平均 ÷ ラスト1F。より短いスパンの加速（accel_1f_vs_3f の単調変換）。
    r["accel_1f_vs_2f"] = (r["mid_2f_per_f"] / f1) if (r["mid_2f_per_f"] and f1) else None

    r["effort_coef"] = EFFORT_COEF.get(r["effort"], DEFAULT_EFFORT_COEF)
    r["effort_bonus"] = EFFORT_BONUS.get(r["effort"], DEFAULT_EFFORT_BONUS)


def _group_keys(r: dict):
    """z-score の集計グループを細かい順に返す（前から順に n を満たすものを採用）。"""
    return [
        ("course_baba", (r["course"], r["baba"])),
        ("course", (r["course"],)),
        ("kind", (r["kind"],)),
        ("all", ("*",)),
    ]


def _zscore_by_group(rows, field, min_n=4, out=None):
    """同一グループ内でのタイムの z（**符号反転済み: 高い＝速い**）。

    母数が min_n 未満のグループは 1 段粗いキーへフォールバックする。
    """
    out = out or f"z_{field}"
    stats = {}
    for level, _ in _group_keys(rows[0]):
        buckets = defaultdict(list)
        for r in rows:
            v = r.get(field)
            if v is not None:
                buckets[dict(_group_keys(r))[level]].append(v)
        stats[level] = {k: _mean_sd(v) for k, v in buckets.items()}
        stats[level + "_n"] = {k: len(v) for k, v in buckets.items()}

    for r in rows:
        v = r.get(field)
        if v is None:
            r[out] = r[out + "_group"] = None
            r[out + "_n"] = 0
            continue
        for level, key in _group_keys(r):
            n = stats[level + "_n"].get(key, 0)
            if n >= min_n or level == "all":
                m, sd = stats[level][key]
                r[out] = round(-(v - m) / sd, 4) if sd and sd > 1e-9 else 0.0
                r[out + "_group"] = f"{level}:{'/'.join(map(str, key))}"
                r[out + "_n"] = n
                break
    return rows


def _rank_in_race(rows, field, out, higher_is_better=False):
    """レース内順位パーセンタイル。1.0=そのレースで最良、0.0=最悪。"""
    by_race = defaultdict(list)
    for r in rows:
        by_race[r["race_id"]].append(r)
    for _rid, rs in by_race.items():
        vals = [(r.get(field), r) for r in rs if r.get(field) is not None]
        n = len(vals)
        vals.sort(key=lambda t: t[0], reverse=higher_is_better)
        for i, (_, r) in enumerate(vals):
            r[out] = round(1.0 - i / (n - 1), 4) if n > 1 else 0.5
            r[out + "_rank"] = i + 1
            r[out + "_of"] = n
        for r in rs:
            r.setdefault(out, None)
    return rows


def race_date(race_id: str) -> "str | None":
    """hist/{race_id}.json から開催日(YYYYMMDD)を取る。無ければ None。"""
    p = os.path.join(HIST_DIR, f"{race_id}.json")
    if not os.path.exists(p):
        return None
    try:
        return str(json.load(open(p, encoding="utf-8")).get("date"))
    except Exception:
        return None


def _days_between(md: str, ymd: "str | None") -> "int | None":
    """追切日(MM/DD) と レース日(YYYYMMDD) の日数差。年跨ぎを補正。"""
    if not ymd or len(ymd) != 8:
        return None
    import datetime as dt
    try:
        rd = dt.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
        mm, dd = (int(x) for x in md.split("/"))
        wd = dt.date(rd.year, mm, dd)
    except ValueError:
        return None
    if wd > rd:                       # 年末年始跨ぎ
        wd = dt.date(rd.year - 1, mm, dd)
    return (rd - wd).days


def build_features(races, race_dates=None, min_group_n=4) -> "list[dict]":
    """パース結果 → 1頭1行の特徴量リスト。

    コース差の吸収は2系統:
      (a) 同一 (コース,馬場) 内の z-score（母数不足なら コース→種別→全体 にフォールバック）
      (b) 同一レース内の相対順位パーセンタイル（標本が小さいうちはこちらが主力）
    """
    rows = ([r for rs in races.values() for r in rs]
            if isinstance(races, dict) else list(races))
    if not rows:
        return []

    for r in rows:
        _add_derived(r)

    # (a) コース×馬場の z（高い＝速い）
    for fld in ("last_1f", "last_3f", "mid_2f_per_f"):
        _zscore_by_group(rows, fld, min_n=min_group_n, out=f"z_{fld}")

    # (b) レース内相対（タイムは小さいほど良い / 加速度は大きいほど良い）
    _rank_in_race(rows, "last_1f", "pr_last_1f", higher_is_better=False)
    _rank_in_race(rows, "last_3f", "pr_last_3f", higher_is_better=False)
    _rank_in_race(rows, "accel_1f_vs_3f", "pr_accel", higher_is_better=True)
    _rank_in_race(rows, "z_last_1f", "pr_z_last_1f", higher_is_better=True)

    # 余力指標
    for r in rows:
        z1, z3 = r.get("z_last_1f"), r.get("z_last_3f")
        c, b = r["effort_coef"], r["effort_bonus"]
        # 乗算版（依頼仕様どおり）。z<0 側で符号が反転する既知の病理あり → NOTES参照
        r["reserve_mult_1f"] = round(z1 * c, 4) if z1 is not None else None
        r["reserve_mult_3f"] = round(z3 * c, 4) if z3 is not None else None
        # 加算版（推奨）。遅い馬でも「一杯に追って遅い」が正しく最低評価になる
        r["reserve_add_1f"] = round(z1 + b, 4) if z1 is not None else None
        r["reserve_add_3f"] = round(z3 + b, 4) if z3 is not None else None

    race_dates = race_dates or {}
    for r in rows:
        ymd = race_dates.get(r["race_id"]) or race_date(r["race_id"])
        r["race_date"] = ymd
        r["days_to_race"] = _days_between(r["wk_date_md"], ymd)
    return rows


FEATURE_COLUMNS = [
    "race_id", "num", "race_date", "wk_date_md", "days_to_race",
    "course", "venue", "kind", "layout", "layout_flag", "best_of_day",
    "baba", "baba_idx", "rider", "rider_type", "jockey_ride",
    "effort", "effort_coef", "position", "has_partner", "start_f",
    "f6", "f5", "f4", "f3", "f2", "f1",
    "last_1f", "last_3f", "last_4f", "f3_per_f", "mid_2f", "mid_2f_per_f",
    "accel_1f_vs_3f", "accel_1f_vs_2f",
    "z_last_1f", "z_last_1f_group", "z_last_1f_n", "z_last_3f", "z_mid_2f_per_f",
    "pr_last_1f", "pr_last_1f_rank", "pr_last_3f", "pr_accel", "pr_z_last_1f",
    "reserve_mult_1f", "reserve_mult_3f", "reserve_add_1f", "reserve_add_3f",
]


def to_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


# ---------------------------------------------------------------- 初期検証

def load_outcomes(race_ids):
    """hist/{rid}.json から {(rid,num): {top3,finish,odds,ninki,field}} を作る。"""
    out = {}
    for rid in race_ids:
        p = os.path.join(HIST_DIR, f"{rid}.json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        field = d.get("race", {}).get("field")
        for o in d.get("result", {}).get("order", []):
            try:
                rank = int(str(o.get("rank")).strip())
            except (TypeError, ValueError):
                rank = None
            out[(rid, o["num"])] = {
                "finish": rank, "top3": 1 if rank and rank <= 3 else 0,
                "win": 1 if rank == 1 else 0,
                "odds": o.get("odds"), "ninki": o.get("ninki"), "field": field}
    return out


def _logit_fit(X, y, l2=1e-3, iters=200):
    """ニュートン法のロジスティック回帰（切片は X に含めて渡す）。numpy のみ。"""
    import numpy as np
    X = np.asarray(X, float); y = np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-X @ b))
        W = np.clip(p * (1 - p), 1e-9, None)
        g = X.T @ (y - p) - l2 * b
        H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    p = 1.0 / (1.0 + np.exp(-X @ b))
    W = np.clip(p * (1 - p), 1e-9, None)
    H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
    se = np.sqrt(np.diag(np.linalg.pinv(H)))
    return b, se


def auc(scores, labels):
    """同順位を平均順位で扱う AUC。"""
    pairs = sorted(zip(scores, labels))
    pos = sum(labels); neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    ranks, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    s = sum(rk for rk, (_, lab) in zip(ranks, pairs) if lab == 1)
    return (s - pos * (pos + 1) / 2.0) / (pos * neg)


def needed_n(p_base=0.22, or_target=1.10, r2_market=0.0, alpha=0.05, power=0.80):
    """ロジスティック回帰で 1SD あたり OR=or_target を検出するのに要る頭数。"""
    za, zb = 1.959964, 0.8416212
    se_max = math.log(or_target) / (za + zb)
    return (1.0 / (p_base * (1 - p_base) * se_max ** 2)) / max(1e-6, 1.0 - r2_market)


VALIDATE_FEATS = [
    "z_last_1f", "z_last_3f", "z_mid_2f_per_f", "pr_last_1f", "pr_last_3f",
    "pr_accel", "accel_1f_vs_3f", "reserve_mult_1f", "reserve_add_1f",
    "reserve_mult_3f", "reserve_add_3f", "days_to_race", "jockey_ride",
    "has_partner", "position",
]


def cmd_validate(path, nperm=400, seed=7):
    import numpy as np
    from scipy.stats import norm
    races = parse_file(path)
    rows = build_features(races)
    out = load_outcomes(races.keys())

    data = []
    for r in rows:
        o = out.get((r["race_id"], r["num"]))
        if o and o.get("odds") and o.get("finish"):
            d = dict(r); d.update(o); data.append(d)
    n = len(data)
    y = np.array([d["top3"] for d in data], float)
    lo = np.array([math.log(d["odds"]) for d in data])
    rid = np.array([d["race_id"] for d in data])
    print(f"# 初期検証 n={n}頭 / {len(set(rid))}レース  (★極小標本。予測力の結論は出さない)")
    print(f"  複勝(3着内)率 = {int(y.sum())}/{n} = {y.mean():.3f}")
    print(f"  市場(log単勝オッズ)のみ: AUC={auc(list(-lo), [int(v) for v in y]):.3f}")
    print()

    hdr = (f"{'feature':<18}{'n':>4}{'mean':>8}{'sd':>7}{'AUC':>7}{'r_top3':>8}"
           f"{'R2_mkt':>8}{'beta|mkt':>10}{'SE':>7}{'z':>7}{'p':>7}")
    print(hdr); print("-" * len(hdr))
    zobs = {}
    for f in VALIDATE_FEATS:
        ok = [i for i, d in enumerate(data) if d.get(f) is not None]
        if len(ok) < 10:
            continue
        x = np.array([float(data[i][f]) for i in ok])
        yy, ll = y[ok], lo[ok]
        m, sd = float(x.mean()), float(x.std())
        a = auc(list(x), [int(v) for v in yy])
        r = float(np.corrcoef(x, yy)[0, 1]) if sd > 0 else 0.0
        rm = float(np.corrcoef(x, ll)[0, 1]) if sd > 0 else 0.0
        xz = (x - m) / sd if sd > 1e-9 else x * 0
        b, se = _logit_fit(np.column_stack([np.ones(len(ok)), ll, xz]), yy)
        z = b[2] / se[2] if se[2] > 0 else 0.0
        zobs[f] = abs(z)
        print(f"{f:<18}{len(ok):>4}{m:>8.3f}{sd:>7.3f}{a:>7.3f}{r:>+8.3f}"
              f"{rm*rm:>8.3f}{b[2]:>+10.3f}{se[2]:>7.3f}{z:>+7.2f}"
              f"{2*(1-norm.cdf(abs(z))):>7.3f}")
    print(f"\n※ p値は多重比較未補正・n={n}。有意/非有意いずれの主張も不可。参考表示のみ。")
    print("※ accel_1f_vs_3f と accel_1f_vs_2f は定義上の単調変換（相関1.000）。片方だけ使う。")

    # レース内シャッフルによる帰無検定（family-wise）
    rng = np.random.default_rng(seed)
    feats = [f for f in zobs]

    def maxz(yv):
        best = 0.0
        for f in feats:
            ok = [i for i, d in enumerate(data) if d.get(f) is not None]
            x = np.array([float(data[i][f]) for i in ok])
            s = x.std() or 1.0
            b, se = _logit_fit(np.column_stack(
                [np.ones(len(ok)), lo[ok], (x - x.mean()) / s]), yv[ok])
            if se[2] > 0:
                best = max(best, abs(b[2] / se[2]))
        return best

    obs = max(zobs.values())
    null = []
    for _ in range(nperm):
        yp = y.copy()
        for r_ in set(rid):
            mm = rid == r_
            v = yp[mm]; rng.shuffle(v); yp[mm] = v
        null.append(maxz(yp))
    null = np.array(null)
    print(f"\n# 帰無検定（複勝をレース内でシャッフル×{nperm}回, {len(feats)}特徴のmax|z|）")
    print(f"  観測 max|z| = {obs:.2f}")
    print(f"  帰無分布   : 中央値 {np.median(null):.2f} / 90%点 "
          f"{np.quantile(null,.9):.2f} / 95%点 {np.quantile(null,.95):.2f}")
    print(f"  family-wise p = {(null >= obs).mean():.3f}"
          f"   （1に近い＝観測は雑音と区別できない）")

    # 記述クロス集計
    for key in ("effort", "rider_type", "course"):
        g = defaultdict(lambda: [0, 0])
        for d in data:
            g[d[key]][0] += 1; g[d[key]][1] += d["top3"]
        print(f"\n-- 複勝率 by {key}（記述のみ・検定なし）")
        for k, (cn, t) in sorted(g.items(), key=lambda kv: -kv[1][0]):
            print(f"   {str(k):<12} n={cn:<4} top3={t:<3} rate={t/cn:.3f}")

    print("\n# 必要サンプル数（1SDあたり OR を検出力80%・両側5%で検出、複勝率22%想定）")
    print("  r2 = その特徴が市場オッズで説明される割合（既に価格に織り込まれている分）")
    print(f"{'OR/SD':>7}{'r2=0':>10}{'r2=0.30':>10}{'r2=0.50':>10}{'≒レース数':>12}")
    for orv in (1.05, 1.10, 1.15, 1.20, 1.30):
        n0, n3, n5 = (needed_n(or_target=orv),
                      needed_n(or_target=orv, r2_market=0.30),
                      needed_n(or_target=orv, r2_market=0.50))
        print(f"{orv:>7.2f}{n0:>10.0f}{n3:>10.0f}{n5:>10.0f}{n3/12.5:>12.0f}")
    za, zb = 1.959964, 0.8416212
    se = math.sqrt(1.0 / (n * 0.22 * 0.78))
    print(f"\n  現状 n={n}頭 で検出力80%を得られる最小効果は OR/SD ≒ "
          f"{math.exp((za+zb)*se):.2f}（＝ほぼ何も検出できない）")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, path = argv[1], argv[2]
    if cmd == "verify":
        v = verify_file(path)
        print(json.dumps(v, ensure_ascii=False, indent=2))
        ok = (v["max_residual"] <= 0.051 and not v["layout_suspect_rows"]
              and not v["unknown_effort"] and not v["unknown_course"])
        print("OK" if ok else "NG: 上の suspect/unknown を確認すること")
        return 0 if ok else 2
    if cmd == "features":
        rows = build_features(parse_file(path))
        if "--csv" in argv:
            p = argv[argv.index("--csv") + 1]
            print("wrote", to_csv(rows, p), len(rows), "rows")
        else:
            for r in rows[:5]:
                print(json.dumps({k: r.get(k) for k in FEATURE_COLUMNS},
                                 ensure_ascii=False))
            print(f"... total {len(rows)} rows")
        return 0
    if cmd == "validate":
        cmd_validate(path)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
