# -*- coding: utf-8 -*-
"""敷地図（公式様式・縮尺1/500・単位mm）。道路の向きを指定できる。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
S = 0.0155


def draw(sw, sd, road, area, side='S', road2=None):
    ML, MT = 104, 74
    RW = road * S
    RW2 = (road2 or 0) * S
    W = int(ML + sw * S + 172 + (RW2 if 'E' in side else 0))
    H = int(MT + sd * S + (RW if 'S' in side or 'N' in side else 0) + 96)
    top_pad = RW if 'N' in side else 0
    s = Svg(W, H)

    def X(mm):
        return ML + mm * S

    def Y(mm):
        return MT + top_pad + (sd - mm) * S

    # 周囲（隣地・宅地）
    s.rect(X(-2800), Y(sd) - top_pad - 24, (sw + 5600) * S + RW2,
           sd * S + top_pad + RW + 48, fill='#fbfaf7', stroke='none')

    def road_band(x, y, w, h, rot=False):
        s.rect(x, y, w, h, fill='#f0f0ee', stroke='#999', stroke_width=0.8)
        if rot:
            s.text_rot(x + w / 2.0 + 5, y + h / 2.0, '道　路', -90, size=12,
                       weight='700', fill='#555')
        else:
            s.text(x + w / 2.0, y + h / 2.0 + 5, '道　路', size=12,
                   weight='700', fill='#555')

    if 'S' in side:
        road_band(X(-2800), Y(0), (sw + 5600) * S + RW2, RW)
    if 'N' in side:
        road_band(X(-2800), Y(sd) - RW, (sw + 5600) * S + RW2, RW)
    if 'E' in side:
        rw = RW2 if road2 else RW
        road_band(X(sw), Y(sd) - top_pad - 24, rw, sd * S + top_pad + 48,
                  rot=True)

    # 敷地
    s.rect(X(0), Y(sd), sw * S, sd * S, fill='#ffffff', stroke='#111',
           stroke_width=2.0)
    s.text(X(sw / 2.0), Y(sd / 2.0) - 6, '敷　地', size=15, weight='700')
    s.text(X(sw / 2.0), Y(sd / 2.0) + 16, '（%s ㎡）' % area, size=12,
           fill='#444')

    # まわりの表示
    if 'E' not in side:
        s.text_rot(X(sw + 1500), Y(sd / 2.0), '隣　地', -90, size=12,
                   fill='#777')
    s.text_rot(X(-1500), Y(sd / 2.0), '隣　地', -90, size=12, fill='#777')
    if 'N' not in side:
        s.text(X(sw / 2.0), Y(sd) - 13, '宅　地', size=12, fill='#777')
    if 'S' not in side:
        s.text(X(sw / 2.0), Y(0) + 20, '宅　地', size=12, fill='#777')

    # 寸法
    s.dim_h(X(0), X(sw), Y(sd) - 34, format(sw, ','))
    dx = X(0) - 44
    s.line(dx, Y(0), dx, Y(sd), stroke='#444', stroke_width=0.8)
    for m in (0, sd):
        s.line(dx - 4, Y(m), dx + 4, Y(m), stroke='#444', stroke_width=0.8)
    s.text_rot(dx - 6, Y(sd / 2.0), format(sd, ','), -90, size=11, fill='#444')

    # 道路の幅員
    rx = X(sw) + (RW2 if 'E' in side and road2 else
                  (RW if 'E' in side else 0)) + 60
    if 'S' in side or 'N' in side:
        yy = Y(0) if 'S' in side else Y(sd) - RW
        s.line(rx, yy, rx, yy + RW, stroke='#444', stroke_width=0.8)
        for y2 in (yy, yy + RW):
            s.line(rx - 4, y2, rx + 4, y2, stroke='#444', stroke_width=0.8)
        s.text_rot(rx - 6, yy + RW / 2.0, format(road, ','), -90, size=11,
                   fill='#444')
    if 'E' in side:
        rw = RW2 if road2 else RW
        yy = Y(sd) - 34
        s.dim_h(X(sw), X(sw) + rw, yy, format(road2 or road, ','))

    # 方位
    nx = X(sw) + (RW2 + 34 if 'E' in side and road2 else
                  (RW + 34 if 'E' in side else 42))
    ny = Y(sd) + 34
    s.line(nx, ny + 26, nx, ny - 12, stroke='#111', stroke_width=1.2)
    s.polygon([(nx, ny - 18), (nx - 5, ny - 4), (nx + 5, ny - 4)], fill='#111')
    s.text(nx, ny + 40, 'N', size=12, weight='700')

    s.text(W / 2.0, H - 18, '敷地図（縮尺：1/500、単位：mm）', size=12,
           fill='#333')
    return s


SITES = {
    'A': dict(sw=12000, sd=15000, road=8000, area='180.00', side='S'),
    'B': dict(sw=14000, sd=16000, road=6000, area='224.00', side='S'),
    'C': dict(sw=9000, sd=20000, road=6000, area='180.00', side='S'),
    'D': dict(sw=15000, sd=12000, road=6000, area='180.00', side='E'),
    'E': dict(sw=13000, sd=14000, road=8000, area='182.00', side='SE',
              road2=6000),
    'F': dict(sw=12000, sd=15000, road=6000, area='180.00', side='N'),
}

if __name__ == '__main__':
    for tag, kw in SITES.items():
        draw(**kw).save(os.path.join(OUT, 'site_%s.svg' % tag))
    draw(**SITES['A']).save(os.path.join(OUT, 'site_map.svg'))
    print('wrote site_A..F.svg')
