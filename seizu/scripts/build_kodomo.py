# -*- coding: utf-8 -*-
"""kodomo.src.html から「小学生でもわかる 答案の描き方」（kodomo.html）を作る。

図は figures/*.svg から切り抜いて PNG にし（figures/kodomo/*.png）、
{{PNG:name}} の所にデータURIで埋めこむ。説明の矢印や色は PIL で描き足す。
"""
import base64
import io
import os
import re
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(BASE, 'figures')
OUT = os.path.join(FIG, 'kodomo')
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def crop(svg, box, scale=2.0):
    """svg の (x0,y0,x1,y1) を 0〜1 の割合で切り抜いて PIL 画像にする。"""
    d = pymupdf.open(os.path.join(FIG, svg))
    pg = d[0]
    r = pg.rect
    clip = pymupdf.Rect(r.x0 + r.width * box[0], r.y0 + r.height * box[1],
                        r.x0 + r.width * box[2], r.y0 + r.height * box[3])
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip)
    return Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')


def label(im, x, y, text, color=(176, 48, 96), size=20, w=None):
    """白い箱に文字。x,y は箱の左上。"""
    dr = ImageDraw.Draw(im)
    f = font(size)
    lines = text.split('\n')
    tw = max(dr.textlength(t, font=f) for t in lines)
    th = (size + 6) * len(lines)
    dr.rectangle([x - 6, y - 4, x + tw + 6, y + th + 2], fill=(255, 255, 255),
                 outline=color, width=2)
    for i, t in enumerate(lines):
        dr.text((x, y + i * (size + 6)), t, fill=color, font=f)


def arrow(im, p, q, color=(176, 48, 96)):
    dr = ImageDraw.Draw(im)
    dr.line([p, q], fill=color, width=3)
    dr.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], fill=color)


def circle(im, cx, cy, r, color=(176, 48, 96)):
    ImageDraw.Draw(im).ellipse([cx - r, cy - r, cx + r, cy + r], outline=color,
                               width=3)


