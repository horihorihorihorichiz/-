# -*- coding: utf-8 -*-
"""解答用紙の1枚に何が載っているかを、番号つきで示す地図。"""
import os
import re
import io
from svgkit import Svg

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.join(HERE, '..', 'sheets')
OUT = os.path.join(HERE, '..', 'figures')

W, H = 700, 700
INK, RED = '#111', '#c0392b'

ITEMS = [
    ('1', 0.145, 0.30, '1階平面図 兼 配置図', '建物と敷地。いちばん時間がかかる'),
    ('2', 0.435, 0.30, '2階平面図', '1階の上にのる部屋'),
    ('3', 0.725, 0.30, '3階平面図', 'いちばん上の階'),
    ('4', 0.19, 0.755, '面積表', 'マスを数えて掛け算'),
    ('5', 0.62, 0.72, '凡例欄', '柱と梁の太さを書きこむ'),
    ('6', 0.62, 0.845, 'タイトル欄', '課題名など'),
    ('7', 0.30, 0.935, '解答のポイント', 'この教材だけの欄'),
]


def main():
    t = io.open(os.path.join(SH, 'kaitou_A.svg'), encoding='utf-8').read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t)
    bw, bh = float(m.group(1)), float(m.group(2))
    body = t[t.index('>', t.index('<svg')) + 1:t.rindex('</svg>')]
    for i in set(re.findall(r'id="([^"]+)"', body)):
        body = body.replace('id="%s"' % i, 'id="m%s"' % i)
        body = body.replace('url(#%s)' % i, 'url(#m%s)' % i)

    s = Svg(W, H)
    s.text(W / 2.0, 30, '答案用紙には、この7つが載る', size=20, weight='700')
    s.text(W / 2.0, 51, 'A2横の紙1枚。左から右へ、上から下へ埋めていく',
           size=11.5, fill='#666')

    mx, my, mw = 24.0, 70.0, W - 48.0
    sc = mw / bw
    mh = bh * sc
    s.add('<g transform="translate(%.2f,%.2f) scale(%.4f)" opacity="0.45">%s'
          '</g>' % (mx, my, sc, body))
    s.rect(mx, my, mw, mh, fill='none', stroke=INK, stroke_width=1.2)

    for no, fx, fy, name, memo in ITEMS:
        cx, cy = mx + mw * fx, my + mh * fy
        s.circle(cx, cy, 13, fill=RED, stroke='#fff', stroke_width=1.5)
        s.text(cx, cy + 5, no, size=13, fill='#fff', weight='700')

    ly = my + mh + 26
    for i, (no, fx, fy, name, memo) in enumerate(ITEMS):
        col = i // 4
        row = i % 4
        x = 30 + col * 348
        y = ly + row * 30
        s.circle(x + 11, y - 4, 11, fill=RED, stroke='none')
        s.text(x + 11, y, no, size=11.5, fill='#fff', weight='700')
        s.text(x + 30, y - 1, name, size=12.5, anchor='start', weight='700')
        s.text(x + 30, y + 12, memo, size=10, anchor='start', fill='#666')

    s.save(os.path.join(OUT, 'sheet_map.svg'))
    print('wrote sheet_map.svg')


if __name__ == '__main__':
    main()
