# -*- coding: utf-8 -*-
"""建具（扉と窓）の描き方。壁に穴をあけて、そこに記号を描く。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 700, 1180
INK, RED, BLUE = '#111', '#c0392b', '#2f7fd0'
G = 92.0                       # 1マス
T = 120.0 / 910.0 * G          # 壁の厚さ
h = T / 2.0


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


s = Svg(W, H)
s.text(W / 2.0, 32, '扉と窓の描き方', size=21, weight='700')
s.text(W / 2.0, 55, '壁は2本線。そこに穴をあけて、記号を描く', size=12,
       fill='#666')


def wall(x0, x1, y, gaps):
    """壁を2本線で引き、gaps のところだけ穴をあける。"""
    cuts = sorted(gaps)
    pos = x0
    for a, b in cuts:
        if a > pos:
            for d in (-h, h):
                s.line(pos, y + d, a, y + d, stroke=INK, stroke_width=1.6)
        pos = b
    if x1 > pos:
        for d in (-h, h):
            s.line(pos, y + d, x1, y + d, stroke=INK, stroke_width=1.6)


def jamb(x, y):
    s.line(x, y - h, x, y + h, stroke=INK, stroke_width=1.4)


def madoru(a, b, y):
    """引違い窓。細い3本の線。"""
    for d in (-h, 0, h):
        s.line(a, y + d, b, y + d, stroke=INK, stroke_width=1.0)
    jamb(a, y)
    jamb(b, y)


def hikido(a, b, y):
    """引戸。戸を2枚、少しずらす。"""
    m = (a + b) / 2.0
    s.line(a, y - h * 0.5, m, y - h * 0.5, stroke=INK, stroke_width=2.4)
    s.line(m, y + h * 0.5, b, y + h * 0.5, stroke=INK, stroke_width=2.4)
    jamb(a, y)
    jamb(b, y)


def hirakido(a, b, y, up=True):
    """開き戸。戸の板と四分円の弧。"""
    r = b - a
    sg = -1 if up else 1
    s.line(a, y, a, y + sg * r, stroke=INK, stroke_width=2.4)
    s.path('M %.1f %.1f A %.1f %.1f 0 0 %d %.1f %.1f'
           % (a, y + sg * r, r, r, 1 if up else 0, b, y),
           stroke='#888', stroke_width=1.1, fill='none')
    jamb(a, y)
    jamb(b, y)


def ryoubiraki(a, b, y):
    """両開き戸。まん中から2枚。"""
    m = (a + b) / 2.0
    r = m - a
    for x_, sg in ((a, 1), (b, -1)):
        s.line(x_, y, x_, y - r, stroke=INK, stroke_width=2.4)
        s.path('M %.1f %.1f A %.1f %.1f 0 0 %d %.1f %.1f'
               % (x_, y - r, r, r, 1 if sg > 0 else 0, x_ + sg * r, y),
               stroke='#888', stroke_width=1.1, fill='none')
    jamb(a, y)
    jamb(b, y)


ROWS = [
    ('引違い窓', 2, madoru, '細い線を3本。いちばんよく使う',
     '1,820（2マス）／1,365（1.5マス）'),
    ('引戸（ひきど）', 2, hikido, '戸を2枚、少しずらして太めの線',
     '1,820（2マス）／1,365（1.5マス）'),
    ('開き戸', 1, hirakido, '戸の板＋四分円の弧。弧の半径＝穴の幅',
     '780〜910（1マス）'),
    ('両開き戸', 2, ryoubiraki, 'まん中から2枚。店舗の出入口など',
     '1,820（2マス）'),
]

band(74, 636, 'その1', '4つだけ覚える')
y = 132
for name, nm, fn, memo, dim in ROWS:
    x0, x1 = 60, 60 + 5 * G / 1.6
    xa = x0 + 1.1 * G / 1.6
    xb = xa + nm * G / 1.6
    wall(x0, x1, y, [(xa, xb)])
    fn(xa, xb, y)
    s.text(x1 + 22, y - 8, name, size=13, anchor='start', weight='700')
    s.text(x1 + 22, y + 9, memo, size=10.5, anchor='start', fill='#555')
    s.text(x1 + 22, y + 25, '幅の目安　' + dim, size=10.5, anchor='start',
           fill=RED)
    y += 128

band(646, 900, 'その2', '描く順番はこれだけ')
STEPS = [('壁を2本線で全部ひく', '先に外まわり、次に中の壁'),
         ('建具のところに穴をあける', '2本線を切る。長さはマスで数える'),
         ('穴に記号を描く', '窓は3本線、戸は板と弧'),
         ('開く向きを確かめる', '壁や家具にぶつかっていないか')]
for i, (t, m) in enumerate(STEPS):
    yy = 700 + i * 46
    s.circle(70, yy - 4, 14, fill=RED)
    s.text(70, yy + 1, str(i + 1), size=13, fill='#fff', weight='700')
    s.text(96, yy - 2, t, size=13, anchor='start', weight='700')
    s.text(96, yy + 15, m, size=10.5, anchor='start', fill='#555')

band(910, 1180, 'その3', '開く向きの決まり')
NOTES = [('部屋のドアは「中へ」開く',
          '廊下側に開くと、通る人にぶつかる'),
         ('便所は「外へ」開く',
          '中で人が倒れたとき、ドアを開けて助けられるように'),
         ('弧の大きさは穴の幅と同じ',
          '幅910の戸なら、半径910の四分円。小さく描くと戸が入らない'),
         ('引戸は戸がしまう場所が要る',
          '横の壁に戸1枚ぶんの余白。窓や柱があるとしまえない')]
for i, (t, m) in enumerate(NOTES):
    yy = 962 + i * 52
    s.polygon([(66, yy - 10), (60, yy + 1), (72, yy + 1)], fill=BLUE)
    s.text(84, yy - 2, t, size=12.5, anchor='start', weight='700')
    s.text(84, yy + 15, m, size=10.5, anchor='start', fill='#555')

s.save(os.path.join(OUT, 'tobira.svg'))
print('wrote tobira.svg')
