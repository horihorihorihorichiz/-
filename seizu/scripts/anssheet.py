# -*- coding: utf-8 -*-
"""公式の標準解答例と同じ描き方で平面図を描く。

・壁は2本線（厚さ120mm）。柱は壁の中の黒い四角
・建具は記号（引違い窓・開き戸・引戸）
・家具と設備を描く
・室名の下に面積と床高
・耐力壁は△、出入口は▲
"""
import os
from svgkit import Svg
import plans
from plans import fit_openings, _bearing_marks, _union

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'figures')

G = 56.0
ML, MR, MT, MB = 104, 116, 104, 150
WT = 120.0 / 910.0          # 壁の厚さ（マス）
INK = '#111'


def _cut(segs, a, b):
    """区間 a..b から segs を取りのぞいて、残った実線の区間を返す。"""
    out, pos = [], a
    for p0, p1 in _union([(max(a, q0), min(b, q1)) for q0, q1 in segs
                          if min(b, q1) > max(a, q0) + 1e-9]):
        if p0 > pos + 1e-9:
            out.append((pos, p0))
        pos = max(pos, p1)
    if b > pos + 1e-9:
        out.append((pos, b))
    return out


def _openings(d, nx, ny):
    """外周の開口と室内の建具を、向きと通りごとに集める。"""
    op = {}
    for face, pos, ln, kind, lab in d.get('openings', []):
        key = ('H', 0 if face == 'S' else ny) if face in ('S', 'N') \
            else ('V', 0 if face == 'W' else nx)
        op.setdefault(key, []).append((pos, pos + ln, kind, face))
    for ori, wall, pos, ln in d.get('doors', []):
        op.setdefault((ori, wall), []).append((pos, pos + ln, 'door', None))
    return op


