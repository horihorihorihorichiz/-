# -*- coding: utf-8 -*-
"""howto.src.html を組み立てて『部分詳細図 かんたんガイド』を作る。"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402
from howto import STEPS                       # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WHY = [
    'よこ線が さきに あると、あとは 線と線の あいだを うめる だけに なります。'
    'いきなり 材料から かくと、かならず ズレます。',
    'はしらは 120mm。かみの うえでは たった 6mm です。'
    '三角スケールの「1／20」の めんを あてて はかって ください。',
    'きそは じめんの 上に 371、下に 300。'
    '上は「300いじょう」と きまっているので、371 なら あんしんです。',
    'どだいは きその 上に よこに ねかせる 木。'
    'くさらない ように くすりを ぬるので「防腐・防蟻」と かきます。',
    'どうさしは 1かいの はしらと 2かいの はしらを つなぐ 太い 木。'
    'せいが 300 と 大きいので、たかさに 気を つけて。',
    'いちばん うちがわの いたは ふつうの ボードでは なく'
    '「きょうか」せっこうボード。この 2文字が 点に なります。',
    'かべは ぜんぶで 15＋120＋9＋18＋16＝178mm。'
    'この 5つの すうじ だけ おぼえます。',
    'たかさは ぜんぶ「じめん」から はかります。'
    'じめんが 0、1かいの ゆかが 550、2かいの ゆかが 3,650。',
    'ひきだしせんは「ななめ → よこ → 文字」の 3ステップ。'
    '文字は 線の 上では なく、線の よこに かきます。',
]


def main():
    src = io.open(os.path.join(BASE, 'howto.src.html'),
                  encoding='utf-8').read()
    pages = []
    for i, (title, subs) in enumerate(STEPS):
        pages.append(
            '<div class="page">\n'
            '<h2 class="st"><span class="n">%d</span>%s</h2>\n'
            '<p class="lead">%s</p>\n'
            '<figure>%s</figure>\n'
            '<div class="why"><p><b>なんで？</b><br>%s</p></div>\n'
            '</div>\n'
            % (i + 1, title, '　'.join(subs),
               inline_svg('howto%d' % (i + 1)), WHY[i]))
    src = src.replace('{{STEPS}}', ''.join(pages))
    src = re.sub(r'\{\{SVG:(\w+)\}\}',
                 lambda m: inline_svg(m.group(1)), src)
    p = os.path.join(BASE, 'howto.html')
    io.open(p, 'w', encoding='utf-8').write(src)
    print('wrote %s  (%.1f KB)' % (p, len(src) / 1024.0))


if __name__ == '__main__':
    main()
