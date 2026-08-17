#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_score.py -- netkeibaプレミアム「調教レビュー原文」の辞書ベース定量化モジュール

目的:
  レビュー本文(日本語1-2文)から、ポジ/ネガ/条件語を抽出して
  score = (ポジ語のヒット種類数) - (ネガ語のヒット種類数) を返す。
  ライブ運用でも同じ関数を呼べばよいようにモジュール化してある。

設計上の約束(2026-08-17 凍結):
  * 辞書は「結果(着順/オッズ)を見る前」に確定した。以後、成績を見て語彙を足し引きしない。
    もし辞書を変更したら、検証は全段やり直しとして報告すること。
  * 1頭のレビュー内で同じ語が複数回出ても、その語は1回だけ数える(語の重複による水増し防止)。
  * ネガ語は直後10文字以内に否定マーカー(ない/なし/なく/なさ/解消 等)があれば打ち消す。
    例: 「太め感もない」「重苦しさはなし」「反動はなく」「調子落ちはなさそう」→ ネガに数えない。
  * 逆接(「〜だが」「〜ものの」)の減衰は実装しない(恣意性を避けるため)。
  * 「平行線」は直前に「いい意味で」がある場合のみ打ち消す(1件だけ用法が逆のため、事前に規定)。

使い方:
  from review_score import score_review, score_race
  r = score_review("入念に併せ馬を消化し、素軽い動きを見せてきた。仕上がりは良好で初戦から。")
  r['score'], r['pos'], r['neg'], r['cond']
