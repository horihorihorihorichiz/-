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


if __name__ == '__main__':
    for i in range(1, 10):
        draw(i).save(os.path.join(OUT, 'dh%d.svg' % i))
    print('wrote dh1〜dh9.svg')
