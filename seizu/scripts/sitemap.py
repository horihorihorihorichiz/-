# -*- coding: utf-8 -*-
"""敷地図（公式様式・縮尺1/500・単位mm）。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')


def draw(sw=12000, sd=15000, road=6000, name='site_map',
         area='180.00', side='S'):
    S = 0.0155                       # 表示倍率
    ML, MT = 96, 74
    RW = road * S
    W = int(ML + sw * S + 150)
    H = int(MT + sd * S + RW + 92)
    s = Svg(W, H)

    def X(mm):
        return ML + mm * S

    def Y(mm):
        return MT + (sd - mm) * S

    # 隣地・宅地
    s.rect(X(-2600), Y(sd + 2600), (sw + 5200) * S, (sd + 2600) * S + RW,
           fill='#fbfaf7', stroke='none')
    # 道路
    s.rect(X(-2600), Y(0), (sw + 5200) * S, RW, fill='#f0f0ee',
           stroke='#999', stroke_width=0.8)
    s.text(X(sw / 2.0), Y(0) + RW / 2.0 + 5, '道　路', size=13, weight='700',
           fill='#555')
    # 敷地
    s.rect(X(0), Y(sd), sw * S, sd * S, fill='#ffffff', stroke='#111',
           stroke_width=2.0)
    s.text(X(sw / 2.0), Y(sd / 2.0) - 6, '敷　地', size=15, weight='700')
    s.text(X(sw / 2.0), Y(sd / 2.0) + 16, '（%s ㎡）' % area, size=12,
           fill='#444')
    # まわりの表示
    s.text_rot(X(-1500), Y(sd / 2.0), '隣　地', -90, size=12, fill='#777')
    s.text_rot(X(sw + 1500), Y(sd / 2.0), '隣　地', -90, size=12, fill='#777')
    s.text(X(sw / 2.0), Y(sd) - 14, '宅　地', size=12, fill='#777')

    # 寸法（上・左）
    dy = Y(sd) - 34
    s.dim_h(X(0), X(sw), dy, format(sw, ','))
    dx = X(0) - 40
    s.line(dx, Y(0), dx, Y(sd), stroke='#444', stroke_width=0.8)
    for m in (0, sd):
        s.line(dx - 4, Y(m), dx + 4, Y(m), stroke='#444', stroke_width=0.8)
    s.text_rot(dx - 6, Y(sd / 2.0), format(sd, ','), -90, size=11, fill='#444')
    # 道路の幅員
    dx2 = X(sw) + 100
    s.line(dx2, Y(0), dx2, Y(0) + RW, stroke='#444', stroke_width=0.8)
    for yy in (Y(0), Y(0) + RW):
        s.line(dx2 - 4, yy, dx2 + 4, yy, stroke='#444', stroke_width=0.8)
    s.text_rot(dx2 - 6, Y(0) + RW / 2.0, format(road, ','), -90, size=11,
               fill='#444')

    # 方位
    nx, ny = X(sw) + 56, Y(sd) + 30
    s.line(nx, ny + 26, nx, ny - 12, stroke='#111', stroke_width=1.2)
    s.polygon([(nx, ny - 18), (nx - 5, ny - 4), (nx + 5, ny - 4)], fill='#111')
    s.text(nx, ny + 40, 'N', size=12, weight='700')

    s.text(W / 2.0, H - 18, '敷地図（縮尺：1/500、単位：mm）', size=12,
           fill='#333')
    return s


if __name__ == '__main__':
    draw().save(os.path.join(OUT, 'site_map.svg'))
    print('wrote site_map.svg')
