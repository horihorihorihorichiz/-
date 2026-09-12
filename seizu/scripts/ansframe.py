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
    """スパン（マス）から梁のせいを決める（plans.sei と同じ）。"""
    import plans as _plans
    return _plans.sei(masu)


def draw(kind='floor', floors=None, nx=None, ny=None, xlines=None,
         ylines=None, tag=''):
    """伏図を1枚描く。

    floors/nx/ny/xlines/ylines を渡すと、予想問題B〜Fのように
    大きさや通りの位置がちがう建物でもそのまま描ける（省略すると型）。
    """
    NX = nx if nx is not None else globals()['NX']
    NY = ny if ny is not None else globals()['NY']
    XL = xlines if xlines is not None else globals()['XL']
    YL = ylines if ylines is not None else globals()['YL']
    gkw = dict(floors=floors, nx=NX, ny=NY, xlines=XL, ylines=YL)
    W = ML + NX * G + MR
    H = MT + NY * G + MB

    def px(gx):
        return ML + gx * G

    def py(gy):
        return MT + (NY - gy) * G

    s = Svg(W, H)
    title = ('３階床伏図　縮尺1／100' if kind == 'floor'
             else '小屋伏図　縮尺1／100')
    if tag:
        title = '予想問題　%s 解答例　%s' % (tag, title)
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

    def member(ori, ln, a, b, dim, chamfer=False, label=True):
        """部材を2本線で描き、断面寸法を書きこむ。

        端は、ぶつかる相手の材の面で止める（交点に短い線が残ると
        管柱の記号 ×・□ と紛らわしいので、端の線・面取り線は描かない）。
        """
        if ori == 'H':
            y = py(ln)
            for dd in (-hw, hw):
                s.line(px(a) + hw, y + dd, px(b) - hw, y + dd, stroke=INK,
                       stroke_width=1.1)
            if label:
                texts.append(('H', (px(a) + px(b)) / 2.0, y - hw - 5, dim))
        else:
            x = px(ln)
            for dd in (-hw, hw):
                s.line(x + dd, py(a) - hw, x + dd, py(b) + hw, stroke=INK,
                       stroke_width=1.1)
            if label:
                texts.append(('V', x + hw + 12, (py(a) + py(b)) / 2.0,
                              dim))

    xs = [g for g, _ in XL]
    ys = [g for g, _ in YL]

    import plans as _plans
    lo_, up_ = (2, 3) if kind == 'floor' else (3, None)
    # 壁の上下と通り芯には必ず梁。残りは床梁 @910／小屋梁 @1,820（plans.framing）
    for ori_, ln_, a_, b_, sz_, _kd in _plans.framing(lo_, up_, **gkw):
        member(ori_, ln_, a_, b_, sz_)
    if kind != 'floor':
        # 棟木（南北・中央）は正角材なので2本の平行線で描く
        for dd in (-hw, hw):
            s.line(px(NX / 2.0) + dd, py(0) - 4, px(NX / 2.0) + dd,
                   py(NY) + 4, stroke=INK, stroke_width=1.2)
        s.text(px(NX / 2.0) + 26, py(NY / 2.0), '棟木 120×120', size=9,
               anchor='start')
        for gy in range(2, NY, 2):          # 棟束（棟木を受ける）
            s.circle(px(NX / 2.0), py(gy), 3.6, fill=INK)
        for gx in [g for g in range(1, NX) if abs(g - NX / 2.0) > 1e-9]:
            s.line(px(gx), py(0) - 4, px(gx), py(NY) + 4, stroke=INK,
                   stroke_width=0.9, stroke_dasharray='14 3 2 3')
            for gy in range(2, NY, 2):
                s.circle(px(gx), py(gy), 3.6, fill=INK)
        s.text(px(1) - 8, py(NY) - 16, '母屋 90×90（小屋束 90×90）', size=9,
               anchor='start')

    # 火打梁（建物の四隅と、中央の区画の四隅。合計8か所）
    d_ = 1.0
    ix0, ix1 = XL[1][0], XL[-2][0]          # 中の通り（東西）
    iy0, iy1 = YL[1][0], YL[-2][0]          # 中の通り（南北）
    for (x_, y_, sx, sy) in ((0, 0, 1, 1), (NX, 0, -1, 1),
                             (0, NY, 1, -1), (NX, NY, -1, -1),
                             (ix0, iy0, 1, 1), (ix1, iy0, -1, 1),
                             (ix0, iy1, 1, -1), (ix1, iy1, -1, -1)):
        s.line(px(x_ + sx * d_), py(y_), px(x_), py(y_ + sy * d_),
               stroke=INK, stroke_width=1.2, stroke_dasharray='8 4')

    # 柱（下の階＝×、上の階＝小さい四角、重なる＝四角にバツ、通し柱＝○で囲む）
    import plans as _plans
    lower, upper = (2, 3) if kind == 'floor' else (3, None)
    TOOSHI, BOTH, LOW, UP = _plans.columns_pair(lower, upper, **gkw)
    # 公式の凡例どおり：四角は梁の幅（120）と同じ大きさ、×は少しはみ出す
    r = hw + 0.3
    rx = hw * 1.7

    def sq(x, y, sw=1.3):
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke=INK,
               stroke_width=sw)

    def cross(x, y):
        s.line(x - rx, y - rx, x + rx, y + rx, stroke=INK, stroke_width=1.3)
        s.line(x - rx, y + rx, x + rx, y - rx, stroke=INK, stroke_width=1.3)

    for gx, gy in BOTH:                     # 上下の階が重なる管柱 → 四角にバツ
        x, y = px(gx), py(gy)
        sq(x, y, 1.6)
        cross(x, y)
    for gx, gy in LOW:                      # 下の階だけの管柱 → バツ
        x, y = px(gx), py(gy)
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke='none')
        cross(x, y)
    for gx, gy in UP:                       # 上の階だけの管柱 → 梁の幅の小さい四角
        x, y = px(gx), py(gy)
        sq(x, y, 1.6)
    for gx, gy in TOOSHI:                   # 通し柱 → 四角を丸で囲む
        x, y = px(gx), py(gy)
        sq(x, y, 1.6)
        s.circle(x, y, r * 2.4, fill='none', stroke=INK, stroke_width=1.2)

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
