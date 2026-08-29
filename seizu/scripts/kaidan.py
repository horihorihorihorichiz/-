# -*- coding: utf-8 -*-
"""階段の描き方。1コマずつ、線を足していく。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 700, 1080
INK, RED, BLUE = '#111', '#c0392b', '#2f7fd0'
G = 46.0                       # 1マス
T = 0.25                       # 踏面＝マスの4分の1（227.5mm）
NX, NY = 2, 4                  # 階段室は2マス×4マス
LAND = 3                       # 踊り場は北の1マス（Y3〜4）
N1, N2 = 6, 7                  # 東の段・西の段の数

s = Svg(W, H)
s.text(W / 2.0, 32, '階段の描き方', size=21, weight='700')
s.text(W / 2.0, 55, '2マス×4マスの中に、6本の線を順に足していくだけ',
       size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


def cell(ox, oy, step, cap, memo):
    def px(g):
        return ox + g * G

    def py(g):
        return oy + (NY - g) * G

    # マスの下地
    for i in range(NX * 2 + 1):
        s.line(px(i / 2.0), py(NY), px(i / 2.0), py(0), stroke='#e4e4e4',
               stroke_width=0.6)
    for j in range(NY * 4 + 1):
        s.line(px(0), py(j / 4.0), px(NX), py(j / 4.0), stroke='#e4e4e4',
               stroke_width=0.6)
    s.rect(px(0), py(NY), NX * G, NY * G, fill='none', stroke=INK,
           stroke_width=1.6)
    mid = NX / 2.0
    if step >= 2:
        s.line(px(mid), py(0), px(mid), py(LAND), stroke=INK,
               stroke_width=1.8)
    if step >= 3:
        s.line(px(0), py(LAND), px(NX), py(LAND), stroke=INK,
               stroke_width=1.6)
        s.text(px(mid), py(LAND + 0.55), '踊場', size=8.5, fill='#555')
    if step >= 4:
        for k in range(1, N1 + 1):
            s.line(px(mid) + 1, py(LAND - k * T), px(NX) - 2,
                   py(LAND - k * T), stroke=INK, stroke_width=1.0)
        for k in range(1, N2 + 1):
            s.line(px(0) + 2, py(LAND - k * T), px(mid) - 1,
                   py(LAND - k * T), stroke=INK, stroke_width=1.0)
    if step >= 5:
        ax = px(mid + 0.5)
        yb, yt = py(LAND - N1 * T - 0.2), py(LAND - 0.1)
        s.line(ax, yb, ax, yt + 8, stroke=INK, stroke_width=1.6)
        s.polygon([(ax, yt), (ax - 4.5, yt + 8), (ax + 4.5, yt + 8)],
                  fill=INK)
        s.text(ax, yb + 13, 'UP', size=9.5, weight='700')
    if step >= 6:
        yy = py(LAND - (N1 - 1) * T)
        s.line(px(mid) + 1, yy + 6, px(NX) - 1, yy - 6, stroke=INK,
               stroke_width=1.1)
        s.line(px(mid) + 1, yy + 11, px(NX) - 1, yy - 1, stroke=INK,
               stroke_width=1.1)
    s.circle(ox - 4, oy - 12, 12, fill=RED)
    s.text(ox - 4, oy - 8, str(step), size=12, fill='#fff', weight='700')
    s.text(ox + 20, oy - 8, cap, size=12, anchor='start', weight='700')
    s.text(ox, py(0) + 22, memo, size=10, anchor='start', fill='#555')


band(74, 620, 'その1', '6コマで完成する')
STEPS = [
    ('わくを描く', '2マス×4マス。1マスは910'),
    ('まん中に手摺の線', 'これで「910の階段が2本」になる'),
    ('踊り場の線', '北の1マス。ここでUターン'),
    ('段の線を等間隔に', 'マスの4分の1おき（踏面227.5）'),
    ('矢印とUP', '南から北へ。歩き出す向き'),
    ('切断線', '床から1.5mを追いこしたところ'),
]
for i, (cap, memo) in enumerate(STEPS):
    ox = 74 + (i % 3) * 216
    oy = 140 + (i // 3) * 250
    cell(ox, oy, i + 1, cap, memo)

band(630, 872, 'その2', '段数はこうして決める')
s.lines_text(64, 676, [
    ('① 階高（かいだか）を段数で割る', 13, '700', INK),
    ('　1階の階高は 3,100mm。これを何段で上がるか。', 11.5, '400', '#444'),
    ('② 蹴上（けあげ）の上限を守る', 13, '700', INK),
    ('　1段の高さ＝蹴上。店舗のある建物は 220mm 以下（令23条）。', 11.5,
     '400', '#444'),
    ('　3,100 ÷ 220 ＝ 14.09 … 14段だと超える。だから 15段。', 11.5, '400',
     '#444'),
    ('　3,100 ÷ 15 ＝ 206.7mm　→ 220以下なのでOK', 12.5, '700', RED),
    ('③ 踏面（ふみづら）は 210mm 以上', 13, '700', INK),
    ('　この型は 227.5mm（910の4分の1）。マスに乗るので描きやすい。',
     11.5, '400', '#444'),
], size=12, lh=21, anchor='start')

band(882, 1080, 'その3', 'UPとDNは階でちがう')
ROWS = [('1階', 'UP だけ', '上がる先はあるが、下りる先がない'),
        ('2階', 'UP と DN の2本', '上にも下にも行ける。ここだけ2本'),
        ('3階', 'DN だけ', '下りる先はあるが、上がる先がない')]
for i, (a, b, c) in enumerate(ROWS):
    yy = 934 + i * 44
    s.rect(64, yy - 18, 56, 26, fill='#fff', stroke=INK, stroke_width=1.0)
    s.text(92, yy, a, size=12.5, weight='700')
    s.text(136, yy, b, size=12.5, anchor='start', weight='700', fill=RED)
    s.text(264, yy, c, size=11, anchor='start', fill='#555')
s.text(64, 1064, '※ 矢印の向きはどの階も「南から北」。'
       '矢印は高くなる方向ではなく、その階の床から歩き出す方向。',
       size=11, anchor='start', fill=BLUE)

s.save(os.path.join(OUT, 'kaidan.svg'))
print('wrote kaidan.svg')
