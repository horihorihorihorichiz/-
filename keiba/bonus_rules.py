# -*- coding: utf-8 -*-
"""加点方式（離散ボーナスルール）の自動発掘と最適化（2026-08-21）。

指示: 「システム組み替えたらいける / 加点方式入れたりしたら」

なぜ加点方式か（前回の実測から）:
  線形の重み付けだけで T5BOX(上位5頭BOXで三連複的中) を最大化すると、
  的中率は上がる（素16.4%→CONFIRM32.7%）が、**的中1回の払戻が-38%落ちてROIが下がる**。
  最適化が「人気どおりの並び」に収束するため。
  → 条件を満たした馬だけに +N点 する離散ルールなら、市場が見ていない型の馬を
     ピンポイントで持ち上げられる。Ver.99.27のTFB/SSC(+8/+10)と同じ構造をデータに探させる。

目的関数は前回と同じユーザー仕様:
  T5BOX / WIN1 / AX16 の的中率。ただし**払戻も同時に見る**（ROIが落ちる加点は採らない）。
"""
import json, itertools, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B


def horse_facts(r):
    """各馬の「加点ルールの材料」を素のまま作る。レース内相対も含む。
       返り値: dict(馬番 -> {特徴名: 値})"""
    out = {}
    n = len(r["nums"])
    # レース内の相対量を作るための材料
    for i, num in enumerate(r["nums"]):
        out[num] = {}
    return out


# ── 候補ルールの定義（人が思いつく形ではなく、素材×閾値の総当たり） ──
def build_candidates(races):
    """(ルール名, 判定関数) のリスト。判定関数は (race, 馬index) -> bool。
       素材は hist の過去走から直接作る（Ver.99.27の成分を経由しない生データ）。"""
    cands = []

    def mk(name, fn):
        cands.append((name, fn))

    # --- 過去走の素材から作る述語 ---
    def past(r, i):
        return r.get("raw_hist", [{}] * len(r["nums"]))[i]

    # 4角位置の型
    for k in (1, 2, 3):
        for th in (0.25, 0.35, 0.45):
            mk(f"4角正規化<={th}が{k}走以上",
               lambda r, i, k=k, th=th: sum(
                   1 for p in past(r, i).get("c4n", []) if p is not None and p <= th) >= k)
    # 上がり最速級
    for k in (1, 2):
        mk(f"レース内上がり1位が{k}走以上",
           lambda r, i, k=k: sum(1 for p in past(r, i).get("ag_rank", []) if p == 1) >= k)
    # 着差（僅差負け）
    for th in (0.2, 0.5):
        for k in (1, 2):
            mk(f"着差{th}秒以内の敗戦が{k}走以上",
               lambda r, i, th=th, k=k: sum(
                   1 for m, rk in zip(past(r, i).get("margin", []), past(r, i).get("rank", []))
                   if m is not None and rk and rk > 1 and abs(m) <= th) >= k)
    # 多頭数での好走
    for fld in (12, 14):
        mk(f"{fld}頭以上で3着内が1走以上",
           lambda r, i, fld=fld: any(
               f and f >= fld and rk and rk <= 3
               for f, rk in zip(past(r, i).get("field", []), past(r, i).get("rank", []))))
    # 距離短縮・延長
    for d in (200, 400):
        mk(f"前走から{d}m以上の短縮",
           lambda r, i, d=d: (past(r, i).get("dist", [None])[0] or 0) - r["distance"] >= d)
        mk(f"前走から{d}m以上の延長",
           lambda r, i, d=d: r["distance"] - (past(r, i).get("dist", [None])[0] or 0) >= d)
    # 休み明け・連戦
    mk("休み明け(間隔85日以上)", lambda r, i: (past(r, i).get("days", [None])[0] or 0) >= 85)
    mk("連戦(間隔21日以内)", lambda r, i: 0 < (past(r, i).get("days", [None])[0] or 999) <= 21)
    # 同コース実績
    mk("同距離±0mで3着内が1走以上",
       lambda r, i: any(d == r["distance"] and rk and rk <= 3
                        for d, rk in zip(past(r, i).get("dist", []), past(r, i).get("rank", []))))
    # 前走大敗からの巻き返し余地
    for th in (8, 10):
        mk(f"前走{th}着以下",
           lambda r, i, th=th: (past(r, i).get("rank", [None])[0] or 0) >= th)
    # ペース経験
    mk("前後半差-1.0秒以下(ハイペース経験)",
       lambda r, i: any(pf is not None and pl is not None and (pf - pl) <= -1.0
                        for pf, pl in zip(past(r, i).get("pf", []), past(r, i).get("pl", []))))
    mk("前後半差+1.0秒以上(スロー経験)",
       lambda r, i: any(pf is not None and pl is not None and (pf - pl) >= 1.0
                        for pf, pl in zip(past(r, i).get("pf", []), past(r, i).get("pl", []))))
    return cands
