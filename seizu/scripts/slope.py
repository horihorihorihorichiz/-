# -*- coding: utf-8 -*-
"""スロープの長さは「床の高さ」で決まる、という説明図。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 660, 560
INK, RED, BLUE, EARTH, GREEN = '#111', '#c0392b', '#2f7fd0', '#8a7a5f', '#2f8f6a'

s = Svg(W, H)
s.text(W / 2.0, 34, 'スロープは「床を下げる」と短くなる', size=21, weight='700')
s.text(W / 2.0, 57, '敷地が狭い年ほど、ここで建物のスペースが決まる', size=12,
       fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


K = 0.055                        # 長さ 1mm あたりのピクセル
KV = 0.10                        # 高さは見やすいように長さの約2倍で描く


def ramp(oy, rise, grad, label, col, note):
    """1本のスロープを横から見た図。"""
    run = rise * grad
    x0 = 74
    x1 = x0 + run * K
    yb = oy + 76
    yt = yb - rise * KV
    s.line(40, yb, W - 40, yb, stroke=EARTH, stroke_width=1.6)
    for i in range(int((W - 80) / 10)):
        s.line(40 + i * 10, yb + 9, 40 + i * 10 + 6, yb, stroke=EARTH,
               stroke_width=0.7)
    s.polygon([(x0, yb), (x1, yb), (x1, yt)], fill='#f2f6fb', stroke=col,
              stroke_width=1.8)
    s.rect(x1, yt - 34, 74, 34 + (yb - yt), fill='#fff', stroke=INK,
           stroke_width=1.4)
    s.text(x1 + 37, yt - 12, label, size=11, weight='700')
    s.line(x1 + 90, yb, x1 + 90, yt, stroke=col, stroke_width=1.0)
    s.line(x1 + 86, yb, x1 + 94, yb, stroke=col, stroke_width=1.0)
    s.line(x1 + 86, yt, x1 + 94, yt, stroke=col, stroke_width=1.0)
    s.text(x1 + 98, (yb + yt) / 2.0 + 4, 'GL＋%d' % rise, size=11.5,
           anchor='start', fill=col, weight='700')
    s.dim_h(x0, x1, yb + 32, '%s（%d × %d）' % (format(int(run), ','),
                                               rise, grad))
    s.text(x0 + 4, yb + 54, note, size=11, anchor='start', fill='#555')
    return run


band(74, 296, 'その1', '住宅の玄関　床が高い → スロープが長い')
ramp(96, 500, 15, '住宅玄関 GL＋500', RED,
     '勾配 1/15 なら 500 × 15 ＝ 7,500mm。'
     '幅1,200以上、途中に踊り場も必要。')
s.text(74, 276, '道路側に7.5mも取られると、建物を置くスペースが残らない。',
       size=12, anchor='start', weight='700', fill=RED)

band(306, 528, 'その2', '店舗の床を150まで下げる → スロープは1,800')
ramp(328, 150, 12, '店舗 GL＋150', GREEN,
     '勾配 1/12 なら 150 × 12 ＝ 1,800mm。段差が小さいので勾配もゆるくできる。')
s.text(74, 508, 'これだけで 5,700mm ＝ 約6マス分の敷地が建物にまわせる。',
       size=12, anchor='start', weight='700', fill=GREEN)

s.save(os.path.join(OUT, 'slope.svg'))
print('wrote slope.svg')
