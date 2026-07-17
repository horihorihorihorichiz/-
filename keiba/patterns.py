# -*- coding: utf-8 -*-
"""買いパターンカタログ（pattern_mine.py のウォークフォワード統計に基づく）。
   レースごとに該当パターンを判定し「推奨/縁/見送り」と過去統計ROIを返す。
   基準: ROI≥105%=買い推奨 / 95-105%=プラス圏の縁(小額のみ) / <95%=見送り推奨"""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_stats():
    try:
        rows = json.load(open(os.path.join(_DIR, "pattern_stats.json"), encoding="utf-8"))
        return {r["pattern"]: r for r in rows}
    except Exception:
        return {}


STATS = _load_stats()
# 乖離単勝はモデル系列で101〜117%のレンジ(線形117.2%/227点, V3-WF111.1%/309点, 本採掘100.8%/255点)
KAIRI_NOTE = "WF実測レンジ101〜117%(3系列)・現状唯一のプラス圏"


def verdict_of(roi):
    if roi >= 105:
        return "◎買い推奨"
    if roi >= 95:
        return "△縁(小額のみ)"
    return "✕見送り推奨"


# 2段階採掘(pattern_lab.py 7/14)の生存者: 発見(202511-04)+確認(202605-07)両方プラスのみ
SURVIVORS = [
    dict(cond="中距離", roi=130.5, dev="108.4%/89点", conf="191.9%/32点", n=121),
    dict(cond="上級(2勝+)", roi=129.9, dev="137.5%/105点", conf="112.2%/45点", n=150),
    dict(cond="ダ", roi=121.9, dev="109.7%/96点", conf="161.0%/30点", n=126),
    dict(cond="混戦(gap小)", roi=105.8, dev="104.3%/167点", conf="109.4%/69点", n=236),
]


def classify(order, tan, field, surface=None, dist=None, tier=None, gap12=None):
    """order=V3得点順の馬番リスト, tan={num:単勝オッズ}, field=頭数。
       返り値: [(パターン名, 買い目説明, ROI, 判定, note)]"""
    out = []
    if not order or not tan:
        return out
    t1 = order[0]
    mr = (sorted(tan, key=lambda h: tan[h]).index(t1) + 1) if t1 in tan else 99
    mrb = "1人気" if mr == 1 else ("2-3人気" if mr <= 3 else "4人気以下")
    fs = "小頭数" if field <= 12 else "多頭数"

    def add(key, desc, note=""):
        s = STATS.get(key)
        if not s:
            return
        roi = s["roi"]
        out.append((key, desc, roi, verdict_of(roi), note))

    if mr >= 4:
        add("乖離単勝(1位が4人気以下)", f"単勝 {t1}", KAIRI_NOTE)
        # 条件付き強化版(2段階採掘の生存者)
        hits = []
        if dist and 1401 <= dist <= 1900:
            hits.append(SURVIVORS[0])
        if tier and tier >= 6:
            hits.append(SURVIVORS[1])
        if surface == "ダ":
            hits.append(SURVIVORS[2])
        if gap12 is not None and gap12 < 0.45:
            hits.append(SURVIVORS[3])
        for s2 in hits:
            out.append((f"乖離単勝×{s2['cond']}", f"単勝 {t1} (強化条件該当)",
                        s2["roi"], "◎買い推奨",
                        f"発見{s2['dev']}→確認{s2['conf']} 通算{s2['n']}点"))
        # ヴェルテンベルク型(7/14 lab4生存者): 中距離の乖離レースは三連複軸×市場上位3ながしも重ねる
        if dist and 1401 <= dist <= 1900:
            mtop = [n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:3]
            if len(mtop) >= 3:
                out.append(("三連複軸×市場上位3ながし×中距離",
                            f"三連複 {t1}軸 - {sorted(mtop)} ながし(3点)",
                            121.5, "◎買い推奨",
                            "発見116.4%/89R→確認135.6%/32R 通算121R。軸が2-3着でも獲れる(ヴェルテンベルク型)"))
    else:
        add(f"単勝1位[{mrb}]", f"単勝 {t1}")
    add(f"複勝1位[{mrb}]", f"複勝 {t1}")
    if len(order) >= 2:
        add(f"ワイド1-2位[{mrb}]", f"ワイド {'-'.join(map(str, sorted(order[:2])))}")
        add(f"馬連1-2位[{mrb}]", f"馬連 {'-'.join(map(str, sorted(order[:2])))}")
    if len(order) >= 5:
        add(f"三連複BOX上位5[{fs}]", f"三連複BOX {sorted(order[:5])} (10点)")
        add(f"三連複軸1位ながし2-5位[{fs}]", f"三連複 {t1}軸-{sorted(order[1:5])} (6点)")
    out.sort(key=lambda x: -x[2])
    return out


def print_patterns(order, tan, field, surface=None, dist=None, tier=None, gap12=None):
    pats = classify(order, tan, field, surface=surface, dist=dist, tier=tier, gap12=gap12)
    if not pats:
        return
    print("\n🎯 パターン判定（ウォークフォワード実測ROI・未来を知らない状態での過去統計）")
    for name, desc, roi, verd, note in pats:
        line = f"  {verd} {name}: {desc}  [過去ROI {roi:.1f}%]"
        if note:
            line += f" ※{note}"
        print(line)
    best = pats[0]
    if best[2] >= 95:
        print(f"  → 本線: {best[1]}（{best[0]} / 過去ROI {best[2]:.1f}%）")
    else:
        print("  → 全パターンがROI95%未満＝このレースは統計的に見送りが正解")