def draw(d, title, sub=''):
    nx = d.get('nx', plans.NX)
    ny = d.get('ny', plans.NY)
    xlines = d.get('xlines', plans.XLINES)
    ylines = d.get('ylines', plans.YLINES)
    tooshi = d.get('tooshi', plans.TOOSHI)
    kuda = d.get('kuda', plans.KUDA)
    side = d.get('road_side', 'S')
    d = dict(d, openings=fit_openings(d, nx, ny, xlines, ylines))

    W = ML + nx * G + MR
    H = MT + ny * G + MB

    def px(gx):
        return ML + gx * G

    def py(gy):
        return MT + (ny - gy) * G

    s = Svg(W, H)
    s.text(W / 2.0, 30, title, size=15, weight='700')
    if sub:
        s.text(W / 2.0, 48, sub, size=10.5, fill='#555')

    x0, y0, x1, y1 = px(0), py(ny), px(nx), py(0)

    # ---- 方眼（答案用紙の目盛4.55mm＝455mm。紙いっぱいに入っている） ----
    half = G / 2.0
    i = 0
    gx_ = px(0) % half
    while gx_ < W:
        dark = abs((gx_ - px(0)) / G - round((gx_ - px(0)) / G)) < 1e-6
        s.line(gx_, 0, gx_, H, stroke='#c9c9c9' if dark else '#dedede',
               stroke_width=0.7 if dark else 0.55)
        gx_ += half
        i += 1
    gy_ = py(0) % half
    while gy_ < H:
        dark = abs((gy_ - py(0)) / G - round((gy_ - py(0)) / G)) < 1e-6
        s.line(0, gy_, W, gy_, stroke='#c9c9c9' if dark else '#dedede',
               stroke_width=0.7 if dark else 0.55)
        gy_ += half

    # ---- 通り芯 ----
    for gx, _ in xlines:
        s.line(px(gx), y0 - 26, px(gx), y1 + 30, stroke='#888',
               stroke_width=0.6, stroke_dasharray='12 3 2 3')
    for gy, _ in ylines:
        s.line(x0 - 26, py(gy), x1 + 30, py(gy), stroke='#888',
               stroke_width=0.6, stroke_dasharray='12 3 2 3')

    # ---- 壁（2本線） ----
    cov = {}
    for _, _, a, b, c, e, _ in d['rooms']:
        cov.setdefault(('V', a), []).append((b, e))
        cov.setdefault(('V', c), []).append((b, e))
        cov.setdefault(('H', b), []).append((a, c))
        cov.setdefault(('H', e), []).append((a, c))
    op = _openings(d, nx, ny)
    h = WT / 2.0 * G

    def wall_line(ori, ln_, a, b, thin=False):
        w = 0.9 if thin else 1.15
        if ori == 'V':
            for dd in (-h, h):
                s.line(px(ln_) + dd, py(a), px(ln_) + dd, py(b), stroke=INK,
                       stroke_width=w)
        else:
            for dd in (-h, h):
                s.line(px(a), py(ln_) + dd, px(b), py(ln_) + dd, stroke=INK,
                       stroke_width=w)

    for key, segs in cov.items():
        ori, ln_ = key
        holes = [(p0, p1) for p0, p1, k, f in op.get(key, [])]
        for a, b in _union(segs):
            for pa, pb in _cut(holes, a, b):
                wall_line(ori, ln_, pa, pb)

    # ---- 建具 ----
    def jamb(ori, ln_, at):
        if ori == 'V':
            s.line(px(ln_) - h, py(at), px(ln_) + h, py(at), stroke=INK,
                   stroke_width=1.0)
        else:
            s.line(px(at), py(ln_) - h, px(at), py(ln_) + h, stroke=INK,
                   stroke_width=1.0)

    def window(ori, ln_, a, b):
        wall_line(ori, ln_, a, b, thin=True)
        if ori == 'V':
            s.line(px(ln_), py(a), px(ln_), py(b), stroke=INK,
                   stroke_width=0.7)
        else:
            s.line(px(a), py(ln_), px(b), py(ln_), stroke=INK,
                   stroke_width=0.7)
        jamb(ori, ln_, a)
        jamb(ori, ln_, b)

    def slide(ori, ln_, a, b):
        """引戸。壁の中に2枚の戸を少しずらして描く。"""
        m = (a + b) / 2.0
        for (p, q, dd) in ((a, m, -h * 0.5), (m, b, h * 0.5)):
            if ori == 'V':
                s.line(px(ln_) + dd, py(p), px(ln_) + dd, py(q), stroke=INK,
                       stroke_width=1.6)
            else:
                s.line(px(p), py(ln_) + dd, px(q), py(ln_) + dd, stroke=INK,
                       stroke_width=1.6)
        jamb(ori, ln_, a)
        jamb(ori, ln_, b)

    def hinged(ori, ln_, a, b, inward=1):
        """開き戸。戸の板と四分円の弧。"""
        r = (b - a) * G
        jamb(ori, ln_, a)
        jamb(ori, ln_, b)
        if ori == 'V':
            xx, yy = px(ln_), py(a)
            s.line(xx, yy, xx + inward * r, yy, stroke='#555',
                   stroke_width=1.2)
            s.path('M %.1f %.1f A %.1f %.1f 0 0 %d %.1f %.1f'
                   % (xx + inward * r, yy, r, r, 0 if inward > 0 else 1,
                      xx, yy - r), stroke='#777', stroke_width=0.9,
                   fill='none')
        else:
            xx, yy = px(a), py(ln_)
            s.line(xx, yy, xx, yy + inward * r, stroke='#555',
                   stroke_width=1.2)
            s.path('M %.1f %.1f A %.1f %.1f 0 0 %d %.1f %.1f'
                   % (xx, yy + inward * r, r, r, 1 if inward > 0 else 0,
                      xx + r, yy), stroke='#777', stroke_width=0.9,
                   fill='none')

    for key, lst in op.items():
        ori, ln_ = key
        for a, b, kind, face in lst:
            if kind in ('win', 'balc'):
                window(ori, ln_, a, b)
            elif kind == 'entry':
                slide(ori, ln_, a, b)
            else:
                if b - a >= 1.4:
                    slide(ori, ln_, a, b)
                else:
                    inward = 1 if (ln_ < (nx if ori == 'V' else ny) / 2.0) \
                        else -1
                    hinged(ori, ln_, a, b, inward)
    # ---- 家具・設備 ----
    cur = [None]                       # いま家具を描いている部屋
    ROOMS = [(r[2], r[3], r[4], r[5]) for r in d['rooms']]

    def ok_here(a, b, c, e):
        """他の部屋にかぶる家具は描かない（L字の部屋のはみ出しよけ）。"""
        for i, (ra, rb, rc, re) in enumerate(ROOMS):
            if i == cur[0]:
                continue
            if a < rc - 1e-6 and c > ra + 1e-6 and b < re - 1e-6 \
                    and e > rb + 1e-6:
                return False
        return True

    def R(a, b, c, e, fill='#fff', sw=0.85, dash=None):
        if not ok_here(a, b, c, e):
            return
        s.rect(px(a), py(e), (c - a) * G, (e - b) * G, fill=fill,
               stroke='#333', stroke_width=sw, stroke_dasharray=dash)

    def T(a, b, c, e, t, size=8.5):
        s.text((px(a) + px(c)) / 2.0, (py(b) + py(e)) / 2.0 + 3, t,
               size=size, fill='#333')

    def ell(cx, cy, rx, ry):
        s.add('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#fff" '
              'stroke="#333" stroke-width="0.85"/>'
              % (px(cx), py(cy), rx * G, ry * G))

    def toilet(a, b):
        """洋式便器と手洗い器。1マスに収める。"""
        R(a + .12, b + .72, a + .62, b + .90)          # ロータンク
        ell(a + .37, b + .52, .17, .22)                # 便座
        R(a + .72, b + .70, a + .95, b + .92)          # 手洗い器
        ell(a + .835, b + .81, .07, .07)

    def basin(a, b, w=.9):
        R(a, b, a + w, b + .5)
        ell(a + w / 2.0, b + .25, .16, .13)

    def washer(a, b):
        R(a, b, a + .7, b + .7)
        ell(a + .35, b + .35, .2, .2)

    def bath(a, b, c, e):
        R(a + .06, b + .06, c - .06, e - .06)
        R(a + .16, b + .16, c - .16, e - .34)

    def kitchen(a, b, ln, vertical=False):
        """流し台・調理台・コンロ台・冷蔵庫を1列に並べる。"""
        if vertical:
            R(a, b, a + .6, b + ln)
            ell(a + .3, b + ln - .45, .16, .16)
            for i in range(2):
                for j in range(2):
                    ell(a + .18 + i * .24, b + .30 + j * .22, .06, .06)
            R(a, b + ln, a + .6, b + ln + .6)
            T(a, b + ln, a + .6, b + ln + .6, '冷', 7.5)
        else:
            R(a, b, a + ln, b + .6)
            ell(a + .45, b + .3, .16, .16)
            for i in range(2):
                for j in range(2):
                    ell(a + ln - .45 + i * .22, b + .18 + j * .24, .06, .06)
            R(a + ln, b, a + ln + .6, b + .6)
            T(a + ln, b, a + ln + .6, b + .6, '冷', 7.5)

    def bed(a, b, w=1.0, hh=2.2):
        R(a, b, a + w, b + hh)
        s.line(px(a), py(b + hh - .35), px(a + w), py(b + hh - .35),
               stroke='#333', stroke_width=0.7)

    def desk(a, b, w=1.3, hh=.7):
        R(a, b, a + w, b + hh)

    def closet(a, b, c, e, t='収納'):
        R(a, b, c, e, dash='4 3')
        T(a, b, c, e, t, 8)

    def sofa(a, b, w=2.0):
        R(a, b, a + w, b + .9)
        s.line(px(a), py(b + .62), px(a + w), py(b + .62), stroke='#333',
               stroke_width=0.7)

    def table(a, b, c, e, n=3):
        R(a + .25, b + .25, c - .25, e - .25)
        for i in range(n):
            t = a + .45 + i * ((c - a - .9) / max(1, n - 1))
            R(t - .16, b - .02, t + .16, b + .22)
            R(t - .16, e - .22, t + .16, e + .02)

    def display(a, b, c, e, n=3):
        """陳列棚。細長い棚を数本ならべる。"""
        for i in range(n):
            y = b + .3 + i * ((e - b - .6) / max(1, n - 1))
            R(a + .2, y - .16, c - .2, y + .16)

    def counter(a, b, c, e):
        R(a, b, c, e)
        T(a, b, c, e, 'レジ', 8)

    def tatami(a, b, c, e):
        for i in range(int(round((c - a) * (e - b) / 2.0))):
            pass
        n = int(round((e - b) / 1.0))
        for i in range(1, n):
            s.line(px(a) + 2, py(b + i), px(c) - 2, py(b + i), stroke='#999',
                   stroke_width=0.6)
        s.line(px((a + c) / 2.0), py(b) - 2, px((a + c) / 2.0), py(e) + 2,
               stroke='#999', stroke_width=0.6)

    def furnish(name, a, b, c, e):
        w, hh = c - a, e - b
        if '便所' in name:
            toilet(a + (w - 1) / 2.0, b + .05)
        elif '洗面' in name and '脱衣' in name:
            basin(a + .1, e - .6, w - .9)
            washer(c - .85, b + .15)
        elif '浴室' in name:
            bath(a, b, c, e)
        elif '厨房' in name or '作業場' in name:
            kitchen(a + .3, b + .3, w - 1.5)
            R(c - .9, e - 1.2, c - .2, e - .2)
            T(c - .9, e - 1.2, c - .2, e - .2, '作業台', 7.5)
        elif '売場' in name:
            display(c - 2.8, b + .6, c - .3, e - .6, 3)
            display(a + .3, e - 2.4, c - 3.2, e - .4, 2)
            counter(a + .35, b + .3, a + 1.85, b + .95)
        elif '居間' in name or 'ＬＤＫ' in name or 'LDK' in name:
            kitchen(a + .35, e - 1.0, 1.8)
            table(a + w * .35, b + .5, a + w * .35 + 2.2, b + 1.7, 3)
            sofa(c - 2.4, b + .35, 2.0)
        elif '和室' in name:
            tatami(a, b, c, e)
            closet(c - 1.0, b + .1, c - .1, b + 1.0, '押入')
        elif '寝室' in name:
            bed(a + .35, b + .4)
            bed(a + 1.55, b + .4)
            closet(c - 1.0, e - 1.0, c - .1, e - .1)
        elif '子供室' in name or '子ども室' in name:
            bed(a + .3, e - 2.6)
            desk(c - 1.6, b + .3)
            closet(c - 1.0, e - 1.0, c - .1, e - .1)
        elif '玄関' in name:
            R(a + .1, e - .5, a + 1.2, e - .1)
            T(a + .1, e - .5, a + 1.2, e - .1, '下足入れ', 7)
        elif '倉庫' in name or '納戸' in name or '収納' in name:
            for i in range(2):
                R(a + .12, b + .3 + i * (hh - .8), c - .12,
                  b + .55 + i * (hh - .8))
            T(a, b, c, e, '棚', 8)
        elif 'スタッフ' in name:
            table(a + .5, b + .6, a + 2.2, b + 1.6, 2)
            for i in range(2):
                R(c - 1.0 + i * .45, e - 1.0, c - .65 + i * .45, e - .2)
            T(c - 1.05, e - 1.25, c - .15, e - 1.05, 'ロッカー', 6.5)
        elif '家事' in name:
            R(a + .12, e - .7, c - .12, e - .15)
            T(a + .12, e - .7, c - .12, e - .15, '棚', 7.5)
        elif '廊下' in name or 'ホール' in name:
            pass

    for i, (name, ar, a, b, c, e, kind) in enumerate(d['rooms']):
        if kind != 'stair':
            cur[0] = i
            furnish(name, a, b, c, e)
    cur[0] = None

    # ---- 階段 ----
    sa, sb, sc, sd = d.get('stair_box', (0, 2, 2, 6))
    mid = (sa + sc) / 2.0
    Tt = 210.0 / 910.0
    land = sd - 1
    n1, n2 = d.get('stair_runs', (6, 7))
    mode = d.get('stair_mode') or (
        'top' if 'DN' in d.get('stair_up', '') else 'bottom')
    s.line(px(sa) + h, py(land), px(sc) - h, py(land), stroke=INK,
           stroke_width=1.0)
    s.line(px(mid), py(sb), px(mid), py(land), stroke=INK, stroke_width=1.0)
    for k in range(1, n1 + 1):
        s.line(px(mid) + 1, py(land - k * Tt), px(sc) - h,
               py(land - k * Tt), stroke=INK, stroke_width=0.7)
    for k in range(1, n2 + 1):
        s.line(px(sa) + h, py(land - k * Tt), px(mid) - 1,
               py(land - k * Tt), stroke=INK, stroke_width=0.7)

    def arrow(gx, n, lab_):
        ax = px(gx)
        yb, yt = py(land - n * Tt - .22), py(land - .12)
        s.line(ax, yb, ax, yt + 8, stroke=INK, stroke_width=1.2)
        s.polygon([(ax, yt), (ax - 4, yt + 8), (ax + 4, yt + 8)], fill=INK)
        s.text(ax, yb + 12, lab_, size=9, weight='700')

    def brk(g0, g1, gy):
        x_0, x_1, yy = px(g0), px(g1), py(gy)
        s.line(x_0, yy + 6, x_1, yy - 6, stroke=INK, stroke_width=0.9)
        s.line(x_0, yy + 11, x_1, yy - 1, stroke=INK, stroke_width=0.9)

    if mode in ('bottom', 'middle'):
        arrow((mid + sc) / 2.0, n1, 'UP')
        brk(mid + .05, sc - .05, land - (n1 - 1) * Tt)
    if mode in ('middle', 'top'):
        arrow((sa + mid) / 2.0, n2, 'DN')

    # ---- 竪穴区画（階段室） ----
    s.rect(px(sa) + 3, py(sd) + 3, (sc - sa) * G - 6, (sd - sb) * G - 6,
           fill='none', stroke=INK, stroke_width=1.0,
           stroke_dasharray='7 3 2 3')
    s.text(px((sa + sc) / 2.0), py(sd) + 13, '竪穴区画', size=7.5,
           fill='#333')

    # ---- 耐力壁の△ ----
    for ori, ln_, m in _bearing_marks(d, nx, ny, xlines, ylines):
        if ori == 'V':
            o = -1 if ln_ == 0 else (1 if ln_ == nx else 1)
            cx, cy = px(ln_) + o * 13, py(m)
            tri = [(cx - o * 6, cy), (cx + o * 4, cy - 5.5),
                   (cx + o * 4, cy + 5.5)]
        else:
            o = 1 if ln_ == 0 else (-1 if ln_ == ny else -1)
            cx, cy = px(m), py(ln_) + o * 13
            tri = [(cx, cy - o * 6), (cx - 5.5, cy + o * 4),
                   (cx + 5.5, cy + o * 4)]
        s.polygon(tri, fill='#fff', stroke=INK, stroke_width=1.1)

    # ---- 柱 ----
    cs = WT * G
    for gx, gy in kuda:
        s.rect(px(gx) - cs / 2.0, py(gy) - cs / 2.0, cs, cs, fill=INK)
    for gx, gy in tooshi:
        s.rect(px(gx) - cs / 2.0, py(gy) - cs / 2.0, cs, cs, fill=INK)
        s.circle(px(gx), py(gy), 8, fill='none', stroke=INK,
                 stroke_width=1.2)

    # ---- 出入口の▲印 ----
    for face, pos, ln, kind, lab_ in d['openings']:
        if kind != 'entry':
            continue
        m = pos + ln / 2.0
        if face == 'S':
            cx, cy = px(m), py(0) + 15
            tri = [(cx, cy - 8), (cx - 6, cy + 4), (cx + 6, cy + 4)]
        elif face == 'N':
            cx, cy = px(m), py(ny) - 15
            tri = [(cx, cy + 8), (cx - 6, cy - 4), (cx + 6, cy - 4)]
        elif face == 'E':
            cx, cy = px(nx) + 15, py(m)
            tri = [(cx - 8, cy), (cx + 4, cy - 6), (cx + 4, cy + 6)]
        else:
            cx, cy = px(0) - 15, py(m)
            tri = [(cx + 8, cy), (cx - 4, cy - 6), (cx - 4, cy + 6)]
        s.polygon(tri, fill=INK)

    # ---- 室名・面積・床高 ----
    fl = d.get('floor_label', '')
    for name, ar, a, b, c, e, kind in d['rooms']:
        cx = (px(a) + px(c)) / 2.0
        cy = (py(b + .62) if kind == 'stair'
              else py(e) + ((e - b) * G) * (0.30 if (e - b) >= 3 else 0.42))
        big = (c - a) >= 5
        s.text(cx, cy - 4, name, size=11.5 if big else 10, weight='700')
        s.text(cx, cy + 9, ar + '㎡', size=9)
        if fl and kind in ('shop', 'hall'):
            s.text(cx, cy + 21, fl, size=8.5, fill='#333')

    # ---- 通り符号 ----
    for gx, nm in xlines:
        s.circle(px(gx), y0 - 40, 9, fill='#fff', stroke=INK,
                 stroke_width=0.9)
        s.text(px(gx), y0 - 36, nm, size=10, weight='700')
    for gy, nm in ylines:
        s.circle(x0 - 40, py(gy), 9, fill='#fff', stroke=INK,
                 stroke_width=0.9)
        s.text(x0 - 40, py(gy) + 4, nm, size=10, weight='700')

    # ---- 寸法 ----
    s.dim_h(x0, x1, y1 + 56, format(nx * 910, ','))
    s.dim_v(y1, y0, x1 + 52, format(ny * 910, ','))

    # ---- 方位・道路 ----
    if d.get('road', True):
        if 'S' in side:
            s.text(W / 2.0, y1 + 88, '道　路', size=11, weight='700')
        if 'N' in side:
            s.text(W / 2.0, y0 - 62, '道　路', size=11, weight='700')
        if 'E' in side:
            s.text_rot(x1 + 86, (y0 + y1) / 2.0, '道　路', -90, size=11,
                       weight='700')
        if 'W' in side:
            s.text_rot(x0 - 74, (y0 + y1) / 2.0, '道　路', -90, size=11,
                       weight='700')
    nxp, nyp = W - 30, 34
    s.circle(nxp, nyp, 12, fill='#fff', stroke='#444', stroke_width=0.9)
    s.polygon([(nxp, nyp - 9), (nxp - 4, nyp + 7), (nxp, nyp + 3),
               (nxp + 4, nyp + 7)], fill=INK)
    s.text(nxp, nyp + 24, 'N', size=9.5, weight='700')
    return s


if __name__ == '__main__':
    import answers
    for k in 'ABCDEF':
        for i, ti in enumerate(('１階平面図 兼 配置図　縮尺1／100',
                                '２階平面図　縮尺1／100',
                                '３階平面図　縮尺1／100')):
            dd = dict(answers.PLANS[k][i])
            dd['floor_label'] = 'GL＋550' if i == 0 else ''
            draw(dd, ti).save(os.path.join(OUT, 'ans2%s_%df.svg' % (k, i + 1)))
    print('wrote ans2*_?f.svg')
