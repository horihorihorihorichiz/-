# -*- coding: utf-8 -*-
"""公式の標準解答例と同じ描き方で南側立面図を描く。

窓の位置は平面図の開口からそのまま拾うので、平面図と食いちがわない。
"""
import os
from svgkit import Svg
import plans
from plans import fit_openings

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

G = 56.0                     # 1マス（910mm）
K = G / 910.0                # 1mmあたり
ML, MR, MT, MB = 200, 110, 96, 120
INK = '#111'

FL = [550, 3650, 6550]       # 各階の床（GLから）
NOKI = 9350                  # 軒高
TOP = 10806                  # 最高の高さ
NOKIDE = 600                 # 軒の出


# 玄関まわりの高さ（平面図の記入と同じ数字にそろえる）
DOMA_GL = 400                # 玄関土間（土足のところ）
PORCH_GL = 380               # 玄関ポーチ
PORCH_STEPS = 2              # 地面からポーチまで（190×2）
SHOP_STEPS = 3               # 地面から店舗の床 GL+550 まで
DOOR_H = 2000                # 出入口の高さ


def south_openings(n, floors=None, **kw):
    """その南面の開口を（位置, 幅, 種別, 名前）で返す。"""
    ops = plans.fit_all(floors or plans.FLOORS, **kw)[n]
    return [(p, l, k, lab) for f, p, l, k, lab in ops if f == 'S']


def draw(floors=None, nx=None, ny=None, xlines=None, ylines=None, tag='',
         face='S'):
    """南側立面図。floors などを渡すと予想問題B〜Fの建物でも描ける。

    屋根は切妻・棟が南北なので、妻面（南）は三角に見える。
    最高の高さは 軒高 ＋ 間口の半分 × 0.4（4寸勾配）で決まるので、
    間口がちがえば最高の高さも変わる。
    """
    floors = floors or plans.FLOORS
    nx = plans.NX if nx is None else nx
    gkw = dict(nx=nx,
               ny=plans.NY if ny is None else ny,
               xlines=plans.XLINES if xlines is None else xlines,
               ylines=plans.YLINES if ylines is None else ylines)
    rise = nx * 910 / 2.0 * 0.4
    TOP = int(round(NOKI + rise))
    W = ML + nx * G + MR
    H = MT + TOP * K + MB

    def px(gx):
        return ML + gx * G

    def py(mm):
        return MT + (TOP - mm) * K

    s = Svg(W, H)
    ttl = '南側立面図　縮尺1／100'
    if tag:
        ttl = '予想問題　%s 解答例　%s' % (tag, ttl)
    s.text(W / 2.0, 30, ttl, size=15, weight='700')

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
    ey = py(NOKI)
    apex = py(TOP)
    t = 180 * K                                  # 屋根の厚み
    s.poly([(ex0, ey), (mid, apex), (ex1, ey)], stroke=INK, stroke_width=1.6,
           fill='none')
    dy = t * (1 + 0.4 ** 2) ** 0.5
    s.poly([(ex0, ey + dy), (mid, apex + dy), (ex1, ey + dy)], stroke=INK,
           stroke_width=1.2, fill='none')
    s.line(ex0, ey, ex0, ey + dy, stroke=INK, stroke_width=1.2)
    s.line(ex1, ey, ex1, ey + dy, stroke=INK, stroke_width=1.2)
    s.text(mid + 80, apex + 62, '4 / 10（4寸勾配）', size=9, anchor='start')

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

    def door(a, b, lo, hi):
        """出入口。窓とちがって下まで枠があるので、中は縦1本＋引手。"""
        s.rect(a, hi, b - a, lo - hi, fill='#fff', stroke=INK,
               stroke_width=1.6)
        s.rect(a + 3, hi + 3, b - a - 6, lo - hi - 6, fill='none',
               stroke=INK, stroke_width=1.0)
        mid = (a + b) / 2.0
        s.line(mid, hi + 3, mid, lo - 3, stroke=INK, stroke_width=1.0)
        for d in (-9, 9):                       # 引手（両開き・引違いどちらでも）
            s.line(mid + d, lo - (lo - hi) * 0.46,
                   mid + d, lo - (lo - hi) * 0.40,
                   stroke=INK, stroke_width=1.4)

    def steps(a, b, sill, porch, n_st, genkan):
        """出入口の下。ポーチ（あれば）と、地面からの段。

        正面から見た段は「幅は変わらず、蹴上ごとに横線が1本」。
        幅は開口の左右に半マス（455）ずつ広げる。
        """
        ext = G * 0.5
        pa, pb = a - ext, b + ext
        top = porch if genkan else sill
        s.rect(pa, py(top), pb - pa, top * K, fill='#fff', stroke=INK,
               stroke_width=1.2)
        r = top / float(n_st)
        for i in range(1, n_st):
            s.line(pa, py(r * i), pb, py(r * i), stroke=INK,
                   stroke_width=1.0)
        if genkan:                              # ポーチ（+380）→ 土間（+400）
            s.line(a, py(sill), b, py(sill), stroke=INK, stroke_width=1.2)

    for n in (1, 2, 3):
        f = FL[n - 1]
        for pos, ln, kind, lab in south_openings(n, floors, **gkw):
            a, b = px(pos), px(pos + ln)
            if kind == 'entry':
                # 玄関は土間（GL+400）、店・勝手口は床（GL+550）に立つ。
                # ドアの下は床の高さで、そこまで外から段で上がる。
                genkan = '玄関' in lab
                sill = DOMA_GL if genkan else f
                door(a, b, py(sill), py(sill + DOOR_H))
                if n == 1:
                    steps(a, b, sill, PORCH_GL if genkan else 0,
                          PORCH_STEPS if genkan else SHOP_STEPS, genkan)
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
