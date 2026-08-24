# -*- coding: utf-8 -*-
"""型の平面図（1階・2階・3階）をSVGで描く。

910mmを1マスとして、間口8マス(7,280) × 奥行10マス(9,100)。
座標は grid 単位。x は西(0)→東(8)、y は南(0)→北(10)。
南側が道路（商店街）。
"""
import os
from svgkit import Svg

G = 56.0            # 1マス(910mm)あたりの表示ピクセル
ML, MR, MT, MB = 100, 112, 120, 162
NX, NY = 8, 10
W = ML + NX * G + MR
H = MT + NY * G + MB

# 通り符号
XLINES = [(0, 'A'), (2, 'B'), (5, 'C'), (8, 'D')]
YLINES = [(0, '1'), (2, '2'), (6, '3'), (10, '4')]

COLORS = {
    'shop':   ('#ffe6d0', '#c9762f'),
    'living': ('#dce9fb', '#4a76b8'),
    'water':  ('#d5f0e7', '#2f9077'),
    'stair':  ('#fff3c4', '#bb9508'),
    'store':  ('#ececec', '#8a8a8a'),
    'hall':   ('#f1e6fa', '#8b62b5'),
}

TOOSHI = [(0, 0), (8, 0), (0, 10), (8, 10)]                 # 通し柱
KUDA = [(2, 0), (5, 0), (0, 2), (8, 2), (0, 6), (8, 6),
        (2, 10), (5, 10), (2, 2), (5, 2), (2, 6), (5, 6)]   # 管柱

