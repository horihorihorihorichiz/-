# -*- coding: utf-8 -*-
"""部分詳細図を「分かる」形に分解した図たち。

detail_key.svg    どこを切った図なのか
detail_wall.svg   外壁の6層（横に切った図）
detail_foot.svg   足元まわりの拡大（番号つき）
detail_floor2.svg 2階の床まわりの拡大（番号つき）
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

PATTERNS = '''<defs>
<pattern id="w2" width="7" height="7" patternUnits="userSpaceOnUse"
 patternTransform="rotate(45)">
 <rect width="7" height="7" fill="#efdcbb"/>
 <line x1="0" y1="0" x2="0" y2="7" stroke="#c9a86c" stroke-width="1"/>
</pattern>
<pattern id="c2" width="10" height="10" patternUnits="userSpaceOnUse">
 <rect width="10" height="10" fill="#e2e2e2"/>
 <circle cx="2.5" cy="3" r="1.1" fill="#a8a8a8"/>
 <circle cx="7.5" cy="7.5" r="0.9" fill="#b8b8b8"/>
 <path d="M5 1 L6.4 3.6 L3.6 3.6 Z" fill="#bdbdbd"/>
</pattern>
<pattern id="i2" width="9" height="9" patternUnits="userSpaceOnUse">
 <rect width="9" height="9" fill="#fde8f0"/>
 <path d="M0 4.5 Q2.25 1 4.5 4.5 T9 4.5" stroke="#e79bbb" stroke-width="1"
  fill="none"/>
</pattern>
<pattern id="g2" width="9" height="9" patternUnits="userSpaceOnUse">
 <rect width="9" height="9" fill="#ece5d8"/>
 <circle cx="2" cy="2.5" r="1.6" fill="none" stroke="#b9ab8e" stroke-width=".8"/>
 <circle cx="6.5" cy="6" r="1.9" fill="none" stroke="#b9ab8e" stroke-width=".8"/>
</pattern>
<pattern id="d2" width="8" height="8" patternUnits="userSpaceOnUse"
 patternTransform="rotate(45)">
 <rect width="8" height="8" fill="#f2ece0"/>
 <line x1="0" y1="0" x2="0" y2="8" stroke="#cbbfa5" stroke-width=".8"/>
</pattern>
</defs>'''

NAVY = '#1f2937'
RED = '#c0392b'
BLUE = '#1f6fb2'


def num(s, x, y, n, col=NAVY, r=13):
    """番号の丸。"""
    s.circle(x, y, r, fill='#fff', stroke=col, stroke_width=2.0)
    s.text(x, y + 4.5, str(n), size=13, weight='700', fill=col)


# ==========================================================
# 1) どこを切った図なのか
# ==========================================================
def key():
    S = 0.040
    ML, MT = 306, 150
    BW, TOP = 7280.0, 10806.0
    NOKI = 9350.0
    W, H = 760, int(MT + TOP * S + 150)
    s = Svg(W, H)
    s.add(PATTERNS)
    s.text(W / 2.0, 36, 'この図は、建物のどこを切ったもの？', size=22,
           weight='700')
    s.text(W / 2.0, 60,
           '外壁を上から下まで、まっすぐ包丁で切ったところを横から見ています。',
           size=12.5, fill='#666')
    s.text(W / 2.0, 82,
           'そのうち「地面のところ」と「2階の床のところ」を拡大したのが部分詳細図。',
           size=12.5, fill=RED, weight='700')

    def X(mm):
        return ML + mm * S

    def Y(mm):
        return MT + (TOP - mm) * S

    # 地面
    s.rect(X(-1400), Y(0), (BW + 2800) * S, 46, fill='url(#d2)', stroke='none')
    s.line(X(-1400), Y(0), X(BW + 1400), Y(0), stroke='#333', stroke_width=2)
    s.text(X(BW + 700), Y(0) - 7, 'GL（地面）', size=11, anchor='start',
           fill='#555', weight='700')
    # 建物
    s.rect(X(0), Y(NOKI), BW * S, NOKI * S, fill='#f3efe7', stroke=NAVY,
           stroke_width=2.2)
    s.polygon([(X(-600), Y(NOKI - 240)), (X(BW / 2), Y(TOP)),
               (X(BW + 600), Y(NOKI - 240))], fill='#5b6b7a', stroke='#33414d',
              stroke_width=1.6)
    for mm, lab in ((550, '1階'), (3650, '2階'), (6550, '3階')):
        s.line(X(0), Y(mm), X(BW), Y(mm), stroke='#c7bfb2', stroke_width=1.0)
    for mm, lab in ((2100, '1階'), (5100, '2階'), (7950, '3階')):
        s.text(X(BW / 2), Y(mm), lab, size=15, fill='#9aa3ab', weight='700')

    # 切る位置（左の外壁）
    s.line(X(0), Y(TOP) - 26, X(0), Y(-700), stroke=RED, stroke_width=2.0,
           stroke_dasharray='10 4 3 4')
    s.text(X(0) + 14, Y(TOP) - 22, 'この線で切る', size=12.5, anchor='start',
           fill=RED, weight='700')

    # 拡大する2か所
    for mm0, mm1, lab, ly in ((3100, 3800, 'B', 3450), (-400, 800, 'A', 200)):
        s.rect(X(-700), Y(mm1), 1500 * S, (mm1 - mm0) * S, fill='none',
               stroke=RED, stroke_width=2.0)
        num(s, X(-700) - 24, Y(ly), lab, RED, 14)

    # 引き出し
    for ly, ty, big, small in ((3450, 300, 'B　2階の床のところ',
                               '胴差・床・天井の納まり'),
                              (200, 470, 'A　地面のところ',
                               '基礎・土台・1階の床の納まり')):
        s.line(X(-700) - 12, Y(ly), 216, ty + 4, stroke=RED,
               stroke_width=1.0, stroke_dasharray='5 4')
        s.text(210, ty, big, size=13, anchor='end', weight='700', fill=RED)
        s.text(210, ty + 20, small, size=11, anchor='end', fill='#777')

    ly = MT + TOP * S + 46
    s.rect(40, ly - 20, W - 80, 84, fill='#fff8e1', stroke='#e0c060',
           stroke_width=1, rx=8)
    s.text(56, ly, '★ 1/20 は「実物の20分の1」。1/100の平面図の5倍の大きさ。'
                   'だから細かい部材まで描ける。', size=12, anchor='start',
           fill='#6b5200')
    s.text(56, ly + 22, '★ 図の左が室内、右が屋外。'
                        'この向きは絶対に変えないこと。', size=12,
           anchor='start', fill='#6b5200')
    s.text(56, ly + 44, '★ 問題文で「どこを描くか」は指定される。'
                        'AとBの両方を描けるようにしておく。', size=12,
           anchor='start', fill='#6b5200')
    return s


# ==========================================================
# 2) 外壁の6層（横に切った図）
# ==========================================================
def wall():
    S = 2.05                       # 1mm あたり
    LEN = 190.0                    # 見せる壁の長さ(mm)
    ML, MT = 96, 178
    LAYERS = [
        (15,  '#ebebeb', '強化石膏ボード', '15', '火に耐える'),
        (105, None,      '柱 ＋ グラスウール', '105', '構造 ＋ 断熱'),
        (9,   '#f0e2c8', '構造用合板', '9', '地震・風に耐える'),
        (0.0, None,      '透湿防水シート', '—', '雨は止め湿気は通す'),
        (18,  '#f7f7f7', '通気胴縁', '18', '湿気を上へ逃がす'),
        (16,  '#cfd8dc', '窯業系サイディング', '16', '外側の仕上げ'),
    ]
    total = sum(l[0] for l in LAYERS)
    tw = total * S
    W = int(ML + tw + 330)
    H = int(MT + LEN * S + 150)
    s = Svg(W, H)
    s.add(PATTERNS)
    s.text(W / 2.0, 36, '外壁の6層　── 壁を「横に」切ってみる', size=22,
           weight='700')
    s.text(W / 2.0, 60,
           '縦の断面だと細すぎて分かりません。水平に切って上から見た形にしました。',
           size=12.5, fill='#666')
    s.text(W / 2.0, 82, '左が室内、右が屋外。この順番を丸ごと覚えます。',
           size=12.5, fill=RED, weight='700')

    y0, y1 = MT, MT + LEN * S
    s.rect(ML - 72, y0, 64, y1 - y0, fill='#fbf7ef', stroke='none')
    s.text_rot(ML - 40, (y0 + y1) / 2.0, '室　内', -90, size=16, weight='700',
               fill='#8a8f88')
    s.rect(ML + tw + 8, y0, 64, y1 - y0, fill='#eef2f5', stroke='none')
    s.text_rot(ML + tw + 40, (y0 + y1) / 2.0, '屋　外', -90, size=16,
               weight='700', fill='#8a8f88')

    # 層を描く
    x = ML
    centers = []
    for i, (t, fill, name, th, memo) in enumerate(LAYERS, 1):
        wpx = t * S
        if name.startswith('柱'):
            half = (y1 - y0) * 0.46
            s.rect(x, y0, wpx, half, fill='url(#w2)', stroke='#8a6a35',
                   stroke_width=1.4)
            s.rect(x, y0 + half, wpx, y1 - y0 - half, fill='url(#i2)',
                   stroke='#d98cae', stroke_width=1.2)
            s.text(x + wpx / 2.0, y0 + half / 2.0 - 4, '柱 105×105', size=13,
                   weight='700', fill='#6b5220')
            s.text(x + wpx / 2.0, y0 + half / 2.0 + 16, '（柱のあるところ）',
                   size=10.5, fill='#8a7550')
            s.text(x + wpx / 2.0, y0 + half + 28, 'グラスウール 16K t=100',
                   size=12.5, weight='700', fill='#a34e76')
            s.text(x + wpx / 2.0, y0 + half + 48, '（柱と柱の間）', size=10.5,
                   fill='#b5789a')
            s.line(x, y0 + half, x + wpx, y0 + half, stroke='#999',
                   stroke_width=1.0, stroke_dasharray='5 4')
        elif t == 0.0:
            s.line(x, y0, x, y1, stroke='#2f7fd0', stroke_width=3.4)
        else:
            s.rect(x, y0, wpx, y1 - y0, fill=fill, stroke='#666',
                   stroke_width=1.2)
        centers.append(x + wpx / 2.0)
        if t > 0:
            s.dim_h(x, x + wpx, y1 + 34, th)
        x += wpx

    # 番号は等間隔に並べて、引き出し線で層につなぐ（重ならない）
    slot = tw / len(LAYERS)
    for i, cx in enumerate(centers, 1):
        nx = ML + slot * (i - 0.5)
        s.poly([(nx, y0 - 34), (nx, y0 - 20), (cx, y0 - 6)], stroke='#999',
               stroke_width=0.9)
        num(s, nx, y0 - 46, i)

    s.dim_h(ML, ML + tw, y1 + 76, '合計 163mm')

    # 右の一覧
    lx = ML + tw + 106
    s.text(lx, MT - 44, '内から外へ、この順番', size=13.5, weight='700',
           anchor='start')
    for i, (t, fill, name, th, memo) in enumerate(LAYERS, 1):
        yy = MT - 12 + (i - 1) * 46
        num(s, lx + 12, yy, i, r=12)
        s.text(lx + 32, yy - 2, name, size=13, weight='700', anchor='start')
        s.text(lx + 32, yy + 16,
               ('t=' + th if t > 0 else '厚さなし') + '　' + memo, size=11,
               fill='#777', anchor='start')

    ly = y1 + 112
    s.rect(40, ly - 20, W - 80, 50, fill='#f6f9f4', stroke='#bcd4bc',
           stroke_width=1, rx=8)
    s.text(W / 2.0, ly + 2,
           '15 ・ 105 ・ 9 ・ 18 ・ 16　　合計 163mm。この5つの数字だけ覚える。',
           size=14, weight='700', fill='#245a2c')
    s.text(W / 2.0, ly + 24,
           '④の透湿防水シートは薄すぎて厚さを描けないので、線1本で表す。',
           size=11.5, fill='#4a7a52')
    return s



# ==========================================================
# 3) 拡大図（足元まわり／2階の床まわり）
# ==========================================================
S3 = 0.62
X3MIN, X3MAX = -330.0, 250.0
ML3 = 122


def _x(mm):
    return ML3 + (mm - X3MIN) * S3


def _zoom(title, sub, lo, hi, notes, body):
    """lo..hi(mm) の範囲を拡大した図を作る。"""
    MT = 122
    dh = (hi - lo) * S3
    W = 764
    H = int(MT + dh + 54)
    s = Svg(W, H)
    s.add(PATTERNS)

    def Y(mm):
        return MT + (hi - mm) * S3

    s.text(W / 2.0, 36, title, size=21, weight='700')
    s.text(W / 2.0, 59, sub, size=12.5, fill='#666')
    # 室内・屋外
    s.text(_x(-250), MT - 22, '← 室内', size=13, weight='700', fill='#8a8f88')
    s.text(_x(170), MT - 22, '屋外 →', size=13, weight='700', fill='#8a8f88')
    body(s, _x, Y)
    # 番号と一覧
    lx = _x(X3MAX) + 42
    s.line(lx - 18, MT - 6, lx - 18, MT + dh, stroke='#eee', stroke_width=1)
    for i, (nx, ny, ly, name, memo) in enumerate(notes):
        num(s, _x(nx), Y(ny), name)
        yy = ly
        num(s, lx + 12, yy, name, r=12)
        s.text(lx + 32, yy - 2, memo[0], size=12.5, weight='700',
               anchor='start')
        if len(memo) > 1:
            s.text(lx + 32, yy + 16, memo[1], size=10.5, fill='#777',
                   anchor='start')
    return s


def _wall_layers(s, X, Y, top, bottom):
    """外壁の6層を縦に描く（top/bottom は mm）。"""
    s.rect(X(-67.5), Y(top), X(-52.5) - X(-67.5), Y(bottom) - Y(top),
           fill='#ebebeb', stroke='#666', stroke_width=0.9)
    s.rect(X(-52.5), Y(top), X(52.5) - X(-52.5), Y(bottom) - Y(top),
           fill='url(#i2)', stroke='#8a6a35', stroke_width=1.3)
    s.rect(X(52.5), Y(top), X(61.5) - X(52.5), Y(bottom) - Y(top),
           fill='#f0e2c8', stroke='#666', stroke_width=0.9)
    s.line(X(61.5), Y(top), X(61.5), Y(bottom), stroke='#2f7fd0',
           stroke_width=1.8)
    s.rect(X(61.5), Y(top), X(79.5) - X(61.5), Y(bottom) - Y(top),
           fill='#f7f7f7', stroke='#666', stroke_width=0.9)
    s.rect(X(79.5), Y(top), X(95.5) - X(79.5), Y(bottom) - Y(top),
           fill='#cfd8dc', stroke='#666', stroke_width=0.9)


def foot():
    LO, HI = -420.0, 820.0

    def body(s, X, Y):
        # 地面
        s.rect(X(95.5), Y(0), X(X3MAX) - X(95.5), Y(LO) - Y(0),
               fill='url(#d2)', stroke='none')
        s.line(X(75), Y(0), X(X3MAX), Y(0), stroke='#333', stroke_width=1.8)
        s.text(X(X3MAX) - 4, Y(0) - 7, 'GL', size=12, anchor='end',
               weight='700')
        # 砕石・基礎
        s.rect(X(X3MIN), Y(-300), X(75) - X(X3MIN), Y(-360) - Y(-300),
               fill='url(#g2)', stroke='#aa9', sw=0.8) if False else None
        s.rect(X(X3MIN), Y(-300), X(75) - X(X3MIN), Y(-360) - Y(-300),
               fill='url(#g2)', stroke='#aa9', stroke_width=0.8)
        s.line(X(X3MIN), Y(-300), X(75), Y(-300), stroke='#2f7fd0',
               stroke_width=1.6)
        s.rect(X(X3MIN), Y(-150), X(75) - X(X3MIN), Y(-300) - Y(-150),
               fill='url(#c2)', stroke='#666', stroke_width=1.2)
        s.rect(X(-75), Y(386), X(75) - X(-75), Y(-150) - Y(386),
               fill='url(#c2)', stroke='#666', stroke_width=1.2)
        s.text(X(-215), Y(140), '床　下', size=12, fill='#999')
        # 基礎パッキン・土台
        s.rect(X(-52.5), Y(406), X(52.5) - X(-52.5), Y(386) - Y(406),
               fill='#d9d9d9', stroke='#555', stroke_width=1.0)
        s.rect(X(-52.5), Y(511), X(52.5) - X(-52.5), Y(406) - Y(511),
               fill='url(#w2)', stroke='#8a6a35', stroke_width=1.5)
        # 1階の床
        s.rect(X(X3MIN), Y(535), X(52.5) - X(X3MIN), Y(511) - Y(535),
               fill='#f5e7cb', stroke='#8a6a35', stroke_width=0.9)
        s.rect(X(X3MIN), Y(550), X(-52.5) - X(X3MIN), Y(535) - Y(550),
               fill='#e6d3ad', stroke='#8a6a35', stroke_width=0.9)
        s.rect(X(X3MIN), Y(511), X(-52.5) - X(X3MIN), Y(461) - Y(511),
               fill='url(#i2)', stroke='#d98cae', stroke_width=0.9)
        # 外壁
        _wall_layers(s, X, Y, HI, 511)
        s.rect(X(79.5), Y(420), X(95.5) - X(79.5), Y(511) - Y(420),
               fill='#cfd8dc', stroke='#666', stroke_width=0.9)
        s.rect(X(-67.5), Y(550), X(-52.5) - X(-67.5), Y(511) - Y(550),
               fill='#ebebeb', stroke='#666', stroke_width=0.9)
        # 水切り
        s.poly([(X(61.5), Y(430)), (X(102), Y(398)), (X(116), Y(366))],
               stroke='#607d8b', stroke_width=2.4)
        # アンカーボルト
        s.line(X(-20), Y(120), X(-20), Y(566), stroke='#444',
               stroke_width=2.2)
        s.line(X(-40), Y(120), X(-20), Y(120), stroke='#444',
               stroke_width=2.2)
        # レベル線
        for mm, lab in ((550, '1FL  GL+550'), (386, '基礎天端 GL+386'),
                        (0, 'GL ±0'), (-300, '基礎の底 GL−300')):
            s.line(X(X3MIN) - 24, Y(mm), X(130), Y(mm), stroke='#b03060',
                   stroke_width=0.8, stroke_dasharray='9 3 2 3')
            s.text(X(X3MIN) - 26, Y(mm) - 5, lab, size=10.5, anchor='end',
                   fill='#b03060', weight='700')
        # 寸法
        dx = X(X3MIN) - 96
        for a, b, lab in ((-360, -300, '60'), (-300, -150, '150'),
                          (-150, 386, '536'), (386, 406, '20'),
                          (406, 511, '105')):
            s.line(dx, Y(a), dx, Y(b), stroke='#444', stroke_width=0.8)
            for m in (a, b):
                s.line(dx - 3.5, Y(m), dx + 3.5, Y(m), stroke='#444',
                       stroke_width=0.8)
            s.text_rot(dx - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=9.5,
                       fill='#444')

    notes = [
        (-180, -330, 168, 1, ('砕石 t=60 ＋ 防湿フィルム', '地面を固めて湿気を止める')),
        (-180, -225, 214, 2, ('べた基礎 底盤 t=150', '根入れ300（240以上）')),
        (0, 100, 260, 3, ('べた基礎 立上り t=150', '地上386（300以上）')),
        (-20, 300, 306, 4, ('アンカーボルト M12', '基礎と土台をつなぐ')),
        (0, 396, 352, 5, ('基礎パッキン t=20', '床下の換気口をかねる')),
        (0, 458, 398, 6, ('土台 105×105', '防腐防蟻処理')),
        (-210, 486, 444, 7, ('床断熱 t=50', '押出法ポリスチレンフォーム')),
        (-260, 542, 490, 8, ('1階の床 ＝ 1FL', '構造用合板24 ＋ フローリング15')),
        (20, 700, 536, 9, ('外壁の6層 t=163', '別図（外壁を横に切った図）')),
        (108, 388, 582, 10, ('水切り', '雨を外へ落とす')),
    ]
    return _zoom('拡大A　地面のところ（基礎・土台・1階の床）',
                 '下から順に、作る順番で番号をふってあります。',
                 LO, HI, notes, body)


def floor2():
    LO, HI = 3080.0, 3820.0

    def body(s, X, Y):
        _wall_layers(s, X, Y, HI, LO)
        # 胴差
        s.rect(X(-52.5), Y(3611), X(52.5) - X(-52.5), Y(3311) - Y(3611),
               fill='url(#w2)', stroke='#8a6a35', stroke_width=1.6)
        # 2階の床
        s.rect(X(X3MIN), Y(3635), X(52.5) - X(X3MIN), Y(3611) - Y(3635),
               fill='#f5e7cb', stroke='#8a6a35', stroke_width=1.0)
        s.rect(X(X3MIN), Y(3650), X(-52.5) - X(X3MIN), Y(3635) - Y(3650),
               fill='#e6d3ad', stroke='#8a6a35', stroke_width=1.0)
        # 1階の天井
        s.rect(X(X3MIN), Y(3250), X(-52.5) - X(X3MIN), Y(3240.5) - Y(3250),
               fill='#ebebeb', stroke='#666', stroke_width=0.9)
        for k in range(5):
            xx = X3MIN + 34 + k * 56
            s.rect(X(xx), Y(3290), X(xx + 36) - X(xx), Y(3250) - Y(3290),
                   fill='url(#w2)', stroke='#c9a86c', stroke_width=0.8)
        # 内側の石膏ボード
        s.rect(X(-67.5), Y(3250), X(-52.5) - X(-67.5), Y(LO) - Y(3250),
               fill='#ebebeb', stroke='#666', stroke_width=0.9)
        s.rect(X(-67.5), Y(HI), X(-52.5) - X(-67.5), Y(3650) - Y(HI),
               fill='#ebebeb', stroke='#666', stroke_width=0.9)
        # レベル線
        for mm, lab in ((3650, '2FL  GL+3,650'), (3250, '天井 GL+3,250')):
            s.line(X(X3MIN) - 24, Y(mm), X(130), Y(mm), stroke='#b03060',
                   stroke_width=0.8, stroke_dasharray='9 3 2 3')
            s.text(X(X3MIN) - 26, Y(mm) - 5, lab, size=10.5, anchor='end',
                   fill='#b03060', weight='700')
        dx = X(X3MIN) - 96
        for a, b, lab in ((3311, 3611, '300'), (3611, 3650, '39')):
            s.line(dx, Y(a), dx, Y(b), stroke='#444', stroke_width=0.8)
            for m in (a, b):
                s.line(dx - 3.5, Y(m), dx + 3.5, Y(m), stroke='#444',
                       stroke_width=0.8)
            s.text_rot(dx - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=9.5,
                       fill='#444')

    notes = [
        (0, 3460, 176, 11, ('胴差 105×300', '上の階の床を受ける梁')),
        (-210, 3623, 238, 12, ('構造用合板 t=24', '根太レス＝剛床')),
        (-150, 3643, 300, 13, ('フローリング t=15 ＝ 2FL', 'GL+3,650')),
        (0, 3740, 362, 14, ('2階の柱 105×105', '1階の柱の真上に立つ')),
        (-210, 3245, 424, 15, ('1階の天井', '石膏ボード9.5 ＋ 野縁40×45')),
        (75, 3420, 486, 16, ('外壁は下と同じ6層', '上から下まで同じ構成')),
    ]
    return _zoom('拡大B　2階の床のところ（胴差まわり）',
                 '外壁は地面から屋根まで、ずっと同じ6層です。',
                 LO, HI, notes, body)


if __name__ == '__main__':
    key().save(os.path.join(OUT, 'detail_key.svg'))
    wall().save(os.path.join(OUT, 'detail_wall.svg'))
    foot().save(os.path.join(OUT, 'detail_foot.svg'))
    floor2().save(os.path.join(OUT, 'detail_floor2.svg'))
    print('wrote detail_key / detail_wall / detail_foot / detail_floor2')
