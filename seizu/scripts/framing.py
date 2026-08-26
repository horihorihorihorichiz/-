# -*- coding: utf-8 -*-
"""伏図の型（床伏図・小屋伏図）をSVGで描く。"""
import os
from svgkit import Svg

G = 56.0
ML, MR, MT, MB = 100, 112, 120, 268
NX, NY = 8, 10
W = ML + NX * G + MR
H = MT + NY * G + MB

XLINES = [(0, 'A'), (2, 'B'), (5, 'C'), (8, 'D')]
YLINES = [(0, '1'), (2, '2'), (6, '3'), (10, '4')]
TOOSHI = [(0, 0), (8, 0), (0, 10), (8, 10)]
KUDA = [(2, 0), (5, 0), (0, 2), (8, 2), (0, 6), (8, 6),
        (2, 10), (5, 10), (2, 2), (5, 2), (2, 6), (5, 6)]
# 火打梁を入れる隅（交点と、そこから伸ばす2方向）
HIUCHI = [(0, 0, 1, 1), (8, 0, -1, 1), (0, 10, 1, -1), (8, 10, -1, -1),
          (2, 2, 1, 1), (5, 2, -1, 1), (2, 6, 1, -1), (5, 6, -1, -1)]

C_DOUBUCHI = '#c0392b'   # 胴差・軒桁
C_OOBARI = '#1f6fb2'     # 大梁
C_KOBARI = '#2e8b57'     # 小梁・母屋
C_MUNE = '#7d3c98'       # 棟木
C_HIUCHI = '#e67e22'     # 火打梁


def px(gx):
    return ML + gx * G


def py(gy):
    return MT + (NY - gy) * G


def base(title, sub):
    s = Svg(W, H)
    s.text(W / 2.0, 36, title, size=21, weight='700')
    s.text(W / 2.0, 60, sub, size=12, fill='#666')
    x0, y0, x1, y1 = px(0), py(10), px(8), py(0)
    for i in range(NX + 1):
        s.line(px(i), y0, px(i), y1, stroke='#ededed', stroke_width=0.7)
    for j in range(NY + 1):
        s.line(x0, py(j), x1, py(j), stroke='#ededed', stroke_width=0.7)
    for gx, nm in XLINES:
        s.circle(px(gx), y0 - 36, 11, fill='#fff', stroke='#b03060',
                 stroke_width=1.2)
        s.text(px(gx), y0 - 32, nm, size=12, weight='700', fill='#b03060')
    for gy, nm in YLINES:
        s.circle(x0 - 40, py(gy), 11, fill='#fff', stroke='#b03060',
                 stroke_width=1.2)
        s.text(x0 - 40, py(gy) + 4, nm, size=12, weight='700', fill='#b03060')
    return s


def columns(s, tooshi=True):
    for gx, gy in KUDA:
        s.rect(px(gx) - 4.5, py(gy) - 4.5, 9, 9, fill='#111')
    if tooshi:
        for gx, gy in TOOSHI:
            s.circle(px(gx), py(gy), 8.5, fill='#fff', stroke='#c0392b',
                     stroke_width=2.4)
            s.circle(px(gx), py(gy), 4, fill='#c0392b')


def hiuchi(s, span=1.0):
    for gx, gy, dx, dy in HIUCHI:
        ax, ay = px(gx + dx * span), py(gy)
        bx, by = px(gx), py(gy + dy * span)
        s.line(ax, ay, bx, by, stroke=C_HIUCHI, stroke_width=2.6)


def legend(s, rows):
    ly = py(0) + 84
    s.rect(ML - 8, ly - 22, W - ML - MR + 16, 22 * len(rows) + 18,
           fill='#fafafa', stroke='#ddd', stroke_width=0.8, rx=6)
    for i, (kind, color, wdt, label) in enumerate(rows):
        yy = ly + i * 22
        cx = ML + 14
        if kind == 'line':
            s.line(cx - 8, yy - 4, cx + 26, yy - 4, stroke=color,
                   stroke_width=wdt)
        elif kind == 'dash':
            s.line(cx - 8, yy - 4, cx + 26, yy - 4, stroke=color,
                   stroke_width=wdt, stroke_dasharray='6 4')
        elif kind == 'tooshi':
            s.circle(cx + 9, yy - 4, 7, fill='#fff', stroke='#c0392b',
                     stroke_width=2.0)
            s.circle(cx + 9, yy - 4, 3.5, fill='#c0392b')
        elif kind == 'kuda':
            s.rect(cx + 5, yy - 8, 9, 9, fill='#111')
        elif kind == 'dot':
            s.circle(cx + 9, yy - 4, 5, fill='#fff', stroke=color,
                     stroke_width=2.0)
        s.text(ML + 52, yy, label, size=12, anchor='start', fill='#333')
    return s