FLOORS = {
    1: dict(
        title='1階平面図 兼 配置図',
        rooms=[
            ('住宅玄関',      '3.31', 0, 0, 2, 2, 'hall'),
            ('階　段',        '6.62', 0, 2, 2, 6, 'stair'),
            ('店舗用便所',    '3.31', 0, 6, 2, 8, 'water'),
            ('倉　庫',        '3.31', 0, 8, 2, 10, 'store'),
            ('店舗売場',      '29.81', 2, 0, 8, 6, 'shop'),
            ('厨房・作業場',  '9.94', 2, 6, 5, 10, 'shop'),
            ('スタッフルーム', '9.94', 5, 6, 8, 10, 'shop'),
        ],
        # 窓・出入口（外壁）: (向き, 位置, 長さ, 種別, ラベル)
        # 向き 'S','N','E','W' / 位置は壁に沿った grid 座標
        openings=[
            ('S', 2.5, 3.0, 'entry', '店舗出入口'),
            ('S', 0.3, 1.4, 'entry', '住宅玄関'),
            ('S', 6.0, 1.5, 'win', ''),
            ('E', 0.5, 1.5, 'win', ''),
            ('E', 3.0, 2.0, 'win', ''),
            ('E', 6.5, 2.5, 'win', ''),
            ('N', 2.5, 2.0, 'entry', '勝手口'),
            ('N', 5.5, 2.0, 'win', ''),
            ('W', 8.4, 1.2, 'win', ''),
        ],
        # 室内の建具（開口）: (向き, 壁の位置, 沿い座標, 長さ)
        doors=[
            ('H', 2, 0.4, 1.2),   # 玄関 → 階段
            ('V', 2, 3.2, 1.0),   # 階段 → 売場（竪穴区画：防火設備）
            ('H', 6, 3.0, 1.6),   # 売場 → 厨房
            ('V', 2, 6.5, 1.0),   # 厨房 → 店舗用便所
            ('V', 2, 8.5, 1.0),   # 厨房 → 倉庫
            ('V', 5, 7.5, 1.2),   # 厨房 → スタッフルーム
        ],
        note='南＝商店街の通り。売場を道路に面して最大に取る。',
        stair_up='UP 15段（蹴上206.7 / 踏面210）',
    ),
    2: dict(
        title='2階平面図',
        rooms=[
            ('便　所',            '3.31', 0, 0, 2, 2, 'water'),
            ('階　段',            '6.62', 0, 2, 2, 6, 'stair'),
            ('洗面脱衣室',        '3.31', 0, 6, 2, 8, 'water'),
            ('浴　室',            '3.31', 0, 8, 2, 10, 'water'),
            ('居間・食事室・台所', '29.81', 2, 0, 8, 6, 'living'),
            ('和室 6帖',          '9.94', 2, 6, 5, 10, 'living'),
            ('家事室・納戸',      '9.94', 5, 6, 8, 10, 'store'),
        ],
        openings=[
            ('S', 2.5, 3.0, 'balc', 'バルコニー'),
            ('S', 6.2, 1.5, 'win', ''),
            ('S', 0.4, 1.2, 'win', ''),
            ('E', 0.5, 1.5, 'win', ''),
            ('E', 3.0, 2.0, 'win', ''),
            ('E', 6.5, 2.5, 'win', ''),
            ('N', 2.6, 2.0, 'win', ''),
            ('N', 5.6, 1.8, 'win', ''),
            ('W', 0.4, 1.2, 'win', ''),
            ('W', 6.4, 1.2, 'win', ''),
            ('W', 8.4, 1.2, 'win', ''),
        ],
        doors=[
            ('H', 2, 0.4, 1.2),   # 便所 → 階段ホール
            ('V', 2, 3.2, 1.0),   # 階段ホール → 居間
            ('H', 6, 0.4, 1.2),   # 階段ホール → 洗面脱衣室
            ('H', 8, 0.4, 1.2),   # 洗面脱衣室 → 浴室
            ('H', 6, 3.0, 2.0),   # 居間 → 和室（引込み戸）
            ('V', 5, 7.5, 1.2),   # 和室 → 家事室・納戸
        ],
        note='水まわりを西側にまとめて、1階・3階と配管の位置をそろえる。',
        stair_up='UP 14段（蹴上207.1 / 踏面210）',
    ),
    3: dict(
        title='3階平面図',
        rooms=[
            ('便　所',   '3.31', 0, 0, 2, 2, 'water'),
            ('階　段',   '6.62', 0, 2, 2, 6, 'stair'),
            ('納　戸',   '6.62', 0, 6, 2, 10, 'store'),
            ('子供室A',  '12.42', 2, 0, 5, 5, 'living'),
            ('子供室B',  '12.42', 5, 0, 8, 5, 'living'),
            ('廊　下',   '4.97', 2, 5, 8, 6, 'hall'),
            ('夫婦寝室', '19.87', 2, 6, 8, 10, 'living'),
        ],
        openings=[
            ('S', 2.6, 1.8, 'win', ''),
            ('S', 5.6, 1.8, 'win', ''),
            ('S', 0.4, 1.2, 'win', ''),
            ('E', 1.0, 2.5, 'win', ''),
            ('E', 7.0, 2.0, 'win', ''),
            ('N', 2.6, 2.2, 'win', ''),
            ('N', 5.6, 2.2, 'win', ''),
            ('W', 1.0, 2.5, 'win', ''),
            ('W', 7.0, 2.0, 'win', ''),
        ],
        doors=[
            ('H', 2, 0.4, 1.2),   # 便所 → 階段ホール
            ('V', 2, 5.2, 0.8),   # 階段ホール → 廊下
            ('H', 6, 0.4, 1.2),   # 階段ホール → 納戸
            ('H', 5, 3.0, 1.0),   # 廊下 → 子供室A
            ('H', 5, 6.0, 1.0),   # 廊下 → 子供室B
            ('H', 6, 4.0, 1.0),   # 廊下 → 夫婦寝室
        ],
        note='廊下を東西に1本通して、階段から全部屋へ行けるようにする。',
        stair_up='DN（下り）',
    ),
}


