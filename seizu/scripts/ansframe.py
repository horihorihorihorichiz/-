# -*- coding: utf-8 -*-
"""公式の標準解答例と同じ描き方で、床伏図と小屋伏図を描く。

・部材はすべて2本線。平角材は端を斜めに落とす
・1本ずつに断面寸法（120×240 など）を書き込む
・柱は 1階＝×、2階＝たて2本線、重なる＝四角にバツ、通し柱＝○で囲む
・火打梁は破線。棟木・母屋は一点鎖線＋黒丸（小屋束）
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

G = 56.0
ML, MR, MT, MB = 108, 132, 116, 150
INK = '#111'
MW = 120.0 / 910.0          # 部材の幅120mm（マス）

XL = [(0, 'A'), (2, 'B'), (5, 'C'), (8, 'D')]
YL = [(0, '1'), (2, '2'), (6, '3'), (10, '4')]
NX, NY = 8, 10


def sei(masu, taika=False):
    """スパン（マス）から梁のせいを決める。上に柱が乗るぶんを見込む。"""
    mm = masu * 910
    if mm <= 1900:
        return 180
    if mm <= 2800:
        return 240
    return 300


def draw(kind='floor'):
    W = ML + NX * G + MR
    H = MT + NY * G + MB

    def px(gx):
        return ML + gx * G

    def py(gy):
        return MT + (NY - gy) * G

    s = Svg(W, H)
    title = ('３階床伏図（２階の床も同じ組み方）　縮尺1／100' if kind == 'floor'
             else '小屋伏図　縮尺1／100')
    s.text(W / 2.0, 32, title, size=15, weight='700')

    # 方眼（目盛4.55mm＝455mm）
    half = G / 2.0
    v = px(0) % half
    while v < W:
        s.line(v, 0, v, H, stroke='#e0e0e0', stroke_width=0.5)
        v += half
    v = py(0) % half
    while v < H:
        s.line(0, v, W, v, stroke='#e0e0e0', stroke_width=0.5)
        v += half

    hw = MW / 2.0 * G
    texts = []

    def member(ori, ln, a, b, dim, chamfer=True, label=True):
        """部材を2本線で描き、断面寸法を書きこむ。"""
        c = min(hw, 4.0) if chamfer else 0
        if ori == 'H':
            y = py(ln)
            for dd in (-hw, hw):
                s.line(px(a) + c, y + dd, px(b) - c, y + dd, stroke=INK,
                       stroke_width=1.1)
            s.line(px(a), y - hw + c, px(a), y + hw - c, stroke=INK,
                   stroke_width=1.1)
            s.line(px(b), y - hw + c, px(b), y + hw - c, stroke=INK,
                   stroke_width=1.1)
            if c:
                for xx, sg in ((px(a), 1), (px(b), -1)):
                    s.line(xx, y - hw + c, xx + sg * c, y - hw, stroke=INK,
                           stroke_width=1.1)
                    s.line(xx, y + hw - c, xx + sg * c, y + hw, stroke=INK,
                           stroke_width=1.1)
            if label:
                texts.append(('H', (px(a) + px(b)) / 2.0, y - hw - 5, dim))
        else:
            x = px(ln)
            for dd in (-hw, hw):
                s.line(x + dd, py(a) - c, x + dd, py(b) + c, stroke=INK,
                       stroke_width=1.1)
            s.line(x - hw + c, py(a), x + hw - c, py(a), stroke=INK,
                   stroke_width=1.1)
            s.line(x - hw + c, py(b), x + hw - c, py(b), stroke=INK,
                   stroke_width=1.1)
            if c:
                for yy, sg in ((py(a), -1), (py(b), 1)):
                    s.line(x - hw + c, yy, x - hw, yy + sg * c, stroke=INK,
                           stroke_width=1.1)
                    s.line(x + hw - c, yy, x + hw, yy + sg * c, stroke=INK,
                           stroke_width=1.1)
            if label:
                texts.append(('V', x + hw + 12, (py(a) + py(b)) / 2.0,
                              dim))

    xs = [g for g, _ in XL]
    ys = [g for g, _ in YL]

    if kind == 'floor':
        # 外周の胴差
        for ln in (0, NY):
            member('H', ln, 0, NX, '120×300')
        for ln in (0, NX):
            member('V', ln, 0, NY, '120×300')
        # 通り芯の大梁
        for ln in xs[1:-1]:
            for a, b in zip(ys[:-1], ys[1:]):
                member('V', ln, a, b, '120×300')
        for ln in ys[1:-1]:
            for a, b in zip(xs[:-1], xs[1:]):
                member('H', ln, a, b, '120×240')
        # 床小梁（東西方向、910mmおき）
        for a, b in zip(ys[:-1], ys[1:]):
            for gy in range(int(a) + 1, int(b)):
                for c_, e_ in zip(xs[:-1], xs[1:]):
                    member('H', gy, c_, e_, '120×%d' % sei(e_ - c_))
    else:
        # 軒桁（東西の外周）と小屋梁
        for ln in (0, NY):
            member('H', ln, 0, NX, '120×240')
        for ln in (0, NX):
            member('V', ln, 0, NY, '120×240')
        for ln in xs[1:-1]:
            for a, b in zip(ys[:-1], ys[1:]):
                member('V', ln, a, b, '120×240')
        # 小屋梁（東西方向、1,820おき）
        for gy in range(2, NY, 2):
            for c_, e_ in zip(xs[:-1], xs[1:]):
                member('H', gy, c_, e_, '120×240')
        # 棟木（南北・中央）は正角材なので2本の平行線で描く
        for dd in (-hw, hw):
            s.line(px(NX / 2.0) + dd, py(0) - 4, px(NX / 2.0) + dd,
                   py(NY) + 4, stroke=INK, stroke_width=1.2)
        s.text(px(NX / 2.0) + 26, py(NY / 2.0), '棟木 120×120', size=9,
               anchor='start')
        for gx in (1, 2, 3, 5, 6, 7):
            s.line(px(gx), py(0) - 4, px(gx), py(NY) + 4, stroke=INK,
                   stroke_width=0.9, stroke_dasharray='14 3 2 3')
            for gy in range(2, NY, 2):
                s.circle(px(gx), py(gy), 3.6, fill=INK)
        s.text(px(1) - 8, py(NY) - 16, '母屋 90×90（小屋束 90×90）', size=9,
               anchor='start')

    # 火打梁（建物の四隅と、中央の区画の四隅。合計8か所）
    d_ = 1.0
    for (x_, y_, sx, sy) in ((0, 0, 1, 1), (NX, 0, -1, 1),
                             (0, NY, 1, -1), (NX, NY, -1, -1),
                             (2, 2, 1, 1), (5, 2, -1, 1),
                             (2, 6, 1, -1), (5, 6, -1, -1)):
        s.line(px(x_ + sx * d_), py(y_), px(x_), py(y_ + sy * d_),
               stroke=INK, stroke_width=1.2, stroke_dasharray='8 4')

    # 柱（1階＝×、2階＝たて2本線、重なる＝四角にバツ、通し柱＝○で囲む）
    KUDA = [(2, 0), (5, 0), (0, 2), (8, 2), (0, 6), (8, 6),
            (2, 10), (5, 10), (2, 2), (5, 2), (2, 6), (5, 6)]
    TOOSHI = [(0, 0), (8, 0), (0, 10), (8, 10)]
    r = 5.0
    for gx, gy in KUDA:
        x, y = px(gx), py(gy)
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke=INK,
               stroke_width=1.0)
        s.line(x - r, y - r, x + r, y + r, stroke=INK, stroke_width=1.2)
        s.line(x - r, y + r, x + r, y - r, stroke=INK, stroke_width=1.2)
    for gx, gy in TOOSHI:
        x, y = px(gx), py(gy)
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke=INK,
               stroke_width=1.0)
        s.circle(x, y, r + 4, fill='none', stroke=INK, stroke_width=1.2)

    # 断面寸法の文字（部材のあとに描いて隠れないようにする）
    for kind_, a, b, t in texts:
        if kind_ == 'H':
            s.text(a, b, t, size=8, fill=INK)
        else:
            s.text_rot(a, b, t, -90, size=8, fill=INK)

    # 寸法（スパン＋全体）
    for a, b in zip(xs[:-1], xs[1:]):
        s.dim_h(px(a), px(b), py(0) + 34, format(int((b - a) * 910), ','),
                size=9)
    s.dim_h(px(0), px(NX), py(0) + 62, format(NX * 910, ','))
    for a, b in zip(ys[:-1], ys[1:]):
        s.dim_v(py(a), py(b), px(NX) + 30, format(int((b - a) * 910), ','),
                size=9, anchor='start', dx=6)
    s.dim_v(py(0), py(NY), px(NX) + 96, format(NY * 910, ','),
            anchor='start', dx=6)

    s.text(px(0), py(0) + 90,
           '火打梁 90×90（破線）　／　柱の記号は凡例欄のとおり　／　'
           '寸法の単位はmm', size=9, anchor='start', fill='#333')

    # 通り符号
    for gx, nm in XL:
        s.circle(px(gx), py(NY) - 34, 9, fill='#fff', stroke=INK,
                 stroke_width=0.9)
        s.text(px(gx), py(NY) - 30, nm, size=10, weight='700')
    for gy, nm in YL:
        s.circle(px(0) - 36, py(gy), 9, fill='#fff', stroke=INK,
                 stroke_width=0.9)
        s.text(px(0) - 36, py(gy) + 4, nm, size=10, weight='700')
    return s


if __name__ == '__main__':
    draw('floor').save(os.path.join(OUT, 'ansfuse_floor.svg'))
    draw('roof').save(os.path.join(OUT, 'ansfuse_roof.svg'))
    print('wrote ansfuse_floor / ansfuse_roof')
