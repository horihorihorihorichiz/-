# -*- coding: utf-8 -*-
"""公式の標準解答例と同じ描き方で南側立面図を描く。

窓の位置は平面図の開口からそのまま拾うので、平面図と食いちがわない。
"""
import os
from svgkit import Svg
import plans
from plans import fit_openings

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

G = 60.0                     # 1マス（910mm）
K = G / 910.0                # 1mmあたり
ML, MR, MT, MB = 200, 110, 96, 120
INK = '#111'

FL = [550, 3650, 6550]       # 各階の床（GLから）
NOKI = 9350                  # 軒高
TOP = 10806                  # 最高の高さ
NOKIDE = 600                 # 軒の出


def south_openings(n):
    """その階の南面の開口を（位置, 幅, 種別）で返す。"""
    d = plans.FLOORS[n]
    nx, ny = plans.NX, plans.NY
    ops = fit_openings(d, nx, ny, plans.XLINES, plans.YLINES)
    return [(p, l, k) for f, p, l, k, _ in ops if f == 'S']


def draw():
    nx = plans.NX
    W = ML + nx * G + MR
    H = MT + TOP * K + MB

    def px(gx):
        return ML + gx * G

    def py(mm):
        return MT + (TOP - mm) * K

    s = Svg(W, H)
    s.text(W / 2.0, 30, '南側立面図　縮尺1／100', size=15, weight='700')

    half = G / 2.0
    v = px(0) % half
    while v < W:
        s.line(v, 0, v, H, stroke='#e0e0e0', stroke_width=0.5)
        v += half
    v = py(0) % half
    while v < H:
        s.line(0, v, W, v, stroke='#e0e0e0', stroke_width=0.5)
        v += half

    x0, x1 = px(0), px(nx)
    gl = py(0)

    # ---- 地面 ----
    s.line(ML - 60, gl, W - 40, gl, stroke=INK, stroke_width=1.6)
    for i in range(int((W - 40 - ML + 60) / 9)):
        gx_ = ML - 60 + i * 9
        s.line(gx_, gl + 9, gx_ + 6, gl, stroke='#777', stroke_width=0.7)
    s.text(ML - 62, gl - 6, 'G.L.', size=10, anchor='end', weight='700')

    # ---- 基礎の立上り ----
    s.rect(x0 - 3, py(550), (x1 - x0) + 6, 550 * K, fill='#fff',
           stroke=INK, stroke_width=1.2)

    # ---- 外壁 ----
    s.rect(x0, py(NOKI), x1 - x0, (NOKI - 550) * K, fill='#fff', stroke=INK,
           stroke_width=1.6)

    # ---- 屋根（切妻・妻面。4寸勾配、軒の出600） ----
    ex0, ex1 = x0 - NOKIDE * K, x1 + NOKIDE * K
    mid = (x0 + x1) / 2.0
    rise = (x1 - x0) / 2.0 * 0.4
    ey = py(NOKI)
    apex = ey - rise
    t = 180 * K                                  # 屋根の厚み
    s.poly([(ex0, ey), (mid, apex), (ex1, ey)], stroke=INK, stroke_width=1.6,
           fill='none')
    dy = t * (1 + 0.4 ** 2) ** 0.5
    s.poly([(ex0, ey + dy), (mid, apex + dy), (ex1, ey + dy)], stroke=INK,
           stroke_width=1.2, fill='none')
    s.line(ex0, ey, ex0, ey + dy, stroke=INK, stroke_width=1.2)
    s.line(ex1, ey, ex1, ey + dy, stroke=INK, stroke_width=1.2)
    s.text(mid + 46, apex + 40, '4 / 10（4寸勾配）', size=9, anchor='start')

    # ---- 窓・出入口（平面図から拾う） ----
    def sash(a, b, lo, hi, panes=2):
        """建具。外枠と内枠、それに中桟。"""
        s.rect(a, hi, b - a, lo - hi, fill='#fff', stroke=INK,
               stroke_width=1.3)
        s.rect(a + 3, hi + 3, b - a - 6, lo - hi - 6, fill='none',
               stroke=INK, stroke_width=0.9)
        for i in range(1, panes):
            xx = a + (b - a) * i / float(panes)
            s.line(xx, hi + 3, xx, lo - 3, stroke=INK, stroke_width=0.9)

    for n in (1, 2, 3):
        f = FL[n - 1]
        for pos, ln, kind in south_openings(n):
            a, b = px(pos), px(pos + ln)
            if kind == 'entry':
                sash(a, b, py(f), py(f + 2000), 2)
            elif kind == 'balc':
                sash(a, b, py(f), py(f + 2000), 2)
                s.rect(a - 6, py(f + 1100), (b - a) + 12, 1100 * K,
                       fill='none', stroke=INK, stroke_width=1.3)
                for i in range(1, 6):
                    xx = a - 6 + ((b - a) + 12) * i / 6.0
                    s.line(xx, py(f), xx, py(f + 1100), stroke=INK,
                           stroke_width=0.7)
            else:
                sash(a, b, py(f + 800), py(f + 2100), 2)

    # ---- 高さのしるし ----
    marks = [(TOP, '▽最高の高さ'), (NOKI, '▽軒高'), (FL[2], '3FL'),
             (FL[1], '2FL'), (FL[0], '1FL')]
    for mm, lab in marks:
        s.line(x0 - 96, py(mm), x0 - 4, py(mm), stroke=INK,
               stroke_width=0.8, stroke_dasharray='10 3 2 3')
        s.text(x0 - 100, py(mm) - 4, lab, size=9.5, anchor='end',
               weight='700')
        s.text(x0 - 100, py(mm) + 9, 'GL＋%s' % format(mm, ','), size=8.5,
               anchor='end', fill='#333')
    s.dim_v(gl, py(TOP), x1 + 46, format(TOP, ','), anchor='start', dx=6)
    s.dim_v(gl, py(NOKI), x1 + 20, format(NOKI, ','), size=9,
            anchor='start', dx=5)
    s.dim_h(x0, x1, gl + 46, format(nx * 910, ','))
    return s


if __name__ == '__main__':
    draw().save(os.path.join(OUT, 'anselev_s.svg'))
    print('wrote anselev_s.svg')
