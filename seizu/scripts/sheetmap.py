# -*- coding: utf-8 -*-
"""この教材の標準解答例・1枚目に何が載っているかを、番号つきで示す地図。

背景に使っているのは sheets/kaitou_A.svg（標準解答例の1枚目）。
練習用紙（renshu1〜4）とは枠の割り方がちがうので、取りちがえないこと。
"""
import os
import re
import io
from svgkit import Svg

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.join(HERE, '..', 'sheets')
OUT = os.path.join(HERE, '..', 'figures')

W, H = 760, 812
INK, RED = '#111', '#c0392b'

ITEMS = [
    ('1', 0.169, 0.245, '⑴ 1階平面図 兼 配置図', '建物と敷地。いちばん時間がかかる'),
    ('2', 0.450, 0.245, '⑵ 2階平面図', '1階の上にのる部屋'),
    ('3', 0.732, 0.245, '⑶ 3階平面図', 'いちばん上の階'),
    ('4', 0.127, 0.668, '⑷ 3階床伏図', '床の骨組み。壁も家具も描かない'),
    ('5', 0.319, 0.668, '⑷ 小屋伏図', '屋根の骨組み。⑷はこの2枠でひとつ'),
    ('6', 0.521, 0.668, '⑸ 南側立面図', '南から横に見た絵。高さの数字'),
    ('7', 0.726, 0.668, '⑹ 部分詳細図（1/20）', 'ここだけ方眼が10mm'),
    ('8', 0.931, 0.155, '⑺ 面積表', 'マスを数えて掛け算'),
    ('9', 0.913, 0.668, '⑻ 計画の要点等', '文章で答える。3問'),
    ('10', 0.359, 0.923, '凡例欄', '柱と梁の太さを書きこむ'),
    ('11', 0.847, 0.879, 'タイトル欄', '課題名・受験番号・氏名'),
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
    s.text(W / 2.0, 30, '答案用紙（A2横1枚）にある、11の枠', size=20,
           weight='700')
    s.text(W / 2.0, 51,
           '要求図書⑴〜⑹と⑺面積表・⑻計画の要点等が、この1枚に全部のる。'
           '左から右へ、上から下へ埋めていく',
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
        col = i // 6
        row = i % 6
        x = 24 + col * 344
        y = ly + row * 30
        s.circle(x + 11, y - 4, 11, fill=RED, stroke='none')
        s.text(x + 11, y, no, size=11.5, fill='#fff', weight='700')
        s.text(x + 30, y - 1, name, size=12.5, anchor='start', weight='700')
        s.text(x + 30, y + 12, memo, size=10, anchor='start', fill='#666')

    s.save(os.path.join(OUT, 'sheet_map.svg'))
    print('wrote sheet_map.svg')


if __name__ == '__main__':
    main()
