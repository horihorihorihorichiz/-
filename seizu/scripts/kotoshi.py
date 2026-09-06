# -*- coding: utf-8 -*-
"""「今年の試験・旬ネタ」ページの図。

出力：
  figures/rank4.svg          ランクⅣ（重大な不適合）の割合の推移 令和4〜7年
  figures/takasa_nigashi.svg 「軒の高さ9m以下」が来たときの型の逃がし方
数字の出典：JAEIC「設計製図の試験」の合否判定基準等について（各年）
"""
import os
from svgkit import Svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')
INK, RED, BLUE, GRN, GRY = '#111', '#c0392b', '#2f7fd0', '#3e6b47', '#8a8f88'
ACC = '#c0392b'


def rank4():
    W, H = 1240, 680
    s = Svg(W, H)
    s.text(W / 2.0, 36, '「重大な不適合」で落ちた人の割合（ランクⅣ）', size=24,
           weight='700')
    s.text(W / 2.0, 62, '出典：建築技術教育普及センター「設計製図の試験」の'
           '合否判定基準等について（令和4〜7年）', size=12.5, fill='#666')
    data = [
        ('令和4年', '保育所（木造2階）', 9.1, 52.5,
         ['未完成', '面積・保育室の床面積不足', '東側立面図でない', '架構計画']),
        ('令和5年', '専用住宅（木造2階）', 6.5, 49.9,
         ['未完成', '多目的室と台所の配置', '階段・吹抜けの計画', '矩計図の切断位置']),
        ('令和6年', 'ゲストハウス（RC2階）', 11.1, 47.0,
         ['未完成', '主要室の欠落', '席数・屋外広場', '防火設備の表示']),
        ('令和7年', 'シェアハウス（木造2階）', 25.1, 46.4,
         ['未完成', '面積違反', '主要室の欠落', '吹抜けの大きさ・避難経路']),
    ]
    x0, y0, bw, gap, scale = 80, 110, 140, 100, 12.0
    base = y0 + 330
    s.line(x0 - 30, base, x0 + 4 * (bw + gap), base, stroke='#999',
           stroke_width=1)
    for i, (yr, name, r4, r1, why) in enumerate(data):
        x = x0 + i * (bw + gap)
        h = r4 * scale
        col = ACC if i == 3 else '#c9a07a'
        s.rect(x, base - h, bw, h, fill=col, stroke='none', rx=4)
        s.text(x + bw / 2.0, base - h - 10, '%.1f%%' % r4, size=22,
               weight='700', fill=ACC if i == 3 else '#7a5a3a')
        s.text(x + bw / 2.0, base + 24, yr, size=15, weight='700')
        s.text(x + bw / 2.0, base + 44, name, size=12, fill='#555')
        s.text(x + bw / 2.0, base + 64, '合格 %.1f%%' % r1, size=12,
               fill=GRN, weight='700')
        for j, w in enumerate(why):
            s.text(x + bw / 2.0, base + 90 + j * 17, '・' + w, size=11,
                   fill='#333')
    s.text(x0 + 4 * (bw + gap) + 8, base + 4, '0%', size=11, anchor='start',
           fill='#999')
    # 右の説明
    px = 1010
    s.rect(px - 20, y0 - 10, 210, 300, fill='#fdeeee', stroke='#e0a0a0',
           stroke_width=1, rx=8)
    s.lines_text(px + 85, y0 + 22, [
        ('去年は', 13, '700', ACC),
        ('4人に1人が', 20, '700', ACC),
        ('ランクⅣ', 20, '700', ACC),
        ('', 8),
        ('ランクⅣ＝', 11.5, '400', '#333'),
        ('「うまいへた」の前に、', 11.5, '400', '#333'),
        ('条件を守れていない人。', 11.5, '400', '#333'),
        ('', 6),
        ('図面が1枚でも未完成、', 11.5, '400', '#333'),
        ('面積が範囲の外、', 11.5, '400', '#333'),
        ('部屋が1つ足りない。', 11.5, '400', '#333'),
        ('これだけで、', 11.5, '400', '#333'),
        ('図面の出来は見てもらえ', 11.5, '400', '#333'),
        ('ません。', 11.5, '400', '#333'),
    ], size=12, lh=17)
    s.text(W / 2.0, H - 22, '棒の下は、その年に「多かった」と公表された落ち方。'
           '毎年いちばん上に「未完成」がある。', size=13, fill='#444',
           weight='700')
    s.save(os.path.join(OUT, 'rank4.svg'))


