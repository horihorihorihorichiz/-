# -*- coding: utf-8 -*-
"""配置図の型：敷地のどこに建物を置くか。"""
import os
from svgkit import Svg

S = 26.0                      # 1m あたりの表示ピクセル
SW, SD = 12.0, 15.0           # 敷地 間口12m × 奥行15m
BW, BD = 7.28, 9.10           # 建物
ROAD = 4.0                    # 図に描く道路の幅
ML, MT = 118, 132
W = int(ML * 2 + SW * S + 90)
H = int(MT + (SD + ROAD) * S + 160)

EW = (SW - BW) / 2.0          # 東西のあき 2.36m
NGAP = 1.00                   # 北の境界からのあき
BY = SD - NGAP - BD           # 建物の南端の位置（南境界から）4.90m


def X(m):
    return ML + m * S


def Y(m):
    """南（道路側）を0として上向きに測る。"""
    return MT + (SD - m) * S


def draw():
    s = Svg(W, H)
    s.text(W / 2.0, 36, '配置図の型　敷地のどこに建物を置くか', size=21,
           weight='700')
    s.text(W / 2.0, 59, '敷地 間口12m × 奥行15m ＝ 180㎡　／　南側に道路',
           size=12, fill='#666')
    s.text(W / 2.0, 79, '建物は北へ寄せる。南の空地が来店スペースになる。',
           size=12, fill='#b03060', weight='700')

    # 道路
    s.rect(X(-1.4), Y(0), (SW + 2.8) * S, ROAD * S, fill='#f0f0ee',
           stroke='none')
    s.line(X(-1.4), Y(0), X(SW + 1.4), Y(0), stroke='#333', stroke_width=2.2)
    s.text(X(SW / 2.0), Y(0) + ROAD * S / 2.0 + 5,
           '道　路（商店街の通り）　幅員 8m', size=12, fill='#777',
           weight='700')

    # 敷地
    s.rect(X(0), Y(SD), SW * S, SD * S, fill='#fbfaf6', stroke='#b03060',
           stroke_width=2.0, stroke_dasharray='11 4 2 4')
    s.text(X(0) - 8, Y(SD) - 8, '敷地境界線', size=11, anchor='start',
           fill='#b03060', weight='700')

    # 建物
    s.rect(X(EW), Y(BY + BD), BW * S, BD * S, fill='#eef3fa',
           stroke='#1f2937', stroke_width=3.0)
    for k in range(1, 8):
        s.line(X(EW + k * 0.91), Y(BY + BD), X(EW + k * 0.91), Y(BY),
               stroke='#dfe5ec', stroke_width=0.7)
    for k in range(1, 10):
        s.line(X(EW), Y(BY + k * 0.91), X(EW + BW), Y(BY + k * 0.91),
               stroke='#dfe5ec', stroke_width=0.7)
    s.text(X(SW / 2.0), Y(BY + BD / 2.0) - 4, '建　物', size=17, weight='700')
    s.text(X(SW / 2.0), Y(BY + BD / 2.0) + 18,
           '7,280 × 9,100 ＝ 66.25㎡', size=12, fill='#555')
    s.text(X(SW / 2.0), Y(BY + BD / 2.0) + 38, '木造3階建て', size=12,
           fill='#555')

    # 店舗出入口・住宅玄関
    s.line(X(EW + 1.82), Y(BY), X(EW + 4.55), Y(BY), stroke='#d0342f',
           stroke_width=6)
    s.text(X(EW + 3.2), Y(BY) + 18, '店舗出入口', size=11, fill='#d0342f',
           weight='700')
    s.line(X(EW + 0.27), Y(BY), X(EW + 1.55), Y(BY), stroke='#d0342f',
           stroke_width=6)
    s.text(X(EW + 0.9), Y(BY) + 36, '住宅玄関', size=11, fill='#d0342f',
           weight='700')

    # 来店スペース／アプローチ
    s.text(X(SW / 2.0 + 1.6), Y(BY / 2.0) + 4, '前面空地（来店スペース）',
           size=12, fill='#8a8f88')

    # 駐輪
    s.rect(X(0.4), Y(2.5), 2.4 * S, 1.9 * S, fill='#eef6ee',
           stroke='#3e6b47', stroke_width=1.4)
    for k in range(4):
        xx = X(0.4 + 0.3 + k * 0.6)
        s.line(xx, Y(2.4) - 6, xx, Y(0.7), stroke='#3e6b47',
               stroke_width=1.6)
        s.circle(xx, Y(0.72), 4, fill='none', stroke='#3e6b47',
                 stroke_width=1.2)
    s.text(X(1.6), Y(2.5) - 8, '駐輪 4台', size=11, fill='#3e6b47',
           weight='700')

    # 住宅へのアプローチ
    s.poly([(X(EW + 0.9), Y(BY) + 4), (X(EW + 0.9), Y(1.2)),
            (X(SW / 2.0), Y(1.2)), (X(SW / 2.0), Y(0.1))],
           stroke='#8b62b5', stroke_width=2.2, stroke_dasharray='7 4')
    s.text(X(SW / 2.0) + 8, Y(1.2) - 8, '住宅へのアプローチ', size=11,
           fill='#8b62b5', weight='700', anchor='start')

    # 寸法
    s.dim_h(X(0), X(EW), Y(SD) - 24, '2,360')
    s.dim_h(X(EW), X(EW + BW), Y(SD) - 24, '7,280')
    s.dim_h(X(EW + BW), X(SW), Y(SD) - 24, '2,360')
    dx = X(SW) + 42
    for a, b, lab in ((SD - NGAP, SD, '1,000'), (BY, BY + BD, '9,100'),
                      (0, BY, '4,900')):
        s.line(dx, Y(a), dx, Y(b), stroke='#444', stroke_width=0.8)
        for m in (a, b):
            s.line(dx - 4, Y(m), dx + 4, Y(m), stroke='#444',
                   stroke_width=0.8)
        s.text_rot(dx - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=10.5,
                   fill='#444')

    # 方位
    nx, ny = X(SW) + 6, MT + 24
    s.circle(nx, ny, 17, fill='#fff', stroke='#444', stroke_width=1.1)
    s.polygon([(nx, ny - 13), (nx - 5, ny + 6), (nx, ny + 2), (nx + 5, ny + 6)],
              fill='#c0392b')
    s.text(nx, ny + 18, 'N', size=10.5, weight='700', fill='#444')

    # まとめ
    ly = MT + (SD + ROAD) * S + 26
    s.rect(30, ly - 18, W - 60, 116, fill='#f6f9f4', stroke='#bcd4bc',
           stroke_width=1, rx=6)
    s.text(46, ly, '外壁から敷地境界線まで：東西 2,360 ／ 北 1,000 '
                   '→ どちらも 500mm以上でOK', size=11.5, anchor='start',
           fill='#245a2c')
    s.text(46, ly + 20, '建蔽率　66.25 ÷ 180 ＝ 36.8%　（限度80%）',
           size=11.5, anchor='start', fill='#245a2c')
    s.text(46, ly + 42, '容積率　まず限度を決める：'
                        '前面道路 8m × 6/10 ＝ 480%　と　都市計画 300%',
           size=11.5, anchor='start', fill='#245a2c')
    s.text(46, ly + 62, '　　　　小さいほうを採るので 限度は 300%。'
                        '198.74 ÷ 180 ＝ 110.4% → OK', size=11.5,
           anchor='start', fill='#245a2c')
    s.text(46, ly + 84, '南に4.9mの空地ができるので、駐輪4台も'
                        '住宅への通路もここに入る。', size=11.5,
           anchor='start', fill='#245a2c')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    draw().save(os.path.join(out, 'site.svg'))
    print('wrote site.svg')