# ============================================================
# 床伏図（2階床＝3階床も同じ）
# ============================================================
def floor_framing():
    s = base('床伏図の型（2階床伏図／3階床伏図 共通）',
             '1マス = 910mm　／　梁は「東西方向」に910ピッチで並べ、'
             'それを「南北方向」の4本の大梁で受ける')

    # 床小梁（東西方向 @910）
    for gy in (1, 3, 4, 5, 7, 8, 9):
        s.line(px(0), py(gy), px(8), py(gy), stroke=C_KOBARI,
               stroke_width=2.0)
    # 東西方向の大梁（2・3通り）
    for gy in (2, 6):
        s.line(px(0), py(gy), px(8), py(gy), stroke=C_OOBARI,
               stroke_width=4.2)
    # 南北方向の大梁（B・C通り）
    for gx in (2, 5):
        s.line(px(gx), py(0), px(gx), py(10), stroke=C_OOBARI,
               stroke_width=4.8)
    # 外周＝胴差
    s.rect(px(0), py(10), 8 * G, 10 * G, fill='none', stroke=C_DOUBUCHI,
           stroke_width=5.4)

    hiuchi(s, 1.0)
    columns(s)

    # 部材の寸法を図中に
    s.text(px(4), py(10) - 12, '胴差 120×300', size=11, fill=C_DOUBUCHI,
           weight='700')
    s.text_rot(px(2) - 10, py(8), '大梁 120×300', -90, size=11,
               fill=C_OOBARI, weight='700')
    s.text(px(6.5), py(2) - 8, '大梁 120×240', size=11, fill=C_OOBARI,
           weight='700')
    s.text(px(6.5), py(4) - 8, '床小梁 120×180 @910', size=11, fill=C_KOBARI,
           weight='700')
    s.text(px(1.15), py(0.55), '火打梁 90×90', size=10.5, fill=C_HIUCHI,
           weight='700', anchor='start')

    # スパンの寸法
    s.dim_h(px(0), px(2), py(0) + 34, '1,820')
    s.dim_h(px(2), px(5), py(0) + 34, '2,730')
    s.dim_h(px(5), px(8), py(0) + 34, '2,730')
    s.line(px(8) + 46, py(0), px(8) + 46, py(10), stroke='#444',
           stroke_width=0.8)
    for gy in (0, 2, 6, 10):
        s.line(px(8) + 42, py(gy), px(8) + 50, py(gy), stroke='#444',
               stroke_width=0.8)
    s.text_rot(px(8) + 40, (py(0) + py(2)) / 2.0, '1,820', -90, size=10.5,
               fill='#444')
    s.text_rot(px(8) + 40, (py(2) + py(6)) / 2.0, '3,640', -90, size=10.5,
               fill='#444')
    s.text_rot(px(8) + 40, (py(6) + py(10)) / 2.0, '3,640', -90, size=10.5,
               fill='#444')

    legend(s, [
        ('tooshi', '', 0, '通し柱 120×120（建物の四隅・1階から3階まで1本）'),
        ('kuda', '', 0, '管柱 120×120（各階ごとの柱・16か所すべて上下でそろう）'),
        ('line', C_DOUBUCHI, 5.4, '胴差 120×300（外周をぐるり1周）'),
        ('line', C_OOBARI, 4.8, '大梁 120×300／120×240（B・C通り と 2・3通り）'),
        ('line', C_KOBARI, 2.0, '床小梁 120×180 ＠910（東西方向に並べる）'),
        ('line', C_HIUCHI, 2.6, '火打梁 90×90（隅8か所・水平のゆがみ止め）'),
    ])
    s.text(W / 2.0, H - 14,
           '床は構造用合板 t=24 を梁に直接張る（根太レス＝剛床）。'
           '梁の最大スパンは 3,640mm におさえている。',
           size=11.5, fill='#555')
    return s


