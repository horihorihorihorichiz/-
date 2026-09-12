# -*- coding: utf-8 -*-
"""玄関まわりの図（平面＋断面）。figures/genkan.svg

地面（GL 0）→ 段2つ → ポーチ GL+380 → 玄関土間 GL+400 →
上がり框 150 → 玄関ホール GL+550 の流れを、上から見た図と横から切った図で示す。
数字は anssheet.py の DOMA（gl=400, porch=380, kamachi=150）と同じ。
"""
import os

from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
INK, RED, BLU, GRY = '#111', '#b03060', '#2f7fd0', '#777'
CONC, WOOD, FLOOR = '#e3e0d8', '#dfae6a', '#efdcbb'

W, H = 1040, 624
K = 0.13                        # 断面：1mm → px
SX, SY = 500, 556               # 断面：外壁の外面 x=0／GL y=0 の位置


def X(mm):
    return SX + mm * K


def Y(mm):
    return SY - mm * K


def plan(s):
    """上から見た図（左上）。1マス＝52px。"""
    G = 52
    x0, yn = 70, 112            # 西の壁／北の壁
    ys = yn + 2 * G             # 南の壁（外壁）
    s.text(x0, yn - 24, '① 上から見た図（平面図）', size=13, weight='700',
           anchor='start')

    # 玄関 2×2マス
    s.rect(x0, yn, 2 * G, 2 * G, fill='#fff', stroke=INK, stroke_width=2.4)
    s.line(x0 + 3, yn + G, x0 + 2 * G - 3, yn + G, stroke=INK,
           stroke_width=3.6)                                  # 上がり框
    s.text(x0 + G, yn + G * 0.42, '玄関ホール', size=11.5, weight='700')
    s.text(x0 + G, yn + G * 0.72, 'GL＋550', size=9.5, fill=RED)
    s.text(x0 + G, yn + G * 1.42, '土　間', size=11.5, weight='700')
    s.text(x0 + G, yn + G * 1.72, 'GL＋400', size=9.5, fill=RED)

    # 玄関の引き戸（南の外壁）
    s.line(x0 + 0.3 * G, ys, x0 + 1.3 * G, ys, stroke='#fff',
           stroke_width=6)
    s.line(x0 + 0.3 * G, ys - 4, x0 + 1.3 * G, ys - 4, stroke=INK,
           stroke_width=2.6)
    s.line(x0 + 1.3 * G, ys - 4, x0 + 1.95 * G, ys - 4, stroke=GRY,
           stroke_width=0.9)
    # 下足入れ
    s.rect(x0 + 5, yn + 6, G * 0.32, G * 0.72, fill='#fff', stroke='#333',
           stroke_width=0.9)
    s.text_rot(x0 + 5 + G * 0.16 + 3, yn + 6 + G * 0.36, '下足入れ', -90,
               size=7.5)
    # 階段へ
    s.line(x0 + G, yn, x0 + 2 * G, yn, stroke='#fff', stroke_width=6)
    s.line(x0 + G, yn + 4, x0 + 2 * G, yn + 4, stroke=INK, stroke_width=2.6)
    s.text(x0 + 2 * G + 8, yn + 8, '→ 階段へ', size=9.5, anchor='start',
           fill=GRY)

    # ポーチと段
    s.rect(x0 + 0.5 * G, ys, G, G, fill='#f6f4ef', stroke=INK,
           stroke_width=1.1)
    s.text(x0 + G, ys + G * 0.42, 'ポーチ', size=10.5)
    s.text(x0 + G, ys + G * 0.72, 'GL＋380', size=9, fill=RED)
    for i in (1, 2):
        yy = ys + G + i * 16
        s.line(x0 + 0.5 * G, yy, x0 + 1.5 * G, yy, stroke=INK,
               stroke_width=0.9)
    s.line(x0 + 0.5 * G, ys + G, x0 + 0.5 * G, ys + G + 32, stroke=INK,
           stroke_width=0.9)
    s.line(x0 + 1.5 * G, ys + G, x0 + 1.5 * G, ys + G + 32, stroke=INK,
           stroke_width=0.9)
    s.text(x0 + 2 * G + 8, ys + G + 22, '2段（地面から上がる）', size=9.5,
           anchor='start', fill=GRY)

    # 切断位置
    cx = x0 + G
    s.line(cx, yn - 14, cx, ys + G + 44, stroke=RED, stroke_width=1.2,
           stroke_dasharray='10 4 2 4')
    s.text(cx + 7, yn - 6, 'この線で切ったのが下の図', size=9.5,
           anchor='start', fill=RED)


def note_box(s):
    """右上の説明。"""
    bx, by = 330, 96
    s.rect(bx, by, 660, 190, fill='#fbfaf6', stroke='#d9d2c4',
           stroke_width=1.0)
    lines = [
        ('くつのまま歩くところ（土間）と、くつをぬいで上がるところ（ホール）を、'
         '段差で分けます。', True),
        ('① 地面（GL ±0）から 2段 上がって、ポーチ（GL＋380）。'
         '190mm の段を2つです。', False),
        ('② ポーチから引き戸をあけて中へ。土間（GL＋400）。'
         'ポーチより 20mm 高いのは、雨水を外へ流すため。', False),
        ('③ 土間から 150mm 上がって、玄関ホール（GL＋550）。'
         'この段差の横木が 上がり框（あがりかまち）。', False),
        ('④ ホールは1階の床と同じ高さ。ここから戸を1枚あけると階段のホールです。',
         False),
        ('答案には「GL＋400」「GL＋380」「GL＋550」の3つと、'
         '上がり框の太い1本線を書きます。', True),
    ]
    yy = by + 26
    for t, bold in lines:
        s.text(bx + 18, yy, t, size=11.5, anchor='start',
               weight='700' if bold else '400',
               fill=RED if bold else '#333')
        yy += 30


