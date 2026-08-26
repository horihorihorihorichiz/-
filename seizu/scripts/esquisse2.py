# -*- coding: utf-8 -*-
"""エスキスの配置のコツ：2階・3階を先に決めて、そのスパンを1階へ落とす。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 660, 944
INK, RED, BLUE, GREEN = '#111', '#c0392b', '#2f7fd0', '#2f8f6a'
SUB = '#dbe6f2'      # 主要室以外（水まわり・階段・廊下）
MAIN = '#fbe3cd'     # 主要室

s = Svg(W, H)
s.text(W / 2.0, 34, 'エスキスの山場「スパンをどこで割るか」', size=21,
       weight='700')
s.text(W / 2.0, 57, '1階は最後。2階と3階から決める', size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


G = 17.0
NX, NY = 8, 10


def grid(ox, oy, cap):
    s.rect(ox, oy, NX * G, NY * G, fill='#fff', stroke='#bbb',
           stroke_width=1.0)
    for i in range(1, NX):
        s.line(ox + i * G, oy, ox + i * G, oy + NY * G, stroke='#eee',
               stroke_width=0.6)
    for j in range(1, NY):
        s.line(ox, oy + j * G, ox + NX * G, oy + j * G, stroke='#eee',
               stroke_width=0.6)
    s.text(ox + NX * G / 2.0, oy + NY * G + 17, cap, size=11, weight='700')


def cell(ox, oy, a, b, c, d, col, lab='', size=9):
    s.rect(ox + a * G, oy + b * G, (c - a) * G, (d - b) * G, fill=col,
           stroke='#9aa', stroke_width=0.8)
    if lab:
        s.text(ox + (a + c) * G / 2.0, oy + (b + d) * G / 2.0 + 3, lab,
               size=size)


def span_line(ox, oy, gy, col=RED):
    s.line(ox - 8, oy + gy * G, ox + NX * G + 8, oy + gy * G, stroke=col,
           stroke_width=1.6, stroke_dasharray='6 3')


band(74, 356, 'その1', 'まず3階と2階。主要室「以外」を先に置く')
for i, (cap, subs) in enumerate((
        ('3階', [(0, 0, 2, 4, '階段'), (2, 0, 4, 2, '便所'),
                 (4, 0, 8, 2, '納戸')]),
        ('2階', [(0, 0, 2, 4, '階段'), (2, 0, 5, 2, '洗面・浴室'),
                 (5, 0, 8, 2, '便所')]))):
    ox = 90 + i * 190
    grid(ox, 116, cap + '　主要室以外を先に')
    for a, b, c, d, lab in subs:
        cell(ox, 116, a, b, c, d, SUB, lab)
s.lines_text(474, 152, [
    ('先に取るもの', 12, '700', INK),
    ('・階段（3階とも同じ位置）', 11.5, '400', '#444'),
    ('・水まわり（上下でそろえる）', 11.5, '400', '#444'),
    ('・便所、納戸、廊下', 11.5, '400', '#444'),
    ('', 6, '400', '#444'),
    ('これは動かせないので、', 12, '700', RED),
    ('先に場所を決める。', 12, '700', RED),
], size=11.5, lh=20, anchor='start')

band(366, 648, 'その2', '主要室を押し込む → ここでスパンが決まる')
for i, (cap, subs, mains, sp) in enumerate((
        ('3階', [(0, 0, 2, 4, '階段'), (2, 0, 4, 2, '便所'),
                 (4, 0, 8, 2, '納戸')],
         [(2, 2, 5, 6, '子供室'), (5, 2, 8, 6, '子供室'),
          (0, 6, 8, 10, '夫婦寝室')], 6),
        ('2階', [(0, 0, 2, 4, '階段'), (2, 0, 5, 2, '洗面・浴室'),
                 (5, 0, 8, 2, '便所')],
         [(2, 2, 5, 6, '和室'), (5, 2, 8, 6, '納戸'),
          (0, 6, 8, 10, 'LDK')], 6))):
    ox = 90 + i * 190
    grid(ox, 408, cap + '　主要室が入った')
    for a, b, c, d, lab in subs:
        cell(ox, 408, a, b, c, d, SUB, lab)
    for a, b, c, d, lab in mains:
        cell(ox, 408, a, b, c, d, MAIN, lab)
    span_line(ox, 408, sp)
s.lines_text(474, 444, [
    ('赤い線＝スパン', 12, '700', RED),
    ('主要室のはしが、', 11.5, '400', '#444'),
    ('そのまま柱の通る線', 11.5, '400', '#444'),
    ('になる。', 11.5, '400', '#444'),
    ('', 6, '400', '#444'),
    ('2階と3階で同じ線が', 12, '700', INK),
    ('使えるか必ず確かめる。', 12, '700', INK),
], size=11.5, lh=20, anchor='start')

band(658, 944, 'その3', '決まったスパンを1階に落とす → 通し柱が確定')
ox = 90
grid(ox, 706, '1階　上から下ろしたスパンに合わせる')
for a, b, c, d, lab in ((0, 0, 2, 4, '階段'), (2, 0, 8, 4, '厨房・スタッフ'),
                        (0, 4, 2, 10, '玄関・便所'), (2, 4, 8, 10, '売場')):
    cell(ox, 706, a, b, c, d, MAIN if a >= 2 else SUB, lab)
span_line(ox, 706, 4)
for gx, gy in ((0, 0), (8, 0), (0, 10), (8, 10)):
    s.circle(ox + gx * G, 706 + gy * G, 6, fill='#fff', stroke=RED,
             stroke_width=1.8)
    s.rect(ox + gx * G - 3, 706 + gy * G - 3, 6, 6, fill=INK)

s.lines_text(268, 716, [
    ('なぜ1階が最後なのか', 13, '700', INK),
    ('1階は店舗など大きな部屋が多いので、割り方の自由がききます。',
     11.5, '400', '#444'),
    ('逆に2階・3階は「6帖」「8帖」と大きさの決まった部屋を並べるので、',
     11.5, '400', '#444'),
    ('ほとんど動かせません。', 11.5, '400', '#444'),
    ('', 6, '400', '#444'),
    ('動かせない方を先に決めて、動かせる方を後から合わせる。', 12, '700', RED),
    ('', 6, '400', '#444'),
    ('「3階のスパンの下に1階の柱がない」という事故もこれで防げます。',
     11.5, '400', '#444'),
    ('スパンが決まった時点で、四隅の通し柱（○）の位置も確定します。',
     11.5, '400', '#444'),
], size=11.5, lh=20, anchor='start')

s.save(os.path.join(OUT, 'esquisse2.svg'))
print('wrote esquisse2.svg')
