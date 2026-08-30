# -*- coding: utf-8 -*-
"""立面図の窓の描き方。位置は平面図から、高さは床から決める。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 700, 1160
INK, RED, BLUE = '#111', '#c0392b', '#2f7fd0'

s = Svg(W, H)
s.text(W / 2.0, 32, '立面図の窓の描き方', size=21, weight='700')
s.text(W / 2.0, 55, 'よこの位置は平面図から写す。たての位置は床から決める',
       size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


def sash(a, b, top, bot, panes=2, step=3):
    """建具。step 1=外枠 2=内枠 3=中桟まで"""
    s.rect(a, top, b - a, bot - top, fill='#fff', stroke=INK,
           stroke_width=1.8)
    if step >= 2:
        s.rect(a + 5, top + 5, b - a - 10, bot - top - 10, fill='none',
               stroke=INK, stroke_width=1.0)
    if step >= 3:
        for i in range(1, panes):
            x = a + (b - a) * i / float(panes)
            s.line(x, top + 5, x, bot - 5, stroke=INK, stroke_width=1.0)


# ============================================================
band(74, 300, 'その1', '3ステップで描ける')
CAP = [('外わくの長方形', '少し太い線で'),
       ('内がわにもう1つ四角', '5mmくらい内側。これがまどのわく'),
       ('まん中にたて線1本', 'ガラス2枚ならこれで完成')]
for i, (t, m) in enumerate(CAP):
    ox = 90 + i * 200
    sash(ox, ox + 110, 122, 200, 2, i + 1)
    s.circle(ox - 14, 116, 12, fill=RED)
    s.text(ox - 14, 120, str(i + 1), size=12, fill='#fff', weight='700')
    s.text(ox + 8, 120, t, size=12, anchor='start', weight='700')
    s.text(ox, 222, m, size=10.5, anchor='start', fill='#555')
s.text(90, 254, '※ ガラスが4枚ならたて線は3本。',
       size=11, anchor='start', fill='#555')
s.text(90, 276, '※ 出入口（ドア）も同じ描き方。ちがうのは高さだけ。',
       size=11, anchor='start', fill='#555')

# ============================================================
band(310, 640, 'その2', 'たての位置は「その階の床から」決める')
K = 0.055                       # 1mmあたりのピクセル
bx, by = 120, 600               # 床（FL）の位置
s.line(70, by, 560, by, stroke=INK, stroke_width=1.8)
s.text(66, by + 4, 'FL', size=11, anchor='end', weight='700')
s.line(70, by - 3100 * K, 560, by - 3100 * K, stroke=INK, stroke_width=1.8)
s.text(66, by - 3100 * K + 4, '上の階のFL', size=11, anchor='end',
       weight='700')

# 腰窓
a1, b1 = 190, 300
sash(a1, b1, by - 2100 * K, by - 800 * K, 2)
s.dim_v(by, by - 800 * K, a1 - 18, '800', size=9.5)
s.dim_v(by - 800 * K, by - 2100 * K, a1 - 18, '1,300', size=9.5)
s.text((a1 + b1) / 2.0, by + 22, '腰窓（こしのあたりから上）', size=11.5, weight='700')
s.text((a1 + b1) / 2.0, by + 38, 'FL＋800 〜 FL＋2,100', size=10, fill=RED)

# 掃き出し窓
a2, b2 = 380, 520
sash(a2, b2, by - 2000 * K, by, 2)
s.dim_v(by, by - 2000 * K, b2 + 20, '2,000', size=9.5, anchor='start', dx=5)
s.text((a2 + b2) / 2.0, by + 22, '掃き出し窓・ドア（床から立つ）', size=11.5,
       weight='700')
s.text((a2 + b2) / 2.0, by + 38, 'FL＋0 〜 FL＋2,000', size=10, fill=RED)
s.text(70, 352, '地面からではなく、その階の床から測る。'
       'どの階も同じ数字にすると、窓が横一列にきれいに並ぶ。',
       size=11, anchor='start', fill='#555')

# ============================================================
band(650, 950, 'その3', 'よこの位置は平面図から真下に写す')
px0, pw = 130, 340
py0 = 700
# 平面図（南面の壁だけ）
s.text(px0 - 10, py0 - 6, '平面図（南の壁）', size=10.5, anchor='start',
       fill='#555')
OPS = [(0.10, 0.22, '窓'), (0.38, 0.62, '出入口'), (0.74, 0.92, '窓')]
for d in (-4, 4):
    pos = px0
    for f0, f1, _ in OPS:
        a, b = px0 + pw * f0, px0 + pw * f1
        if a > pos:
            s.line(pos, py0 + d, a, py0 + d, stroke=INK, stroke_width=1.6)
        pos = b
    s.line(pos, py0 + d, px0 + pw, py0 + d, stroke=INK, stroke_width=1.6)
for f0, f1, lab in OPS:
    a, b = px0 + pw * f0, px0 + pw * f1
    for dd in (-4, 0, 4):
        s.line(a, py0 + dd, b, py0 + dd, stroke=INK, stroke_width=0.9)
    s.line(a, py0 - 4, a, py0 + 4, stroke=INK, stroke_width=1.2)
    s.line(b, py0 - 4, b, py0 + 4, stroke=INK, stroke_width=1.2)
# 立面図
ey = 900
s.line(px0, ey, px0 + pw, ey, stroke=INK, stroke_width=1.8)
s.rect(px0, ey - 120, pw, 120, fill='none', stroke=INK, stroke_width=1.6)
s.text(px0 - 10, ey - 130, '立面図', size=10.5, anchor='start', fill='#555')
for f0, f1, lab in OPS:
    a, b = px0 + pw * f0, px0 + pw * f1
    for x in (a, b):
        s.line(x, py0 + 8, x, ey - 122, stroke=RED, stroke_width=0.8,
               stroke_dasharray='5 4')
    if lab == '出入口':
        sash(a, b, ey - 100, ey, 2)
    else:
        sash(a, b, ey - 96, ey - 30, 2)
s.lines_text(500, 726, [
    ('やることは1つ', 12.5, '700', INK),
    ('平面図の窓の', 11.5, '400', '#444'),
    ('左はしと右はしから、', 11.5, '400', '#444'),
    ('まっすぐ下へ線を', 11.5, '400', '#444'),
    ('下ろすだけ。', 11.5, '400', '#444'),
    ('', 6, '400', '#444'),
    ('位置も幅も', 12, '700', RED),
    ('平面図と同じになる。', 12, '700', RED),
], size=11.5, lh=20, anchor='start')

# ============================================================
band(960, 1160, 'その4', 'よくある間違い')
NG = [('平面図と位置がちがう',
       '図面どうしが食いちがう＝大きな減点。必ず線を下ろして写す'),
      ('階ごとに高さがバラバラ',
       '腰窓はどの階も 床＋800 にそろえる。見た目もきれいになる'),
      ('1階の窓が基礎にめり込む',
       '窓は1階の床より下に描かない。1階の床＝地面＋550 の線を先に引く'),
      ('バルコニーの手すりを忘れる',
       '掃き出し窓の前に格子をかく。高さ1,100以上（3階建てには必要）')]
for i, (t, m) in enumerate(NG):
    yy = 1006 + i * 40
    s.text(70, yy, '×', size=15, anchor='start', fill=RED, weight='700')
    s.text(92, yy, t, size=12.5, anchor='start', weight='700')
    s.text(92, yy + 16, m, size=10.5, anchor='start', fill='#555')

s.save(os.path.join(OUT, 'mado.svg'))
print('wrote mado.svg')
