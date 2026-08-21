# -*- coding: utf-8 -*-
"""VG（Venue Group＝コース特性分類）判定。堀川システム Ver.99.27 の定義をコード化。

VG1瞬発(+0.6) / VG2持続(+0.1) / VG3フラット(0) / VG4小回り(-0.2) / VG5消耗(-0.5)

内外回りの区別は、出馬表に内外の情報が無いため**距離で代表させる**。
（例: 京都芝1800は外回りしか無いのでVG1。京都芝2000は内回りなのでVG3）
両設定がある距離は、その場で本数の多い側に寄せた。判断した箇所はコメントに残す。
"""

# 距離帯（堀川システムの定義）
def dist_cat(d):
    if d <= 1400:
        return "S"
    if d <= 2200:
        return "M"
    return "L"


def vg_of(venue, surface, distance):
    """venue=場名(例 '東京'), surface='芝'/'ダ', distance=m → 'VG1'..'VG5' または None"""
    v, s, d = venue, surface, int(distance)

    # ── VG5消耗 ──
    if v in ("園田", "姫路", "高知", "佐賀", "笠松", "金沢", "水沢", "浦和"):
        return "VG5"

    # ── 地方（南関その他）──
    if v == "大井":
        # 外回り 1000/1200/1400/1700/1800/2000/2400/2600 → VG2
        # 内回り 1500/1600/1650 → VG4
        return "VG4" if d in (1500, 1600, 1650) else "VG2"
    if v in ("船橋", "川崎", "名古屋"):
        return "VG4"
    if v == "門別":
        return "VG3"
    if v == "盛岡":
        return "VG2" if s == "芝" else "VG4"

    # ── JRA ──
    if v == "東京":
        return "VG1" if s == "芝" else "VG2"
    if v == "中京":
        return "VG2"
    if v == "札幌":
        return "VG3"
    if v in ("中山", "函館", "福島", "小倉"):
        return "VG4"
    if v == "新潟":
        if s == "ダ":
            return "VG3"
        # 芝: 外回り=1600/1800/2000外/3000/3200 → VG1
        #     1400は内外両設定・1200/2200/2400は内回り → VG3
        #     2000は内外両設定だが内回り開催が多数 → VG3 に寄せた
        return "VG1" if d in (1600, 1800, 3000, 3200) else "VG3"
    if v == "京都":
        if s == "ダ":
            return "VG3"          # ダートは内外なし・全距離VG3
        # 芝外回り 1400外/1600外/1800/2200/2400/3000/3200 → VG1
        # 芝内回り 1100/1200/1400内/1600内/2000 → VG3
        # 1400は内回りが標準・1600は外回り(マイル)が標準 → そう寄せた
        return "VG1" if d in (1600, 1800, 2200, 2400, 3000, 3200) else "VG3"
    if v == "阪神":
        if s == "ダ":
            return "VG4"          # 阪神ダは全距離VG4
        # 芝外回り 1600/1800/2400/2600 → VG1
        # 芝内回り 1200/1400/2000/2200/3000 → VG4
        return "VG1" if d in (1600, 1800, 2400, 2600) else "VG4"
    return None


def cell_of(venue, surface, distance):
    """'VG1/M' のような条件セル名。判定できなければ None。"""
    g = vg_of(venue, surface, distance)
    return f"{g}/{dist_cat(distance)}" if g else None


# LTS配点（Ver.99.27）
LTS_PT = {"VG1": 30, "VG2": 25, "VG3": 20, "VG4": 15, "VG5": 15}
# C補正（Ver.99.27）
C_ADJ = {"VG1": 0.6, "VG2": 0.1, "VG3": 0.0, "VG4": -0.2, "VG5": -0.5}


if __name__ == "__main__":
    tests = [("東京", "芝", 1600), ("東京", "ダ", 1400), ("京都", "芝", 1800),
             ("京都", "芝", 2000), ("阪神", "芝", 1600), ("阪神", "芝", 2000),
             ("阪神", "ダ", 1800), ("中山", "芝", 2500), ("新潟", "芝", 1000),
             ("新潟", "芝", 1600), ("小倉", "ダ", 1700), ("大井", "ダ", 1600)]
    for v, s, d in tests:
        print(f"{v}{s}{d:>5}m → {vg_of(v,s,d)} / {cell_of(v,s,d)}")
