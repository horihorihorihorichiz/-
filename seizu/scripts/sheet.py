# -*- coding: utf-8 -*-
"""予想問題 A〜F の「標準解答例」を、本物と同じ1枚もの（A3横）に組む。

・黒だけで描く（本番の答案は黒鉛筆のみ）
・左に縦書きのタイトル帯、右下に面積表と凡例欄
"""
import os
import re
import io
from svgkit import Svg, to_mono
import answers
import anssheet
import sitemap

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, '..', 'figures')
OUT = os.path.join(HERE, '..', 'sheets')
os.makedirs(OUT, exist_ok=True)

W, H = 1191.0, 842.0            # A3横（ポイント）
INK = '#111111'

# 問題ごとの中身： (記号, 副題, マス, 敷地面積, 各階面積の計算式)
POINTS = {
 'A': ['売場を道路（南）に面して最大に取り、住宅玄関と店舗出入口を分けている。',
       '店舗用便所を売場の角から直接入れるようにして、客が厨房を通らない。',
       '階段を西側の同じ位置に3階まで通し、直下率100％としている。'],
 'B': ['1階の西側を3マス幅にして廊下を通し、その北に祖母の和室6帖を置いている。',
       '和室から便所・洗面へ廊下1本で行けるようにして、段差をなくしている。',
       '間口を9マスに広げたぶん、通り芯をA・B・C・Dの4本に組みかえている。'],
 'C': ['間口が狭いので7マス×11マスとし、売場を奥へ長く取っている。',
       '水まわりを西の列にそろえて、1階から3階まで配管の位置を合わせている。',
       '通り芯を1・2・3・4・5の5本にして、奥行方向のスパンを2,730以下に抑えた。'],
 'D': ['道路が東なので売場を東面に向け、店舗出入口も東に取っている。',
       '階段を玄関の西どなりへ動かし、住宅の動線が売場を通らないようにした。',
       '通り芯の組み方を東西方向に変え、大梁のスパンを3,640以下に収めている。'],
 'E': ['南と東の2面が道路なので、店舗出入口を角に向けて開いている。',
       '東面にも窓を取り、売場と住宅の採光を両方から確保している。',
       '角地の建蔽率の割増し（法53条3項）を使える敷地としている。'],
 'F': ['道路が北なので、1階だけ南北を入れかえて店舗を北（道路側）に向けた。',
       '階段の位置は動かさないので、2階・3階は型のまま使える。',
       '住宅の居室は南側に集め、日当たりを確保している。'],
}

SPECS = [
    ('A', '商店街に建つ併用住宅（物販店舗）', 8, 10, '180.00',
     '7.28×9.10', 66.24, 66.24, 66.24),
    ('B', '祖母と暮らす併用住宅（和菓子店）', 9, 10, '224.00',
     '8.19×9.10', 74.52, 74.52, 74.52),
    ('C', '間口の狭い敷地の併用住宅（喫茶店）', 7, 11, '180.00',
     '6.37×10.01', 63.76, 63.76, 63.76),
    ('D', '東側道路の併用住宅（美容室）', 8, 10, '180.00',
     '7.28×9.10', 66.24, 66.24, 66.24),
    ('E', '南東の角地に建つ併用住宅（パン店）', 8, 10, '182.00',
     '7.28×9.10', 66.24, 66.24, 66.24),
    ('F', '北側道路の併用住宅（書店）', 8, 10, '180.00',
     '7.28×9.10', 66.24, 66.24, 66.24),
]


TITLES = ['１階平面図 兼 配置図　縮尺1／100',
          '２階平面図　縮尺1／100',
          '３階平面図　縮尺1／100']


def panel(key, i):
    """公式の標準解答例と同じ描き方で平面図を描く。"""
    d = dict(answers.PLANS[key][i])
    d['floor_label'] = 'GL＋550' if i == 0 else ''
    if i == 0:
        d['cut'] = d.get('nx', 8) - 1.0
        d['site'] = sitemap.SITES[key]
    sv = anssheet.draw(d, TITLES[i])
    t = sv.dump()
    body = t[t.index('>', t.index('<svg')) + 1:t.rindex('</svg>')]
    return body, sv.w, sv.h