# ============================================================
# 小屋伏図
# ============================================================
def roof_framing():
    s = base('小屋伏図の型（切妻・棟は南北方向・4寸勾配）',
             '1マス = 910mm　／　棟木は建物の中央（X=3,640）。'
             '屋根は東西の2方向へ流れる')

    # 屋根の外形（軒の出600 / けらば455）
    eo, ke = 600 / 910.0, 455 / 910.0
    s.rect(px(-eo), py(10 + ke), (8 + 2 * eo) * G, (10 + 2 * ke) * G,
           fill='none', stroke='#999', stroke_width=1.2,
           stroke_dasharray='7 4')
    s.text(px(-eo) - 4, py(5), '', size=10)
    s.text(px(4), py(-ke) + 22, '屋根の外形（軒の出600・けらば455）',
           size=10.5, fill='#888')

    # 母屋（南北方向 @910）
    for gx in (1, 2, 3, 5, 6, 7):
        s.line(px(gx), py(-ke), px(gx), py(10 + ke), stroke=C_KOBARI,
               stroke_width=2.0)
    # 棟木
    s.line(px(4), py(-ke), px(4), py(10 + ke), stroke=C_MUNE,
           stroke_width=4.6)
    # 小屋梁（東西方向・柱通り）
    for gy in (0, 2, 6, 10):
        s.line(px(0), py(gy), px(8), py(gy), stroke=C_OOBARI,
               stroke_width=4.2)
    # 軒桁（A・D通り）
    for gx in (0, 8):
        s.line(px(gx), py(0), px(gx), py(10), stroke=C_DOUBUCHI,
               stroke_width=5.4)

    hiuchi(s, 1.0)

    # 小屋束
    for gx in (1, 2, 3, 4, 5, 6, 7):
        for gy in (0, 2, 6, 10):
            s.circle(px(gx), py(gy), 5, fill='#fff', stroke='#7d3c98',
                     stroke_width=1.8)
    columns(s, tooshi=False)
    for gx, gy in TOOSHI:
        s.circle(px(gx), py(gy), 8.5, fill='#fff', stroke='#c0392b',
                 stroke_width=2.4)
        s.circle(px(gx), py(gy), 4, fill='#c0392b')

    # 垂木の方向
    for gy in (4.5, 8.5):
        for sgn, x_from, x_to in ((-1, 3.7, 0.3), (1, 4.3, 7.7)):
            s.line(px(x_from), py(gy), px(x_to), py(gy), stroke='#b0651a',
                   stroke_width=1.2, stroke_dasharray='4 3')
            ex = px(x_to)
            s.polygon([(ex, py(gy)), (ex - sgn * 9, py(gy) - 4),
                       (ex - sgn * 9, py(gy) + 4)], fill='#b0651a')
    s.text(px(2), py(4.5) - 8, '垂木 45×105 @455', size=10.5, fill='#b0651a',
           weight='700')

    s.text_rot(px(4) - 10, py(8), '棟木 120×120', -90, size=11, fill=C_MUNE,
               weight='700')
    s.text_rot(px(0) - 12, py(4), '軒桁 120×240', -90, size=11,
               fill=C_DOUBUCHI, weight='700')
    s.text(px(6.4), py(6) - 8, '小屋梁 120×240', size=11, fill=C_OOBARI,
           weight='700')
    s.text(px(6.2), py(8.5) + 16, '母屋 90×90 @910', size=11, fill=C_KOBARI,
           weight='700')

    legend(s, [
        ('line', C_MUNE, 4.6, '棟木 120×120（建物の中央・南北方向に1本）'),
        ('line', C_KOBARI, 2.0, '母屋 90×90 ＠910（棟木と平行に6本）'),
        ('dot', '#7d3c98', 0, '小屋束 90×90（母屋と小屋梁の交点に立てる）'),
        ('line', C_OOBARI, 4.2, '小屋梁 120×240（東西方向・柱のある通りに）'),
        ('line', C_DOUBUCHI, 5.4, '軒桁 120×240（A通り・D通り）'),
        ('dash', '#b0651a', 1.6, '垂木 45×105 ＠455（棟から軒へ東西に流す）'),
    ])
    s.text(W / 2.0, H - 14,
           '4寸勾配 → 棟までの高さ 3,640 × 0.4 ＝ 1,456mm。'
           '軒桁天端＋1,456 が屋根のいちばん高いところ。',
           size=11.5, fill='#555')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    floor_framing().save(os.path.join(out, 'framing_floor.svg'))
    roof_framing().save(os.path.join(out, 'framing_roof.svg'))
    print('wrote framing_floor.svg / framing_roof.svg')