def figures():
    os.makedirs(OUT, exist_ok=True)
    F = {}

    # 1階平面図（全体）
    F['plan1'] = crop('ans2A_1f.svg', (0.17, 0.17, 0.86, 0.80), 1.4)

    # 壁・柱・窓・戸の記号（1階の玄関〜階段〜売場の角）
    im = crop('ans2A_1f.svg', (0.2, 0.44, 0.6, 0.78), 2.4)
    label(im, 420, 40, '壁＝2本線', size=18)
    label(im, 420, 560, '柱＝黒い四角', size=18)
    label(im, 560, 120, '窓＝細い線3本\n（▽は耐力壁の印）', size=18)
    arrow(im, (560, 130), (525, 40))
    F['kigou'] = im

    # 引き戸の記号
    im = crop('ans2A_1f.svg', (0.32, 0.44, 0.56, 0.62), 3.0)
    label(im, 230, 380, '①レール（細い線）＝壁の穴\n②戸の板（太い線）＝穴の横に出す\n③引込み（うすい線）＝戸のしまう所', size=17)
    arrow(im, (230, 400), (142, 470))
    arrow(im, (230, 424), (158, 470))
    arrow(im, (230, 448), (158, 330))
    F['hikido'] = im

    # 玄関の土間と上がり框
    im = crop('ans2A_1f.svg', (0.2, 0.6, 0.52, 0.8), 3.0)
    label(im, 500, 240, '上がり框（かまち）\n＝150の段差。太い1本線', size=18)
    arrow(im, (500, 262), (470, 312))
    label(im, 500, 400, '土間 GL+400\n（土足のところ）', size=18)
    arrow(im, (500, 420), (420, 420))
    F['genkan'] = im

    # 階段室の中身
    im = crop('ans2A_1f.svg', (0.2, 0.44, 0.6, 0.78), 2.4)
    S = 2.4
    G = 56 * S
    x0, x1, ybot = 122, 380, 575

    def yg(g):
        return ybot - (g - 2) * G
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    for (g0, g1), col in (((2, 3.5), (60, 160, 60, 90)), ((3.5, 5), (220, 160, 40, 80)),
                          ((5, 6), (60, 90, 200, 90))):
        dr.rectangle([x0, yg(g1), x1, yg(g0)], fill=col)
    im = Image.alpha_composite(im.convert('RGBA'), ov).convert('RGB')
    label(im, 410, 70, '青＝踊場（半階上の床）\n戸はつけない', size=18)
    label(im, 410, 250, '橙＝段（東6段↑ 西7段↑）', size=18)
    label(im, 410, 440, '緑＝ホール（床 GL+550）\n廊下の役目。戸はここ', size=18)
    F['kaidan'] = im

    # 竪穴区画と防火設備
    im = crop('ans2A_1f.svg', (0.2, 0.44, 0.52, 0.72), 3.0)
    label(im, 540, 60, '一点鎖線を階段室の\n内がわに1周＝竪穴区画', size=18)
    arrow(im, (540, 80), (470, 60))
    label(im, 540, 600, '階段室の戸には\n「防火設備」と書く', size=18)
    arrow(im, (540, 640), (440, 700))
    F['tateana'] = im

    # 2階・3階（全体）
    F['plan2'] = crop('ans2A_2f.svg', (0.17, 0.17, 0.86, 0.80), 1.4)
    F['plan3'] = crop('ans2A_3f.svg', (0.17, 0.17, 0.86, 0.80), 1.4)

    # 伏図（全体）と、梁が途中で終わる所
    F['fuse'] = crop('ansfuse_floor.svg', (0.12, 0.08, 0.9, 0.88), 1.3)
    im = crop('ansfuse_floor.svg', (0.28, 0.3, 0.62, 0.8), 2.4)
    label(im, 20, 20, '3階の廊下の壁の下の梁。\n壁が終わる所で梁も終わり、\n横の梁に載って止まる', size=18)
    F['hari'] = im
    F['koya'] = crop('ansfuse_roof.svg', (0.12, 0.08, 0.9, 0.88), 1.3)

    # 立面図
    F['ritsumen'] = crop('anselev_s.svg', (0.02, 0.05, 0.98, 0.95), 1.3)

    # 部分詳細図（Chrome で模様まで描いた PNG があれば使う）
    p = os.path.join(FIG, 'detail_render.png')
    if not os.path.exists(p):
        import subprocess
        subprocess.run(['sh', os.path.join(BASE, 'scripts', 'render.sh'),
                        os.path.join(FIG, 'detail.svg'), p, '720', '920'])
    if os.path.exists(p):
        im = Image.open(p).convert('RGB')
        label(im, 30, 300, '床の合板と仕上げは\n柱の手前で止める\n（1階も2階も同じ）', size=17)
        F['shousai'] = im

    for k, im in F.items():
        im.save(os.path.join(OUT, k + '.png'), optimize=True)
    return F


def main():
    figures()
    src = io.open(os.path.join(BASE, 'kodomo.src.html'), encoding='utf-8').read()
    css = io.open(os.path.join(BASE, 'style.css'), encoding='utf-8').read()

    def png(m):
        p = os.path.join(OUT, m.group(1) + '.png')
        b = base64.b64encode(io.open(p, 'rb').read()).decode('ascii')
        return '<img src="data:image/png;base64,%s" alt="%s">' % (b, m.group(1))
    out = src.replace('{{CSS}}', css)
    out = re.sub(r'\{\{PNG:(\w+)\}\}', png, out)
    out = re.sub(r'\{\{SVG:(\w+)\}\}', lambda m: inline_svg(m.group(1)), out)
    p = os.path.join(BASE, 'kodomo.html')
    io.open(p, 'w', encoding='utf-8').write(out)
    print('wrote %s  (%.1f KB)' % (p, len(out) / 1024.0))


if __name__ == '__main__':
    main()
