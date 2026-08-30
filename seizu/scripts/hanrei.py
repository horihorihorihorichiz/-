# -*- coding: utf-8 -*-
"""伏図の「表示記号」の一覧。公式の標準解答例（令和4〜7年）の凡例欄どおり。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 660, 840
INK, RED = '#111', '#c0392b'

s = Svg(W, H)
s.text(W / 2.0, 34, '伏図の表示記号（答案用紙の凡例欄）', size=21, weight='700')
s.text(W / 2.0, 57, '公式の標準解答例で使われている描き方。'
       'この欄は答案用紙に印刷されている', size=12, fill='#666')

s.rect(30, 78, W - 60, 40, fill='#eaf1f7', stroke='#2f7fd0',
       stroke_width=1.2, rx=6)
s.text(W / 2.0, 96, '凡例の表は自分で作るものではありません。'
       '記号の意味を思い出して、', size=12, weight='700')
s.text(W / 2.0, 112, '空いている「断面寸法の記入欄」に数字を書き込むだけです。',
       size=12, weight='700')

X0, X1 = 60, 250          # 記号を描く範囲
NX, DX = 274, 466         # 名前・寸法の位置
Y0, DY = 158, 54


def beam(y, dash=None, chain=False):
    """材の2本線（正角材）。"""
    if chain:
        s.line(X0, y, X1, y, stroke=INK, stroke_width=1.2,
               stroke_dasharray='14 3 2 3')
        return
    for d in (-4, 4):
        s.line(X0, y + d, X1, y + d, stroke=INK, stroke_width=1.2,
               stroke_dasharray=dash)


ROWS = []


def row(i, name, dim, draw, note=''):
    y = Y0 + i * DY
    s.line(30, y + 26, W - 30, y + 26, stroke='#e2e2e2', stroke_width=0.8)
    draw(y)
    s.text(NX, y + 5, name, size=12.5, anchor='start', weight='700')
    if note:
        s.text(NX, y + 21, note, size=10, anchor='start', fill='#888')
    s.text(DX, y + 5, dim, size=13, anchor='start', weight='700',
           fill=RED if dim.startswith('120') or dim.startswith('90') else INK)


mid = (X0 + X1) / 2.0


def d_tooshi(y):
    beam(y)
    s.rect(mid - 6, y - 6, 12, 12, fill='#fff', stroke=INK, stroke_width=1.4)
    s.circle(mid, y, 12, fill='none', stroke=INK, stroke_width=1.4)


def d_kuda1(y):
    beam(y)
    s.line(mid - 7, y - 7, mid + 7, y + 7, stroke=INK, stroke_width=1.6)
    s.line(mid - 7, y + 7, mid + 7, y - 7, stroke=INK, stroke_width=1.6)


def d_kuda2(y):
    beam(y)
    s.line(mid - 3, y - 7, mid - 3, y + 7, stroke=INK, stroke_width=1.6)
    s.line(mid + 3, y - 7, mid + 3, y + 7, stroke=INK, stroke_width=1.6)


def d_kasanari(y):
    beam(y)
    s.rect(mid - 7, y - 7, 14, 14, fill='#fff', stroke=INK, stroke_width=1.3)
    s.line(mid - 7, y - 7, mid + 7, y + 7, stroke=INK, stroke_width=1.4)
    s.line(mid - 7, y + 7, mid + 7, y - 7, stroke=INK, stroke_width=1.4)


def d_seikaku(y):
    beam(y)


def d_hirakaku(y):
    s.polygon([(X0, y - 7), (X1, y - 7), (X1 - 18, y + 7), (X0 + 18, y + 7)],
              fill='#fff', stroke=INK, stroke_width=1.2)


def d_maruta(y):
    s.path('M %d %d Q %.1f %.1f %d %d Q %.1f %.1f %d %d'
           % (X0, y, mid, y - 11, X1, y - 2, mid, y + 6, X0, y),
           fill='#fff', stroke=INK, stroke_width=1.2)


def d_hiuchi(y):
    s.line(X0, y, X1, y, stroke=INK, stroke_width=1.4,
           stroke_dasharray='16 8')


def d_munagi(y):
    beam(y)
    s.circle(mid, y, 5, fill=INK)


def d_moya(y):
    beam(y, chain=True)
    s.circle(mid, y, 5, fill=INK)


row(0, '通し柱', '120×120', d_tooshi, '四角を丸で囲む')
row(1, '1階の管柱', '120×120', d_kuda1, 'バツ印')
row(2, '2階の管柱', '120×120', d_kuda2, 'たて2本線')
row(3, '1階と2階が重なる管柱', '（記入なし）', d_kasanari,
    '四角の中にバツ')
row(4, '胴差・床梁・桁・小屋梁', '120×120', d_seikaku,
    '正角材（真四角の材）。2本の平行線で描く')
row(5, '同上（平角材）', '図中に記入', d_hirakaku,
    '120×240 のように、図の中の梁のわきへ書く')
row(6, '同上（丸太材）', '図中に記入', d_maruta, '木の形にふくらませる')
row(7, '火打梁', '90×90', d_hiuchi, '破線')
row(8, '棟木・小屋束', '120×120', d_munagi, '2本線＋黒丸（小屋束）')
row(9, '母屋・小屋束', '90×90', d_moya, '一点鎖線＋黒丸（小屋束）')

yy = Y0 + 10 * DY + 6
s.rect(30, yy, W - 60, 108, fill='#fdf3e7', stroke='#c9762f', stroke_width=1.2,
       rx=6)
s.lines_text(48, yy + 22, [
    ('覚え方はこれだけ', 12.5, '700', '#c9762f'),
    ('柱も梁の幅も 120。火打梁と母屋だけ 90。', 13, '700', INK),
    ('管柱は「1階＝×」「2階＝たて2本線」「重なる＝四角の中にバツ」。',
     12, '400', '#333'),
    ('平角材（120×240 など）の寸法は、この欄には書かない。', 12.5, '700',
     RED),
    ('　→ 伏図の中の、梁1本ずつのわきに書く。', 12.5, '700', RED),
], size=12, lh=20, anchor='start')

s.save(os.path.join(OUT, 'hanrei.svg'))
print('wrote hanrei.svg')
