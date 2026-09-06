# -*- coding: utf-8 -*-
"""部分詳細図（1/20）を、答案用紙の10mm方眼の上で1手ずつ建てていく9コマ。

答案用紙の部分詳細図らんは 1目盛 10mm。縮尺1／20なので
  1目盛 ＝ 実物 200mm、半目盛 ＝ 実物 100mm。
この図はその方眼を実寸で敷いたうえに描いてある。
高さの数値は scripts/detail.py（完成図）と同じ。
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

SC = 0.16                       # 1mm → px（1目盛200mm ＝ 32px）
GRID = 200.0                    # 1目盛が表す実寸
XL, XR = -800.0, 500.0          # 描く横の範囲（柱心が0）
YB, YT = -400.0, 3750.0
OX, OY = 140.0, 60.0
W = 520
H = int(OY + (YT - YB) * SC + 96)

INK = '#111'
ACC = '#c0392b'
GRY = '#8f948c'
CONC = '#d9d9d9'
WOOD = '#ecd9b4'
PLY = '#f2e3c4'
BOARD = '#efefef'
SIDE = '#cfd8dc'
INS = '#fbeecf'
GLASS = '#dfeaf0'

# 高さ（mm）。detail.py と同じ
Z_BOT, Z_SLAB, Z_KISO = -300.0, -150.0, 371.0
Z_PACK, Z_DODAI = 391.0, 511.0
Z_PLY1, Z_1FL = 535.0, 550.0
Z_CEIL = 3250.0
Z_BEAM_B, Z_BEAM_T = 3311.0, 3611.0
Z_PLY2, Z_2FL = 3635.0, 3650.0
WIN_B, WIN_T = 1350.0, 2650.0   # 腰窓（腰高800・高さ1,300）


def X(mm):
    return OX + (mm - XL) * SC


def Y(mm):
    return OY + (YT - mm) * SC


def rect(s, x0, x1, z0, z1, fill, stroke=INK, sw=1.0, **kw):
    s.rect(X(x0), Y(z1), (x1 - x0) * SC, (z1 - z0) * SC, fill=fill,
           stroke=stroke, stroke_width=sw, **kw)


def grid(s):
    """答案用紙の10mm方眼。GLと柱心を線に合わせてある。

    5目盛ごとに濃くして、目で数えやすくしてある（実際の答案用紙は
    ぜんぶ同じ濃さなので、そこは数えるしかない）。
    """
    z = YB - (YB % GRID)
    while z <= YT:
        n = int(round(z / GRID))
        five = (n % 5 == 0)
        s.line(X(XL), Y(z), X(XR), Y(z),
               stroke='#b9c6ba' if five else '#dde3dc',
               stroke_width=0.9 if five else 0.65)
        if five and n != 0:
            s.text(X(XL) + 5, Y(z) - 4, '%d目盛' % n, size=8.5,
                   anchor='start', fill='#a8b2a8')
        z += GRID
    x = XL - (XL % GRID)
    while x <= XR:
        n = int(round(x / GRID))
        s.line(X(x), Y(YT), X(x), Y(YB),
               stroke='#b9c6ba' if n % 5 == 0 else '#dde3dc',
               stroke_width=0.9 if n % 5 == 0 else 0.65)
        x += GRID


def head(s, n, title, line):
    s.rect(0, 0, W, 52, fill='#fbfaf7', stroke='none')
    s.circle(26, 26, 14, fill=ACC)
    s.text(26, 31, str(n), size=15, weight='700', fill='#fff')
    s.text(48, 24, title, size=15, anchor='start', weight='700')
    s.text(48, 42, line, size=11, anchor='start', fill='#666')


def zlabel(s, z, text, col=INK, size=10.5):
    s.text(X(XL) - 8, Y(z) + 3.5, text, size=size, anchor='end', fill=col)


def note(s, x, z, text, col=ACC, anchor='start', size=10):
    s.text(X(x), Y(z), text, size=size, anchor=anchor, fill=col, weight='700')


# ------------------------------------------------------------------ 各手
def draw(step):
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='#fff', stroke='none')
    grid(s)
    a = lambda n: ACC if n == step else INK        # noqa: E731
    aw = lambda n: 2.0 if n == step else 1.0       # noqa: E731

    # 1 …… 基準線
    if step >= 1:
        s.line(X(XL), Y(0), X(XR), Y(0), stroke=a(1), stroke_width=aw(1) + 0.6)
        zlabel(s, 0, 'GL（地面）', a(1), 11)
        s.line(X(0), Y(YT), X(0), Y(YB), stroke=a(1), stroke_width=aw(1),
               stroke_dasharray='16 3 3 3')
        s.text(X(0) + 26, Y(YT - 210), '柱心', size=10, fill=a(1),
               weight='700')

    # 2 …… 高さの基準線4本
    if step >= 2:
        for z, lab, cnt in ((Z_BOT, '基礎の底  GL−300', '下へ 1目盛半'),
                            (Z_1FL, '1FL  GL+550', '上へ 2目盛と3/4'),
                            (Z_2FL, '2FL  GL+3,650', '上へ 18目盛と1/4')):
            s.line(X(XL), Y(z), X(XR), Y(z), stroke=a(2), stroke_width=aw(2),
                   stroke_dasharray='7 4' if step == 2 else None)
            zlabel(s, z, lab, a(2), 10.5)
            if step == 2:
                note(s, XL + 60, z + (150 if z < 0 else -190), cnt)

    # 3 …… 基礎
    if step >= 3:
        rect(s, -240, 240, Z_BOT, Z_SLAB, CONC, a(3), aw(3))     # 底盤
        rect(s, -75, 75, Z_SLAB, Z_KISO, CONC, a(3), aw(3))      # 立上り
        if step == 3:
            note(s, 260, Z_BOT + 40, 'べた基礎 底盤 t150')
            note(s, 260, Z_KISO - 90, '立上り t150')
            note(s, 260, Z_KISO + 30, '地上371（300以上）')
            note(s, -560, Z_BOT - 70, '根入れ300 ＝ 下へ1目盛半')

    # 4 …… 基礎パッキン・土台・アンカーボルト
    if step >= 4:
        rect(s, -60, 60, Z_KISO, Z_PACK, '#e2e2e2', a(4), aw(4))
        rect(s, -60, 60, Z_PACK, Z_DODAI, WOOD, a(4), aw(4))
        s.line(X(-20), Y(Z_DODAI + 30), X(-20), Y(Z_KISO - 250),
               stroke=a(4), stroke_width=aw(4) + 0.4)
        if step == 4:
            note(s, 90, Z_DODAI - 10, '土台 120×120（0.6目盛）')
            note(s, 90, Z_PACK - 8, '基礎パッキン t20')
            note(s, -620, Z_KISO - 200, 'アンカーボルト')
            note(s, -620, Z_KISO - 260, 'M12 埋込み250以上')

    # 5 …… 1階の床
    if step >= 5:
        rect(s, XL + 40, 60, Z_DODAI, Z_PLY1, PLY, a(5), aw(5))   # 合板t24
        rect(s, XL + 40, 60, Z_PLY1, Z_1FL, '#e8d7b8', a(5), aw(5))
        if step == 5:
            note(s, -560, Z_1FL + 70, '構造用合板 t=24 ＋ 仕上 t=15')
            note(s, -560, Z_1FL + 20, '→ ここで 1FL＝GL+550 になる')

    # 6 …… 外壁の6層
    if step >= 6:
        rect(s, -75, -60, Z_DODAI, Z_2FL, BOARD, a(6), aw(6))     # 石膏15
        rect(s, -60, 60, Z_DODAI, Z_BEAM_B, INS, a(6), aw(6))     # 柱＋GW
        rect(s, 60, 69, Z_DODAI, Z_2FL, PLY, a(6), aw(6))         # 合板9
        rect(s, 69, 87, Z_DODAI, Z_2FL, '#f7f7f7', a(6), aw(6))   # 胴縁18
        rect(s, 87, 103, Z_DODAI, Z_2FL, SIDE, a(6), aw(6))       # サイディング
        if step == 6:
            note(s, 118, 1900, '外へ →')
            for i, (lab, z) in enumerate((
                    ('① 強化石膏ボード t=15', 1700),
                    ('② 柱120＋グラスウール16K t=100', 1560),
                    ('③ 構造用合板 t=9', 1420),
                    ('④ 透湿防水シート', 1280),
                    ('⑤ 通気胴縁 t=18（通気層）', 1140),
                    ('⑥ 窯業系サイディング t=16', 1000))):
                note(s, 118, z, lab, size=9.5)
            note(s, 118, 860, '合計 178 ＝ 約0.9目盛', size=10)

    # 7 …… 2階の床と1階の天井
    if step >= 7:
        rect(s, -60, 60, Z_BEAM_B, Z_BEAM_T, WOOD, a(7), aw(7))   # 胴差
        rect(s, XL + 40, 60, Z_BEAM_T, Z_PLY2, PLY, a(7), aw(7))
        rect(s, XL + 40, 60, Z_PLY2, Z_2FL, '#e8d7b8', a(7), aw(7))
        s.line(X(XL + 40), Y(Z_CEIL), X(-75), Y(Z_CEIL), stroke=a(7),
               stroke_width=aw(7))
        if step == 7:
            note(s, -560, Z_BEAM_T + 90, '胴差 120×300')
            note(s, -560, Z_BEAM_T + 40, '＋ 合板t24 ＋ 仕上t15 → 2FL')
            note(s, -560, Z_CEIL - 70, '天井 GL+3,250（天井高2,700＝13目盛半）')

    # 8 …… 開口部
    if step >= 8:
        s.rect(X(-75), Y(WIN_T), 178 * SC, (WIN_T - WIN_B) * SC,
               fill='#fff', stroke='none')
        rect(s, -75, 103, WIN_B, WIN_B + 60, WOOD, a(8), aw(8))   # 窓台
        rect(s, -75, 103, WIN_T - 60, WIN_T, WOOD, a(8), aw(8))   # まぐさ
        rect(s, 0, 20, WIN_B + 60, WIN_T - 60, GLASS, a(8), aw(8))
        if step == 8:
            note(s, 118, WIN_T + 40, '開口部（腰窓）')
            note(s, 118, (WIN_B + WIN_T) / 2.0 + 60, 'まぐさ・窓台')
            note(s, 118, (WIN_B + WIN_T) / 2.0, 'アルミサッシ＋複層ガラス')
            note(s, -560, WIN_B - 60, '腰高800（4目盛）')
            note(s, -560, WIN_B - 120, '窓の高さ1,300（6目盛半）')

    # 9 …… 寸法と文字
    if step >= 9:
        dx = 320.0
        s.dim_v(Y(Z_2FL), Y(Z_1FL), X(dx), '階高 3,100', size=10,
                anchor='start', dx=6, color=a(9))
        s.dim_v(Y(Z_CEIL), Y(Z_1FL), X(dx - 190), '天井高 2,700', size=10,
                anchor='end', dx=-6, color=a(9))
        s.dim_v(Y(Z_1FL), Y(0), X(dx), '床高 550', size=10, anchor='start',
                dx=6, color=a(9))
        s.dim_v(Y(0), Y(Z_BOT), X(dx), '根入れ 300', size=10, anchor='start',
                dx=6, color=a(9))
        if step == 9:
            note(s, -790, 2500, '書き落とし注意', size=10.5)
            for i, r in enumerate(('・部材の名称と断面寸法',
                                   '・内外の仕上材料名',
                                   '・断熱と防湿の措置',
                                   '・アンカーボルトの寸法',
                                   '・床高／天井高／階高')):
                note(s, -790, 2350 - i * 140, r, col='#555', size=9.5)

    TITLES = (
        ('基準線を2本引く', 'GLと柱心を、方眼の線にぴったり合わせる'),
        ('高さの基準線を引く', '目盛を数えるだけ。1目盛＝200mm、半目盛＝100mm'),
        ('基礎を描く', '底盤t150と立上りt150。根入れは下へ1目盛半'),
        ('土台とアンカーボルト', '基礎パッキンt20をはさんで土台120×120'),
        ('1階の床', '合板t24＋仕上t15。これで1FL＝GL+550'),
        ('外壁を内から外へ6層', '15/120/9/18/16 ＝ 178。約0.9目盛'),
        ('2階の床と1階の天井', '胴差120×300を先に置くと位置が決まる'),
        ('開口部を入れる', '「開口部を含む」ことが要求されている'),
        ('寸法と文字を入れる', 'ここが点になる。図より文字のほうが大事'),
    )
    head(s, step, TITLES[step - 1][0], TITLES[step - 1][1])
    s.text(W / 2.0, H - 30, '1目盛 10mm ＝ 実物 200mm（縮尺1／20）',
           size=10.5, fill='#999')
    s.text(W / 2.0, H - 14, '半目盛 ＝ 実物 100mm', size=10.5, fill='#999')
    return s


def panel(s, x, y, w, h, title, sub=''):
    """区切りのわく。"""
    s.rect(x, y, w, h, fill='#fcfcfb', stroke='#e0ded8', stroke_width=1.0,
           rx=10)
    s.text(x + 16, y + 26, title, size=14.5, anchor='start', weight='700')
    if sub:
        s.text(x + 16, y + 45, sub, size=11, anchor='start', fill='#777')

# ============================================ 実物はどれくらい細いのか
def real():
    """1／20で紙の上に何mmになるかを、実際の比率で見せる。

    説明用の図は層を太らせてあるので、本当の細さが分からない。
    ここだけは比率をいじらずに描く。
    """
    W, H = 1240, 700
    s = Svg(W, H)
    s.text(W / 2.0, 40, '実物はどれくらい細いのか（1／20 の紙の上）',
           size=22, weight='700')
    s.text(W / 2.0, 66,
           '説明の図は層を太らせてある。'
           'ここだけは、ふくらませずに本当の比率で描いた。',
           size=12.5, fill='#666')

    # ---------------------------------------- 左：全体の比率
    panel(s, 20, 90, 372, 560, '① 図ぜんぶの大きさ',
          '高さ約20cm、壁の幅たった9mm')
    K1 = 2.1                                   # 紙1mm → px
    bx, by = 210.0, 150.0                      # 壁の内面の位置・上端
    hh = 197.5 * K1                            # 高さ198mm
    s.rect(bx - 46 * K1, by, 46 * K1, hh, fill='#f4f2ec', stroke='#c9c9c0',
           stroke_width=0.8)                   # 室内（床など）
    s.rect(bx, by, 8.9 * K1, hh, fill='#c0392b', stroke='none')   # 外壁
    s.rect(bx - 12 * K1, by + hh - 24 * K1, 36 * K1, 24 * K1,
           fill='#e0e0da', stroke='#b6b6ae', stroke_width=0.8)    # 基礎
    for cm, lab in ((0, '0'), (5, '5cm'), (10, '10cm'), (15, '15cm'),
                    (20, '20cm')):
        yy = by + cm * 10 * K1
        s.line(bx - 118, yy, bx - 108, yy, stroke='#999', stroke_width=1.0)
        s.text(bx - 124, yy + 4, lab, size=10, anchor='end', fill='#888')
    s.line(bx - 113, by, bx - 113, by + hh, stroke='#999', stroke_width=1.0)
    s.line(bx + 4.45 * K1, by - 16, bx + 4.45 * K1, by - 4, stroke=ACC,
           stroke_width=1.2)
    s.text(bx + 4.45 * K1 + 6, by - 18, '← 壁はこの赤いところだけ',
           size=10.5, anchor='start', fill=ACC, weight='700')
    s.text(bx + 4.45 * K1 + 6, by - 4, '　 幅 8.9mm', size=10.5,
           anchor='start', fill=ACC, weight='700')
    s.text(36, 626, '★ 紙の上では、ほとんど「細い棒」です。',
           size=11.5, anchor='start', fill='#555')

    # ---------------------------------------- 中：9mmの中身
    panel(s, 406, 90, 404, 560, '② その 8.9mm の中身',
          '20倍にふくらませたところ')
    K2 = 34.0                                  # 紙1mm → px
    lx, ly, lh = 452.0, 156.0, 200.0
    LAYERS = (('強化石膏ボード', 15, BOARD),
              ('柱＋グラスウール', 120, INS),
              ('構造用合板', 9, PLY),
              ('通気胴縁', 18, '#f7f7f7'),
              ('サイディング', 16, SIDE))
    x = lx
    for nm, mm, col in LAYERS:
        w = mm / 20.0 * K2
        s.rect(x, ly, w, lh, fill=col, stroke=INK, stroke_width=0.9)
        x += w
    s.dim_h(lx, x, ly - 14, '8.9mm', size=11)
    x = lx
    for i, (nm, mm, col) in enumerate(LAYERS):
        w = mm / 20.0 * K2
        pm = mm / 20.0
        thin = pm < 1.0
        yy = ly + lh + 30 + i * 34
        s.line(x + w / 2.0, ly + lh, x + w / 2.0, yy - 10,
               stroke=ACC if thin else '#aaa', stroke_width=0.9)
        s.text(430, yy, nm, size=11, anchor='start',
               fill=ACC if thin else '#333', weight='700' if thin else '400')
        s.text(700, yy, '実物%dmm' % mm, size=10.5, anchor='end',
               fill='#888')
        s.text(790, yy, '→ %.2fmm' % pm, size=11, anchor='end',
               fill=ACC if thin else '#333', weight='700')
        x += w
    s.text(424, 626,
           '★ 赤い4つは 1mm未満。鉛筆の線（約0.5mm）とほぼ同じ太さです。',
           size=11.5, anchor='start', fill=ACC, weight='700')

    # ---------------------------------------- 右：だからこう描く
    panel(s, 824, 90, 396, 560, '③ だから、こう描く',
          '線を詰めこまない。名前は外に出す')
    wx, wy, wh = 856.0, 160.0, 300.0
    ww = 56.0
    s.rect(wx, wy, ww, wh, fill='#fff', stroke=INK, stroke_width=1.6)
    s.line(wx + 14, wy, wx + 14, wy + wh, stroke=INK, stroke_width=1.2)
    s.line(wx + 42, wy, wx + 42, wy + wh, stroke=INK, stroke_width=1.2)
    s.rect(wx + 14, wy + 40, 28, wh - 80, fill=INS, stroke=INK,
           stroke_width=1.0)
    s.text(wx + 28, wy + wh / 2.0 + 4, '柱', size=11, weight='700')
    s.line(wx + ww, wy + 60, wx + ww + 34, wy + 14, stroke='#888',
           stroke_width=1.0)
    for i, r in enumerate(('① 強化石膏ボード t=15',
                           '② 柱120＋GW16K t=100',
                           '③ 構造用合板 t=9',
                           '④ 透湿防水シート',
                           '⑤ 通気胴縁 t=18',
                           '⑥ 窯業系サイディング t=16')):
        s.text(wx + ww + 38, wy + 10 + i * 27, r, size=11, anchor='start',
               fill='#333')
    s.rect(848, 546, 348, 82, fill='#fdeeee', stroke='#e0a0a0',
           stroke_width=1.0, rx=8)
    s.text(864, 570, '線は3〜4本でいい', size=12.5, anchor='start',
           weight='700', fill=ACC)
    s.text(864, 592, '9mmの中に6本の線は入りません。', size=11.5,
           anchor='start', fill='#8a3a3a')
    s.text(864, 612, '外面・柱の2本・内面。名前は引き出し線で外へ。',
           size=11.5, anchor='start', fill='#8a3a3a')

    s.text(W / 2.0, H - 16,
           '★ 部分詳細図の点は「線の細かさ」ではなく「文字の数」で決まる。'
           'ここが分かると、一気に楽になります。',
           size=13, weight='700', fill='#333')
    return s


# ================================================ 提出する形（答案の完成形）
def kansei():
    """答案に出すときの姿。黒だけ、方眼の上、文字びっしり。"""
    global SC, OX, OY
    SC0, OX0, OY0 = SC, OX, OY
    SC, OX, OY = 0.168, 128.0, 74.0
    W2, H2 = 800, int(OY + (YT - YB) * SC + 84)
    s = Svg(W2, H2)
    s.rect(0, 0, W2, H2, fill='#fff', stroke='none')
    s.rect(0, 0, W2, 50, fill='#fbfaf7', stroke='none')
    s.text(20, 24, '提出する形　部分詳細図（断面）　縮尺1／20', size=15,
           anchor='start', weight='700')
    s.text(20, 42, '黒鉛筆だけ。目盛10mm。線は太く数本、文字はびっしり。',
           size=11, anchor='start', fill='#666')
    grid(s)

    # ---- 図（ぜんぶ黒）
    rect(s, -240, 240, Z_BOT, Z_SLAB, CONC)
    rect(s, -75, 75, Z_SLAB, Z_KISO, CONC)
    rect(s, -60, 60, Z_KISO, Z_PACK, '#e2e2e2')
    rect(s, -60, 60, Z_PACK, Z_DODAI, WOOD)
    s.line(X(-20), Y(Z_DODAI + 30), X(-20), Y(Z_KISO - 250), stroke=INK,
           stroke_width=1.6)
    rect(s, XL + 40, 60, Z_DODAI, Z_PLY1, PLY)
    rect(s, XL + 40, 60, Z_PLY1, Z_1FL, '#e8d7b8')
    rect(s, -75, -60, Z_DODAI, Z_2FL, BOARD)
    rect(s, -60, 60, Z_DODAI, Z_BEAM_B, INS)
    rect(s, 60, 69, Z_DODAI, Z_2FL, PLY)
    rect(s, 69, 87, Z_DODAI, Z_2FL, '#f7f7f7')
    rect(s, 87, 103, Z_DODAI, Z_2FL, SIDE)
    rect(s, -60, 60, Z_BEAM_B, Z_BEAM_T, WOOD)
    rect(s, XL + 40, 60, Z_BEAM_T, Z_PLY2, PLY)
    rect(s, XL + 40, 60, Z_PLY2, Z_2FL, '#e8d7b8')
    s.line(X(XL + 40), Y(Z_CEIL), X(-75), Y(Z_CEIL), stroke=INK,
           stroke_width=1.2)
    s.rect(X(-75), Y(WIN_T), 178 * SC, (WIN_T - WIN_B) * SC, fill='#fff',
           stroke='none')
    rect(s, -75, 103, WIN_B, WIN_B + 60, WOOD)
    rect(s, -75, 103, WIN_T - 60, WIN_T, WOOD)
    rect(s, 0, 20, WIN_B + 60, WIN_T - 60, GLASS)

    # ---- 引き出し線＋文字（ここが点になる）
    LX2 = 470.0
    LABELS = (
        (103, Z_2FL - 120, '窯業系サイディング t=16（外壁仕上げ）'),
        (78, Z_2FL - 340, '通気胴縁 18×45 ＠455（通気層）'),
        (64, Z_2FL - 560, '透湿防水シート／構造用合板 t=9'),
        (0, Z_BEAM_T - 150, '胴差 120×300'),
        (0, Z_PLY2, '構造用合板 t=24（根太レス）＋ フローリング t=15'),
        (-70, Z_CEIL, '天井 石膏ボード t=9.5（天井仕上げ）'),
        (0, 2300, '柱 120×120'),
        (0, 2050, 'グラスウール16K t=100（断熱）'),
        (-68, 1800, '強化石膏ボード t=15（内壁仕上げ）'),
        (60, WIN_T - 30, 'まぐさ／アルミサッシ＋複層ガラス'),
        (60, WIN_B + 30, '窓台'),
        (0, Z_1FL, 'フローリング t=15（床仕上げ）＋ 構造用合板 t=24'),
        (0, Z_DODAI - 60, '土台 120×120'),
        (0, Z_PACK - 10, '基礎パッキン t=20'),
        (-20, Z_KISO - 220, 'アンカーボルト M12 ＠2,730以下（埋込み250以上）'),
        (0, 120, 'べた基礎 立上り t=150（地上371）'),
        (0, Z_SLAB - 80, 'べた基礎 底盤 t=150（根入れ300）'),
        (-180, Z_BOT + 40, '防湿フィルム t=0.15 ＋ 割栗石'),
    )
    # 引き出し線は、文字が重ならないように行を送ってから折り曲げる
    src = [(X(x0), Y(z)) for x0, z, _ in LABELS]
    order = sorted(range(len(LABELS)), key=lambda i: src[i][1])
    prev, rows = -1e9, {}
    for i in order:
        rows[i] = max(src[i][1], prev + 17.0)
        prev = rows[i]
    for i, (x0, z, txt) in enumerate(LABELS):
        sx, sy = src[i]
        ty = rows[i]
        s.line(sx, sy, LX2 - 46, sy, stroke='#666', stroke_width=0.7)
        s.line(LX2 - 46, sy, LX2 - 12, ty, stroke='#666', stroke_width=0.7)
        s.circle(sx, sy, 1.8, fill=INK)
        s.text(LX2, ty + 3.5, txt, size=10, anchor='start', fill=INK)

    # ---- 寸法（左）
    for a, b, dx, lab in ((Z_2FL, Z_1FL, -540, '階高 3,100'),
                          (Z_CEIL, Z_1FL, -400, '天井高 2,700'),
                          (Z_1FL, 0.0, -540, '床高 550'),
                          (0.0, Z_BOT, -540, '根入れ 300')):
        s.dim_v(Y(a), Y(b), X(dx), lab, size=10, anchor='end', dx=-6)
    for z, lab in ((0.0, 'GL'), (Z_1FL, '1FL  GL+550'),
                   (Z_2FL, '2FL  GL+3,650')):
        s.text(X(XL) - 6, Y(z) + 3.5, lab, size=10, anchor='end', fill=INK)

    s.text(20, H2 - 34,
           '★ 要求されているのは 部材の名称・断面寸法／仕上材料名（外壁・床・'
           '内壁・天井）／断熱と防湿／アンカーボルト／床高・天井高・階高。',
           size=10.5, anchor='start', fill='#555')
    s.text(20, H2 - 16,
           '★ 線は太く数本でよい。上の文字が1行でも欠けると、'
           'そのぶん点にならない。', size=10.5, anchor='start', fill=ACC,
           weight='700')
    SC, OX, OY = SC0, OX0, OY0
    return s


# ==================================================== 柱はどこまで描くのか
def hashira():
    """同じ柱が、図面によってどう見えるか。3枚ならべる。"""
    W2, H2 = 1240, 640
    s = Svg(W2, H2)
    s.text(W2 / 2.0, 40, '柱はどこまで描くのか', size=22, weight='700')
    s.text(W2 / 2.0, 66,
           '同じ1本の柱でも、図面によって描き方がまったくちがう。'
           '3つとも「必要」です。',
           size=12.5, fill='#666')

    g = 96.0                       # 1マス910mm
    for i, (px0, ttl, sub) in enumerate((
            (20, '① 平面図（1／100）', '壁の中に ■。四隅は ○ で囲む'),
            (426, '② 伏図（1／100）', '■にバツ。四隅は ■を○で囲む'),
            (832, '③ 部分詳細図（1／20）', '切った断面。120×120と書く'))):
        panel(s, px0, 90, 388, 420, ttl, sub)

    # ---------------------------------------- ① 平面図
    ax, ay = 130.0, 200.0
    for k in range(3):
        s.line(ax, ay + k * g, ax + 2 * g, ay + k * g, stroke='#eee',
               stroke_width=0.8)
        s.line(ax + k * g, ay, ax + k * g, ay + 2 * g, stroke='#eee',
               stroke_width=0.8)
    for a, b, c, d in ((0, 0, 2, 0), (0, 0, 0, 2)):          # 外壁（2本線）
        for o in (-3.0, 3.0):
            if a == c:
                s.line(ax + a * g + o, ay + b * g, ax + c * g + o,
                       ay + d * g, stroke=INK, stroke_width=1.4)
            else:
                s.line(ax + a * g, ay + b * g + o, ax + c * g,
                       ay + d * g + o, stroke=INK, stroke_width=1.4)
    for gx, gy in ((0, 0), (1, 0), (2, 0), (0, 1), (0, 2)):  # 柱の■
        s.rect(ax + gx * g - 5, ay + gy * g - 5, 10, 10, fill=INK)
    s.circle(ax, ay, 11, fill='none', stroke=INK, stroke_width=1.6)
    s.polygon([(ax + 0.5 * g, ay - 14), (ax + 0.5 * g - 7, ay - 2),
               (ax + 0.5 * g + 7, ay - 2)], fill='none', stroke=INK,
              stroke_width=1.3)
    s.text(ax + 0.5 * g + 16, ay - 6, '△ 耐力壁', size=10.5, anchor='start')
    s.text(ax - 18, ay - 20, '○ 通し柱', size=10.5, anchor='start',
           fill=ACC, weight='700')
    s.text(ax + 1.15 * g, ay + 0.5 * g, '■ 管柱', size=10.5, anchor='start')
    for i, r in enumerate((
            '・柱は<壁の中>に小さな■で描く',
            '・四すみ4本だけ○で囲む（通し柱）',
            '・耐力壁には△',
            '・3階ぶん、同じ位置に描く')):
        s.text(40, 448 + i * 22, r.replace('<', '「').replace('>', '」'),
               size=11.5, anchor='start', fill='#444')

    # ---------------------------------------- ② 伏図
    bx = 536.0
    for k in range(3):
        s.line(bx, ay + k * g, bx + 2 * g, ay + k * g, stroke='#eee',
               stroke_width=0.8)
        s.line(bx + k * g, ay, bx + k * g, ay + 2 * g, stroke='#eee',
               stroke_width=0.8)
    hw = 5.0
    for a, b, c, d in ((0, 0, 2, 0), (0, 0, 0, 2), (0, 2, 2, 2),
                       (2, 0, 2, 2)):
        for o in (-hw, hw):
            if a == c:
                s.line(bx + a * g + o, ay + b * g, bx + c * g + o,
                       ay + d * g, stroke=INK, stroke_width=1.1)
            else:
                s.line(bx + a * g, ay + b * g + o, bx + c * g,
                       ay + d * g + o, stroke=INK, stroke_width=1.1)
    r = 7.0
    for gx, gy in ((1, 0), (2, 0), (0, 1), (0, 2), (2, 2), (1, 2), (2, 1)):
        x, y = bx + gx * g, ay + gy * g
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke=INK,
               stroke_width=1.1)
        s.line(x - r, y - r, x + r, y + r, stroke=INK, stroke_width=1.3)
        s.line(x - r, y + r, x + r, y - r, stroke=INK, stroke_width=1.3)
    s.rect(bx - r, ay - r, 2 * r, 2 * r, fill='#fff', stroke=INK,
           stroke_width=1.1)
    s.circle(bx, ay, r + 5, fill='none', stroke=INK, stroke_width=1.4)
    s.text(bx - 16, ay - 22, '通し柱', size=10.5, anchor='start', fill=ACC,
           weight='700')
    s.text(bx + 1.15 * g, ay + 0.5 * g, '管柱', size=10.5, anchor='start')
    for i, r_ in enumerate((
            '・柱は「点」。記号だけ',
            '・■にバツ＝上下階が重なる管柱',
            '・■を○で囲む＝通し柱',
            '・断面寸法120×120は凡例欄へ')):
        s.text(446, 448 + i * 22, r_, size=11.5, anchor='start',
               fill='#444')

    # ---------------------------------------- ③ 部分詳細図
    cx, cy = 880.0, 190.0
    ch = 208.0
    s.rect(cx, cy, 20, ch, fill=BOARD, stroke=INK, stroke_width=1.2)
    s.rect(cx + 20, cy, 96, ch, fill=INS, stroke=INK, stroke_width=1.4)
    s.rect(cx + 116, cy, 14, ch, fill=PLY, stroke=INK, stroke_width=1.2)
    s.text(cx + 68, cy + ch / 2.0 + 5, '柱', size=15, weight='700')
    s.dim_h(cx + 20, cx + 116, cy - 12, '120', size=10.5)
    s.text(cx + 156, cy + 56, '柱 120×120', size=11.5, anchor='start',
           weight='700')
    s.line(cx + 130, cy + 62, cx + 152, cy + 52, stroke='#666',
           stroke_width=0.8)
    s.text(cx + 156, cy + 112, 'グラスウール16K', size=11,
           anchor='start')
    s.text(cx + 156, cy + 130, 't=100（断熱）', size=11, anchor='start')
    s.text(cx + 156, cy + 176, '石膏ボード t=15', size=11,
           anchor='start', fill='#777')
    for i, r_ in enumerate((
            '・切った断面がそのまま出る',
            '・名前と断面寸法を書く',
            '・断熱材は柱の間に入る',
            '・見えるのは「切った1本」だけ')):
        s.text(852, 448 + i * 22, r_, size=11.5, anchor='start',
               fill='#444')

    # ---------------------------------------- まとめ
    s.rect(20, 540, W2 - 40, 78, fill='#f1f8f2', stroke='#b9d8bd',
           stroke_width=1.0, rx=8)
    s.text(W2 / 2.0, 566,
           '★ 「柱をどこまで描くか」の答え ── 3つの図で、それぞれ1回ずつ。',
           size=13.5, weight='700', fill='#1e7e34')
    s.text(W2 / 2.0, 588,
           '平面図＝壁の中に■（＋四すみに○）　／　'
           '伏図＝記号（■にバツ・○囲み）　／　部分詳細図＝断面と寸法。',
           size=12, fill='#3d6b46')
    s.text(W2 / 2.0, 608,
           'どれか1つでも抜けると、そのぶん要求図書の不足になります。',
           size=12, fill='#3d6b46')
    return s


if __name__ == '__main__':
    for i in range(1, 10):
        draw(i).save(os.path.join(OUT, 'dh%d.svg' % i))
    real().save(os.path.join(OUT, 'dh_real.svg'))
    kansei().save(os.path.join(OUT, 'dh_kansei.svg'))
    hashira().save(os.path.join(OUT, 'dh_hashira.svg'))
    print('wrote dh1〜dh9.svg ＋ dh_real.svg')
