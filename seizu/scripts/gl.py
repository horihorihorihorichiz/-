# -*- coding: utf-8 -*-
"""GL（地盤面）とFL（床の高さ）の説明図。

①GLとは何か ②この型の高さの積み上げ ③GLから1FLまでの550mmの中身
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

W, H = 660, 1220
INK, GREY = '#111', '#888'
RED, BLUE, EARTH = '#c0392b', '#2f7fd0', '#8a7a5f'
CON, WOOD = '#dedede', '#e7d3a8'

s = Svg(W, H)
s.text(W / 2.0, 34, 'GL（ジーエル）ってなに？', size=21, weight='700')
s.text(W / 2.0, 57, '高さを測るときの「ものさしの0（ゼロ）の位置」', size=12,
       fill='#666')

_cid = [0]


def box(y0, y1, title, kicker):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 14, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 26, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 27, title, size=15, anchor='start', weight='700')


def ground(x0, x1, y, depth=15, step=9):
    """地面のしるし（斜線）。"""
    s.line(x0, y, x1, y, stroke=EARTH, stroke_width=1.8)
    for i in range(int((x1 - x0) / step)):
        gx = x0 + i * step
        s.line(gx, y + depth, gx + depth * 0.7, y, stroke=EARTH,
               stroke_width=0.8)


def hatch(x0, y0, x1, y1, col='#aaa', step=7):
    """コンクリートの斜線ハッチ。"""
    _cid[0] += 1
    cid = 'h%d' % _cid[0]
    g = ['<clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" '
         'height="%.1f"/></clipPath><g clip-path="url(#%s)">'
         % (cid, x0, y0, x1 - x0, y1 - y0, cid)]
    for i in range(int((x1 - x0 + y1 - y0) / step) + 2):
        gx = x0 - (y1 - y0) + i * step
        g.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width="0.6"/>' % (gx, y1, gx + (y1 - y0), y0, col))
    s.add(''.join(g) + '</g>')


# ============================================================
# ① GLとは
# ============================================================
box(74, 404, 'GLは「この敷地の地面」を0にした線', 'その1')
s.text(40, 122, 'GL ＝ Ground Level ＝ 地盤面（じばんめん）', size=14,
       anchor='start', weight='700')
s.rect(40, 136, W - 80, 66, fill='#fdecea', stroke=RED, stroke_width=1.2, rx=6)
s.lines_text(56, 158, [
    ('よくある勘違い', 12, '700', RED),
    ('GLは「海抜」ではありません。'
     'その敷地の地面を「ここを0にしよう」と決めた線です。', 12.5, '400', INK),
    ('敷地がちがえばGLの位置もちがう。その図面の中だけで通じる0です。',
     12.5, '400', INK),
], size=12, lh=20, anchor='start')

gy = 356
ground(46, 258, gy)
s.rect(84, gy - 78, 108, 78, fill='#fff', stroke=INK, stroke_width=1.5)
s.poly([(72, gy - 78), (138, gy - 112), (204, gy - 78)], stroke=INK,
       stroke_width=1.5, fill='#f4efe6')
s.rect(122, gy - 32, 20, 32, fill='#efe6d8', stroke=INK, stroke_width=1.0)
s.text(138, 240, '建物', size=11, fill='#999')

# 小さなものさし
rx, kk = 292, 0.085
s.line(rx, gy - 620 * kk, rx, gy + 470 * kk, stroke=GREY, stroke_width=1.2)
for mm, lab, col in ((550, 'GL＋550', BLUE), (0, 'GL±0', RED),
                     (-400, 'GL−400', EARTH)):
    yy = gy - mm * kk
    s.line(rx - 7, yy, rx + 7, yy, stroke=col, stroke_width=1.8)
    s.text(rx + 12, yy + 4, lab, size=12, anchor='start', fill=col,
           weight='700')
s.text(rx - 12, gy - 620 * kk + 4, '上', size=11, anchor='end', fill='#888')
s.text(rx - 12, gy + 470 * kk + 4, '下', size=11, anchor='end', fill='#888')
s.line(46, gy, 258, gy, stroke=RED, stroke_width=1.6)

s.lines_text(410, 262, [
    ('読み方はこれだけ', 12.5, '700', INK),
    ('GL＋550 … 地面から550mm上', 12, '400', '#444'),
    ('GL±0 　… 地面ちょうど', 12, '400', '#444'),
    ('GL−400 … 地面から400mm下', 12, '400', '#444'),
    ('高さはぜんぶ、この線から測る。', 12.5, '700', RED),
], size=12, lh=22, anchor='start')

# ============================================================
# ② 高さの積み上げ
# ============================================================
box(414, 862, 'この型の高さを、GLから積み上げる', 'その2')
k = 0.0345                        # 1mm あたりの表示ピクセル
bx, bw = 150, 7280 * k
by = 826                          # GL の位置


def ly(mm):
    return by - mm * k


hatch(bx, ly(386), bx + bw, ly(-300), CON)
s.rect(bx, ly(386), bw, (386 + 300) * k, fill='none', stroke=INK,
       stroke_width=1.0)
ground(60, bx, by)
ground(bx + bw, W - 176, by)
s.rect(bx, ly(9350), bw, (9350 - 550) * k, fill='#fff', stroke=INK,
       stroke_width=1.6)
for mm in (550, 3650, 6550):
    s.line(bx, ly(mm), bx + bw, ly(mm), stroke=INK, stroke_width=1.2)
s.poly([(bx - 10, ly(9350)), (bx + bw / 2.0, ly(10806)),
        (bx + bw + 10, ly(9350))], stroke=INK, stroke_width=1.6,
       fill='#f4efe6')
for lab, mm in (('1階　店舗', 2000), ('2階　住宅', 5000), ('3階　住宅', 7900)):
    s.text(bx + bw / 2.0, ly(mm), lab, size=11.5, fill='#aaa')

LV = [(10806, '最高高さ', 'GL＋10,806', '棟のてっぺん'),
      (9350, '軒高', 'GL＋9,350', '軒桁の上'),
      (6550, '3FL', 'GL＋6,550', '3階の床'),
      (3650, '2FL', 'GL＋3,650', '2階の床'),
      (550, '1FL', 'GL＋550', '1階の床'),
      (0, 'GL±0', '', '地面')]
for mm, name, gl, note in LV:
    yy = ly(mm)
    top = mm == 0
    s.line(bx + bw + 12, yy, W - 180, yy, stroke=RED if top else GREY,
           stroke_width=1.0, stroke_dasharray=None if top else '5 3')
    dy = 13 if top else -12
    s.text(W - 176, yy + dy, name, size=12.5, anchor='start', weight='700',
           fill=RED if top else INK)
    if gl:
        s.text(W - 176, yy + dy + 14, gl, size=11, anchor='start', fill=BLUE,
               weight='700')
    s.text(W - 176, yy + dy + (14 if not gl else 27), note, size=10,
           anchor='start', fill='#999')

# 左：階高
for a, b, lab in ((550, 3650, '3,100'), (3650, 6550, '2,900'),
                  (6550, 9350, '2,800')):
    s.dim_v(ly(a), ly(b), bx - 30, lab)
s.dim_v(by, ly(10806), bx - 86, '10,806')
s.text(40, 856, '左の数字＝階高（その階の床から上の階の床まで）　／　'
       '右の数字＝GLからの高さ', size=11, anchor='start', fill='#666')

# ============================================================
# ③ 550mm の中身
# ============================================================
box(872, 1220, 'なぜ床は地面より550mm高いのか', 'その3')
k2 = 0.30
zx, zw = 64, 140
zy = 1130                          # GL の位置
LAYERS = [(535, 550, 'フローリング 15', 940, '#e8cf9a'),
          (511, 535, '構造用合板 24', 962, '#f0e2c0'),
          (406, 511, '土台 105角 105', 984, WOOD),
          (386, 406, '基礎パッキン 20', 1006, '#cfd8dc'),
          (0, 386, '基礎の立上り 386', 1076, CON)]
hatch(zx, zy, zx + zw, zy + 200 * k2, CON)
s.rect(zx, zy, zw, 200 * k2, fill='none', stroke=INK, stroke_width=1.0)
for a, b, name, laby, col in LAYERS:
    y0, y1 = zy - b * k2, zy - a * k2
    s.rect(zx, y0, zw, y1 - y0, fill=col, stroke=INK, stroke_width=1.0)
    if col is CON:
        hatch(zx, y0, zx + zw, y1)
    ym = (y0 + y1) / 2.0
    s.line(zx + zw, ym, zx + zw + 14, laby - 4, stroke='#bbb',
           stroke_width=0.8)
    s.text(zx + zw + 18, laby, name, size=11.5, anchor='start')
ground(30, zx, zy)
ground(zx + zw, 240, zy)
s.line(28, zy, 250, zy, stroke=RED, stroke_width=1.6)
s.text(28, zy + 26, 'GL±0', size=11.5, anchor='start', fill=RED, weight='700')
s.text(zx + zw + 18, zy + 34, '↑ ここから下は土の中', size=10.5,
       anchor='start', fill='#666')
s.line(28, zy - 550 * k2, 250, zy - 550 * k2, stroke=BLUE, stroke_width=1.6)
s.text(28, zy - 550 * k2 - 7, '1FL ＝ GL＋550', size=11.5, anchor='start',
       fill=BLUE, weight='700')
s.dim_v(zy, zy - 550 * k2, 46, '550')

s.lines_text(376, 928, [
    ('床を地面より上げる理由', 13, '700', INK),
    ('・雨が降っても水が入らない', 12, '400', '#444'),
    ('・土の湿気で木が腐らない', 12, '400', '#444'),
    ('・シロアリが上がりにくい', 12, '400', '#444'),
    ('・床下に配管を通せる', 12, '400', '#444'),
], size=12, lh=21, anchor='start')
s.rect(370, 1036, W - 410, 78, fill='#fdecea', stroke=RED, stroke_width=1.2,
       rx=6)
s.lines_text(384, 1058, [
    ('法律で決まっている', 12, '700', RED),
    ('基礎の立上りは、地面から', 12, '400', INK),
    ('300mm以上（平12建告1347号）。', 12, '700', INK),
    ('この型は386mmなのでOK。', 12, '400', INK),
], size=12, lh=18, anchor='start')
s.text(370, 1146, '386＋20＋105＋24＋15 ＝ 550', size=13.5, anchor='start',
       weight='700', fill=BLUE)
s.text(370, 1166, '積み上げた合計が1FLの高さ。', size=11, anchor='start',
       fill='#666')

s.save(os.path.join(OUT, 'gl.svg'))
print('wrote gl.svg')