"""
import re
import unicodedata

VERSION = "1.0-frozen-20260817"

# ---------------------------------------------------------------- 辞書本体
# 各エントリは (ラベル, 正規表現) 。ラベルは報告書の語彙一覧と1対1に対応する。

POS_STRONG = [
    ("絶好", r"絶好"),
    ("文句なし", r"文句な"),
    ("万全", r"万全"),
    ("抜群", r"抜群"),
    ("完璧", r"完璧"),
    ("申し分", r"申し分"),
    ("圧倒", r"圧倒"),
    ("大幅アップ", r"大幅アップ"),
    ("好素材", r"好素材"),
    ("豪快", r"豪快"),
]

POS_READY = [
    ("態勢", r"態勢"),
    ("好仕上がり", r"好仕上"),
    ("仕上がる/仕上がった", r"仕上が(?:る|った|り)"),
    ("十分", r"十分"),
    ("力を出せる", r"力[はを]出せる"),
    ("乗り込み", r"乗り込"),
    ("優秀", r"優秀"),
]

POS_FORM = [
    ("素軽", r"素軽"),
    ("力強", r"力強"),
    ("上々", r"上々"),
    ("好気配", r"好気配"),
    ("好ムード", r"好ムード"),
    ("好状態", r"好状態"),
    ("好調(好調時を除く)", r"好調(?!時)"),
    ("好リズム", r"好リズム"),
    ("好調教", r"好調教"),
    ("好加速", r"好加速"),
    ("シャープ", r"シャープ"),
    ("機敏", r"機敏"),
    ("躍動感", r"躍動感"),
    ("活気", r"活気"),
    ("軽快/軽やか", r"軽快|軽やか"),
    ("余力", r"余力"),
    ("目立つ(目立たず除く)", r"目立(?!た[ずな])"),
    ("スムーズ", r"スムーズ"),
    ("気合", r"気合"),
    ("張り", r"張り"),
    ("充実", r"充実"),
    ("及第点", r"及第点"),
    ("期待", r"期待"),
    ("◎/○", r"[◎○]"),
]

POS_IMPROVE = [
    ("上向", r"上向"),
    ("上昇", r"上昇"),
    ("前進", r"前進"),
    ("成長", r"成長"),
    ("良化(待ち/途上を除く)", r"良化(?!.{0,2}(?:待ち|途上))"),
    ("変わり身", r"変わり身"),
]

POS_RESULT = [
    ("先着", r"先着"),
    ("併入", r"併入"),
    ("食らい付", r"食らい付"),
    ("突き放", r"突き放"),
]

NEG = [
    ("地味", r"地味"),
    ("平凡", r"平凡"),
    ("ひと息/一息", r"ひと息|一息"),
    ("物足り", r"物足り"),
    ("劣勢", r"劣勢"),
    ("遅れ", r"遅れ"),
    ("使いつつ", r"使いつつ"),
    ("良化待ち", r"良化待ち"),
    ("良化途上", r"良化途上"),
    ("太め", r"太め"),
    ("不満", r"不満"),
    ("欠(欠ける/欠く)", r"欠"),
    ("今イチ/今ひとつ", r"今イチ|今ひとつ|イマイチ"),
    ("平行線", r"平行線"),
    ("重苦し", r"重苦し"),
    ("調子落ち", r"調子落ち"),
    ("反動", r"反動"),
    ("鈍", r"鈍"),
    ("モタれ/もたつ", r"モタれ|もたつ"),
    ("ズブ", r"ズブ"),
    ("切れず/きれず", r"切れず|きれず"),
    ("強調材料", r"強調材料"),
]

# 条件語(スコアには入れず、ダミー変数として別に持つ)
COND = [
    ("初戦から", r"初戦から"),
    ("久々", r"久々"),
    ("叩き(叩けば/ひと叩き/1度叩いて)", r"叩"),
    ("一度使われ", r"[1１一]度使われ|使われたこと"),
    ("間隔/フレッシュ", r"間隔|フレッシュ"),
    ("除外", r"除外"),
    ("海外帰り", r"海外帰り"),
]

POS_GROUPS = [
    ("POS_STRONG", POS_STRONG),
    ("POS_READY", POS_READY),
    ("POS_FORM", POS_FORM),
    ("POS_IMPROVE", POS_IMPROVE),
    ("POS_RESULT", POS_RESULT),
]

# ネガ打ち消し(直後10文字以内)
NEGATION_WINDOW = 10
# 注: 「なさ」単独は名詞化(物足りなさ/重苦しさ)を誤って打ち消すため「なさそう/なさげ」に限定。
#     (この修正は結果を一切見る前=2026-08-17 の実装バグ修正。語彙自体は変更していない)
NEGATION_RE = re.compile(r"(ない|なし|なく|なさそう|なさげ|解消|苦にしない|感じさせない|感じられない)")


def _normalize(text: str) -> str:
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", str(text)).strip()
    return t


def _hit(pattern: str, text: str):
    """パターンが当たった位置(最初の一つ)を返す。無ければ None。"""
    m = re.search(pattern, text)
    return m


def _neg_cancelled(text: str, m) -> bool:
    """ネガ語が直後の否定表現で打ち消されているか。"""
    tail = text[m.end(): m.end() + NEGATION_WINDOW]
    if NEGATION_RE.search(tail):
        return True
    # 「いい意味で平行線」だけは例外的に打ち消す(事前規定)
    head = text[max(0, m.start() - 8): m.start()]
    if "いい意味" in head:
        return True
    return False


def score_review(text: str) -> dict:
    """レビュー1本を採点する。

    returns dict:
      score      : pos_n - neg_n
      pos_n/neg_n: ヒットしたポジ/ネガ語の種類数
      pos/neg    : ヒットしたラベルのリスト
      neg_cancel : 否定で打ち消されたネガ語ラベル
      cond       : 条件語ラベルのリスト
      grp        : グループ別ヒット数 dict
    """
    t = _normalize(text)
    pos, grp = [], {}
    for gname, terms in POS_GROUPS:
        n = 0
        for label, pat in terms:
            if _hit(pat, t):
                pos.append(label)
                n += 1
        grp[gname] = n
    neg, neg_cancel = [], []
    for label, pat in NEG:
        m = _hit(pat, t)
        if m is None:
            continue
        if _neg_cancelled(t, m):
            neg_cancel.append(label)
        else:
            neg.append(label)
    grp["NEG"] = len(neg)
    cond = [label for label, pat in COND if _hit(pat, t)]
    return {
        "text": t,
        "score": len(pos) - len(neg),
        "pos_n": len(pos),
        "neg_n": len(neg),
        "pos": pos,
        "neg": neg,
        "neg_cancel": neg_cancel,
        "cond": cond,
        "grp": grp,
        "has_neg": 1 if neg else 0,
    }


def score_race(rows) -> list:
    """rows = [(umaban, name, text), ...] を採点し、レース内zスコアも付ける。"""
    out = []
    for num, name, text in rows:
        r = score_review(text)
        r["num"] = num
        r["name"] = name
        out.append(r)
    vals = [r["score"] for r in out]
    n = len(vals)
    mu = sum(vals) / n if n else 0.0
    var = sum((v - mu) ** 2 for v in vals) / n if n else 0.0
    sd = var ** 0.5
    for r in out:
        r["score_c"] = r["score"] - mu                      # レース内センタリング
        r["score_z"] = (r["score"] - mu) / sd if sd > 0 else 0.0
    return out


def load_review_file(path: str) -> dict:
    """race_id,馬番,馬名,本文 形式のファイルを {race_id: [(num,name,text),...]} で返す。"""
    races = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(",", 3)
            if len(parts) < 4:
                continue
            rid, num, name, text = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3]
            races.setdefault(rid, []).append((int(num), name, text))
    return races


def lexicon_summary() -> dict:
    """辞書サイズ(報告書用)。"""
    d = {g: len(terms) for g, terms in POS_GROUPS}
    d["NEG"] = len(NEG)
    d["COND"] = len(COND)
    d["POS_TOTAL"] = sum(len(terms) for _, terms in POS_GROUPS)
    d["ALL_SCORED"] = d["POS_TOTAL"] + d["NEG"]
    return d


if __name__ == "__main__":
    import sys, json
    print("review_score.py", VERSION)
    print(json.dumps(lexicon_summary(), ensure_ascii=False, indent=1))
    for p in sys.argv[1:]:
        races = load_review_file(p)
        for rid, rows in races.items():
            for r in score_race(rows):
                print(f"{rid} {r['num']:>2} {r['name']:<12} score={r['score']:+d} "
                      f"z={r['score_z']:+.2f} pos={r['pos']} neg={r['neg']} "
                      f"cancel={r['neg_cancel']} cond={r['cond']}")
