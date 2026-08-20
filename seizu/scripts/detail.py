# -*- coding: utf-8 -*-
"""部分詳細図（1/20）外壁 断面：基礎まわり ～ 2階床まわり。

高さの基準（GL＝地面）：
  基礎の底         GL -300 （根入れ 300mm。240mm以上が必要）
  基礎の底盤 厚150  GL -300 ～ -150
  基礎の立上り 厚150 GL -150 ～ +386 （地上部分 386mm。300mm以上が必要）
  基礎パッキン t20  GL +386 ～ +406
  土台 105×105     GL +406 ～ +511
  構造用合板 t24    GL +511 ～ +535
  フローリング t15  GL +535 ～ +550  ＝ 1FL（GL+550）
  1階の階高 3,100   → 2FL ＝ GL +3,650
  胴差 105×300     GL +3,311 ～ +3,611
  1階の天井        GL +3,250 （天井高 2,700）
"""
import os
from svgkit import Svg

S = 0.30                 # 1mm あたりの表示ピクセル
ML, MT = 176, 108
XMIN, XMAX = -420.0, 230.0
TOP_HI, TOP_LO = 3750.0, 3100.0
BOT_HI, BOT_LO = 1000.0, -400.0
GAP = 46.0

TOP_H = (TOP_HI - TOP_LO) * S
BOT_H = (BOT_HI - BOT_LO) * S
DRAW_H = TOP_H + GAP + BOT_H
W, H = 700, int(MT + DRAW_H + 132)
LX = 388.0               # 右側の説明文の位置


def X(mm):
    return ML + (mm - XMIN) * S


def Y(mm):
    if mm >= TOP_LO:
        return MT + (TOP_HI - mm) * S
    return MT + TOP_H + GAP + (BOT_HI - mm) * S


PATTERNS = '''<defs>
<pattern id="pWood" width="7" height="7" patternUnits="userSpaceOnUse"
 patternTransform="rotate(45)">
 <rect width="7" height="7" fill="#efdcbb"/>
 <line x1="0" y1="0" x2="0" y2="7" stroke="#c9a86c" stroke-width="1"/>
</pattern>
<pattern id="pConc" width="10" height="10" patternUnits="userSpaceOnUse">
 <rect width="10" height="10" fill="#e2e2e2"/>
 <circle cx="2.5" cy="3" r="1.1" fill="#a8a8a8"/>
 <circle cx="7.5" cy="7.5" r="0.9" fill="#b8b8b8"/>
 <path d="M5 1 L6.4 3.6 L3.6 3.6 Z" fill="#bdbdbd"/>
</pattern>
<pattern id="pIns" width="8" height="8" patternUnits="userSpaceOnUse">
 <rect width="8" height="8" fill="#fde8f0"/>
 <path d="M0 4 Q2 1 4 4 T8 4" stroke="#e79bbb" stroke-width="0.9"
  fill="none"/>
</pattern>
<pattern id="pGrav" width="9" height="9" patternUnits="userSpaceOnUse">
 <rect width="9" height="9" fill="#ece5d8"/>
 <circle cx="2" cy="2.5" r="1.6" fill="none" stroke="#b9ab8e"
  stroke-width="0.8"/>
 <circle cx="6.5" cy="6" r="1.9" fill="none" stroke="#b9ab8e"
  stroke-width="0.8"/>
</pattern>
<pattern id="pGround" width="8" height="8" patternUnits="userSpaceOnUse"
 patternTransform="rotate(45)">
 <rect width="8" height="8" fill="#f2ece0"/>
 <line x1="0" y1="0" x2="0" y2="8" stroke="#cbbfa5" stroke-width="0.8"/>
</pattern>
</defs>'''


def band(s, x0, x1, y0, y1, fill, stroke='#555', sw=0.9):
    """mm 指定で矩形を描く（y0 が上、y1 が下）。"""
    s.rect(X(x0), Y(y0), X(x1) - X(x0), Y(y1) - Y(y0), fill=fill,
           stroke=stroke, stroke_width=sw)


def callout(s, px_mm, py_mm, ly, text, color='#333'):
    """部材から右側の説明文へ引き出し線を引く。"""
    x0, y0 = X(px_mm), Y(py_mm)
    s.circle(x0, y0, 2.0, fill=color)
    s.poly([(x0, y0), (LX - 16, ly - 4), (LX - 6, ly - 4)], stroke=color,
           stroke_width=0.7)
    s.text(LX, ly, text, size=11, anchor='start', fill='#222')