def section(s):
    s.text(70, 312, '② 横から切った図（断面）　左が外（道路）・右が家の中',
           size=13, weight='700', anchor='start')

    # 地面
    s.line(X(-3000), Y(0), X(-1456), Y(0), stroke=INK, stroke_width=2.0)
    for i in range(11):
        xx = X(-2980) + i * 14
        s.line(xx, Y(0), xx - 10, Y(0) + 12, stroke=GRY, stroke_width=0.8)
    s.text(X(-2980), Y(0) - 10, '地面 GL ±0', size=11, weight='700',
           anchor='start', fill=RED)

    # 段2つ → ポーチ
    s.rect(X(-1456), Y(190), 273 * K, 190 * K, fill=CONC, stroke=INK,
           stroke_width=1.1)
    s.rect(X(-1183), Y(380), 273 * K, 380 * K, fill=CONC, stroke=INK,
           stroke_width=1.1)
    s.rect(X(-910), Y(380), 910 * K, 380 * K, fill=CONC, stroke=INK,
           stroke_width=1.3)
    s.text(X(-455), Y(380) + 22, 'ポーチ', size=11, weight='700')
    s.text(X(-1320), Y(190) - 7, '190', size=8.5, fill=GRY)
    s.text(X(-1046), Y(380) - 7, '190', size=8.5, fill=GRY)

    # 土間コンクリート
    s.rect(X(60), Y(400), 850 * K, 400 * K, fill=CONC, stroke=INK,
           stroke_width=1.3)
    s.text(X(500), Y(400) + 26, '土間コンクリート', size=11, weight='700')
    s.text(X(500), Y(400) + 44, 'くつのまま', size=9.5, fill=GRY)

    # 上がり框
    s.rect(X(910), Y(550), 120 * K, 150 * K, fill=WOOD, stroke='#8a6a35',
           stroke_width=1.4)

    # ホールの床・床下
    s.rect(X(1030), Y(550), 1170 * K, 60 * K, fill=FLOOR, stroke='#8a6a35',
           stroke_width=1.2)
    s.rect(X(1030), Y(490), 1170 * K, 490 * K, fill='#f7f6f1', stroke='#ccc',
           stroke_width=0.8)
    s.text(X(1620), Y(230), '床下', size=9.5, fill='#aaa')
    s.text(X(1800), Y(900), '玄関ホール', size=11.5, weight='700')
    s.text(X(1800), Y(780), 'くつをぬぐ', size=9.5, fill=GRY)

    # 外壁と引き戸（上は破断）
    s.rect(X(-60), Y(1560), 120 * K, 60 * K, fill='#e6ddcc', stroke=INK,
           stroke_width=1.2)
    s.rect(X(-60), Y(1500), 120 * K, 1100 * K, fill='#eaf3f9', stroke=BLU,
           stroke_width=1.4)
    s.text_rot(X(0) + 4, Y(950), '玄関の引き戸', -90, size=10, fill=BLU)
    d = 'M %.1f %.1f' % (X(-130), Y(1560))
    up = True
    xx = X(-130)
    while xx < X(130):
        xx += 13
        d += ' L %.1f %.1f' % (xx, Y(1560) + (5 if up else -5))
        up = not up
    s.path(d, stroke='#888', stroke_width=1.0)
    s.text(X(230), Y(1560) + 4, '（上は省略）', size=9, anchor='start',
           fill='#999')

    # 下足入れ
    s.rect(X(1090), Y(1420), 420 * K, 870 * K, fill='#fff', stroke='#333',
           stroke_width=1.0)
    s.text(X(1300), Y(950), '下足入れ', size=9.5)

    # 高さの線と名前
    for mm, lab, col in ((0, '', RED), (550, '', RED)):
        s.line(X(-3000), Y(mm), X(2280), Y(mm), stroke=col,
               stroke_width=0.7, stroke_dasharray='9 3 2 3')
    s.line(X(-1456), Y(380), X(2280), Y(380), stroke=RED, stroke_width=0.7,
           stroke_dasharray='9 3 2 3')
    for mm, lab in ((0, 'GL ±0'), (380, 'ポーチ ＋380 ／ 土間 ＋400（差20）'),
                    (550, 'ホール・1階の床 ＋550')):
        s.text(X(2310), Y(mm) + 4, lab, size=10.5, anchor='start', fill=RED,
               weight='700')
    s.dim_v(Y(400), Y(550), X(980), '150', size=9.5, anchor='end', dx=-6)
    s.text(X(960), Y(760), '上がり框', size=10, anchor='end', fill=RED,
           weight='700')
    s.line(X(950), Y(720), X(985), Y(500), stroke=RED, stroke_width=0.9)
    s.dim_v(Y(0), Y(380), X(-1560), '380', size=9.5, anchor='end', dx=-6)


def draw():
    s = Svg(W, H)
    s.text(W / 2.0, 34, '玄関まわり ── 地面からホールまで', size=21,
           weight='700')
    s.text(W / 2.0, 57,
           'ポーチ＋380 →（引き戸）→ 土間＋400 →（上がり框150）→ ホール＋550',
           size=12, fill=GRY)
    plan(s)
    note_box(s)
    section(s)
    s.text(W / 2.0, H - 18,
           '★ 1階平面図に書くのは「GL＋400（土間）」「GL＋380（ポーチ）」'
           '「GL＋550（ホール・売場）」の3つ。', size=11.5, weight='700',
           fill='#333')
    s.save(os.path.join(OUT, 'genkan.svg'))
    print('wrote genkan.svg')


if __name__ == '__main__':
    draw()
