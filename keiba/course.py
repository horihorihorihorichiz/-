# -*- coding: utf-8 -*-
"""コース特性判定 (Venue Group = VG)。template-v99.27.md の内外別VG定義をコード化。
   これまで fetch_race/harvest が vg=2 固定にしていた見落としを修正する土台。

   VG: 1=瞬発(+0.6) 2=持続(+0.1) 3=フラット(0) 4=小回り(-0.2) 5=消耗(-0.5)
   内外の判定:
     - io 引数(netkeibaの (内)/(外) 表記, JRA芝で有効)を最優先
     - 無ければ距離とコース定義から判定 (NARの大井などは netkeiba が(右)しか出さないため必須)

   ★大井ダ1600m は内回り(左回り)=VG4。同じ大井でも1400/1200=外回りVG2 と別物。
   ★新潟芝1400m 等は内外両設定 → io表記が要る(無ければ保守的に内側)。
"""

# io表記を含むJRA芝の内外境界(内外両設定 or 外回り専用距離)
_JRA_SHIBA_OUTER = {          # (venue): {外回りとみなす距離}
    "新潟": {1600, 1800, 2000, 3000, 3200},   # 1400は内外両設定(io必須)
    "京都": {1400, 1600, 1800, 2200, 2400, 3000, 3200},  # 1400/1600は両設定寄り
    "阪神": {1600, 1800, 2400, 2600},
}

def course_vg(venue, surface, dist, io=None):
    """venue×surface×dist(+netkeiba内外表記io) → VG(1..5)"""
    v = (venue or "").strip()
    s = surface or ""
    d = dist or 0
    io = io if io in ("内", "外") else None

    # ---- NAR(地方) ----
    if v == "大井":
        if s == "ダ" and d in (1500, 1600, 1650):
            return 4                     # 内回り(左回り)=小回り
        return 2                         # 外回り=持続
    if v in ("船橋", "川崎", "名古屋"):
        return 4
    if v in ("園田", "姫路", "高知", "佐賀", "笠松", "金沢", "水沢", "浦和"):
        return 5
    if v == "門別":
        return 3
    if v == "盛岡":
        return 2 if s == "芝" else 4     # 芝=持続 / ダ=小回り

    # ---- JRA(中央) ----
    if v == "東京":
        return 1 if s == "芝" else 2     # 芝=瞬発 / ダ=持続
    if v == "中京":
        return 2
    if v in ("中山", "函館", "福島", "小倉"):
        return 4                         # 全距離 小回り
    if v == "札幌":
        return 3
    if v in ("新潟", "京都", "阪神"):
        # ダートは内外なしの既定VG
        if s == "ダ":
            return 3 if v in ("新潟", "京都") else 4   # 阪神ダ=小回り
        # 芝: io表記があれば確定
        if io == "外":
            return 1
        if io == "内":
            return 3 if v in ("新潟", "京都") else 4   # 阪神芝内=小回り
        # io無し: 距離定義で外回りか判定
        if d in _JRA_SHIBA_OUTER.get(v, set()):
            return 1
        # 残り=内回り(保守的)
        return 3 if v in ("新潟", "京都") else 4

    return 3    # 未知の場はフラット


def parse_io(racedata_text):
    """netkeiba RaceData01 テキストから (内)/(外) を抽出。無ければNone(大井は(右)等でNone)"""
    import re
    m = re.search(r"[（(]\s*(内|外)\s*[）)]", racedata_text or "")
    return m.group(1) if m else None


VG_LABEL = {1: "瞬発(外/直長)", 2: "持続", 3: "フラット", 4: "小回り(内)", 5: "消耗"}

# NAR場コード(race_id 5-6桁目) → 場名
NAR_CODE = {
    "30": "帯広", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
    "44": "大井", "45": "川崎", "46": "笠松", "47": "金沢", "48": "名古屋",
    "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀",
}

_VENUES = ("札幌 函館 福島 新潟 東京 中山 中京 京都 阪神 小倉 "
           "大井 船橋 川崎 浦和 門別 名古屋 園田 姫路 高知 佐賀 笠松 金沢 盛岡 水沢 帯広").split()

def extract_venue(s):
    """開催文字列(例 '3ヶ月2大井5' や '2東京5') から場名だけ抽出"""
    import re
    m = re.search("(" + "|".join(_VENUES) + ")", s or "")
    return m.group(1) if m else ""