def takasa_nigashi():
    """型（軒高9,350）と、軒高9m以下・最高10m以下の逃がし方をならべる。"""
    W, H = 1240, 760
    s = Svg(W, H)
    s.text(W / 2.0, 36, '「軒の高さ9m以下」が来たら、階高を少しずつ下げる',
           size=24, weight='700')
    s.text(W / 2.0, 62, '左：この教材の型　／　右：逃がし方の一例。'
           '数字はぜんぶ GL（地面）からの高さ', size=12.5, fill='#666')
    K = 0.048          # mm → px
    GY = 640           # GL の y
    cases = [
        (150, '型（いつもの数字）', 550, (3100, 2900, 2800), 0.4,
         '軒 9,350 ／ 最高 10,806', '#7a5a3a'),
        (700, '軒9m以下・最高10m以下 のとき', 500, (2900, 2700, 2700), 0.3,
         '軒 8,800 ／ 最高 9,892', GRN),
    ]
    for (x0, title, fl1, hs, pitch, res, col) in cases:
        bw = 300
        s.text(x0 + bw / 2.0, 96, title, size=16, weight='700', fill=col)
        # 地面
        s.rect(x0 - 40, GY, bw + 80, 14, fill='#e8e1d6', stroke='none')
        s.text(x0 - 46, GY + 5, 'GL 0', size=11, anchor='end', fill='#555')
        z = fl1
        levels = [('1FL', fl1)]
        for i, h in enumerate(hs):
            z += h
            levels.append((['2FL', '3FL', '軒'][i], z))
        eaves = z
        top = eaves + int(3640 * pitch)
        # 壁
        s.rect(x0, GY - eaves * K, bw, eaves * K - (fl1 * K), fill='#fbfaf8',
               stroke=INK, stroke_width=1.4)
        # 基礎〜1FL
        s.rect(x0, GY - fl1 * K, bw, fl1 * K, fill='#ddd', stroke=INK,
               stroke_width=1.0)
        # 屋根
        s.polygon([(x0 - 30, GY - eaves * K), (x0 + bw / 2.0, GY - top * K),
                   (x0 + bw + 30, GY - eaves * K)], fill='#f4e9d8',
                  stroke=INK, stroke_width=1.4)
        # 階の線と高さ
        prev = 0
        for name, zz in levels:
            y = GY - zz * K
            s.line(x0, y, x0 + bw, y, stroke=INK, stroke_width=0.9,
                   stroke_dasharray='5,3')
            s.text(x0 + bw + 40, y + 4, '%s  +%s' % (name, format(zz, ',')),
                   size=12, anchor='start', weight='700',
                   fill=col if name == '軒' else '#333')
            if prev:
                s.text(x0 + bw / 2.0, (y + GY - prev * K) / 2.0 + 5,
                       '階高 %s' % format(zz - prev, ','), size=13,
                       fill='#555')
            prev = zz
        s.text(x0 + bw / 2.0, (GY - fl1 * K + GY) / 2.0 + 5,
               '1FL +%s' % format(fl1, ','), size=11.5, fill='#333')
        yt = GY - top * K
        s.text(x0 + bw + 40, yt + 4, '最高  +%s' % format(top, ','), size=12,
               anchor='start', weight='700', fill=col)
        s.text(x0 + bw / 2.0, yt + 32,
               '%s寸勾配（3,640×%.1f＝%s）' % (
                   int(pitch * 10), pitch, format(int(3640 * pitch), ',')),
               size=11, fill='#555')
        s.rect(x0 - 10, 690, bw + 20, 36, fill='#fff', stroke=col,
               stroke_width=1.4, rx=6)
        s.text(x0 + bw / 2.0, 714, res, size=15, weight='700', fill=col)
    # 真ん中の矢印と説明
    s.text(590, 300, '→', size=44, fill=ACC, weight='700')
    s.lines_text(590, 340, [
        ('1FL を 550 → 500', 11.5, '700', ACC),
        ('1階 3,100 → 2,900', 11.5, '700', ACC),
        ('2階 2,900 → 2,700', 11.5, '700', ACC),
        ('3階 2,800 → 2,700', 11.5, '700', ACC),
        ('屋根 4寸 → 3寸', 11.5, '700', ACC),
    ], lh=18)
    s.text(W / 2.0, H - 16,
           '天井高は 1階2,500・2階2,300・3階2,300 になる（法律の最低は2,100）。'
           '1FLを450まで下げると基礎の立上りが地上271になり、告示の300以上を割るので500で止める。', size=12.5, fill='#444')
    s.save(os.path.join(OUT, 'takasa_nigashi.svg'))


if __name__ == '__main__':
    rank4()
    takasa_nigashi()
    print('wrote figures/rank4.svg, figures/takasa_nigashi.svg')