def place(body, pre, x, y, sc):
    """図をIDが衝突しないように名前を付け替えて貼りこむ。"""
    for i in set(re.findall(r'id="([^"]+)"', body)):
        body = body.replace('id="%s"' % i, 'id="%s%s"' % (pre, i))
        body = body.replace('url(#%s)' % i, 'url(#%s%s)' % (pre, i))
    return ('<g transform="translate(%.2f,%.2f) scale(%.4f)">%s</g>'
            % (x, y, sc, body))


def sheet(sp):
    key, sub, nx, ny, site, keisan, a1, a2, a3 = sp
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='none', stroke=INK, stroke_width=1.4)

    # ---- 左の縦書きタイトル帯 ----
    s.line(38, 0, 38, H, stroke=INK, stroke_width=1.0)
    s.text_rot(22, 150, '二級建築士試験', -90, size=15, weight='700')
    s.text_rot(22, 330, '「設計製図の試験」', -90, size=13)
    s.text_rot(22, 560, '予想問題　%s' % key, -90, size=14, weight='700')
    s.text_rot(22, 730, '解　答　例', -90, size=13)

    # ---- 平面図3枚 ----
    pw = (W - 56) / 3.0
    top, hrow = 12.0, 448.0
    for i in range(3):
        body, bw, bh = panel(key, i)
        sc = min(pw / bw, hrow / bh)
        x = 44 + i * pw + (pw - bw * sc) / 2.0
        s.add(place(body, '%s%d' % (key.lower(), i), x, top, sc))
        if i:
            s.line(44 + i * pw - 4, top, 44 + i * pw - 4, top + hrow,
                   stroke=INK, stroke_width=0.8)
    s.line(38, 466, W - 8, 466, stroke=INK, stroke_width=1.0)

    # ---- 下半分は方眼紙（答案用紙の目盛4.55mm） ----
    gp = 12.9
    yy = 470.0
    while yy < H - 6:
        s.line(40, yy, W - 8, yy, stroke='#e0e0e0', stroke_width=0.5)
        yy += gp
    xx = 40.0
    while xx < W - 8:
        s.line(xx, 470, xx, H - 6, stroke='#e0e0e0', stroke_width=0.5)
        xx += gp

    # ---- 面積表 ----
    ty, tx, tw = 500.0, 52.0, 460.0
    rh = 30.0
    s.text(tx, ty - 8, '面　積　表', size=13, anchor='start', weight='700')
    rows = [('敷地面積', '', site),
            ('建築面積', keisan, '%.2f' % a1),
            ('床面積　1階　ア', keisan, '%.2f' % a1),
            ('　　　　2階　イ', keisan, '%.2f' % a2),
            ('　　　　3階　ウ', keisan, '%.2f' % a3),
            ('延べ面積　ア＋イ＋ウ', '', '%.2f' % (a1 + a2 + a3))]
    s.rect(tx, ty, tw, rh * len(rows), fill='#fff', stroke=INK,
           stroke_width=1.2)
    for i, (nm, ks, va) in enumerate(rows):
        y = ty + i * rh
        if i:
            s.line(tx, y, tx + tw, y, stroke=INK, stroke_width=0.8)
        s.text(tx + 8, y + 20, nm, size=11.5, anchor='start',
               weight='700' if i in (0, 5) else '400')
        if ks:
            s.text(tx + 190, y + 13, '（計算式）', size=8.5, anchor='start',
                   fill='#555')
            s.text(tx + 190, y + 25, ks, size=11, anchor='start')
        s.text(tx + tw - 30, y + 20, va, size=12.5, anchor='end',
               weight='700')
        s.text(tx + tw - 10, y + 20, '㎡', size=10, anchor='end')
    s.line(tx + 180, ty, tx + 180, ty + rh * len(rows), stroke=INK,
           stroke_width=0.8)
    s.line(tx + tw - 100, ty, tx + tw - 100, ty + rh * len(rows), stroke=INK,
           stroke_width=0.8)
    s.text(tx, ty + rh * len(rows) + 18,
           '小数点以下第3位以下は切り捨て。計算式はm単位で書く。', size=10,
           anchor='start', fill='#555')

    # ---- 凡例欄（伏図の表示記号） ----
    lx, ly, lw = 546.0, 500.0, 610.0
    s.text(lx, ly - 8, '凡　例（床伏図兼小屋伏図の表示記号）', size=13,
           anchor='start', weight='700')
    cols = [('通し柱', '120×120', 'tooshi'),
            ('1階の管柱', '120×120', 'k1'),
            ('2階の管柱', '120×120', 'k2'),
            ('重なる管柱', '—', 'kk'),
            ('胴差・床梁・桁', '120×120', 'beam'),
            ('火打梁', '90×90', 'hi'),
            ('棟木', '120×120', 'mune'),
            ('母屋', '90×90', 'moya')]
    cw = lw / len(cols)
    s.rect(lx, ly, lw, 96, fill='#fff', stroke=INK, stroke_width=1.2)
    s.line(lx, ly + 26, lx + lw, ly + 26, stroke=INK, stroke_width=0.8)
    s.line(lx, ly + 66, lx + lw, ly + 66, stroke=INK, stroke_width=0.8)
    for i, (nm, dim, kind) in enumerate(cols):
        cx = lx + i * cw
        if i:
            s.line(cx, ly, cx, ly + 96, stroke=INK, stroke_width=0.8)
        s.text(cx + cw / 2.0, ly + 18, nm, size=9.5)
        mx, my = cx + cw / 2.0, ly + 46
        a, b = cx + 6, cx + cw - 6
        if kind == 'hi':
            s.line(a, my, b, my, stroke=INK, stroke_width=1.3,
                   stroke_dasharray='9 5')
        elif kind == 'moya':
            s.line(a, my, b, my, stroke=INK, stroke_width=1.1,
                   stroke_dasharray='11 3 2 3')
            s.circle(mx, my, 4, fill=INK)
        else:
            for d in (-3.5, 3.5):
                s.line(a, my + d, b, my + d, stroke=INK, stroke_width=1.1)
            if kind == 'tooshi':
                s.rect(mx - 5, my - 5, 10, 10, fill='#fff', stroke=INK,
                       stroke_width=1.2)
                s.circle(mx, my, 10, fill='none', stroke=INK,
                         stroke_width=1.2)
            elif kind == 'k1':
                s.line(mx - 6, my - 6, mx + 6, my + 6, stroke=INK,
                       stroke_width=1.5)
                s.line(mx - 6, my + 6, mx + 6, my - 6, stroke=INK,
                       stroke_width=1.5)
            elif kind == 'k2':
                for d in (-2.5, 2.5):
                    s.line(mx + d, my - 6, mx + d, my + 6, stroke=INK,
                           stroke_width=1.5)
            elif kind == 'kk':
                s.rect(mx - 6, my - 6, 12, 12, fill='#fff', stroke=INK,
                       stroke_width=1.1)
                s.line(mx - 6, my - 6, mx + 6, my + 6, stroke=INK,
                       stroke_width=1.2)
                s.line(mx - 6, my + 6, mx + 6, my - 6, stroke=INK,
                       stroke_width=1.2)
            elif kind == 'mune':
                s.circle(mx, my, 4, fill=INK)
        s.text(cx + cw / 2.0, ly + 84, dim, size=10.5, weight='700')
    s.text(lx - 4, ly + 40, '記号', size=9, anchor='end', fill='#555')
    s.text(lx - 4, ly + 84, '寸法', size=9, anchor='end', fill='#555')

    # ---- 標準解答例のタイトル ----
    bx, by = 546.0, 634.0
    s.rect(bx, by, 290, 50, fill='#fff', stroke=INK, stroke_width=1.4)
    s.text(bx + 145, by + 32, '標　準　解　答　例', size=18, weight='700')
    s.text(bx + 306, by + 16, '予想問題　%s' % key, size=13, anchor='start',
           weight='700')
    s.text(bx + 306, by + 34, sub, size=11, anchor='start')
    s.text(bx + 306, by + 50,
           '木造3階建て　／　%dマス × %dマス（%s × %s）'
           % (nx, ny, format(nx * 910, ','), format(ny * 910, ',')),
           size=10, anchor='start', fill='#555')
    s.text(bx, by + 82,
           '※ 立面図・床伏図兼小屋伏図・部分詳細図は、別紙「共通図」を'
           '見てください。', size=10, anchor='start', fill='#555')

    # ---- 採点のポイント ----
    py_, ph = 738.0, 88.0
    s.rect(52, py_, W - 104, ph, fill='#fff', stroke=INK, stroke_width=1.0)
    s.text(64, py_ + 20, 'この解答例のポイント', size=12, anchor='start',
           weight='700')
    for i, t in enumerate(POINTS[key]):
        s.text(64, py_ + 40 + i * 17, '・' + t, size=10.5, anchor='start')
    return s


