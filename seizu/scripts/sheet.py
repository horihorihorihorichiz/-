# -*- coding: utf-8 -*-
"""予想問題 A〜F の「標準解答例」を、本番と同じ A2横1枚 に組む。

本番の答案用紙は A2横1枚。要求図書がぜんぶ同じ紙に載るので、
この解答例も1枚にまとめる。枠割りは次のとおり。

  上の段 … ⑴1階平面図兼配置図　⑵2階平面図　⑶3階平面図　／ 右に ⑺面積表
  中の段 … ⑷床伏図　⑷小屋伏図　⑸南側立面図　⑹部分詳細図　／ 右に ⑻計画の要点等
  下の段 … 凡例欄（床伏図兼小屋伏図の表示記号）　／ 右にタイトル欄

・黒だけで描く（本番の答案は黒鉛筆のみ）
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

W, H = 1684.0, 1191.0           # A2横（ポイント）
GP4 = 4.55 / 0.3528             # 目盛4.55mm を実寸のポイントに
GP10 = 10.0 / 0.3528            # 部分詳細図らんの目盛10mm

# 縮尺をそろえる。1ポイント = 0.3528mm
#   1/100 の図 … 内部の1マス56px が 910/100 mm になる倍率
#   1/20  の図 … 内部の1mm 0.30px が 1/20 mm になる倍率
SC100 = (910 / 100.0 / 0.3528) / 56.0
SC20 = (1 / 20.0 / 0.3528) / 0.30
INK = '#111111'

# ---- A2横1枚の枠割り（ポイント）
CX0, CX1 = 54.0, 1674.0                 # 中身を置ける左右
R1Y, R1H = 12.0, 560.0                  # 上の段：平面図3枚＋面積表
R2Y, R2H = 580.0, 430.0                 # 中の段：伏図2・立面図・部分詳細図＋要点
R3Y, R3H = 1018.0, 168.0                # 下の段：凡例欄＋タイトル欄
COL1X = 1462.0                          # 上の段の右のはしら（面積表）
COL2X = 1400.0                          # 中の段の右のはしら（計画の要点等）

# 問題ごとの中身： (記号, 副題, マス, 敷地面積, 各階面積の計算式)
POINTS = {
 'A': ['売場を道路（南）に面して最大に取り、住宅玄関と店舗出入口を分けている。',
       '店舗用便所を売場の角から直接入れるようにして、客が厨房を通らない。',
       '階段を西側の同じ位置に3階まで通し、直下率100％としている。'],
 'B': ['1階の西側を3マス幅にして廊下を通し、その北に母の和室6帖を置いている。',
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
    ('B', '母と暮らす併用住宅（和菓子店）', 9, 10, '224.00',
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


TITLES = ['⑴　１階平面図 兼 配置図　縮尺1／100',
          '⑵　２階平面図　縮尺1／100',
          '⑶　３階平面図　縮尺1／100']


def panel(key, i):
    """公式の標準解答例と同じ描き方で平面図を描く。"""
    d = dict(answers.PLANS[key][i])
    d['floor_label'] = 'GL＋550' if i == 0 else ''
    if i == 0:
        d['cut'] = d.get('nx', 8) - 1.0
        d['site'] = sitemap.SITES[key]
    # 2階・3階は敷地を描かないので、建物ぶんの大きさだけにする
    # （本番の答案用紙でも、敷地が入るのは1階平面図兼配置図だけ）
    sv = anssheet.draw(d, '')
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


def legend(s, lx=750.0, ly=748.0, lw=880.0, dims=True, note=True):
    """伏図の凡例欄。dims=False なら寸法らんを空にする（練習用紙）。"""
    s.text(lx, ly - 10, '凡　例（床伏図兼小屋伏図の表示記号）', size=15,
           anchor='start', weight='700')
    cols = [('通し柱', '120×120', 'tooshi'),
            ('1階の管柱', '120×120', 'k1'),
            ('2階の管柱', '120×120', 'k2'),
            ('重なる管柱', '—', 'kk'),
            ('胴差・桁（正角材）', '120×120', 'beam'),
            ('同上（平角材）', '図中に記入', 'hira'),
            ('同上（丸太材）', '図中に記入', 'maru'),
            ('火打梁', '90×90', 'hi'),
            ('棟木', '120×120', 'mune'),
            ('母屋・小屋束', '90×90', 'moya')]
    cw = lw / len(cols)
    s.rect(lx, ly, lw, 118, fill='#fff', stroke=INK, stroke_width=1.2)
    s.line(lx, ly + 32, lx + lw, ly + 32, stroke=INK, stroke_width=0.8)
    s.line(lx, ly + 82, lx + lw, ly + 82, stroke=INK, stroke_width=0.8)
    for i, (nm, dim, kind) in enumerate(cols):
        cx = lx + i * cw
        if i:
            s.line(cx, ly, cx, ly + 118, stroke=INK, stroke_width=0.8)
        s.text(cx + cw / 2.0, ly + 21, nm, size=9)
        mx, my = cx + cw / 2.0, ly + 57
        a, b = cx + 6, cx + cw - 6
        if kind == 'hi':
            s.line(a, my, b, my, stroke=INK, stroke_width=1.3,
                   stroke_dasharray='9 5')
        elif kind == 'hira':                     # 平角材（せいが幅より大きい）
            s.polygon([(a, my - 4), (b, my - 4), (b - 8, my + 4),
                       (a + 8, my + 4)], fill='#fff', stroke=INK,
                      stroke_width=1.1)
        elif kind == 'maru':                     # 丸太材
            s.path('M %.1f %.1f Q %.1f %.1f %.1f %.1f Q %.1f %.1f %.1f %.1f'
                   % (a, my, mx, my - 7, b, my - 1, mx, my + 5, a, my),
                   fill='#fff', stroke=INK, stroke_width=1.1)
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
        if dims:
            s.text(cx + cw / 2.0, ly + 105, dim,
                   size=11 if len(dim) < 8 else 9.5, weight='700')
    s.text(lx - 6, ly + 62, '記号', size=10.5, anchor='end', fill='#555')
    s.text(lx - 6, ly + 105, '寸法', size=10.5, anchor='end', fill='#555')
    if note:
        s.text(lx, ly + 138, '※ 平角材（120×240 など）の断面寸法は、この欄ではなく '
               '床伏図の中の梁1本ずつのわきに記入する。', size=11,
               anchor='start', fill=INK)
    else:
        s.text(lx, ly + 122, '※ 平角材（120×240 など）の断面寸法は、'
               '床伏図の中の梁1本ずつのわきに記入する。', size=8.5,
               anchor='start', fill='#555')


def wrap_text(s, x, y, w, text, size=8.4, lh=11.0, color=INK, maxlines=99):
    """指定の幅で折り返して書く。戻り値は次の行のy。"""
    per = max(4, int(w / (size * 1.02)))
    line, n = '', 0
    for ch in text:
        line += ch
        if len(line) >= per:
            s.text(x, y, line, size=size, anchor='start', fill=color)
            y += lh
            line = ''
            n += 1
            if n >= maxlines:
                return y
    if line:
        s.text(x, y, line, size=size, anchor='start', fill=color)
        y += lh
    return y


def frame(s, x, y, w, h, title, sub=''):
    """図面1枠。細い枠線と、左上の題名。"""
    s.rect(x, y, w, h, fill='none', stroke=INK, stroke_width=0.8)
    s.text(x + 8, y + 16, title, size=11.5, anchor='start', weight='700')
    if sub:
        s.text(x + w - 8, y + 16, sub, size=9.5, anchor='end', fill='#555')


def fit(s, name, pre, x, y, w, h, sc):
    """figures/ の図を、枠の中に中央ぞろえで貼る。"""
    body, bw, bh = load_file(name)
    # 枠に入りきらないときは上ぞろえにする（題名の上にはみ出さないように）
    s.add(place(body, pre, x + max(0.0, (w - bw * sc) / 2.0),
                y + max(0.0, (h - bh * sc) / 2.0), sc))


def area_table(s, x, y, w, site, keisan, a1, a2, a3, blank=False,
               rh=46.0, band=False):
    """面積表。band=True で下の帯に入る1行組の形になる。"""
    s.text(x, y - 8, '⑺　面　積　表', size=12, anchor='start', weight='700')
    rows = [('敷地面積', '', site),
            ('建築面積', keisan, '%.2f' % a1),
            ('床面積　1階　ア', keisan, '%.2f' % a1),
            ('　　　　2階　イ', keisan, '%.2f' % a2),
            ('　　　　3階　ウ', keisan, '%.2f' % a3),
            ('延べ面積　ア＋イ＋ウ', '', '%.2f' % (a1 + a2 + a3))]
    s.rect(x, y, w, rh * len(rows), fill='#fff', stroke=INK, stroke_width=1.2)
    kx = x + w * 0.42
    vx = x + w - 58
    s.line(kx, y, kx, y + rh * len(rows), stroke=INK, stroke_width=0.8)
    s.line(vx, y, vx, y + rh * len(rows), stroke=INK, stroke_width=0.8)
    for i, (nm, ks, va) in enumerate(rows):
        yy = y + i * rh
        if i:
            s.line(x, yy, x + w, yy, stroke=INK, stroke_width=0.8)
        s.text(x + 8, yy + rh * 0.72, nm, size=10.5, anchor='start',
               weight='700' if i in (0, 5) else '400')
        if not blank:
            if ks:
                s.text(kx + 6, yy + rh * 0.72, '（計算式）' + ks, size=9,
                       anchor='start', fill='#555')
            s.text(x + w - 22, yy + rh * 0.72, va, size=11, anchor='end',
                   weight='700')
        s.text(x + w - 5, yy + rh * 0.72, '㎡', size=9, anchor='end')
    if not band:
        wrap_text(s, x, y + rh * len(rows) + 16, w,
                  '※ 小数点以下第3位以下は切り捨て。計算式はm単位で書く。',
                  size=9.5, lh=12.0, color='#555')
    return y + rh * len(rows) + 42


def plain(t):
    """記述の文からHTMLのしるしを取り、紙に書ける形にする。"""
    t = t.replace('m<sup>2</sup>', '㎡').replace('<sup>2</sup>', '²')
    t = re.sub(r'<[^>]+>', '', t)
    return t


def youten_box(s, x, y, w, h, items=None):
    """⑻ 計画の要点等。items があれば解答例、なければ罫線だけ。"""
    s.text(x, y - 8, '⑻　計画の要点等', size=13, anchor='start',
           weight='700')
    n = 3
    bh = (h - (n - 1) * 6.0) / n
    for i in range(n):
        by = y + i * (bh + 6.0)
        s.rect(x, by, w, bh, fill='#fff', stroke=INK, stroke_width=1.0)
        s.line(x, by + 24, x + w, by + 24, stroke=INK, stroke_width=0.7)
        if items and i < len(items):
            q, a = items[i]
            s.text(x + 6, by + 17, '%s　%s' % ('①②③'[i], plain(q)), size=8.0,
                   anchor='start', weight='700')
            wrap_text(s, x + 6, by + 38, w - 12, plain(a), size=7.4, lh=9.2,
                      maxlines=int((bh - 32) / 9.2))
        else:
            s.text(x + 6, by + 18, '%s' % '①②③'[i], size=10,
                   anchor='start', weight='700')
            k = 1
            while by + 26 + k * 19 < by + bh - 4:
                s.line(x + 8, by + 26 + k * 19, x + w - 8, by + 26 + k * 19,
                       stroke='#bbb', stroke_width=0.6)
                k += 1


def sheet(sp, blank=False):
    """A2横1枚の答案。枠割りは公表されている本物の答案用紙に合わせる。

    令和7年の答案用紙（A2横1枚）は
      左の列 … 1階平面図兼配置図／南側立面図
      中の列 … 2階平面図／床伏図兼小屋伏図／凡例
      右の列 … 矩計図（1/20）を紙の高さいっぱいの細長い枠で
      下 　　… 面積表・計画の要点等・受験番号
    今年は3階建てなので平面図が1枚増え、部分詳細図（断面）1/20 になる。
    その分だけ列を増やし、置き場所の考え方は本物と同じにしてある。
    """
    key, sub, nx, ny, site, keisan, a1, a2, a3 = sp
    s = Svg(W, H)
    s.rect(0, 0, W, H, fill='none', stroke=INK, stroke_width=1.4)

    # ---- 左の縦書きタイトル帯（本物と同じ位置） ----
    s.line(46, 0, 46, H, stroke=INK, stroke_width=1.0)
    s.text_rot(26, 210, '令和8年　二級建築士試験', -90, size=15, weight='700')
    s.text_rot(26, 520, '「設計製図の試験」', -90, size=14)
    if blank:
        s.text_rot(26, 820, '練習用 答案用紙', -90, size=15, weight='700')
    else:
        s.text_rot(26, 760, '予想問題　%s' % key, -90, size=15, weight='700')
        s.text_rot(26, 980, '解　答　例', -90, size=14)

    # ---- 列の割り ----
    y0, ybot = 12.0, 1028.0                    # 図面の帯（上下）
    c1, w1 = 54.0, 480.0                       # 1階平面図・立面図
    c2, w2 = 546.0, 348.0                      # 2階・3階平面図・計画の要点等
    c3, w3 = 906.0, 348.0                      # 床伏図・小屋伏図
    c4, w4 = 1266.0, 408.0                     # 部分詳細図（紙の高さいっぱい）
    by, bh = 1036.0, 150.0                     # 下の帯

    ev = 'ans%selev' % key
    import answers as _ans
    import anselev as _ae
    evname = _ae.FACE_NAME[_ans.ELEV_FACE[key]]
    ff = 'ansfuse_floor' if key == 'A' else 'ans%sfuse_floor' % key
    fr = 'ansfuse_roof' if key == 'A' else 'ans%sfuse_roof' % key
    dt = 'dh_nokisaki' if key == 'D' else 'detail'

    def slot(x, y, w, h, title, fig=None, sc=SC100, gp=GP4, pre=''):
        if blank or fig is None:
            grid_frame(s, x, y, w, h, title, gp)
        else:
            frame(s, x, y, w, h, title)
            fit(s, fig, pre, x, y + 22, w, h - 22, sc)

    # ---- 左の列：1階平面図 兼 配置図／立面図 ----
    h1 = 580.0
    if blank:
        grid_frame(s, c1, y0, w1, h1,
                   '⑴ １階平面図 兼 配置図　縮尺1／100　（目盛4.55mm）', GP4)
    else:
        frame(s, c1, y0, w1, h1,
              '⑴ １階平面図 兼 配置図　縮尺1／100　（目盛4.55mm）')
        body, bw, bh_ = panel(key, 0)
        s.add(place(body, key.lower() + '0',
                    c1 + max(0.0, (w1 - bw * SC100) / 2.0),
                    y0 + 22 + max(0.0, (h1 - 22 - bh_ * SC100) / 2.0), SC100))
    slot(c1, y0 + h1 + 8, w1, ybot - (y0 + h1 + 8),
         '⑸ %s立面図' % evname,
         ev, pre=key.lower() + 'e')

    # ---- 中の列：2階・3階平面図／計画の要点等 ----
    hp = 500.0
    for i2, ti in ((1, '⑵ ２階平面図　縮尺1／100　（目盛4.55mm）'),
                   (2, '⑶ ３階平面図　縮尺1／100　（目盛4.55mm）')):
        yy = y0 + (i2 - 1) * (hp + 8)
        if blank:
            grid_frame(s, c2, yy, w2, hp, ti, GP4)
        else:
            frame(s, c2, yy, w2, hp, ti)
            body, bw, bh_ = panel(key, i2)
            s.add(place(body, '%s%d' % (key.lower(), i2),
                        c2 + max(0.0, (w2 - bw * SC100) / 2.0),
                        yy + 22 + max(0.0, (hp - 22 - bh_ * SC100) / 2.0),
                        SC100))


    # ---- 中の列その2：床伏図・小屋伏図 ----
    hf = 404.0
    slot(c3, y0, w3, hf, '⑷ ３階床伏図',
         ff, pre=key.lower() + 'f')
    slot(c3, y0 + hf + 8, w3, hf, '⑷ 小屋伏図',
         fr, pre=key.lower() + 'g')
    # ---- ⑻ 計画の要点等（本物の答案用紙と同じく、罫線の欄） ----
    ry = y0 + 2 * (hf + 8)
    s.rect(c3, ry, w3, ybot - ry, fill='none', stroke=INK, stroke_width=1.0)
    s.text(c3 + 8, ry + 17, '⑻　計画の要点等', size=11, anchor='start',
           weight='700')
    s.line(c3, ry + 24, c3 + w3, ry + 24, stroke=INK, stroke_width=0.8)
    qs = [q for q, _ in _youten(key)] if not blank else ['', '', '']
    n_ = 3
    ih = (ybot - ry - 24) / n_
    for i3 in range(n_):
        yy = ry + 24 + i3 * ih
        if i3:
            s.line(c3, yy, c3 + w3, yy, stroke=INK, stroke_width=0.7)
        s.text(c3 + 6, yy + 14, '%s' % '①②③'[i3], size=9.5,
               anchor='start', weight='700')
        if not blank:
            wrap_text(s, c3 + 20, yy + 14, w3 - 28, plain(qs[i3]), size=8.4,
                      lh=10.4, color='#333')
        for k_ in range(1, 4):
            ly_ = yy + 22 + k_ * 12
            if ly_ < yy + ih - 4:
                s.line(c3 + 8, ly_, c3 + w3 - 8, ly_, stroke='#bbb',
                       stroke_width=0.6)
    if not blank:
        s.text(c3 + w3 - 6, ybot - 6,
               '※ 解答例の本文は別紙「計画の要点等（記述だけ）」に',
               size=8, anchor='end', fill='#666')

    # ---- 右の列：部分詳細図（紙の高さいっぱい） ----
    slot(c4, y0, w4, ybot - y0,
         '⑹ 部分詳細図（断面）　（目盛10mm）',
         dt, sc=SC20, gp=GP10, pre=key.lower() + 'd')

    # ---- 下の帯：面積表・凡例・受験番号 ----
    area_table(s, c1, by + 22, 500.0, site, keisan, a1, a2, a3, blank=blank,
               rh=19.0, band=True)
    s.text(c1, by + 148, '※ 小数点以下第3位以下は切り捨て。計算式はm単位。',
           size=9, anchor='start', fill='#555')
    legend(s, lx=c1 + 600, ly=by + 22, lw=640.0, dims=not blank,
           note=False)
    bx = 1346.0
    s.rect(bx, by, CX1 - bx, 54, fill='#fff', stroke=INK, stroke_width=1.4)
    s.text(bx + (CX1 - bx) / 2.0, by + 36,
           '練習用　答案用紙' if blank else '標　準　解　答　例',
           size=18, weight='700')
    s.rect(bx, by + 62, CX1 - bx, 32, fill='#fff', stroke=INK,
           stroke_width=1.0)
    s.line(bx + 190, by + 62, bx + 190, by + 94, stroke=INK, stroke_width=0.8)
    s.text(bx + 8, by + 83, '受験番号', size=10.5, anchor='start',
           fill='#555')
    s.text(bx + 198, by + 83, '氏名', size=10.5, anchor='start', fill='#555')
    if blank:
        s.text(bx, by + 116,
               '※ 目盛は実寸。印刷は「実際のサイズ／100%」で。',
               size=9.5, anchor='start', fill='#555')
        s.text(bx, by + 132,
               '※「用紙に合わせる」にすると縮尺が狂う。',
               size=9.5, anchor='start', fill='#555')
    else:
        s.text(bx, by + 114, '予想問題　%s　%s' % (key, sub), size=10.5,
               anchor='start', weight='700')
        s.text(bx, by + 132,
               '木造3階建て　／　%dマス × %dマス（%s × %s）'
               % (nx, ny, format(nx * 910, ','), format(ny * 910, ',')),
               size=9.5, anchor='start', fill='#555')
    return s


def _youten(key):
    """予想問題の計画の要点等（問題文と模範解答）。mondai.py から借りる。"""
    import mondai
    for sp in mondai.SPECS:
        if sp['tag'] == key:
            return sp['youten']
    return []


def grid_frame(s, x, y, w, h, title, pitch):
    """白紙の枠。方眼を敷いてから、枠と題名を上に描く。"""
    yy = y + 22.0
    while yy <= y + h - 0.01:
        s.line(x, yy, x + w, yy, stroke='#c8c8c8', stroke_width=0.4)
        yy += pitch
    xx = x
    while xx <= x + w + 0.01:
        s.line(xx, y + 22, xx, y + h, stroke='#c8c8c8', stroke_width=0.4)
        xx += pitch
    s.rect(x, y, w, h, fill='none', stroke=INK, stroke_width=1.0)
    s.rect(x, y, w, 22, fill='#fff', stroke='none')
    s.line(x, y + 22, x + w, y + 22, stroke=INK, stroke_width=0.8)
    s.text(x + 8, y + 16, title, size=11.5, anchor='start', weight='700')


def load_file(name):
    """figures/ のSVGを読み込んで (中身, 幅, 高さ) を返す。"""
    t = io.open(os.path.join(FIG, name + '.svg'), encoding='utf-8').read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', t)
    body = t[t.index('>', t.index('<svg')) + 1:t.rindex('</svg>')]
    return body, float(m.group(1)), float(m.group(2))


if __name__ == '__main__':
    for sp in SPECS:
        s = sheet(sp)
        path = os.path.join(OUT, 'kaitou_%s.svg' % sp[0])
        io.open(path, 'w', encoding='utf-8').write(to_mono(s.dump()))
        print('wrote', os.path.basename(path))
    # 白紙の練習用答案用紙（A2横1枚・本番と同じ枠割り）
    b = sheet(SPECS[0], blank=True)
    io.open(os.path.join(OUT, 'renshu_a2.svg'), 'w',
            encoding='utf-8').write(to_mono(b.dump()))
    print('wrote renshu_a2.svg')
