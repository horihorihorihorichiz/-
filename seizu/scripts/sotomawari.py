# -*- coding: utf-8 -*-
"""外まわり（配置図）のずかん。

1階平面図兼配置図には、建物のほかに「屋外施設等」を描く。
何をどれだけの大きさで描くのか、どこに置くのかを図にする。

寸法の根拠：
  ・駐輪／駐車／門／塀／植栽 … 実務でふつうに使われる大きさ
  ・ゴミ置き場 2,000×1,000 … 令和7年の問題用紙が指定した実際の値
  ・敷地内通路 1.5m（延べ200㎡未満は90cm）… 令128条
出力：
  figures/soto_sizes.svg   外まわりの必要寸法（9つ）
  figures/soto_haichi.svg  外まわりの配置例（型の敷地）
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
INK = '#111'
ACC = '#b03060'
GREEN = '#3e6b47'
BLUE = '#1f6fb2'
GRAY = '#8a8a8a'
K = 26.0                       # 1m → px（寸法ずかん用）


def card(s, x, y, w, h, no, title, sub):
    s.rect(x, y, w, h, fill='#fcfcfb', stroke='#e0ded8', stroke_width=1.0,
           rx=10)
    s.circle(x + 24, y + 24, 12, fill=ACC)
    s.text(x + 24, y + 28.5, str(no), size=12.5, weight='700', fill='#fff')
    s.text(x + 44, y + 29, title, size=14.5, anchor='start', weight='700')
    s.text(x + 44, y + 47, sub, size=11, anchor='start', fill='#888')


def bike(s, cx, cy, r=5.2):
    """自転車の記号（車輪2つ）。"""
    s.circle(cx, cy - r * 1.9, r, fill='none', stroke=GREEN,
             stroke_width=1.2)
    s.circle(cx, cy + r * 1.9, r, fill='none', stroke=GREEN,
             stroke_width=1.2)
    s.line(cx, cy - r * 1.9, cx, cy + r * 1.9, stroke=GREEN,
           stroke_width=1.2)


def car(s, x, y, w, h, col=BLUE):
    """車の記号（上から見た形）。"""
    s.rect(x, y, w, h, fill='none', stroke=col, stroke_width=1.6, rx=5)
    s.rect(x + w * 0.16, y + h * 0.12, w * 0.68, h * 0.22, fill='none',
           stroke=col, stroke_width=1.0, rx=3)
    s.rect(x + w * 0.16, y + h * 0.62, w * 0.68, h * 0.26, fill='none',
           stroke=col, stroke_width=1.0, rx=3)


def tree(s, cx, cy, r, tall=True):
    if tall:
        s.circle(cx, cy, r, fill='none', stroke=GREEN, stroke_width=1.4)
        s.circle(cx, cy, r * 0.45, fill='none', stroke=GREEN,
                 stroke_width=1.0)
    else:
        s.circle(cx, cy, r, fill='none', stroke=GREEN, stroke_width=1.2,
                 stroke_dasharray='4 3')


# ==================================================== 図1：必要寸法
def sizes():
    W, H = 1240, 836
    s = Svg(W, H)
    s.text(W / 2.0, 40, '外まわりずかん ①　いるものと、その大きさ', size=22,
           weight='700')
    s.text(W / 2.0, 66,
           '1階平面図兼配置図には、建物のほかに「屋外施設等」を描く。'
           'この9つの大きさを覚えておけば迷わない。',
           size=12.5, fill='#666')

    CW, CH = 386.0, 216.0
    GX, GY = 20.0, 92.0

    def pos(i):
        return GX + (i % 3) * (CW + 14), GY + (i // 3) * (CH + 14)

    # ---- 1 駐輪スペース
    x, y = pos(0)
    card(s, x, y, CW, CH, 1, '駐輪スペース', '自転車1台 600 × 1,900')
    bx, by = x + 40, y + 74
    s.rect(bx, by, 2.4 * K, 1.9 * K, fill='#f2f8f3', stroke=GREEN,
           stroke_width=1.4)
    for i in range(4):
        bike(s, bx + (i + 0.5) * 0.6 * K, by + 0.95 * K)
    s.dim_h(bx, bx + 2.4 * K, by - 10, '2,400（4台）', size=10.5)
    s.dim_v(by, by + 1.9 * K, bx - 12, '1,900', size=10.5)
    s.text(x + 44, y + 190, '4台で 2,400×1,900。マスなら 約2.6×2.1マス',
           size=11.5, anchor='start', fill='#444')

    # ---- 2 駐車スペース（普通車）
    x, y = pos(1)
    card(s, x, y, CW, CH, 2, '駐車スペース（普通車）', '1台 2,500 × 5,000')
    cx0, cy0 = x + 46, y + 62
    s.rect(cx0, cy0, 2.5 * K, 5.0 * K, fill='#eef4fa', stroke=BLUE,
           stroke_width=1.4)
    car(s, cx0 + 8, cy0 + 10, 2.5 * K - 16, 5.0 * K - 20)
    s.dim_h(cx0, cx0 + 2.5 * K, cy0 - 10, '2,500', size=10.5)
    s.text(cx0 + 2.5 * K + 14, cy0 + 2.5 * K, '5,000', size=10.5,
           anchor='start', fill='#444')
    s.text(x + 200, y + 108, 'マスなら 約2.7×5.5マス。', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 200, y + 128, '型の敷地（東西のあき2.36m）', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 200, y + 148, 'には入らない。要求されたら', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 200, y + 168, '南のあき（4.9m）に置く。', size=11.5,
           anchor='start', fill=ACC, weight='700')

    # ---- 3 駐車スペース（軽自動車）
    x, y = pos(2)
    card(s, x, y, CW, CH, 3, '駐車スペース（軽自動車）', '1台 2,000 × 3,600')
    cx0, cy0 = x + 46, y + 76
    s.rect(cx0, cy0, 2.0 * K, 3.6 * K, fill='#eef4fa', stroke=BLUE,
           stroke_width=1.4)
    car(s, cx0 + 7, cy0 + 8, 2.0 * K - 14, 3.6 * K - 16)
    s.dim_h(cx0, cx0 + 2.0 * K, cy0 - 10, '2,000', size=10.5)
    s.text(cx0 + 2.0 * K + 14, cy0 + 1.8 * K, '3,600', size=10.5,
           anchor='start', fill='#444')
    s.text(x + 176, y + 112, '「軽自動車1台」と指定', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 176, y + 132, 'されたら、こちらの', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 176, y + 152, '小さいほうでよい。', size=11.5,
           anchor='start', fill='#444')

    # ---- 4 ゴミ置き場
    x, y = pos(3)
    card(s, x, y, CW, CH, 4, 'ゴミ置き場', 'ゴミ収納庫 2,000 × 1,000')
    gx, gy = x + 46, y + 96
    s.rect(gx, gy, 2.0 * K, 1.0 * K, fill='#f6f4ef', stroke=GRAY,
           stroke_width=1.4)
    s.line(gx, gy, gx + 2.0 * K, gy + 1.0 * K, stroke=GRAY,
           stroke_width=0.8)
    s.line(gx, gy + 1.0 * K, gx + 2.0 * K, gy, stroke=GRAY,
           stroke_width=0.8)
    s.text(gx + 1.0 * K, gy + 1.0 * K + 18, 'ゴミ置き場', size=10.5,
           fill='#666')
    s.dim_h(gx, gx + 2.0 * K, gy - 10, '2,000', size=10.5)
    s.text(x + 190, y + 96, '令和7年の問題用紙が', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 190, y + 116, '実際に指定した大きさ。', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 190, y + 140, '道路から出しやすく、', size=11.5,
           anchor='start', fill=ACC, weight='700')
    s.text(x + 190, y + 160, '出入口から離した所へ。', size=11.5,
           anchor='start', fill=ACC, weight='700')

    # ---- 5 アプローチ
    x, y = pos(4)
    card(s, x, y, CW, CH, 5, 'アプローチ', '道路から玄関までの道')
    ax0, ay0 = x + 60, y + 76
    s.rect(ax0, ay0, 1.2 * K, 3.4 * K, fill='#faf6ee', stroke='#c9a227',
           stroke_width=1.4)
    for i in range(5):
        s.line(ax0, ay0 + (i + 1) * 0.55 * K, ax0 + 1.2 * K,
               ay0 + (i + 1) * 0.55 * K, stroke='#d9be6a', stroke_width=0.9)
    s.dim_h(ax0, ax0 + 1.2 * K, ay0 - 10, '1,200', size=10.5)
    s.text(x + 130, y + 96, '幅 900〜1,200 あればよい。', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 130, y + 116, '玄関ポーチは床面積に', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 130, y + 136, '算入しない。', size=11.5, anchor='start',
           fill='#444')
    s.text(x + 130, y + 164, '道路との出入口に▲印。', size=11.5,
           anchor='start', fill=ACC, weight='700')

    # ---- 6 敷地内の通路
    x, y = pos(5)
    card(s, x, y, CW, CH, 6, '敷地内の通路', '令128条。避難のための道')
    tx0, ty0 = x + 52, y + 84
    s.rect(tx0, ty0, 1.5 * K, 3.0 * K, fill='#fdeeee', stroke=ACC,
           stroke_width=1.4)
    s.dim_h(tx0, tx0 + 1.5 * K, ty0 - 10, '1,500', size=10.5)
    s.text(x + 128, y + 100, '屋外への出口から道路まで、', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 128, y + 120, '有効幅 1.5m 以上。', size=11.5,
           anchor='start', weight='700', fill='#444')
    s.text(x + 128, y + 146, 'ただし延べ面積200㎡未満', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 128, y + 166, 'なら 90cm でよい。', size=11.5,
           anchor='start', fill='#444')

    # ---- 7 門
    x, y = pos(6)
    card(s, x, y, CW, CH, 7, '門', '柱2本。開き戸は描かなくてよい')
    mx, my = x + 70, y + 110
    for dx in (0, 1.2 * K):
        s.rect(mx + dx - 5, my - 5, 10, 10, fill=INK)
    s.line(mx, my, mx + 1.2 * K, my, stroke=INK, stroke_width=1.0,
           stroke_dasharray='5 4')
    s.dim_h(mx, mx + 1.2 * K, my - 20, '1,200', size=10.5)
    s.text(mx, my + 28, '門', size=11, anchor='start')
    s.text(x + 160, y + 104, 'アプローチの入口に置く。', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 160, y + 124, '住宅の玄関の正面だけでよい。', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 160, y + 148, '店舗の前には置かない', size=11.5,
           anchor='start', fill=ACC, weight='700')
    s.text(x + 160, y + 168, '（客が入れなくなる）。', size=11.5,
           anchor='start', fill=ACC, weight='700')

    # ---- 8 塀
    x, y = pos(7)
    card(s, x, y, CW, CH, 8, '塀', '高さ 1,200 くらい')
    hx, hy = x + 46, y + 104
    s.line(hx, hy, hx + 3.4 * K, hy, stroke=INK, stroke_width=3.4)
    s.text(hx, hy + 20, '平面では「太い1本線」', size=11, anchor='start',
           fill='#666')
    s.text(x + 46, y + 150, '道路に面していない3辺に', size=11.5,
           anchor='start', fill='#444')
    s.text(x + 46, y + 170, '引く。「塀 H=1,200」と注記。', size=11.5,
           anchor='start', fill='#444')

    # ---- 9 植栽
    x, y = pos(8)
    card(s, x, y, CW, CH, 9, '植栽', '高木と低木')
    tree(s, x + 76, y + 112, 20)
    s.text(x + 76, y + 150, '高木（直径3m くらい）', size=10.5, fill='#666')
    for i in range(3):
        tree(s, x + 200 + i * 30, y + 112, 11, tall=False)
    s.text(x + 230, y + 150, '低木（1m くらい）', size=10.5, fill='#666')
    s.text(x + 46, y + 182, '空いたところに置く。数は問われない。',
           size=11.5, anchor='start', fill='#444')

    s.text(W / 2.0, H - 26,
           '★ 駐輪スペース・玄関ポーチ・バルコニーは、床面積に算入しない。'
           '面積表の数字は変わらない。',
           size=13, weight='700', fill='#333')
    return s


# ==================================================== 図2：配置例
def haichi():
    W, H = 1240, 900
    s = Svg(W, H)
    s.text(W / 2.0, 40, '外まわりずかん ②　型の敷地に置いてみる', size=22,
           weight='700')
    s.text(W / 2.0, 66,
           '敷地 12m × 15m ＝ 180㎡、南側に道路。'
           '建物を北へ寄せると、南に4.9mの空地ができる。ここが外まわりの場所。',
           size=12.5, fill='#666')

    M = 40.0                       # 1m → px
    OX, OY = 60.0, 108.0
    SW, SD = 12.0, 15.0
    BW, BD = 7.28, 9.10
    EW = (SW - BW) / 2.0           # 2.36
    NG = 1.00
    BY = SD - NG - BD              # 4.90（南の境界から建物までのあき）

    def X(m):
        return OX + m * M

    def Y(m):
        return OY + (SD - m) * M

    # 道路
    s.rect(X(-1.0), Y(0), (SW + 2.0) * M, 88, fill='#f0f0ee', stroke='none')
    s.line(X(-1.0), Y(0), X(SW + 1.0), Y(0), stroke='#333', stroke_width=2.2)
    s.text(X(SW / 2.0), Y(0) + 52, '道　路（幅員 8,000）', size=13,
           fill='#777', weight='700')

    # 敷地
    s.rect(X(0), Y(SD), SW * M, SD * M, fill='#fbfaf6', stroke=ACC,
           stroke_width=1.8, stroke_dasharray='11 4 2 4')
    s.text(X(0) + 4, Y(SD) - 8, '敷地境界線', size=11, anchor='start',
           fill=ACC, weight='700')

    # 建物
    s.rect(X(EW), Y(BY + BD), BW * M, BD * M, fill='#eef3fa', stroke=INK,
           stroke_width=3.0)
    s.text(X(SW / 2.0), Y(BY + BD / 2.0), '建　物', size=17, weight='700')
    s.text(X(SW / 2.0), Y(BY + BD / 2.0) + 22, '7,280 × 9,100', size=12,
           fill='#666')

    # 境界線からの距離
    s.dim_h(X(0), X(EW), Y(BY + BD - 0.7), '2,360', size=10.5)
    s.dim_h(X(EW + BW), X(SW), Y(BY + BD - 0.7), '2,360', size=10.5)
    s.dim_v(Y(SD), Y(BY + BD), X(SW / 2.0), '1,000', size=10.5,
            anchor='middle', dx=0)
    s.dim_v(Y(BY), Y(0), X(SW - 0.5), '4,900', size=10.5,
            anchor='middle', dx=0)

    # 住宅玄関のアプローチと門（西より）
    ax = EW + 0.8
    s.rect(X(ax), Y(BY), 1.2 * M, BY * M, fill='#faf6ee', stroke='#c9a227',
           stroke_width=1.4)
    s.text(X(ax) + 6, Y(BY / 2.0), 'アプローチ', size=11, anchor='start',
           fill='#a8801c', weight='700')
    for dx in (0, 1.2):
        s.rect(X(ax + dx) - 5, Y(0.4) - 5, 10, 10, fill=INK)
    s.text(X(ax + 0.6), Y(0.4) - 14, '門', size=11, weight='700')

    # 駐輪スペース（店舗の前・東より）
    bx0, by0 = EW + 3.6, 1.4
    s.rect(X(bx0), Y(by0 + 1.9), 2.4 * M, 1.9 * M, fill='#f2f8f3',
           stroke=GREEN, stroke_width=1.4)
    for i in range(4):
        bike(s, X(bx0 + (i + 0.5) * 0.6), Y(by0 + 0.95), r=6.0)
    s.text(X(bx0 + 1.2), Y(by0 + 1.9) - 8, '駐輪スペース（4台）', size=11,
           fill=GREEN, weight='700')
    s.dim_h(X(bx0), X(bx0 + 2.4), Y(by0) + 16, '2,400', size=10)

    # ゴミ置き場（東のあき・道路寄り）
    gx0, gy0 = SW - 1.2, 1.2
    s.rect(X(gx0 - 1.0), Y(gy0 + 2.0), 1.0 * M, 2.0 * M, fill='#f6f4ef',
           stroke=GRAY, stroke_width=1.4)
    s.line(X(gx0 - 1.0), Y(gy0 + 2.0), X(gx0), Y(gy0), stroke=GRAY,
           stroke_width=0.8)
    s.line(X(gx0 - 1.0), Y(gy0), X(gx0), Y(gy0 + 2.0), stroke=GRAY,
           stroke_width=0.8)
    s.text(X(gx0 - 0.5), Y(gy0 + 2.0) - 8, 'ゴミ置き場', size=10.5,
           fill='#666', weight='700')
    s.text(X(gx0 - 0.5), Y(gy0) + 16, '2,000×1,000', size=9.5,
           fill='#888')

    # 塀（道路に面していない3辺）
    for a, b in (((0, 0), (0, SD)), ((0, SD), (SW, SD)),
                 ((SW, SD), (SW, 0))):
        s.line(X(a[0]), Y(a[1]), X(b[0]), Y(b[1]), stroke=INK,
               stroke_width=3.4)
    s.text(X(0) + 10, Y(SD / 2.0), '塀 H=1,200', size=11, anchor='start',
           fill='#444')

    # 植栽
    for m in (2.0, 4.2):
        tree(s, X(EW - 1.1), Y(BY + m), 16)
    for i in range(3):
        tree(s, X(EW + BW + 0.5 + i * 0.5), Y(BY + 0.6), 9, tall=False)
    s.text(X(EW - 1.1), Y(BY + 5.6), '植栽', size=10.5, fill=GREEN,
           weight='700')

    # ▲印（道路から敷地・建築物への出入口）
    def tri(x, y, lab):
        s.polygon([(x, y - 9), (x - 8, y + 6), (x + 8, y + 6)], fill=INK)
        s.text(x + 14, y + 5, lab, size=10.5, anchor='start', weight='700')

    tri(X(ax + 0.6), Y(0) - 2, '▲ 道路から敷地へ')
    tri(X(ax + 0.6), Y(BY) + 12, '▲ 建築物へ（住宅玄関）')
    tri(X(bx0 + 1.9), Y(BY) + 12, '▲ 店舗出入口')

    # ---------------------------------------- 右：書きこむもの
    LX = 700.0
    s.rect(LX - 16, 100, W - LX - 4, 700, fill='#fcfcfb', stroke='#e0ded8',
           stroke_width=1.0, rx=10)
    s.text(LX, 132, '配置図に「文字で」書きこむもの', size=15,
           anchor='start', weight='700')
    ROWS = (('敷地境界線と建築物との距離',
             '2,360 ／ 2,360 ／ 1,000 ／ 4,900'),
            ('道路の幅員', '道路（幅員 8,000）'),
            ('▲印', '道路から敷地へ／建築物への出入口すべて'),
            ('アプローチ', '道路から玄関までの道すじ'),
            ('駐輪スペース', '「駐輪スペース（4台）」と台数まで'),
            ('ゴミ置き場', '要求されたら必ず。2,000×1,000'),
            ('門・塀・植栽', '塀は「H=1,200」と高さも'),
            ('玄関の土間の高さ', '「GL+150」など、地盤面からの高さ'),
            ('玄関ホールの床高', '「GL+550」'),
            ('方位（N）', '敷地図と同じ向きに'))
    for i, (a, b) in enumerate(ROWS):
        yy = 168 + i * 46
        s.line(LX, yy + 22, W - 24, yy + 22, stroke='#eee', stroke_width=0.8)
        s.circle(LX + 8, yy - 4, 8, fill='#f3efe7', stroke='none')
        s.text(LX + 8, yy, str(i + 1), size=10.5, weight='700',
               fill='#7a6a4a')
        s.text(LX + 26, yy, a, size=12.5, anchor='start', weight='700')
        s.text(LX + 26, yy + 17, b, size=11.5, anchor='start', fill='#777')

    s.rect(LX - 16, 640, W - LX - 4, 76, fill='#fdeeee', stroke='#e0a0a0',
           stroke_width=1.0, rx=8)
    s.text(LX, 666, '★ 店舗の前に門・塀を置かない', size=12.5,
           anchor='start', weight='700', fill=ACC)
    s.text(LX, 688, '客が入れなくなる。門は住宅の玄関の正面だけ。',
           size=11.5, anchor='start', fill='#8a3a3a')
    s.text(LX, 706, '店舗の前は開けて、駐輪スペースを置く。',
           size=11.5, anchor='start', fill='#8a3a3a')

    s.rect(LX - 16, 726, W - LX - 4, 62, fill='#f1f8f2', stroke='#b9d8bd',
           stroke_width=1.0, rx=8)
    s.text(LX, 750, '★ 床面積に算入しないもの', size=12.5, anchor='start',
           weight='700', fill='#1e7e34')
    s.text(LX, 772, '玄関ポーチ・バルコニー・駐輪スペース。'
           '面積表の数字は変わらない。',
           size=11.5, anchor='start', fill='#3d6b46')

    s.text(W / 2.0, H - 18,
           '★ 外まわりは配点も時間も小さい。'
           'でも「描いていない」は要求図書の不足になる。最後に必ず10分残す。',
           size=13, weight='700', fill='#333')
    return s


if __name__ == '__main__':
    sizes().save(os.path.join(OUT, 'soto_sizes.svg'))
    haichi().save(os.path.join(OUT, 'soto_haichi.svg'))
    print('wrote soto_sizes.svg / soto_haichi.svg')