def load_file(name):
    """figures/ のSVGを読み込んで (中身, 幅, 高さ) を返す。"""
    t = io.open(os.path.join(FIG, name + '.svg'), encoding='utf-8').read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t)
    body = t[t.index('>', t.index('<svg')) + 1:t.rindex('</svg>')]
    return body, float(m.group(1)), float(m.group(2))


COMMON = [('共通図 ①　立面図と部分詳細図',
           ['anselev_s', 'detail'],
           'この2枚は「型（8マス×10マス）」のもの。'
           '問題B（9マス）・C（7マス）は間口が違うので寸法を読みかえる。'),
          ('共通図 ②　床伏図と小屋伏図',
           ['ansfuse_floor', 'ansfuse_roof'],
           '2階の床伏図と3階の床伏図は同じ組み方でよい。'
           '小屋伏図は棟が南北方向・4寸勾配。')]


def common_sheet(title, names, note):
    """立面図・部分詳細図・伏図をまとめた「共通図」。1枚に2図。"""
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='none', stroke=INK, stroke_width=1.4)
    s.line(38, 0, 38, H, stroke=INK, stroke_width=1.0)
    s.text_rot(22, 190, '二級建築士試験', -90, size=15, weight='700')
    s.text_rot(22, 400, '「設計製図の試験」', -90, size=13)
    s.text_rot(22, 640, title, -90, size=13.5, weight='700')

    cw = (W - 60) / 2.0
    for i, name in enumerate(names):
        body, bw, bh = load_file(name)
        sc = min((cw - 24) / bw, 762.0 / bh)
        x = 46 + i * cw + (cw - bw * sc) / 2.0
        s.add(place(body, 'c%d' % i, x, 18, sc))
        if i:
            s.line(46 + i * cw - 12, 16, 46 + i * cw - 12, 786, stroke=INK,
                   stroke_width=0.8)

    s.rect(52, 796, W - 104, 32, fill='none', stroke=INK, stroke_width=1.0)
    s.text(66, 817, '※ ' + note, size=11, anchor='start')
    return s


if __name__ == '__main__':
    for sp in SPECS:
        s = sheet(sp)
        path = os.path.join(OUT, 'kaitou_%s.svg' % sp[0])
        io.open(path, 'w', encoding='utf-8').write(to_mono(s.dump()))
        print('wrote', os.path.basename(path))
    for k, (ti, names, note) in enumerate(COMMON, 1):
        path = os.path.join(OUT, 'kaitou_common%d.svg' % k)
        io.open(path, 'w', encoding='utf-8').write(
            to_mono(common_sheet(ti, names, note).dump()))
        print('wrote', os.path.basename(path))
