# -*- coding: utf-8 -*-
"""答案で使う記号の一覧。公式の標準解答例で使われている描き方に合わせる。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
CW, CH = 176, 104
COLS = 4
ML, MT = 26, 118
INK = '#111'


def cell(s, i, title, memo=''):
    c, r = i % COLS, i // COLS
    x, y = ML + c * CW, MT + r * CH
    s.rect(x, y, CW - 8, CH - 8, fill='#fff', stroke='#ddd',
           stroke_width=0.8, rx=5)
    s.text(x + 10, y + 17, title, size=11.5, weight='700', anchor='start')
    if memo:
        s.text(x + 10, y + CH - 16, memo, size=9.5, fill='#777',
               anchor='start')
    return x, y


def wall(s, x, y, w, vert=False, t=5):
    """壁は2本線で描く。"""
    if vert:
        s.line(x - t / 2, y, x - t / 2, y + w, stroke=INK, stroke_width=1.3)
        s.line(x + t / 2, y, x + t / 2, y + w, stroke=INK, stroke_width=1.3)
    else:
        s.line(x, y - t / 2, x + w, y - t / 2, stroke=INK, stroke_width=1.3)
        s.line(x, y + t / 2, x + w, y + t / 2, stroke=INK, stroke_width=1.3)


def draw():
    ROWS = 5
    W = ML * 2 + CW * COLS
    H = MT + CH * ROWS + 40
    s = Svg(W, H)
    s.text(W / 2.0, 38, '答案で使う記号の一覧', size=22, weight='700')
    s.text(W / 2.0, 62,
           '公式の標準解答例で使われている描き方。本番は黒鉛筆だけなので、'
           '色は使わず記号で区別する。', size=12, fill='#666')
    s.text(W / 2.0, 84,
           '★ 要求図書に「通し柱を○印で囲み、耐力壁には△印を付ける」'
           '「出入口には▲印を付ける」と明記されている。忘れると減点。',
           size=12, fill='#b03060', weight='700')

    i = 0
    # ---- 構造 ----
    x, y = cell(s, i, '① 通し柱', '小さな■を○で囲む'); i += 1
    wall(s, x + 40, y + 56, 70)
    wall(s, x + 75, y + 36, 44, vert=True)
    s.rect(x + 71, y + 52, 8, 8, fill=INK)
    s.circle(x + 75, y + 56, 12, fill='none', stroke=INK, stroke_width=1.4)

    x, y = cell(s, i, '② 管柱', '小さな■のみ'); i += 1
    wall(s, x + 40, y + 56, 70)
    wall(s, x + 75, y + 36, 44, vert=True)
    s.rect(x + 71, y + 52, 8, 8, fill=INK)

    x, y = cell(s, i, '③ 耐力壁', '壁のそばに△印'); i += 1
    wall(s, x + 26, y + 52, 100)
    for dx in (52, 96):
        s.polygon([(x + dx, y + 64), (x + dx - 7, y + 76),
                   (x + dx + 7, y + 76)], fill='none', stroke=INK,
                  stroke_width=1.3)
    s.text(x + 74, y + 44, '△は壁の外側へ', size=9, fill='#888')

    x, y = cell(s, i, '④ 出入口の▲印', '道路から敷地・建物へ'); i += 1
    wall(s, x + 26, y + 56, 100)
    s.line(x + 62, y + 56, x + 88, y + 56, stroke='#fff', stroke_width=6)
    s.polygon([(x + 75, y + 34), (x + 67, y + 48), (x + 83, y + 48)],
              fill=INK)
    s.line(x + 75, y + 48, x + 75, y + 62, stroke=INK, stroke_width=1.2)

    # ---- 切断位置 ----
    x, y = cell(s, i, '⑤ 部分詳細図の切断位置', '記号と方向の矢印'); i += 1
    s.line(x + 24, y + 52, x + 132, y + 52, stroke=INK, stroke_width=1.4,
           stroke_dasharray='14 4 3 4')
    for dx, sgn in ((36, 1), (120, -1)):
        s.line(x + dx, y + 52, x + dx, y + 52 + 16 * sgn, stroke=INK,
               stroke_width=2.0)
        s.polygon([(x + dx, y + 52 + 22 * sgn),
                   (x + dx - 5, y + 52 + 13 * sgn),
                   (x + dx + 5, y + 52 + 13 * sgn)], fill=INK)
        s.circle(x + dx, y + 52 - 14 * sgn, 9, fill='#fff', stroke=INK,
                 stroke_width=1.2)
        s.text(x + dx, y + 52 - 10 * sgn, 'A', size=10, weight='700')

    x, y = cell(s, i, '⑥ 床高の書き方', '室名の下にGL+○○'); i += 1
    s.text(x + CW / 2 - 4, y + 50, '玄　関', size=13, weight='700')
    s.text(x + CW / 2 - 4, y + 68, 'GL＋480', size=12)

    x, y = cell(s, i, '⑦ 吹抜け', '対角線の破線＋文字'); i += 1
    s.rect(x + 40, y + 32, 70, 46, fill='none', stroke=INK,
           stroke_width=1.0)
    s.line(x + 40, y + 32, x + 110, y + 78, stroke=INK, stroke_width=1.2,
           stroke_dasharray='7 5')
    s.line(x + 110, y + 32, x + 40, y + 78, stroke=INK, stroke_width=1.2,
           stroke_dasharray='7 5')

    x, y = cell(s, i, '⑧ 壁は2本線', '塗りつぶさない'); i += 1
    wall(s, x + 26, y + 46, 100, t=6)
    s.dim_h(x + 26, x + 126, y + 74, '壁の厚み', size=9)

    # ---- 建具 ----
    x, y = cell(s, i, '⑨ 片開き戸', '四分円の弧'); i += 1
    wall(s, x + 24, y + 60, 34)
    wall(s, x + 108, y + 60, 44)
    s.line(x + 58, y + 60, x + 58, y + 24, stroke=INK, stroke_width=1.2)
    s.path('M %d %d A 36 36 0 0 1 %d %d' % (x + 58, y + 24, x + 94, y + 60),
           stroke='#888', stroke_width=1.0)

    x, y = cell(s, i, '⑩ 引違い戸・引戸', '壁と平行に2本'); i += 1
    wall(s, x + 24, y + 60, 30)
    wall(s, x + 122, y + 60, 30)
    s.line(x + 54, y + 55, x + 100, y + 55, stroke=INK, stroke_width=1.2)
    s.line(x + 76, y + 65, x + 122, y + 65, stroke=INK, stroke_width=1.2)

    x, y = cell(s, i, '⑪ 引違い窓', '壁の中に2本線'); i += 1
    wall(s, x + 24, y + 60, 128, t=6)
    s.line(x + 52, y + 60, x + 124, y + 60, stroke='#fff', stroke_width=7)
    s.line(x + 52, y + 57, x + 124, y + 57, stroke=INK, stroke_width=1.1)
    s.line(x + 52, y + 63, x + 124, y + 63, stroke=INK, stroke_width=1.1)
    s.line(x + 52, y + 54, x + 52, y + 66, stroke=INK, stroke_width=1.1)
    s.line(x + 124, y + 54, x + 124, y + 66, stroke=INK, stroke_width=1.1)

    x, y = cell(s, i, '⑫ 防火設備', '建具のそばに記号'); i += 1
    wall(s, x + 24, y + 60, 40)
    wall(s, x + 110, y + 60, 42)
    s.line(x + 64, y + 60, x + 64, y + 28, stroke=INK, stroke_width=1.2)
    s.path('M %d %d A 34 34 0 0 1 %d %d' % (x + 64, y + 28, x + 98, y + 60),
           stroke='#888', stroke_width=1.0)
    s.text(x + 100, y + 40, '防火設備', size=9.5, anchor='start', fill='#444')

    # ---- 家具・設備 ----
    x, y = cell(s, i, '⑬ テーブルと椅子', '矩形＋丸'); i += 1
    s.rect(x + 52, y + 42, 60, 30, fill='none', stroke=INK, stroke_width=1.1)
    for dx in (62, 82, 102):
        s.circle(x + dx, y + 32, 7, fill='none', stroke=INK, stroke_width=1.0)
        s.circle(x + dx, y + 82, 7, fill='none', stroke=INK, stroke_width=1.0)

    x, y = cell(s, i, '⑭ ソファ', '背もたれを1本'); i += 1
    s.rect(x + 44, y + 44, 84, 26, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 44, y + 52, x + 128, y + 52, stroke=INK, stroke_width=1.0)
    s.line(x + 68, y + 52, x + 68, y + 70, stroke=INK, stroke_width=0.9)
    s.line(x + 104, y + 52, x + 104, y + 70, stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '⑮ ベッド', '枕側に線を1本'); i += 1
    s.rect(x + 56, y + 30, 52, 56, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 56, y + 44, x + 108, y + 44, stroke=INK, stroke_width=1.0)
    s.rect(x + 66, y + 33, 32, 9, fill='none', stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '⑯ 台所の設備', '流し・コンロ・冷蔵庫'); i += 1
    s.rect(x + 22, y + 44, 100, 22, fill='none', stroke=INK, stroke_width=1.1)
    s.circle(x + 38, y + 55, 8, fill='none', stroke=INK, stroke_width=1.0)
    for dx in (78, 96):
        for dy in (50, 60):
            s.circle(x + dx, y + dy, 3.6, fill='none', stroke=INK,
                     stroke_width=0.9)
    s.rect(x + 126, y + 42, 26, 26, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 126, y + 42, x + 152, y + 68, stroke=INK, stroke_width=0.9)
    s.line(x + 152, y + 42, x + 126, y + 68, stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '⑰ 洋式便器', '楕円＋タンク'); i += 1
    s.rect(x + 60, y + 34, 26, 9, fill='none', stroke=INK, stroke_width=1.1)
    s.circle(x + 73, y + 58, 13, fill='none', stroke=INK, stroke_width=1.1)
    s.rect(x + 96, y + 40, 18, 12, fill='none', stroke=INK, stroke_width=1.0)
    s.text(x + 118, y + 50, '手洗', size=9, anchor='start', fill='#888')

    x, y = cell(s, i, '⑱ 浴槽', '矩形に×印'); i += 1
    s.rect(x + 46, y + 36, 62, 44, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 46, y + 36, x + 108, y + 80, stroke=INK, stroke_width=0.9)
    s.line(x + 108, y + 36, x + 46, y + 80, stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '⑲ 洗面台・洗濯機', '丸と□に×'); i += 1
    s.rect(x + 30, y + 42, 34, 26, fill='none', stroke=INK, stroke_width=1.1)
    s.circle(x + 47, y + 55, 9, fill='none', stroke=INK, stroke_width=1.0)
    s.rect(x + 86, y + 42, 30, 26, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 86, y + 42, x + 116, y + 68, stroke=INK, stroke_width=0.9)
    s.line(x + 116, y + 42, x + 86, y + 68, stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '⑳ 下足入れ・収納', '斜線を1本'); i += 1
    s.rect(x + 26, y + 42, 46, 22, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 26, y + 64, x + 72, y + 42, stroke=INK, stroke_width=0.9)
    s.rect(x + 92, y + 42, 46, 22, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 92, y + 64, x + 138, y + 42, stroke=INK, stroke_width=0.9)

    x, y = cell(s, i, '㉑ 畳と押入れ', '和室'); i += 1
    for k in range(3):
        s.rect(x + 24 + k * 22, y + 34, 20, 44, fill='none', stroke=INK,
               stroke_width=1.0)
    s.rect(x + 96, y + 34, 44, 20, fill='none', stroke=INK, stroke_width=1.1)
    s.line(x + 96, y + 54, x + 140, y + 34, stroke=INK, stroke_width=0.9)
    s.text(x + 118, y + 70, '押入れ', size=9, fill='#888')

    x, y = cell(s, i, '㉒ 陳列棚・レジ', '店舗'); i += 1
    for dy in (34, 48):
        s.rect(x + 24, y + dy, 62, 10, fill='none', stroke=INK,
               stroke_width=1.0)
    s.rect(x + 100, y + 40, 40, 20, fill='none', stroke=INK, stroke_width=1.1)
    s.text(x + 120, y + 74, 'レジ', size=9.5, fill='#888')

    s.text(W / 2.0, H - 14,
           '本番は黒鉛筆のみ。色は使えないので、線の太さと記号で描き分ける。',
           size=11.5, fill='#555')
    return s


if __name__ == '__main__':
    draw().save(os.path.join(OUT, 'symbols.svg'))
    print('wrote symbols.svg')
