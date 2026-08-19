# -*- coding: utf-8 -*-
"""木材の寸法の書き方（幅×せい）と、断面の大きさくらべ。"""
import os
from svgkit import Svg

S = 0.42                       # 1mm あたりの表示ピクセル
W, H = 760, 738

# (名前, 幅, せい, 色, 補足)
MEMBERS = [
    ('胴差',       105, 300, '#c0392b', '外周を1周'),
    ('大梁・軒桁', 105, 240, '#1f6fb2', '柱と柱をつなぐ'),
    ('床小梁',     105, 180, '#2e8b57', '910mmおき'),
    ('通し柱',     120, 120, '#c0392b', '四隅だけ'),
    ('管柱・土台', 105, 105, '#8a6a35', 'ふつうの柱'),
    ('母屋・火打梁', 90,  90, '#7d3c98', '90mm角'),
    ('垂木',        45, 105, '#b0651a', '455mmおき'),
    ('筋かい',      45,  90, '#8a6a35', 'たすき掛け'),
]


def draw():
    s = Svg(W, H)
    s.text(W / 2.0, 34, '木材の寸法は「幅 × せい」で書く', size=22,
           weight='700')
    s.text(W / 2.0, 58,
           'せい＝上下方向の高さ。木を輪切りにしたときの、よこ × たて。',
           size=12.5, fill='#666')

    # ============ 上の段：1本の梁を立体で見る ============
    bx, by = 74, 140                     # 前面の左上
    L = 260.0                            # 長さ（見た目だけ）
    dx, dy = 36.0, -24.0                 # 奥行き方向のずらし
    hh = 300 * S                         # せい300
    ww = 105 * S                         # 幅105

    s.text(bx - 6, by - 62, '① 梁を立体で見ると', size=15, weight='700',
           anchor='start')
    s.text(bx - 6, by - 42,
           '「幅」は横の厚み、「せい」は上下の高さ。長さは別の話。',
           size=12, fill='#666', anchor='start')

    # 上面
    s.polygon([(bx, by), (bx + L, by), (bx + L + dx, by + dy),
               (bx + dx, by + dy)], fill='#efdcbb', stroke='#8a6a35',
              stroke_width=1.4)
    # 右の木口（断面）
    s.polygon([(bx + L, by), (bx + L + dx, by + dy),
               (bx + L + dx, by + dy + hh), (bx + L, by + hh)],
              fill='#e0c89a', stroke='#8a6a35', stroke_width=1.4)
    # 前面
    s.rect(bx, by, L, hh, fill='#f7ecd8', stroke='#8a6a35', stroke_width=1.6)
    for k in range(1, 5):
        s.line(bx + 8, by + hh * k / 5.0, bx + L - 8, by + hh * k / 5.0,
               stroke='#d9c49c', stroke_width=0.8)

    # 幅の寸法（奥行き方向）
    s.line(bx + L + 8, by + 4, bx + L + dx + 8, by + dy + 4, stroke='#c0392b',
           stroke_width=1.2)
    s.text(bx + L + dx + 22, by + dy + 6, '幅 105', size=13, weight='700',
           fill='#c0392b', anchor='start')
    # せいの寸法
    s.dim_v(by, by + hh, bx - 16, '', color='#1f6fb2', anchor='middle', dx=0)
    s.text_rot(bx - 22, by + hh / 2.0, 'せい 300', -90, size=13, weight='700',
               fill='#1f6fb2')
    # 長さ
    s.dim_h(bx, bx + L, by + hh + 34, '長さ（スパン）')

    # まとめ
    s.rect(bx + L + dx + 24, by + 46, 224, 96, fill='#fff8e1',
           stroke='#e0c060', stroke_width=1, rx=8)
    s.text(bx + L + dx + 38, by + 70, '105 × 300 と書いてあったら', size=12.5,
           weight='700', anchor='start', fill='#6b5200')
    s.text(bx + L + dx + 38, by + 92, '　よこ（幅）　= 105mm', size=12.5,
           anchor='start', fill='#6b5200')
    s.text(bx + L + dx + 38, by + 112, '　たて（せい）= 300mm', size=12.5,
           anchor='start', fill='#6b5200')
    s.text(bx + L + dx + 38, by + 132, '　→ 細くて背の高い木', size=12.5,
           anchor='start', fill='#6b5200')

    # 伏図では幅しか見えない
    py0 = by + hh + 62
    s.text(bx - 6, py0 + 4, '② 伏図（上から見た図）では', size=15,
           weight='700', anchor='start')
    s.text(bx - 6, py0 + 24,
           '真上から見るので「幅」しか見えない。せいは下に隠れている。',
           size=12, fill='#666', anchor='start')
    s.rect(bx, py0 + 40, L + dx, ww, fill='#efdcbb', stroke='#8a6a35',
           stroke_width=1.6)
    s.text(bx + (L + dx) / 2.0, py0 + 40 + ww / 2.0 + 5,
           'この帯の太さ ＝ 幅 105 だけ', size=12.5, fill='#7a5c20')
    s.line(bx + L + dx + 14, py0 + 40, bx + L + dx + 14, py0 + 40 + ww,
           stroke='#c0392b', stroke_width=1.2)
    s.text(bx + L + dx + 22, py0 + 40 + ww / 2.0 + 4, '105', size=12,
           fill='#c0392b', weight='700', anchor='start')
    s.rect(bx + L + dx + 60, py0 + 34, 188, 62, fill='#f6f9f4',
           stroke='#bcd4bc', stroke_width=1, rx=8)
    s.text(bx + L + dx + 72, py0 + 56,
           'だから伏図では、太さの', size=12, anchor='start', fill='#245a2c')
    s.text(bx + L + dx + 72, py0 + 74,
           'ちがいは線の太さと', size=12, anchor='start', fill='#245a2c')
    s.text(bx + L + dx + 72, py0 + 92,
           '文字で表す。', size=12, anchor='start', fill='#245a2c')

    # ============ 下の段：断面くらべ ============
    ty = 508
    s.text(46, ty, '③ 断面の大きさくらべ（同じ縮尺・上をそろえてある）',
           size=15, weight='700', anchor='start')
    s.text(46, ty + 20,
           '幅はほとんど 105 でそろえてある。変わるのは「せい」だけ。',
           size=12, fill='#b03060', weight='700', anchor='start')

    base = ty + 48                         # 上端をそろえる線
    x = 62
    s.line(46, base, W - 40, base, stroke='#bbb', stroke_width=0.8,
           stroke_dasharray='5 4')
    s.text(W - 36, base - 5, '天端', size=10.5, fill='#999', anchor='end')
    for name, w, d, col, memo in MEMBERS:
        pw, pd = w * S, d * S
        s.rect(x, base, pw, pd, fill='#f7ecd8', stroke=col, stroke_width=1.8)
        for k in range(1, int(pd // 14)):
            s.line(x + 3, base + k * 14, x + pw - 3, base + k * 14,
                   stroke='#e3d3b4', stroke_width=0.7)
        s.text(x + pw / 2.0, base - 10, '%d×%d' % (w, d), size=11,
               weight='700', fill=col)
        s.text(x + pw / 2.0, base + pd + 16, name, size=11.5, weight='700')
        s.text(x + pw / 2.0, base + pd + 32, memo, size=10, fill='#888')
        x += pw + 44

    s.text(W / 2.0, H - 16,
           '柱は正方形（105×105・120×120）。梁は縦長にすると同じ木の量で'
           '強くなるので、せいを大きくとる。',
           size=12, fill='#555')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    draw().save(os.path.join(out, 'section.svg'))
    print('wrote section.svg')
