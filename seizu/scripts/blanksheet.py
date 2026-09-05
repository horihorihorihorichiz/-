# -*- coding: utf-8 -*-
"""練習用の白紙答案用紙（A3横×3枚）。

本番の答案用紙はA2横1枚だが、家庭やコンビニではA3までしか出せない。
そこで A3横3枚に分け、かわりに**目盛を実寸のまま**にしてある。
　・ふつうのらん　　　　1目盛 4.55mm（1／100 で 455mm）
　・部分詳細図のらん　　1目盛 10mm （1／20 で 200mm）
※ 印刷は「実際のサイズ／100%」で。「用紙に合わせる」にすると縮尺が狂う。
"""
import os
from svgkit import Svg
from sheet import legend, GP4, GP10

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sheets')
os.makedirs(OUT, exist_ok=True)

W, H = 1190.55, 841.89          # A3横（ポイント）
INK = '#111111'
RULE = '#c8c8c8'                # 方眼の線


def grid(s, x0, y0, x1, y1, pitch):
    """左上を基準に方眼を敷く。"""
    y = y0
    while y <= y1 + 0.01:
        s.line(x0, y, x1, y, stroke=RULE, stroke_width=0.4)
        y += pitch
    x = x0
    while x <= x1 + 0.01:
        s.line(x, y0, x, y1, stroke=RULE, stroke_width=0.4)
        x += pitch


def base(no, name):
    """外わく・左の縦帯・上の見出しまで共通の下地を作る。"""
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='#ffffff', stroke='none')
    s.rect(10, 10, W - 20, H - 20, fill='none', stroke=INK, stroke_width=1.4)
    s.line(44, 10, 44, H - 10, stroke=INK, stroke_width=1.0)
    s.text_rot(27, 250, '二級建築士試験「設計製図の試験」', -90, size=13,
               weight='700')
    s.text_rot(27, 560, '練習用 答案用紙', -90, size=12)
    s.text_rot(27, 740, '%d / 3' % no, -90, size=12, weight='700')
    s.text(56, 38, name, size=15, anchor='start', weight='700')
    return s


def frame(s, x0, y0, x1, y1, label, pitch=GP4):
    """図面1枠。方眼を敷いてから、わくと題名を上に描く。"""
    grid(s, x0, y0, x1, y1, pitch)
    s.rect(x0, y0, x1 - x0, y1 - y0, fill='none', stroke=INK,
           stroke_width=1.0)
    s.rect(x0, y0, x1 - x0, 22, fill='#ffffff', stroke='none')
    s.line(x0, y0 + 22, x1, y0 + 22, stroke=INK, stroke_width=0.8)
    s.text(x0 + 10, y0 + 16, label, size=11.5, anchor='start', weight='700')


def namebox(s, x, y):
    s.rect(x, y, 300, 26, fill='#fff', stroke=INK, stroke_width=1.0)
    s.line(x + 130, y, x + 130, y + 26, stroke=INK, stroke_width=0.8)
    s.text(x + 8, y + 18, '受験番号', size=10.5, anchor='start', fill='#555')
    s.text(x + 138, y + 18, '氏名', size=10.5, anchor='start', fill='#555')


# ============================================================ 1枚目：平面図
def page1():
    s = base(1, '平面図（1／100）　目盛 4.55mm ＝ 455mm')
    namebox(s, W - 320, 18)
    x0, y0, y1 = 52.0, 58.0, H - 18
    cw = (W - 14 - x0) / 3.0
    for i, nm in enumerate(('⑴ 1階平面図 兼 配置図（1／100）',
                            '⑵ 2階平面図（1／100）',
                            '⑶ 3階平面図（1／100）')):
        frame(s, x0 + i * cw, y0, x0 + (i + 1) * cw - 6, y1, nm)
    return s


# ============================================================ 2枚目：伏図
def page2():
    s = base(2, '床伏図 兼 小屋伏図（1／100）　目盛 4.55mm')
    x0, y0 = 52.0, 58.0
    ymid = 560.0
    cw = (W - 14 - x0) / 2.0
    frame(s, x0, y0, x0 + cw - 6, ymid, '⑷ 3階床伏図（1／100）')
    frame(s, x0 + cw, y0, W - 14, ymid, '⑷ 小屋伏図（1／100）')
    s.text(x0, ymid + 26, '凡　例（床伏図兼小屋伏図の表示記号）', size=13,
           anchor='start', weight='700')
    legend(s, lx=x0 + 46, ly=ymid + 36, lw=W - 80 - x0, dims=False)
    s.text(x0 + 46, ymid + 176,
           '※ 正角材（120×120 など）の断面寸法はこの欄に。'
           '平角材（120×240 など）は 床伏図の中の梁1本ずつのわきに記入する。',
           size=10.5, anchor='start', fill='#555')
    s.text(x0 + 46, ymid + 196,
           '※ 小屋束は断面寸法の記入の対象外（問題用紙の指示による）。',
           size=10.5, anchor='start', fill='#555')
    return s


# ============================================ 3枚目：立面図・部分詳細図・面積表
def page3():
    s = base(3, '立面図・部分詳細図・面積表')
    x0 = 52.0
    xd = 700.0                                   # 部分詳細図らんの左はし
    frame(s, x0, 58.0, xd - 14, 476.0, '⑸ 立面図（1／100）　目盛 4.55mm')

    # 部分詳細図のらんだけ 10mm 方眼
    frame(s, xd, 58.0, W - 14, H - 18,
          '⑹ 部分詳細図（断面）（1／20）　目盛 10mm ＝ 200mm', pitch=GP10)

    # 面積表（数字は自分で書く）
    ty, tw, rh = 508.0, xd - 14 - x0, 34.0
    rows = ['敷地面積', '建築面積', '床面積　1階　ア', '　　　　2階　イ',
            '　　　　3階　ウ', '延べ面積　ア＋イ＋ウ']
    s.text(x0, ty - 10, '⑺ 面　積　表', size=13, anchor='start', weight='700')
    s.rect(x0, ty, tw, rh * len(rows), fill='#fff', stroke=INK,
           stroke_width=1.2)
    for i, nm in enumerate(rows):
        y = ty + i * rh
        if i:
            s.line(x0, y, x0 + tw, y, stroke=INK, stroke_width=0.8)
        s.text(x0 + 10, y + 26, nm, size=13, anchor='start',
               weight='700' if i in (0, len(rows) - 1) else '400')
        s.text(x0 + tw - 14, y + 26, '㎡', size=11, anchor='end', fill='#555')
    s.line(x0 + 250, ty, x0 + 250, ty + rh * len(rows), stroke=INK,
           stroke_width=0.8)
    s.line(x0 + tw - 130, ty, x0 + tw - 130, ty + rh * len(rows), stroke=INK,
           stroke_width=0.8)
    s.text(x0 + 258, ty + 16, '（計算式）', size=9.5, anchor='start',
           fill='#888')
    s.text(x0, ty + rh * len(rows) + 22,
           '※ 計算式は m 単位で書く。小数点以下第3位以下は切り捨て。',
           size=10.5, anchor='start', fill='#555')
    s.text(x0, ty + rh * len(rows) + 42,
           '※ 計画の要点等（⑻）は、別の用紙に3問ぶんの罫線を引いて練習する。',
           size=10.5, anchor='start', fill='#555')
    return s


if __name__ == '__main__':
    for i, fn in enumerate((page1, page2, page3), 1):
        fn().save(os.path.join(OUT, 'renshu%d.svg' % i))
    print('wrote sheets/renshu1〜3.svg  （A3横・目盛4.55mm / 10mm 実寸）')
