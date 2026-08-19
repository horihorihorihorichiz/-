# -*- coding: utf-8 -*-
"""エスキス（間取りを決める作業）の手順を6コマで描く。"""
import os
from svgkit import Svg

G = 24.0
NX, NY = 8, 10
PW, PH = NX * G, NY * G          # 1コマの図の大きさ
CW, CH = 232, 346                # 1コマの枠
COLS, ROWS = 3, 2
ML, MT = 26, 116
W = ML * 2 + CW * COLS
H = MT + CH * ROWS + 46

COLORS = {
    'shop':   ('#ffe6d0', '#c9762f'),
    'living': ('#dce9fb', '#4a76b8'),
    'water':  ('#d5f0e7', '#2f9077'),
    'stair':  ('#ffe066', '#bb9508'),
    'store':  ('#ececec', '#8a8a8a'),
    'hall':   ('#f1e6fa', '#8b62b5'),
}
TOOSHI = [(0, 0), (8, 0), (0, 10), (8, 10)]
KUDA = [(2, 0), (5, 0), (0, 2), (8, 2), (0, 6), (8, 6),
        (2, 10), (5, 10), (2, 2), (5, 2), (2, 6), (5, 6)]

F1 = [('売場', 2, 0, 8, 6, 'shop'), ('厨房', 2, 6, 5, 10, 'shop'),
      ('スタッフ', 5, 6, 8, 10, 'shop'), ('玄関', 0, 0, 2, 2, 'hall'),
      ('便所', 0, 6, 2, 8, 'water'), ('倉庫', 0, 8, 2, 10, 'store')]
F2 = [('居間・食事室・台所', 2, 0, 8, 6, 'living'), ('和室', 2, 6, 5, 10, 'living'),
      ('家事室', 5, 6, 8, 10, 'store'), ('便所', 0, 0, 2, 2, 'water'),
      ('洗面', 0, 6, 2, 8, 'water'), ('浴室', 0, 8, 2, 10, 'water')]
F3 = [('夫婦寝室', 2, 6, 8, 10, 'living'), ('子供室A', 2, 0, 5, 5, 'living'),
      ('子供室B', 5, 0, 8, 5, 'living'), ('廊下', 2, 5, 8, 6, 'hall'),
      ('便所', 0, 0, 2, 2, 'water'), ('納戸', 0, 6, 2, 10, 'store')]

STEPS = [
    ('1', '四角を置く', '敷地に 8マス × 10マス の箱を置く。\n道路（南）側に売場が来るように向きを決める。'),
    ('2', '階段を先に置く', '西側の 2マス × 4マス に階段。\nここは3階とも同じ場所。動かさない。'),
    ('3', '1階を割る', '南に売場。北に厨房とスタッフ。\n西の列に 玄関・便所・倉庫 を積む。'),
    ('4', '2階を割る', '南に居間。西の列を水まわりに。\n売場の真上が居間なので壁がそろう。'),
    ('5', '3階を割る', '南に子供室2つ。北に夫婦寝室。\nその間に廊下を1本通す。'),
    ('6', '柱を16本打つ', '通りの交わるところに柱。\nこれで伏図の下ごしらえが終わる。'),
]


def cell_origin(i):
    c, r = i % COLS, i // COLS
    return ML + c * CW + (CW - PW) / 2.0, MT + r * CH


def draw():
    s = Svg(W, H)
    s.text(W / 2.0, 38, 'エスキスは この順番でやる', size=23, weight='700')
    s.text(W / 2.0, 62,
           '「どこに何を置こう」と迷わないために、置く順番を決めてしまう。',
           size=12.5, fill='#666')
    s.text(W / 2.0, 82,
           '本番の60分は「考える時間」ではなく「この6手を実行する時間」。',
           size=12.5, fill='#b03060', weight='700')

    for i, (no, title, note) in enumerate(STEPS):
        ox, oy = cell_origin(i)
        top = oy + 8

        def X(gx):
            return ox + gx * G

        def Y(gy):
            return top + (NY - gy) * G

        # 見出し
        s.circle(ox - 6, top - 16, 12, fill='#b03060')
        s.text(ox - 6, top - 12, no, size=13, weight='700', fill='#fff')
        s.text(ox + 14, top - 12, title, size=14.5, weight='700',
               anchor='start')

        # マス目
        for k in range(NX + 1):
            s.line(X(k), Y(10), X(k), Y(0), stroke='#e9e9e9',
                   stroke_width=0.7)
        for k in range(NY + 1):
            s.line(X(0), Y(k), X(8), Y(k), stroke='#e9e9e9',
                   stroke_width=0.7)

        rooms = []
        if i == 2:
            rooms = F1
        elif i == 3:
            rooms = F2
        elif i == 4:
            rooms = F3
        elif i == 5:
            rooms = F1
        for nm, a, b, c, e, kind in rooms:
            fill, edge = COLORS[kind]
            op = '0.35' if i == 5 else '0.95'
            s.rect(X(a), Y(e), (c - a) * G, (e - b) * G, fill=fill,
                   stroke=edge, stroke_width=0.9, opacity=op)
            if i != 5:
                cx, cy = (X(a) + X(c)) / 2.0, (Y(b) + Y(e)) / 2.0
                small = (c - a) <= 2
                s.text(cx, cy + 3, nm, size=8.5 if small else 10,
                       weight='700', fill='#2a2a2a')

        # 階段（手順2以降）
        if i >= 1:
            fill, edge = COLORS['stair']
            s.rect(X(0), Y(6), 2 * G, 4 * G, fill=fill, stroke=edge,
                   stroke_width=1.4, opacity='0.95' if i < 5 else '0.5')
            if i < 5:
                s.text(X(1), Y(4) + 4, '階段', size=10, weight='700',
                       fill='#7a6100')

        # 外周
        s.rect(X(0), Y(10), PW, PH, fill='none', stroke='#111',
               stroke_width=2.2)

        # 柱（手順6）
        if i == 5:
            for gx, gy in KUDA:
                s.rect(X(gx) - 3, Y(gy) - 3, 6, 6, fill='#111')
            for gx, gy in TOOSHI:
                s.circle(X(gx), Y(gy), 5.5, fill='#fff', stroke='#c0392b',
                         stroke_width=1.8)
                s.circle(X(gx), Y(gy), 2.5, fill='#c0392b')

        # 道路
        s.rect(X(0), Y(0) + 6, PW, 11, fill='#f2f2f2', stroke='none')
        s.text(X(4), Y(0) + 15, '道 路（南）', size=8.5, fill='#999')

        # 説明
        for k, line in enumerate(note.split('\n')):
            s.text(ox + PW / 2.0, Y(0) + 38 + k * 17, line, size=11.5,
                   fill='#555')

    s.text(W / 2.0, H - 14,
           'ここまでで25分。残り35分は「問題文の条件に合わせて直す」時間に使う。',
           size=12, fill='#b03060', weight='700')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    draw().save(os.path.join(out, 'esquisse.svg'))
    print('wrote esquisse.svg  %dx%d' % (W, H))
