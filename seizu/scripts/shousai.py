# -*- coding: utf-8 -*-
"""部分詳細図（1/20）の描き方。よこ線5本から始めて、間をうめていく。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 700, 1270
INK, RED, BLUE, GRY = '#111', '#c0392b', '#2f7fd0', '#8a8f88'
WOOD, CONC, BOARD = '#efdcbb', '#dedede', '#ececec'

s = Svg(W, H)
s.text(W / 2.0, 32, '部分詳細図の描き方', size=21, weight='700')
s.text(W / 2.0, 55, 'よこ線を5本引いてから、その間をうめていくだけ',
       size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


# ============================================================
band(74, 360, 'その1', 'まず「よこ線」を5本引く')

GLY, K = 305.0, 0.05
LX0, LX1 = 150.0, 520.0
s.rect(350, GLY, 170, 20, fill='#f0ede6', stroke='none')      # 地面
LEV = [(3650, 122, '2FL　GL＋3,650'),
       (3250, 148, '1階の天井　GL＋3,250'),
       (550, 268, '1FL　GL＋550'),
       (371, 288, '基礎の天ば　GL＋371'),
       (0, 308, 'GL（地面）　±0')]
for mm, ly, lab in LEV:
    y = GLY - mm * K
    hot = mm in (0, 550)
    s.line(LX0, y, LX1, y, stroke=RED if hot else INK,
           stroke_width=1.8 if hot else 1.2)
    s.line(LX1, y, 526, ly - 4, stroke='#999', stroke_width=0.7)
    s.text(530, ly, lab, size=10.5, anchor='start', weight='700' if hot
           else '400', fill=RED if hot else INK)
s.dim_v(GLY - 550 * K, GLY - 3650 * K, 138, '階高 3,100', size=10)
s.text(150, 336, '※ この5本が引けたら、あとは線と線の間をうめるだけ。'
       'いきなり材料から描くと必ずズレる。', size=11, anchor='start',
       fill='#555')
s.text(150, 352, '※ 3階建てなら 3FL＝GL＋6,550、軒高＝GL＋9,350 も同じように'
       '引いておく。', size=11, anchor='start', fill='#555')

# ============================================================
band(370, 700, 'その2', '描く順番は6つ')


def mini(bx, by, step):
    """1コマ分の外壁断面。step の数だけ描き足す。"""
    y2f, yce, y1f, yft, ygl, ybt = (by + 8, by + 18, by + 74, by + 80,
                                    by + 88, by + 97)
    cl, cr = bx + 48, bx + 64
    s.rect(bx, by, 120, 100, fill='#fff', stroke='#ddd', stroke_width=1.0)
    # 1 よこ線
    for y in (y2f, yce, y1f, yft, ygl):
        s.line(bx + 4, y, bx + 116, y, stroke='#999', stroke_width=0.9)
    if step >= 2:
        s.line(bx + 56, by + 4, bx + 56, by + 94, stroke=BLUE,
               stroke_width=0.7, stroke_dasharray='7 2 1 2')
        for x in (cl, cr):
            s.line(x, y2f, x, ygl, stroke=INK, stroke_width=1.4)
    if step >= 3:
        s.rect(bx + 76, ygl, 40, 9, fill='#f0ede6', stroke='none')
        s.rect(cl, yft, 16, ybt - 5 - yft, fill=CONC, stroke='#666',
               stroke_width=1.0)
        s.rect(bx + 36, ybt - 5, 40, 5, fill=CONC, stroke='#666',
               stroke_width=1.0)
    if step >= 4:
        for r in ((cl, y1f, 16, 6), (bx + 8, y1f - 3, 40, 3),
                  (cl, y2f, 16, 8), (bx + 8, y2f - 3, 40, 3)):
            s.rect(r[0], r[1], r[2], r[3], fill=WOOD, stroke='#8a6a35',
                   stroke_width=0.9)
        s.line(bx + 8, yce, cl, yce, stroke='#8a6a35', stroke_width=1.0)
    if step >= 5:
        s.rect(bx + 44, yce, 4, y1f - yce, fill=BOARD, stroke='#777',
               stroke_width=0.6)
        for a, b, c in ((0, 2, '#f0e2c8'), (2, 4, '#f7f7f7'),
                        (4, 6, '#eceff1'), (6, 9, '#cfd8dc')):
            s.rect(cr + a, y2f, b - a, ygl - y2f, fill=c, stroke='#777',
                   stroke_width=0.5)
    if step >= 6:
        s.line(bx + 28, y2f, bx + 28, y1f, stroke=RED, stroke_width=0.7)
        for y in (y2f, y1f):
            s.line(bx + 25, y, bx + 31, y, stroke=RED, stroke_width=0.7)
        for y, ln in ((by + 30, 30), (by + 46, 24)):
            s.line(cr + 9, y + 6, bx + 88, y, stroke=RED, stroke_width=0.7)
            s.line(bx + 88, y, bx + 88 + ln, y, stroke=RED, stroke_width=0.7)
            s.rect(bx + 88, y - 5, ln, 3.4, fill=RED, stroke='none')


STEPS = [('よこ線を5本', 'GL・基礎天ば・1FL・天井・2FL'),
         ('たて線（柱の幅120）', '通り芯（一点鎖線）もいっしょに'),
         ('基礎をかく', '立上りは地上371、根入れ300'),
         ('木をかく', '土台120角・床合板24・胴差120×300'),
         ('外壁の層をかく', '内から外へ 15・120・9・18・16'),
         ('寸法と材料名', '左に高さ、右に引出線で名前')]
for i, (t, m) in enumerate(STEPS):
    bx = 90 + (i % 3) * 200
    by = 425 if i < 3 else 570
    mini(bx, by, i + 1)
    s.circle(bx - 12, by - 12, 12, fill=RED)
    s.text(bx - 12, by - 8, str(i + 1), size=12, fill='#fff', weight='700')
    s.text(bx + 8, by - 8, t, size=12, anchor='start', weight='700')
    s.text(bx, by + 116, m, size=10, anchor='start', fill='#555')

# ============================================================
band(710, 1010, 'その3', '書きこむのは「高さ」と「材料名」だけ')

SX = 150.0
LAY = [(0, 13, BOARD, '#777'), (13, 73, WOOD, '#8a6a35'),
       (73, 80, '#f0e2c8', '#777'), (80, 92, '#f7f7f7', '#777'),
       (92, 104, '#cfd8dc', '#777')]
for a, b, fc, sc in LAY:
    s.rect(SX + a, 762, b - a, 118, fill=fc, stroke=sc, stroke_width=1.0)
s.text(SX + 52, 754, '外壁を切ったところ', size=10, fill=GRY)
s.text(SX - 6, 800, '室内', size=10, anchor='end', fill=GRY)
s.text(SX + 112, 800, '屋外', size=10, anchor='start', fill=GRY)
PUL = [(98, 786, 778, '窯業系サイディング t=16'),
       (76, 822, 816, '構造用合板 t=9'),
       (43, 862, 856, '柱 120×120 ＋ グラスウール t=100')]
for xa, ya, ty, lab in PUL:
    s.line(SX + xa, ya, 320, ty, stroke=RED, stroke_width=0.8)
    s.line(320, ty, 356, ty, stroke=RED, stroke_width=0.8)
    s.text(360, ty + 4, lab, size=11, anchor='start', weight='700')
s.text(360, 894, '引出線は「ななめ→よこ→文字」。文字は線の上ではなく'
       'よこに書く。', size=10.5, anchor='start', fill='#555')

BOX = [(70, '左がわに書く＝高さ', INK,
        ['GL（地面）　±0', '基礎の天ば　GL＋371', '1FL　GL＋550',
         '1階の天井　GL＋3,250', '2FL　GL＋3,650']),
       (380, '右がわに書く＝材料と厚さ', RED,
        ['窯業系サイディング t=16', '通気胴縁 t=18', '構造用合板 t=9',
         '柱・土台 120×120', 'べた基礎 t=150'])]
for bx, ti, cc, items in BOX:
    s.rect(bx, 908, 250, 92, fill='#fff', stroke='#ddd', stroke_width=1.0)
    s.text(bx + 14, 928, ti, size=12, anchor='start', weight='700', fill=cc)
    for j, it in enumerate(items):
        s.text(bx + 14, 946 + j * 13, '・' + it, size=10.5, anchor='start',
               fill='#444')

# ============================================================
band(1020, 1270, 'その4', 'よくある間違い')
NG = [('切断位置を平面図に書き忘れる',
       'どこを切った図なのか分からなくなる。1階平面図に一点鎖線と A—A を打つ'),
      ('基礎の立上りが300より低い',
       '平12建告1347号ちがい。地上371で描いておけば安全'),
      ('材料の名前を書かない',
       '「主要な部材の名称・寸法」が要求図書。絵だけでは点にならない'),
      ('1／100の目盛で描いてしまう',
       'この図だけ1／20。方眼も10mmきざみで、910mm＝45.5mm＝約4.6マス'),
      ('内と外を逆に描く',
       '左が室内・右が屋外。石膏ボードが左、サイディングが右')]
for i, (t, m) in enumerate(NG):
    y = 1072 + i * 40
    s.text(70, y, '×', size=15, anchor='start', fill=RED, weight='700')
    s.text(92, y, t, size=12.5, anchor='start', weight='700')
    s.text(92, y + 16, m, size=10.5, anchor='start', fill='#555')

s.save(os.path.join(OUT, 'shousai.svg'))
print('wrote figures/shousai.svg')