def draw():
    s = Svg(W, H)
    s.add(PATTERNS)
    s.text(W / 2.0, 34, '部分詳細図（外壁 断面） 1/20', size=21, weight='700')
    s.text(W / 2.0, 57,
           '左が室内・右が屋外　／　準防火地域の準耐火建築物（45分）を想定',
           size=11.5, fill='#666')
    s.text(W / 2.0, 76, '★ 本番の解答用紙に描いて提出するのは、この1枚', size=12,
           fill='#b03060', weight='700')

    xin, xout = XMIN, XMAX

    # 室内・屋外
    s.text(X(-260), MT - 14, '← 室内', size=12.5, weight='700',
           fill='#8a8f88')
    s.text(X(170), MT - 14, '屋外 →', size=12.5, weight='700',
           fill='#8a8f88')

    # ================= 上のパネル：2階床まわり =================
    # 2階の柱＋断熱
    band(s, -52.5, 52.5, TOP_HI, 3611, 'url(#pIns)', stroke='#8a6a35',
         sw=1.4)
    # 胴差
    band(s, -52.5, 52.5, 3611, 3311, 'url(#pWood)', stroke='#8a6a35', sw=1.4)
    # 2階の床
    band(s, xin, 52.5, 3635, 3611, '#f5e7cb')          # 構造用合板 t=24
    band(s, xin, 52.5, 3650, 3635, '#e6d3ad')          # フローリング t=15
    # 外壁（上）
    band(s, 52.5, 61.5, TOP_HI, 3311, '#f0e2c8')       # 構造用合板 t=9
    s.line(X(61.5), Y(TOP_HI), X(61.5), Y(3100), stroke='#2f7fd0',
           stroke_width=1.6)                            # 透湿防水シート
    band(s, 61.5, 79.5, TOP_HI, 3100, '#f7f7f7')       # 通気胴縁 t=18
    band(s, 79.5, 95.5, TOP_HI, 3100, '#cfd8dc')       # サイディング t=16
    band(s, -67.5, -52.5, TOP_HI, 3250, '#ebebeb')     # 強化石膏ボード t=15
    # 1階の天井
    band(s, xin, -52.5, 3250, 3240.5, '#ebebeb')
    for k in range(6):
        xx = xin + 40 + k * 62
        band(s, xx, xx + 40, 3290, 3250, '#efdcbb', stroke='#c9a86c', sw=0.7)
    # 通気層の空気の流れ
    s.line(X(70.5), Y(3120), X(70.5), Y(TOP_HI - 20), stroke='#4aa3df',
           stroke_width=1.0, stroke_dasharray='5 3')
    # レベル
    for mm, lab in ((3650, '2FL  GL+3,650'), (3250, '天井 GL+3,250')):
        s.line(X(xin) - 26, Y(mm), X(110), Y(mm), stroke='#b03060',
               stroke_width=0.8, stroke_dasharray='9 3 2 3')
        s.text(X(xin) - 28, Y(mm) - 5, lab, size=10.5, anchor='end',
               fill='#b03060', weight='700')

    s.rect(6, MT + 2, 20, TOP_H - 4, fill='#f4eef0', stroke='none')
    s.text_rot(16, MT + TOP_H / 2.0, 'B　2階の床のところ', -90,
               size=11.5, weight='700', fill='#b03060')

    # ================= 破断線 =================
    ybreak = MT + TOP_H + GAP / 2.0
    d = 'M %.1f %.1f' % (X(xin) - 30, ybreak - 5)
    xx = X(xin) - 30
    up = True
    while xx < X(xout) + 20:
        xx += 16
        d += ' L %.1f %.1f' % (xx, ybreak + (5 if up else -5))
        up = not up
    s.path(d, stroke='#888', stroke_width=1.1)
    s.text(X(xout) + 40, ybreak + 4, '（中間は省略）', size=10.5, fill='#888',
           anchor='start')

    # ================= 下のパネル：基礎まわり =================
    # 地面
    band(s, 95.5, xout, 0, BOT_LO, 'url(#pGround)', stroke='none')
    s.line(X(75), Y(0), X(xout), Y(0), stroke='#333', stroke_width=1.6)
    s.text(X(xout) - 6, Y(0) - 6, 'GL', size=11, anchor='end', weight='700',
           fill='#333')
    # 砕石＋防湿フィルム
    band(s, xin, 75, -300, -360, 'url(#pGrav)', stroke='#aa9', sw=0.8)
    s.line(X(xin), Y(-300), X(75), Y(-300), stroke='#2f7fd0',
           stroke_width=1.4)
    # べた基礎
    band(s, xin, 75, -150, -300, 'url(#pConc)', stroke='#666', sw=1.2)
    band(s, -75, 75, 386, -150, 'url(#pConc)', stroke='#666', sw=1.2)
    # 床下
    s.text(X(-260), Y(80), '床下', size=10.5, fill='#999')
    # 基礎パッキン
    band(s, -52.5, 52.5, 406, 386, '#d9d9d9', stroke='#555', sw=1.0)
    # 土台
    band(s, -52.5, 52.5, 511, 406, 'url(#pWood)', stroke='#8a6a35', sw=1.4)
    # 1階の床
    band(s, xin, 52.5, 535, 511, '#f5e7cb')
    band(s, xin, 550, 550, 535, '#e6d3ad')
    band(s, xin, -52.5, 511, 461, 'url(#pIns)', stroke='#d98cae', sw=0.8)
    # 柱＋グラスウール
    band(s, -52.5, 52.5, BOT_HI, 511, 'url(#pIns)', stroke='none')
    band(s, -52.5, 52.5, BOT_HI, 511, 'none', stroke='#8a6a35', sw=1.4)
    # 外壁（下）
    band(s, 52.5, 61.5, BOT_HI, 511, '#f0e2c8')
    s.line(X(61.5), Y(BOT_HI), X(61.5), Y(430), stroke='#2f7fd0',
           stroke_width=1.6)
    band(s, 61.5, 79.5, BOT_HI, 430, '#f7f7f7')
    band(s, 79.5, 95.5, BOT_HI, 420, '#cfd8dc')
    band(s, -67.5, -52.5, BOT_HI, 550, '#ebebeb')
    # 水切り
    s.poly([(X(61.5), Y(430)), (X(100), Y(400)), (X(112), Y(372))],
           stroke='#607d8b', stroke_width=2.2)
    # 通気層の空気
    s.line(X(70.5), Y(450), X(70.5), Y(BOT_HI - 20), stroke='#4aa3df',
           stroke_width=1.0, stroke_dasharray='5 3')
    s.polygon([(X(70.5), Y(BOT_HI - 10)), (X(70.5) - 3.5, Y(BOT_HI - 46)),
               (X(70.5) + 3.5, Y(BOT_HI - 46))], fill='#4aa3df')
    # 筋かい（奥にある部材なので破線）
    s.line(X(-48), Y(520), X(48), Y(BOT_HI - 10), stroke='#8a6a35',
           stroke_width=3.2, stroke_dasharray='9 5', opacity='0.85')

    # アンカーボルト
    s.line(X(-20), Y(120), X(-20), Y(560), stroke='#444', stroke_width=2.0)
    s.line(X(-38), Y(120), X(-20), Y(120), stroke='#444', stroke_width=2.0)
    s.circle(X(-20), Y(548), 4.5, fill='none', stroke='#444',
             stroke_width=1.4)
    # レベル
    for mm, lab in ((550, '1FL  GL+550'), (386, '基礎天端 GL+386'),
                    (-300, '基礎の底 GL−300')):
        s.line(X(xin) - 26, Y(mm), X(120), Y(mm), stroke='#b03060',
               stroke_width=0.8, stroke_dasharray='9 3 2 3')
        s.text(X(xin) - 28, Y(mm) - 5, lab, size=10.5, anchor='end',
               fill='#b03060', weight='700')

    s.rect(6, MT + TOP_H + GAP + 2, 20, BOT_H - 4,
           fill='#f4eef0', stroke='none')
    s.text_rot(16, MT + TOP_H + GAP + BOT_H / 2.0,
               'A　地面のところ', -90, size=11.5, weight='700', fill='#b03060')

    # ================= 寸法 =================
    dx = X(xin) - 126
    for a, b, lab in ((-360, -300, '60'), (-300, -150, '150'),
                      (-150, 386, '536'), (386, 406, '20'),
                      (406, 511, '105'), (511, 550, '39')):
        s.line(dx, Y(a), dx, Y(b), stroke='#444', stroke_width=0.8)
        s.line(dx - 3.5, Y(a), dx + 3.5, Y(a), stroke='#444',
               stroke_width=0.8)
        s.line(dx - 3.5, Y(b), dx + 3.5, Y(b), stroke='#444',
               stroke_width=0.8)
        s.text_rot(dx - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=9.5,
                   fill='#444')
    s.text_rot(dx - 24, (Y(-360) + Y(550)) / 2.0, '各部の寸法(mm)', -90,
               size=10, fill='#888')
    # 天井高
    dx2 = X(xin) - 126
    s.line(dx2, Y(3250), dx2, Y(3100), stroke='#444', stroke_width=0.8)
    s.text_rot(dx2 - 6, Y(3180), '天井高 2,700', -90, size=10, fill='#444')

    # ================= 引き出し説明 =================
    s.line(LX - 20, MT - 4, LX - 20, MT + DRAW_H, stroke='#eee',
           stroke_width=0.8)
    top_notes = [
        (0, 3644, 128, 'フローリング t=15'),
        (-200, 3623, 150, '構造用合板 t=24（根太レス＝剛床）'),
        (0, 3460, 196, '胴差 105×300'),
        (87, 3400, 218, '窯業系サイディング t=16'),
        (70, 3350, 240, '通気胴縁 t=18（通気層）'),
        (-200, 3245, 268, '天井 石膏ボード t=9.5 ＋ 野縁 40×45 @455'),
    ]
    bot_notes = [
        (87, 900, 372, '窯業系サイディング t=16（外壁の仕上げ）'),
        (70, 855, 394, '通気胴縁 t=18 → 通気層（湿気を上へ逃がす）'),
        (61, 810, 416, '透湿防水シート（雨は止め、湿気は通す）'),
        (57, 765, 438, '構造用合板 t=9（N50 @150以下・壁倍率2.5）'),
        (0, 715, 460, '柱 105×105 ＋ グラスウール16K t=100'),
        (-60, 665, 482, '強化石膏ボード t=15（準耐火45分の要）'),
        (-10, 660, 504, '筋かい 45×90 たすき掛け（壁倍率4.0・破線）'),
        (-200, 542, 526, 'フローリング t=15 ＋ 構造用合板 t=24'),
        (-250, 486, 548, '床断熱 押出法ポリスチレンフォーム t=50'),
        (0, 458, 570, '土台 105×105（防腐防蟻処理）'),
        (0, 396, 592, '基礎パッキン t=20（床下の換気口をかねる）'),
        (-20, 300, 614, 'アンカーボルト M12 @2,730以下（埋込み250以上）'),
        (100, 400, 636, '水切り（雨を外へ落とす）'),
        (0, 100, 662, 'べた基礎 立上り 厚150（地上386mm ＝ 300mm以上）'),
        (-200, -225, 690, 'べた基礎 底盤 厚150（根入れ300mm ＝ 240mm以上）'),
        (-200, -330, 716, '砕石 t=60 ＋ 防湿フィルム'),
    ]
    for a, b, c, t in top_notes + bot_notes:
        callout(s, a, b, c, t)

    # ================= ハッチの凡例 =================
    gy = MT + DRAW_H + 18
    s.text(30, gy, '模様の意味', size=11.5, weight='700', anchor='start')
    keys = [('url(#pWood)', '木材（切り口）'), ('url(#pConc)', 'コンクリート'),
            ('url(#pIns)', '断熱材'), ('url(#pGrav)', '砕石'),
            ('url(#pGround)', '地面')]
    kx = 110
    for fill, lab in keys:
        s.rect(kx, gy - 11, 26, 14, fill=fill, stroke='#888',
               stroke_width=0.8)
        s.text(kx + 32, gy, lab, size=11, anchor='start', fill='#555')
        kx += 32 + len(lab) * 11.5 + 18

    # ================= 注意書き =================
    ny = MT + DRAW_H + 56
    s.rect(30, ny - 16, W - 60, 62, fill='#fff8e1', stroke='#e0c060',
           stroke_width=1, rx=6)
    s.text(44, ny + 2,
           '★ 外壁の厚さ 15＋105＋9＋18＋16 ＝ 163mm。'
           'この6層を「内から外へ」の順で覚える。', size=11,
           anchor='start', fill='#6b5200')
    s.text(44, ny + 20,
           '★ 1FL は GL+550。基礎の立上りを地上300mm以上とるため、'
           'GL+400 では納まらない（本文の解説を参照）。', size=11,
           anchor='start', fill='#6b5200')
    s.text(44, ny + 38,
           '★ 数値は必ず法令集・告示（平12建告1347号ほか）で確認すること。',
           size=11, anchor='start', fill='#6b5200')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    draw().save(os.path.join(out, 'detail.svg'))
    print('wrote detail.svg  size=%dx%d' % (W, H))
