# -*- coding: utf-8 -*-
"""階段の「上り」と「下り」が、各階の平面図でどう見えるかを説明する図。

折り返し階段（2マス×4マス）を、
 ①上り方 ②横から見た段々 ③各階の平面図での見え方
の3段に分けて描く。
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

W, H = 660, 1130
UP, DN, LAND = '#c9762f', '#2f7fd0', '#bb9508'
GREY, INK = '#888', '#111'

s = Svg(W, H)
s.text(W / 2.0, 34, '階段の「UP」と「DN」', size=21, weight='700')
s.text(W / 2.0, 57, '折り返し階段（1,820 × 3,640）を上から見ると、'
       '段が2本ならんでいる', size=12, fill='#666')


def box(y0, y1, title, kicker):
    """パネルの見出し。"""
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 14, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 26, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 27, title, size=15, anchor='start', weight='700')


def plan(ox, oy, g, label, mode, small=False):
    """階段の2マス×4マスを1つ描く。mode: 'path'/'bottom'/'middle'/'top'"""
    w, d = 2 * g, 4 * g          # 間口2マス、奥行4マス
    mid = ox + g                 # 東西の段を分ける線
    ly = oy + g                  # 踊り場の南のふち（北が上）
    s.rect(ox, oy, w, d, fill='#fffdf4', stroke=LAND, stroke_width=1.4)
    s.line(ox, ly, ox + w, ly, stroke=LAND, stroke_width=1.4)
    s.line(mid, ly, mid, oy + d, stroke=LAND, stroke_width=1.2)
    t = g * 210.0 / 910.0        # 踏面210mmの見た目の幅
    for k in range(1, 7):        # 東の段（6段）
        yy = ly + k * t
        s.line(mid + 1.5, yy, ox + w - 2, yy, stroke=LAND, stroke_width=0.8)
    for k in range(1, 8):        # 西の段（7段）
        yy = ly + k * t
        s.line(ox + 2, yy, mid - 1.5, yy, stroke=LAND, stroke_width=0.8)
    s.text(mid, oy + g * 0.6, '踊場', size=9 if small else 10, fill='#a08840')
    s.text(ox + w / 2.0, oy + d + 18, label,
           size=11 if small else 12, weight='700')

    ex, wx = mid + g / 2.0, ox + g / 2.0      # 東の段・西の段の中心
    ybot, ytop = oy + d - 8, ly + 8

    def arrow(x, col, txt):
        """南（下）から北（上）へ向かう矢印。段を上る／下る向き。"""
        s.line(x, ybot, x, ytop + 9, stroke=col, stroke_width=2.0)
        s.polygon([(x, ytop), (x - 5, ytop + 9), (x + 5, ytop + 9)], fill=col)
        s.text(x, ybot + 14, txt, size=11, fill=col, weight='700')

    def cut(x0, x1, yy):
        """切断線。ここから上は「切ったより上」なので見えない。"""
        s.line(x0, yy + 7, x1, yy - 7, stroke=INK, stroke_width=1.1)
        s.line(x0, yy + 13, x1, yy - 1, stroke=INK, stroke_width=1.1)

    if mode == 'path':
        return ex, wx, ly, ybot
    if mode in ('bottom', 'middle'):
        arrow(ex, UP, 'UP')
        cut(mid + 1, ox + w - 1, ly + 5.0 * t)
    if mode in ('middle', 'top'):
        arrow(wx, DN, 'DN')
    return ex, wx, ly, ybot


# ============================================================
# ① 上り方
# ============================================================
box(74, 386, 'まず、どうやって上るのか', 'その1')
g = 46
ex, wx, ly, ybot = plan(56, 108, g, '1階の階段（上から見た図）', 'path')
s.circle(ex, ybot - 6, 11, fill=UP, stroke='none')
s.text(ex, ybot - 2, '1', size=12, fill='#fff', weight='700')
s.circle(ex, ly + 16, 11, fill=UP, stroke='none')
s.text(ex, ly + 20, '2', size=12, fill='#fff', weight='700')
s.circle(wx, ly + 16, 11, fill=UP, stroke='none')
s.text(wx, ly + 20, '3', size=12, fill='#fff', weight='700')
s.circle(wx, ybot - 6, 11, fill=UP, stroke='none')
s.text(wx, ybot - 2, '4', size=12, fill='#fff', weight='700')
s.path('M %.1f %.1f L %.1f %.1f' % (ex, ybot - 20, ex, ly + 30),
       stroke=UP, stroke_width=1.6, fill='none', stroke_dasharray='4 3')
s.path('M %.1f %.1f A 23 23 0 0 0 %.1f %.1f' % (ex, ly + 5, wx, ly + 5),
       stroke=UP, stroke_width=1.6, fill='none', stroke_dasharray='4 3')
s.path('M %.1f %.1f L %.1f %.1f' % (wx, ly + 30, wx, ybot - 20),
       stroke=UP, stroke_width=1.6, fill='none', stroke_dasharray='4 3')

s.lines_text(258, 128, [
    ('①1階の床に立つ。', 14, '700', INK),
    ('　　立つのは「東の段」の南のはし。', 12, '400', '#444'),
    ('②北へ向かって7段上る。', 14, '700', INK),
    ('③踊り場でくるっと180度まわる。', 14, '700', INK),
    ('　　ここで向きが「北向き」から「南向き」に変わる。', 12, '400', '#444'),
    ('④南へ向かって8段上ると、2階の床。', 14, '700', INK),
    ('　　着くのは「西の段」の南のはし。', 12, '400', '#444'),
], size=13, lh=25, anchor='start')
s.rect(258, 300, 366, 60, fill='#fdf3e7', stroke=UP, stroke_width=1.2, rx=6)
s.lines_text(272, 322, [
    ('ここが大事', 12, '700', UP),
    ('出発は「東の段」、到着は「西の段」。場所がちがう。', 12.5, '700', INK),
], size=12, lh=20, anchor='start')

# ============================================================
# ② 横から見た段々
# ============================================================
box(396, 700, '横から見ると、こうなっている', 'その2')
sw, sh = 10.0, 7.6           # 1段の見た目（踏面・蹴上）
bx, by = 74, 668             # 1階の床の左はし
CUT = 1500.0 / 207.0         # 床から1.5mが何段ぶんか
s.line(bx - 24, by, bx + 380, by, stroke=GREY, stroke_width=1.0)
x, y = bx, by
pts = [(x, y)]
floors, starts = [], []
for a, b in ((7, 8), (7, 7)):        # (東の段, 西の段) の蹴上の数
    starts.append(x)
    for _ in range(a):
        x += sw; pts.append((x, y)); y -= sh; pts.append((x, y))
    lx = x
    x += 24; pts.append((x, y))      # 踊り場
    s.text((lx + x) / 2.0, y - 6, '踊場', size=9, fill='#a08840')
    for _ in range(b):
        x += sw; pts.append((x, y)); y -= sh; pts.append((x, y))
    floors.append((x, y))
s.poly(pts, stroke=LAND, stroke_width=1.8, fill='none')
s.text(bx - 28, by - 5, '1階の床', size=11, anchor='end', fill='#555')
for i, (fx, fy) in enumerate(floors):
    s.line(bx - 24, fy, fx + 40, fy, stroke=GREY, stroke_width=1.0)
    s.text(bx - 28, fy - 5, '%d階の床' % (i + 2), size=11, anchor='end',
           fill='#555')

cutcol = '#c0392b'
for i, fy in enumerate([by, floors[0][1]]):
    cy = fy - CUT * sh
    s.line(bx - 24, cy, starts[i] + CUT * sw + 8, cy, stroke=cutcol,
           stroke_width=1.0, stroke_dasharray='7 4')
    s.text(bx + 400, cy + 4, '← %d階の平面図はここで切る' % (i + 1),
           size=10.5, anchor='start', fill=cutcol)
s.text(W / 2.0, 690, '平面図は「その階の床から1.5mくらいで水平に切って、'
       '下を見た図」。だから切ったより上は見えない。', size=11, fill='#666')

# ============================================================
# ③ 各階の見え方
# ============================================================
box(710, 1130, 'だから、平面図ではこう見える', 'その3')
g2 = 38
for i, (mode, lab) in enumerate([
        ('bottom', '1階平面図'), ('middle', '2階平面図'), ('top', '3階平面図')]):
    plan(78 + i * 196, 776, g2, lab, mode, small=True)
s.lines_text(40, 962, [
    ('1階', 12.5, '700', INK),
    ('　上がるだけ。UPの矢印を1本。切断線から先は「切ったより上」。', 12, '400', '#444'),
    ('2階　　上りと下りが両方ある。矢印は2本いる。', 12.5, '700', INK),
    ('　東の段＝これから3階へ上がる → UP　／　'
     '西の段＝1階から上がってきた道 → DN', 12, '400', '#444'),
    ('3階', 12.5, '700', INK),
    ('　下りるだけ。DNの矢印を1本。上に階がないので切断線もいらない。', 12, '400', '#444'),
], size=12, lh=19, anchor='start')
s.rect(40, 1082, W - 80, 34, fill='#eaf1f7', stroke=DN, stroke_width=1.2, rx=6)
s.text(W / 2.0, 1103, '矢印はどれも「南から北へ」。'
       '上りも下りも、歩き出す向きは同じ。', size=12, weight='700', fill=INK)

s.save(os.path.join(OUT, 'stair_updown.svg'))
print('wrote stair_updown.svg')
