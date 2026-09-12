# -*- coding: utf-8 -*-
"""⑻ 計画の要点等（記述）だけを、読める大きさで1冊にする。

答案用紙の中の記述らんは字が小さいので、覚えるとき用に別のPDFにする。
中身は mondai.py の解答例そのままなので、答案と食いちがわない。
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mondai                                    # noqa: E402

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(BASE, 'kijutsu.html')

FONT = ("'Hiragino Sans','Hiragino Kaku Gothic ProN','Noto Sans JP',"
        "'Yu Gothic',Meiryo,sans-serif")

CSS = """<style>
@page{size:A4;margin:16mm 15mm}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:%s;font-size:13px;line-height:1.95;color:#1b1e1b;background:#fff}
.wrap{max-width:180mm;margin:0 auto}
.cover{display:flex;flex-direction:column;justify-content:center;
  border-bottom:3px solid #b03060;margin-bottom:8mm;padding-bottom:8px}
.cover .k{font-size:12px;letter-spacing:.28em;color:#b03060;font-weight:700}
.cover h1{font-size:30px;margin:8px 0 6px}
.cover p{font-size:13px;color:#555}
h2{font-size:18px;margin:0 0 8px;padding:6px 0 6px 12px;
  border-left:6px solid #b03060;break-after:avoid}
h2 small{font-size:13px;color:#666;font-weight:400;margin-left:10px}
.set{margin-bottom:8mm}
.qa{break-inside:avoid;margin-bottom:5mm}
.q{background:#f3efe7;border-radius:7px;padding:7px 12px;font-weight:700;
  font-size:14px;margin:10px 0 6px;break-after:avoid}
.a{font-size:13px;line-height:2.1;text-align:justify;padding:0 2px 0 12px;
  border-left:2px solid #e0dcd2}
.n{font-size:11.5px;color:#666;margin-top:4px;padding-left:12px}
.parts{background:#fff8e1;border:1px solid #e0c060;border-radius:9px;
  padding:11px 15px;font-size:12.5px;margin-bottom:9mm;line-height:1.95}
.parts b{color:#6b5200}
.foot{margin-top:8mm;padding-top:6px;border-top:1px solid #ddd;
  font-size:11px;color:#666}
.pb{break-before:page}
</style>""" % FONT


def plain(t):
    t = t.replace('m<sup>2</sup>', '㎡').replace('<sup>2</sup>', '²')
    return re.sub(r'<[^>]+>', '', t)


def main():
    o = ['<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">',
         '<title>計画の要点等（記述）だけの冊子</title>', CSS,
         '</head><body><div class="wrap">',
         '<div class="cover"><div class="k">二級建築士 設計製図　'
         '商店街に建つ併用住宅（木造3階建て）</div>',
         '<h1>⑻ 計画の要点等 ── 記述だけ</h1>',
         '<p>答案用紙の記述らんは字が小さいので、覚えるとき用に'
         'この1冊にまとめました。予想問題A〜Fの解答例そのままです。</p></div>',
         '<div class="parts"><b>どの答えも、この4つの部品を順につなぐだけ。</b><br>'
         '① なにをしたか　→　② 数字を入れる　→　③ なぜそうしたか　→　'
         '④ どうなるか（「これにより」で始める）<br>'
         '文章を丸暗記せず、<b>この順番と、分野ごとの部品（数字と言葉）</b>を'
         '覚えてください。本番は<b>自分が描いた図面を見ながら</b>書きます。'
         '図と文章が食いちがうと減点です。</div>']
    for i, sp in enumerate(mondai.SPECS):
        o.append('<div class="set%s">' % (' pb' if i else ''))
        o.append('<h2>予想問題 %s<small>%s</small></h2>'
                 % (sp['tag'], sp['name']))
        for k, (q, a) in enumerate(sp['youten']):
            o.append('<div class="qa">')
            o.append('<div class="q">%s　%s</div>' % ('①②③'[k], plain(q)))
            o.append('<div class="a">%s</div>' % plain(a))
            o.append('<div class="n">%d字</div></div>' % len(plain(a)))
        o.append('</div>')
    o.append('<div class="foot">この記述は、同じ予想問題の標準解答例の図面と'
             '合わせて作ってあります。本番では、問題文の問いと'
             '自分の図面に合わせて書きかえてください。</div>')
    o.append('</div></body></html>')
    io.open(OUT, 'w', encoding='utf-8').write(''.join(o))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
