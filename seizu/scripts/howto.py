# -*- coding: utf-8 -*-
"""部分詳細図 かんたんガイド。1手ずつ絵がふえる9コマ。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
INK, RED, GRY = '#111', '#c0392b', '#9aa09a'
WOOD, CONC, BOARD, SIDE = '#efdcbb', '#dedede', '#ececec', '#cfd8dc'

Y2F, YCE, Y1F, YFT, YGL, YBT = 40, 66, 300, 322, 352, 384
XIN, XL, XR, XOUT = 40, 150, 174, 210
LINES = [(Y2F, '2かいの ゆか'), (YCE, 'てんじょう'), (Y1F, '1かいの ゆか'),
         (YFT, 'きその うえ'), (YGL, 'じめん')]


def cell(s, ox, oy, step):
    def X(v):
        return ox + v

    def Y(v):
        return oy + v

    for y, lab in LINES:
        s.line(X(20), Y(y), X(250), Y(y), stroke='#aaa', stroke_width=1.0)
        if step == 1:
            s.text(X(22), Y(y - 5), lab, size=10, anchor='start', fill=RED,
                   weight='700')
    if step >= 2:
        for x in (XL, XR):
            s.line(X(x), Y(Y2F), X(x), Y(YGL), stroke=INK, stroke_width=1.8)
        if step == 2:
            s.text(X(XL + 12), Y(190), '120', size=10, fill=RED, weight='700')
    if step >= 3:
        s.rect(X(XOUT + 22), Y(YGL), 46, 32, fill='#f0ede6', stroke='none')
        s.rect(X(XL), Y(YFT), XR - XL, YBT - 8 - YFT, fill=CONC,
               stroke='#666', stroke_width=1.2)
        s.rect(X(XL - 22), Y(YBT - 8), XR - XL + 44, 8, fill=CONC,
               stroke='#666', stroke_width=1.2)
    if step >= 4:
        s.rect(X(XL), Y(Y1F), XR - XL, YFT - Y1F, fill=WOOD,
               stroke='#8a6a35', stroke_width=1.2)
        s.rect(X(XIN), Y(Y1F - 8), XL - XIN, 8, fill=WOOD, stroke='#8a6a35',
               stroke_width=1.0)
    if step >= 5:
        s.rect(X(XL), Y(Y2F), XR - XL, 26, fill=WOOD, stroke='#8a6a35',
               stroke_width=1.2)
        s.rect(X(XIN), Y(Y2F - 8), XL - XIN, 8, fill=WOOD, stroke='#8a6a35',
               stroke_width=1.0)
        s.line(X(XIN), Y(YCE), X(XL), Y(YCE), stroke='#8a6a35',
               stroke_width=1.2)
    if step >= 6:
        s.rect(X(XL - 8), Y(YCE), 8, Y1F - YCE, fill=BOARD, stroke='#777',
               stroke_width=0.8)
    if step >= 7:
        for a, b, c in ((0, 5, '#f0e2c8'), (5, 14, '#f7f7f7'), (14, 26, SIDE)):
            s.rect(X(XR + a), Y(Y2F), b - a, YGL - Y2F, fill=c,
                   stroke='#777', stroke_width=0.8)
    if step >= 8:
        s.line(X(112), Y(Y1F), X(112), Y(YGL), stroke=RED, stroke_width=0.9)
        for y in (Y1F, YGL):
            s.line(X(108), Y(y), X(116), Y(y), stroke=RED, stroke_width=0.9)
        s.text(X(106), Y((Y1F + YGL) / 2.0 + 4), '550', size=11,
               anchor='end', fill=RED, weight='700')
    if step >= 9:
        for y, tx in ((Y2F + 44, 'サイディング16'), (Y1F - 70, 'ごうはん9'),
                      (YFT + 16, 'どだい120')):
            s.line(X(XOUT + 24), Y(y + 8), X(XOUT + 40), Y(y),
                   stroke=RED, stroke_width=0.8)
            s.line(X(XOUT + 40), Y(y), X(XOUT + 56), Y(y),
                   stroke=RED, stroke_width=0.8)
            s.text(X(XOUT + 58), Y(y + 4), tx, size=9.5, anchor='start',
                   fill=RED, weight='700')


STEPS = [
    ('よこの せんを 5ほん ひく',
     ['まず たかさの せんだけ ひく。',
      'ノートの けいせん と おなじ。']),
    ('たての せんを 2ほん ひく',
     ['はしらの ひだり と みぎ。',
      'はばは 120mm（かみの うえで 6mm）。']),
    ('きそを かく',
     ['いえを のせる コンクリートの だい。',
      'じめんの うえ 371、した 300。']),
    ('1かいの ゆかの 木を かく',
     ['どだい（120かく）を きその うえに。',
      'その うえに ゆかの いた。']),
    ('2かいの ゆかの 木を かく',
     ['どうさし（120×300）を いれる。',
      'ゆかの いた と てんじょう も。']),
    ('うちがわの いたを はる',
     ['きょうか せっこうボード t=15。',
      'ひに つよい いた。']),
    ('そとがわの かべを はる',
     ['うち から そと へ じゅんばんに。',
      'ごうはん9 → どうぶち18 → サイディング16。']),
    ('たかさの すうじを かく',
     ['ひだりがわに かく。',
      'じめん から 1かいの ゆか まで 550。']),
    ('ざいりょうの なまえを かく',
     ['みぎがわに ひきだしせん を ひいて かく。',
      'ここを わすれると てんが もらえない。']),
]

for i, (title, subs) in enumerate(STEPS):
    W, H = 400, 490
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='#ffffff')
    s.circle(30, 32, 19, fill=RED)
    s.text(30, 39, str(i + 1), size=20, fill='#fff', weight='700')
    s.text(58, 30, title, size=15, anchor='start', weight='700')
    for k, sub in enumerate(subs):
        s.text(58, 48 + k * 15, sub, size=10.5, anchor='start', fill='#555')
    s.text(26, 88, '← へやの なか', size=10, anchor='start', fill=GRY)
    s.text(374, 88, 'そと →', size=10, anchor='end', fill=GRY)
    cell(s, 22, 70, i + 1)
    s.save(os.path.join(OUT, 'howto%d.svg' % (i + 1)))

print('wrote howto1..9.svg')