def draw_floor(n, d=None):
    """d に nx / ny / xlines / ylines / tooshi / kuda を入れるとマス数を変えられる。"""
    d = d or FLOORS[n]
    nx = d.get('nx', NX)
    ny = d.get('ny', NY)
    xlines = d.get('xlines', XLINES)
    ylines = d.get('ylines', YLINES)
    tooshi = d.get('tooshi', TOOSHI)
    kuda = d.get('kuda', KUDA)
    side = d.get('road_side', 'S')          # 'S' 'E' 'N' 'W' 'SE' など
    top_pad = 62 if 'N' in side else 0
    MTd = MT + top_pad
    W = ML + nx * G + MR
    H = MTd + ny * G + MB

    def px(gx):
        return ML + gx * G

    def py(gy):
        return MTd + (ny - gy) * G

    s = Svg(W, H)

    # ---- タイトル ----
    s.text(W / 2.0, 36, d['title'], size=21, weight='700')
    area = nx * ny * 0.8281
    s.text(W / 2.0, 60,
           '1マス = 910mm ／ 間口 %s × 奥行 %s ／ 床面積 %.2f㎡'
           % (format(nx * 910, ','), format(ny * 910, ','), area),
           size=12, fill='#666')

    x0, y0, x1, y1 = px(0), py(ny), px(nx), py(0)

    # ---- 910グリッド ----
    for i in range(nx + 1):
        s.line(px(i), y0, px(i), y1, stroke='#e8e8e8', stroke_width=0.7)
    for j in range(ny + 1):
        s.line(x0, py(j), x1, py(j), stroke='#e8e8e8', stroke_width=0.7)

    # ---- 部屋 ----
    for name, ar, a, b, c, e, kind in d['rooms']:
        fill, edge = COLORS[kind]
        s.rect(px(a), py(e), (c - a) * G, (e - b) * G, fill=fill,
               stroke=edge, stroke_width=1.2, opacity='0.95')
        cx = (px(a) + px(c)) / 2.0
        cy = (py(b) + py(e)) / 2.0
        big = (c - a) >= 5
        s.text(cx, cy - 2, name, size=16 if big else 13, weight='700',
               fill='#1a1a1a')
        s.text(cx, cy + (17 if big else 15), ar + ' ㎡',
               size=12 if big else 11, fill='#555')

    # ---- 通り芯 ----
    for gx, _ in xlines:
        s.line(px(gx), y0 - 18, px(gx), y1 + 26, stroke='#b03060',
               stroke_width=0.9, stroke_dasharray='9 3 2 3', opacity='0.55')
    for gy, _ in ylines:
        s.line(x0 - 18, py(gy), x1 + 26, py(gy), stroke='#b03060',
               stroke_width=0.9, stroke_dasharray='9 3 2 3', opacity='0.55')

    # ---- 外周の壁 ----
    s.rect(px(0), py(ny), nx * G, ny * G, stroke='#111', stroke_width=3.4)

    # ---- 開口部（窓・出入口） ----
    for face, pos, ln, kind, label in d['openings']:
        col = {'win': '#2f7fd0', 'entry': '#d0342f', 'balc': '#2f7fd0'}[kind]
        if face in ('S', 'N'):
            xa, xb = px(pos), px(pos + ln)
            yy = py(0) if face == 'S' else py(ny)
            s.line(xa, yy, xb, yy, stroke='#ffffff', stroke_width=4.2)
            s.line(xa, yy, xb, yy, stroke=col, stroke_width=5.0)
            if label:
                s.text((xa + xb) / 2.0, yy + (20 if face == 'S' else -10),
                       label, size=11, fill=col, weight='700')
        else:
            ya, yb = py(pos), py(pos + ln)
            xx = px(nx) if face == 'E' else px(0)
            s.line(xx, ya, xx, yb, stroke='#ffffff', stroke_width=4.2)
            s.line(xx, ya, xx, yb, stroke=col, stroke_width=5.0)

    # ---- 室内の間仕切り壁 ----
    walls = set()
    for _, _, a, b, c, e, _ in d['rooms']:
        walls.add(('V', a, b, e))
        walls.add(('V', c, b, e))
        walls.add(('H', b, a, c))
        walls.add(('H', e, a, c))
    for w in walls:
        if w[0] == 'V':
            _, gx, ga, gb = w
            if gx in (0, nx):
                continue
            s.line(px(gx), py(ga), px(gx), py(gb), stroke='#111',
                   stroke_width=2.0)
        else:
            _, gy, ga, gb = w
            if gy in (0, ny):
                continue
            s.line(px(ga), py(gy), px(gb), py(gy), stroke='#111',
                   stroke_width=2.0)

    # ---- 室内建具 ----
    for ori, wall, pos, ln in d['doors']:
        r = min(ln * G * 0.72, G * 0.82)
        slide = ln >= 1.5
        if ori == 'V':
            xx, ya, yb = px(wall), py(pos), py(pos + ln)
            s.line(xx, ya, xx, yb, stroke='#ffffff', stroke_width=3.4)
            if slide:
                s.line(xx - 2, ya, xx - 2, yb, stroke='#777', stroke_width=1.0)
                s.line(xx + 2, ya, xx + 2, yb, stroke='#777', stroke_width=1.0)
            else:
                s.line(xx, ya, xx + r, ya, stroke='#777', stroke_width=0.9)
                s.path('M %.1f %.1f A %.1f %.1f 0 0 1 %.1f %.1f'
                       % (xx + r, ya, r, r, xx, ya - r),
                       stroke='#aaa', stroke_width=0.8)
        else:
            yy, xa, xb = py(wall), px(pos), px(pos + ln)
            s.line(xa, yy, xb, yy, stroke='#ffffff', stroke_width=3.4)
            if slide:
                s.line(xa, yy - 2, xb, yy - 2, stroke='#777', stroke_width=1.0)
                s.line(xa, yy + 2, xb, yy + 2, stroke='#777', stroke_width=1.0)
            else:
                s.line(xa, yy, xa, yy + r, stroke='#777', stroke_width=0.9)
                s.path('M %.1f %.1f A %.1f %.1f 0 0 1 %.1f %.1f'
                       % (xa, yy + r, r, r, xa + r, yy),
                       stroke='#aaa', stroke_width=0.8)

    # ---- 竪穴区画（階段室） ----
    sa, sb, sc, sd = d.get('stair_box', (0, 2, 2, 6))
    s.rect(px(sa) + 4, py(sd) + 4, (sc - sa) * G - 8, (sd - sb) * G - 8,
           fill='none', stroke='#c0392b', stroke_width=1.6,
           stroke_dasharray='6 4')

    # ---- 階段（折り返し） ----
    mid = px((sa + sc) / 2.0)
    top = sd - 1
    s.line(mid, py(sb), mid, py(top), stroke='#8a6d00', stroke_width=1.6)
    for k in range(1, 8):
        yy = py(sb) - k * (py(sb) - py(top)) / 8.0
        s.line(px(sa) + 3, yy, mid, yy, stroke='#8a6d00', stroke_width=0.9)
        s.line(mid, yy, px(sc) - 3, yy, stroke='#8a6d00', stroke_width=0.9)
    s.line(px(sa) + 3, py(top), px(sc) - 3, py(top), stroke='#8a6d00',
           stroke_width=1.6)
    s.text(mid, py(top + 0.55), '踊り場', size=10, fill='#8a6d00')
    s.line(px(sa + 0.5), py(sb + 0.3), px(sa + 0.5), py(top - 0.1),
           stroke='#8a6d00', stroke_width=1.6)
    s.polygon([(px(sa + 0.5), py(top + 0.15)),
               (px(sa + 0.5) - 5, py(top - 0.15)),
               (px(sa + 0.5) + 5, py(top - 0.15))], fill='#8a6d00')
    s.text(px(sc - 0.5), py(sb + 0.55), 'UP', size=12, fill='#8a6d00',
           weight='700')

    # ---- 柱 ----
    for gx, gy in kuda:
        s.rect(px(gx) - 4, py(gy) - 4, 8, 8, fill='#111')
    for gx, gy in tooshi:
        s.circle(px(gx), py(gy), 8, fill='#ffffff', stroke='#c0392b',
                 stroke_width=2.4)
        s.circle(px(gx), py(gy), 4, fill='#c0392b')

    # ---- 通り符号 ----
    for gx, nm in xlines:
        s.circle(px(gx), y0 - 36, 11, fill='#ffffff', stroke='#b03060',
                 stroke_width=1.2)
        s.text(px(gx), y0 - 32, nm, size=12, weight='700', fill='#b03060')
    for gy, nm in ylines:
        s.circle(x0 - 40, py(gy), 11, fill='#ffffff', stroke='#b03060',
                 stroke_width=1.2)
        s.text(x0 - 40, py(gy) + 4, nm, size=12, weight='700', fill='#b03060')

    # ---- 寸法 ----
    s.dim_h(px(0), px(nx), y1 + 52,
            '%s  ( 910 × %dマス )' % (format(nx * 910, ','), nx))
    s.line(x1 + 46, py(0), x1 + 46, py(ny), stroke='#444', stroke_width=0.8)
    for gy in (0, ny):
        s.line(x1 + 42, py(gy), x1 + 50, py(gy), stroke='#444',
               stroke_width=0.8)
    s.text_rot(x1 + 40, (y0 + y1) / 2.0,
               '%s  ( 910 × %dマス )' % (format(ny * 910, ','), ny), size=11,
               fill='#444')

    # ---- 方位 ----
    nxp = (x0 - 72) if 'E' in side else (W - 46)
    nyp = MTd + 26
    s.circle(nxp, nyp, 19, fill='#ffffff', stroke='#444', stroke_width=1.1)
    s.polygon([(nxp, nyp - 14), (nxp - 6, nyp + 7), (nxp, nyp + 2),
               (nxp + 6, nyp + 7)], fill='#c0392b')
    s.text(nxp, nyp + 19, 'N', size=11, weight='700', fill='#444')

    # ---- 道路 ----
    ry = y1 + 60

    def road_band(x, y, w, h, label, rot=False):
        s.rect(x, y, w, h, fill='#f2f2f2', stroke='#bbb', stroke_width=0.8)
        if rot:
            s.text_rot(x + w / 2.0 + 4, y + h / 2.0, label, -90, size=12,
                       fill='#666', weight='700')
        else:
            s.text(x + w / 2.0, y + h / 2.0 + 4, label, size=12, fill='#666',
                   weight='700')

    if 'S' in side:
        road_band(px(-0.6), ry, (nx + 1.2) * G, 26, '道　路（南）')
    if 'N' in side:
        road_band(px(-0.6), y0 - 88, (nx + 1.2) * G, 26, '道　路（北）')
    if 'E' in side:
        road_band(x1 + 64, py(ny + 0.4), 26, (ny + 0.8) * G, '道　路（東）',
                  rot=True)
    if 'W' in side:
        road_band(x0 - 90, py(ny + 0.4), 26, (ny + 0.8) * G, '道　路（西）',
                  rot=True)

    # ---- 凡例 ----
    ly = ry + 56
    s.circle(ML + 8, ly - 4, 7, fill='#ffffff', stroke='#c0392b',
             stroke_width=2.0)
    s.circle(ML + 8, ly - 4, 3.5, fill='#c0392b')
    s.text(ML + 20, ly, '通し柱 120角', size=11, anchor='start', fill='#444')
    s.rect(ML + 116, ly - 8, 8, 8, fill='#111')
    s.text(ML + 130, ly, '管柱 105角', size=11, anchor='start', fill='#444')
    s.line(ML + 216, ly - 4, ML + 238, ly - 4, stroke='#2f7fd0',
           stroke_width=5)
    s.text(ML + 244, ly, '窓', size=11, anchor='start', fill='#444')
    s.line(ML + 272, ly - 4, ML + 294, ly - 4, stroke='#d0342f',
           stroke_width=5)
    s.text(ML + 300, ly, '出入口', size=11, anchor='start', fill='#444')
    s.rect(ML + 352, ly - 9, 20, 10, fill='none', stroke='#c0392b',
           stroke_width=1.4, stroke_dasharray='4 3')
    s.text(ML + 378, ly, '竪穴区画', size=11, anchor='start', fill='#444')

    s.text(W / 2.0, ly + 28, d['note'] + '　／　階段 ' + d['stair_up'],
           size=11.5, fill='#555')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    for n in (1, 2, 3):
        p = os.path.join(out, 'plan%df.svg' % n)
        draw_floor(n).save(p)
        print('wrote', os.path.normpath(p))
