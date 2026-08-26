# -*- coding: utf-8 -*-
"""梁のせい（高さ）の決め方。スパンと「上に柱が乗るか」で決まる。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 660, 812
INK, RED, BLUE, WOOD = '#111', '#c0392b', '#2f7fd0', '#c9976a'

s = Svg(W, H)
s.text(W / 2.0, 34, '梁のせい（たての高さ）はこう決める', size=21, weight='700')
s.text(W / 2.0, 57, '「スパン（飛んでいる長さ）」と「上に柱が乗るか」の2つだけ',
       size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


KH = 0.046          # 長さのスケール
KV = 0.20           # せいは見やすいように約4倍で描く


def beam(cx, ybase, span, sei, cap, top_post=False, col=WOOD):
    """柱―梁―柱 を横から見た図。"""
    x0, x1 = cx - span * KH / 2.0, cx + span * KH / 2.0
    h = sei * KV
    s.rect(x0, ybase - h, x1 - x0, h, fill=col, stroke=INK, stroke_width=1.2)
    for x in (x0, x1):                      # 下の柱
        s.rect(x - 7, ybase, 14, 40, fill='#efe6d8', stroke=INK,
               stroke_width=1.1)
    if top_post:                            # 上に乗る柱
        s.rect(cx - 7, ybase - h - 40, 14, 40, fill='#ffe0d0', stroke=RED,
               stroke_width=1.4)
        s.text(cx, ybase - h - 48, '柱', size=10.5, fill=RED, weight='700')
    s.dim_h(x0, x1, ybase + 54, format(span, ','))
    s.line(x1 + 12, ybase, x1 + 12, ybase - h, stroke=BLUE, stroke_width=1.0)
    s.line(x1 + 8, ybase, x1 + 16, ybase, stroke=BLUE, stroke_width=1.0)
    s.line(x1 + 8, ybase - h, x1 + 16, ybase - h, stroke=BLUE,
           stroke_width=1.0)
    s.text(x1 + 20, ybase - h / 2.0 + 4, str(sei), size=12, anchor='start',
           fill=BLUE, weight='700')
    s.text(cx, ybase + 78, cap, size=11, weight='700')


# ① スパンが長いほど、せいは大きい
band(74, 318, 'その1', 'スパンが長いほど、せいは大きくなる')
for i, (span, sei) in enumerate(((1820, 120), (2730, 240), (3640, 300))):
    beam(120 + i * 200, 200, span, sei, '%s → せい %d' % (format(span, ','), sei))
s.text(W / 2.0, 300, 'たては見やすいように約4倍で描いています', size=10.5,
       fill='#999')

# ② 上に柱が乗ったら1寸（30mm）増し
band(328, 574, 'その2', '上に柱が乗ったら「1寸（30mm）」増し')
beam(190, 424, 1820, 120, '柱が乗らない → 120', col=WOOD)
beam(460, 424, 1820, 150, '柱が乗る → 150', top_post=True, col='#e8b98c')
s.rect(40, 512, W - 80, 52, fill='#fdecea', stroke=RED, stroke_width=1.2, rx=6)
s.lines_text(56, 532, [
    ('なぜ？', 11.5, '700', RED),
    ('梁のまん中に柱が立つと、上の階の重さがその1点に集中するから。'
     '1寸ぶん太くして受ける。', 12, '400', INK),
], size=12, lh=18, anchor='start')

# ③ 表
band(584, 812, 'その3', '早見表（これだけ覚える）')
rows = [('スパン', '床（上に柱なし）', '床（上に柱あり）', '小屋'),
        ('1間　1,820', '120（4寸）', '150（5寸）', '120（4寸）'),
        ('1.5間 2,730', '240（8寸）', '270（9寸）', '240（8寸）'),
        ('2間　3,640', '300', '330', '240（8寸）')]
cx = [70, 240, 390, 540]
for r, row in enumerate(rows):
    yy = 634 + r * 30
    if r == 0:
        s.rect(50, yy - 20, W - 100, 28, fill='#efeae2', stroke='none')
    else:
        s.line(50, yy + 8, W - 50, yy + 8, stroke='#ddd', stroke_width=0.8)
    for c, t in enumerate(row):
        s.text(cx[c], yy, t, size=11.5, anchor='start',
               weight='700' if r == 0 or c == 0 else '400',
               fill=INK if r == 0 or c == 0 else '#333')
s.text(W / 2.0, 776, '小屋（屋根）は床より軽いので、1.5間も2間も240でよい。',
       size=11.5, weight='700', fill='#555')
s.text(W / 2.0, 798, '幅は120（4寸）で統一する流儀と105で統一する流儀がある。'
       'どちらでもよいが、図面の中では必ずそろえる。', size=10.5, fill='#999')

s.save(os.path.join(OUT, 'beamsize.svg'))
print('wrote beamsize.svg')
