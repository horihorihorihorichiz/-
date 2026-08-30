# -*- coding: utf-8 -*-
"""計画の要点等（記述）の書き方。絵ではなく文章で答えるらん。"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
W, H = 700, 1225
INK, RED, BLUE, GRN, GRY = '#111', '#c0392b', '#2f7fd0', '#3e6b47', '#8a8f88'

s = Svg(W, H)
s.text(W / 2.0, 32, '計画の要点等の書き方', size=21, weight='700')
s.text(W / 2.0, 55, '絵ではなく、日本語の文章で答える。図面より点になりやすい',
       size=12, fill='#666')


def band(y0, y1, kicker, title):
    s.rect(0, y0, W, y1 - y0, fill='#fbfaf8', stroke='none')
    s.rect(28, y0 + 12, 46, 17, fill='#eee5da', stroke='none', rx=3)
    s.text(51, y0 + 24, kicker, size=10, fill='#9a6b3a', weight='700')
    s.text(84, y0 + 25, title, size=14.5, anchor='start', weight='700')


# ============================================================
band(74, 330, 'その1', '答案用紙のどこに書くの？')

Q = ['① 木造3階建てとするに当たり、構造計画上工夫した点',
     '② 店舗部分と住宅部分の動線計画について工夫した点',
     '③ 防火及び避難について配慮した点']
for i, q in enumerate(Q):
    by = 120 + i * 62
    s.rect(70, by, 360, 54, fill='#fff', stroke=INK, stroke_width=1.2)
    s.rect(70, by, 360, 16, fill='#f3efe9', stroke=INK, stroke_width=1.2)
    s.text(76, by + 12, q, size=9.5, anchor='start', weight='700')
    for k in range(3):
        s.line(78, by + 28 + k * 11, 422, by + 28 + k * 11,
               stroke='#ccc', stroke_width=0.7)

NOTE = [('3問ぜんぶ文章。絵は1つも描かない', INK),
        ('目安は25分。時間割は 15:20〜15:45', INK),
        ('①②③がなにを聞くかは当日わかる', GRY),
        ('でも聞かれる分野はだいたい決まっている', GRY),
        ('白紙だけは絶対にダメ。1行でも書く', RED)]
for i, (n, c) in enumerate(NOTE):
    s.circle(456, 128 + i * 26, 3, fill=c)
    s.text(468, 132 + i * 26, n, size=11, anchor='start', fill=c,
           weight='700' if c == RED else '400')
s.text(70, 316, '※ 図面が下手でも、ここは書けば点になります。'
       '「絵の勝負」ではないので、いちばん取りやすいところです。',
       size=11, anchor='start', fill='#555')

# ============================================================
band(340, 645, 'その2', '文章は4つの部品をつなぐだけ')

PART = [('1', 'なにをしたか', GRN,
         '1階から3階まで柱の位置をすべてそろえた'),
        ('2', '数字を入れる', BLUE,
         '四隅は120mm角の通し柱、梁の最大スパンは3,640mm'),
        ('3', 'なぜそうしたか', '#9a6b3a',
         '直下率を高め、地震の力をまっすぐ下へ流すため'),
        ('4', 'どうなるか', RED,
         '地震力・風圧力を耐力壁へ確実に伝えられる')]
for i, (n, lab, col, frag) in enumerate(PART):
    y = 380 + i * 44
    s.circle(84, y - 4, 12, fill=col)
    s.text(84, y, n, size=12, fill='#fff', weight='700')
    s.text(106, y, lab, size=12.5, anchor='start', weight='700', fill=col)
    s.text(232, y, frag, size=11.5, anchor='start', fill='#333')
    if i < 3:
        s.line(84, y + 10, 84, y + 26, stroke='#ccc', stroke_width=1.0)

s.rect(70, 560, 560, 74, fill='#fff', stroke='#ddd', stroke_width=1.0)
s.text(84, 580, 'つなげると、そのまま1つの文になります', size=11.5,
       anchor='start', weight='700')
for i, ln in enumerate(
        ['1階から3階まで柱の位置をすべてそろえ、直下率を高めた。四隅は',
         '120mm角の通し柱とし、梁の最大スパンは3,640mmに抑えている。これに',
         'より地震力及び風圧力を耐力壁へ確実に伝達させることができる。']):
    s.text(84, 599 + i * 15, ln, size=11, anchor='start', fill='#333')

# ============================================================
band(655, 975, 'その3', 'よく出る5つの分野と、つかえる部品')

FLD = [('構造', GRN,
        ['直下率を高める／通し柱120mm角',
         'スパンは3,640mm以下／剛床t=24／耐力壁を偏らせない']),
       ('動線', BLUE,
        ['店の出入口と住宅の玄関を分ける',
         '売場を通らずに上階へ行ける／搬入は背面の勝手口から']),
       ('防火・避難', RED,
        ['45分準耐火建築物／階段室を竪穴区画',
         '強化石膏ボードt=15／2方向に逃げられる']),
       ('高齢者', '#9a6b3a',
        ['寝室を1階に置く／段差をつくらない',
         '廊下・出入口の有効幅780mm以上／手すりの下地を入れる']),
       ('環境', '#6b4f9a',
        ['南面に大きな開口／通気層で湿気を上へ',
         'グラスウールt=100／越屋根や高窓で風を抜く'])]
for i, (nm, col, rows) in enumerate(FLD):
    y = 712 + i * 52
    s.rect(70, y - 15, 96, 24, fill=col, stroke='none', rx=4)
    s.text(118, y + 1, nm, size=12, fill='#fff', weight='700')
    for k, r in enumerate(rows):
        s.text(180, y + k * 16, r, size=11, anchor='start', fill='#333')
s.text(70, 960, '※ 丸暗記しない。この「部品」を覚えておいて、'
       '当日その場で組み立てます。', size=11, anchor='start', fill='#555')

# ============================================================
band(985, 1225, 'その4', 'よくある間違い')
NG = [('白紙で出す', '1行でも書けば点の可能性がある。ゼロ行はゼロ点'),
      ('自分の図面と食いちがう',
       '図では階段が北なのに「南に配置した」と書く。図を見ながら書く'),
      ('数字が1つもない',
       '「じょうぶにした」だけでは点にならない。120・3,640・t=24 を入れる'),
      ('どこにでも通じる一般論',
       '「安全に配慮した」だけはダメ。この建物の話を書く'),
      ('図面に時間を使いすぎて時間切れ',
       '25分は必ず残す。図面の仕上げより、ここを書くほうが先')]
for i, (t_, m) in enumerate(NG):
    y = 1032 + i * 38
    s.text(70, y, '×', size=15, anchor='start', fill=RED, weight='700')
    s.text(92, y, t_, size=12.5, anchor='start', weight='700')
    s.text(92, y + 16, m, size=10.5, anchor='start', fill='#555')

s.save(os.path.join(OUT, 'youten.svg'))
print('wrote figures/youten.svg')
