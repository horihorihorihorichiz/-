# -*- coding: utf-8 -*-
"""公式の標準解答例と同じ描き方で平面図を描く。

・壁は2本線（厚さ120mm）。柱は壁の中の黒い四角
・建具は記号（引違い窓・片引き戸・引違い戸。開き戸は使わない）
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
ML, MR, MT, MB = 104, 156, 104, 176
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
    for ori, wall, pos, ln in plans.fit_doors(d):
        op.setdefault((ori, wall), []).append((pos, pos + ln, 'door', None))
    return op


def genkan_face(d):
    """住宅玄関のドアがある外壁の向き（土間はその向きに1マス）。"""
    ents = [(f, l, lab) for f, p, l, k, lab in d['openings'] if k == 'entry']
    for f, l, lab in ents:
        if '玄関' in (lab or ''):
            return f
    side = d.get('road_side', 'S')
    road = [(l, f) for f, l, lab in ents if f in side]
    return min(road)[1] if road else 'S'


DOMA = dict(gl='GL＋400', porch='GL＋380', kamachi=150)   # 玄関土間・ポーチ


def _draw_genkan(s, px, py, name, ar, a, b, c, e, face, fl):
    """玄関は道路がわ1マスを土間にして上がり框で分け、両方の高さを書く。

    土間 GL＋400（土間コンクリート）→ 上がり框 150 → ホール GL＋550。
    令和7年の標準解答例（玄関＋370／ホール＋500）と同じ考え方。
    """
    wt = WT * G / 2.0
    if face == 'S':
        dm, hl = (a, b, c, b + 1), (a, b + 1, c, e)
        ln = ((px(a) + wt, py(b + 1)), (px(c) - wt, py(b + 1)))
    elif face == 'N':
        dm, hl = (a, e - 1, c, e), (a, b, c, e - 1)
        ln = ((px(a) + wt, py(e - 1)), (px(c) - wt, py(e - 1)))
    elif face == 'E':
        dm, hl = (c - 1, b, c, e), (a, b, c - 1, e)
        ln = ((px(c - 1), py(b) - wt), (px(c - 1), py(e) + wt))
    else:
        dm, hl = (a, b, a + 1, e), (a + 1, b, c, e)
        ln = ((px(a + 1), py(b) - wt), (px(a + 1), py(e) + wt))
    (x1_, y1_), (x2_, y2_) = ln
    s.line(x1_, y1_, x2_, y2_, stroke=INK, stroke_width=1.8)     # 上がり框

    def ctr(r):
        return (px(r[0]) + px(r[2])) / 2.0, (py(r[1]) + py(r[3])) / 2.0
    cx, cy = ctr(hl)
    s.text(cx, cy - 7, name, size=10, weight='700')
    s.text(cx, cy + 4, ar + '㎡', size=9)
    s.text(cx, cy + 15, fl, size=8.5, fill='#333')
    cx, cy = ctr(dm)
    s.text(cx, cy - 1, '土間', size=8.5)
    s.text(cx, cy + 10, DOMA['gl'], size=8.5, fill='#333')


def draw(d, title, sub='', conflicts=None):
    """答案用紙の平面図を描く。conflicts に「置けなかった家具」を追記する。"""
    if conflicts is None:
        conflicts = []
    nx = d.get('nx', plans.NX)
    ny = d.get('ny', plans.NY)
    xlines = d.get('xlines', plans.XLINES)
    ylines = d.get('ylines', plans.YLINES)
    if 'tooshi' in d and 'kuda' in d:
        tooshi, kuda = d['tooshi'], d['kuda']
    else:
        tooshi, kuda = plans.columns_of(d.get('floor_no', 1))
    side = d.get('road_side', 'S')
    if not d.get('fitted'):
        d = dict(d, openings=fit_openings(d, nx, ny, xlines, ylines))

    site = d.get('site')
    rface = None                        # 配置図で道路のある面
    frame = site or d.get('frame')      # 2階・3階も1階と同じ用紙の大きさにする
    if frame:
        SW, SD = frame['sw'] / 910.0, frame['sd'] / 910.0
        yard = 2.6                                 # 道路側のあき（アプローチ）
        # 道路のある側にあきを取り、反対側は残り。道路のない向きは半分ずつ
        if 'E' in side:
            ox = SW - nx - yard
        elif 'W' in side:
            ox = yard
        else:
            ox = (SW - nx) / 2.0
        if 'S' in side:
            oy = yard
        elif 'N' in side:
            oy = SD - ny - yard
        else:
            oy = (SD - ny) / 2.0
        LG, TG = -ox, SD - oy                      # 紙の左端・上端の目盛
    else:
        SW, SD, LG, TG = nx, ny, 0, ny
    W = ML + SW * G + MR
    H = MT + SD * G + MB

    def px(gx):
        return ML + (gx - LG) * G

    def py(gy):
        return MT + (TG - gy) * G

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

    # ---- 敷地・屋外施設（1階平面図 兼 配置図） ----
    if site:
        sx0, sx1 = LG, LG + SW
        sy0, sy1 = TG - SD, TG
        s.rect(px(sx0), py(sy1), SW * G, SD * G, fill='none', stroke=INK,
               stroke_width=1.4, stroke_dasharray='16 4 3 4')
        # 塀（道路に面していない3辺）
        for f, seg in (('S', ((sx0, sy0), (sx1, sy0))),
                       ('N', ((sx0, sy1), (sx1, sy1))),
                       ('W', ((sx0, sy0), (sx0, sy1))),
                       ('E', ((sx1, sy0), (sx1, sy1)))):
            if f in side:
                continue
            (ax_, ay_), (bx_, by_) = seg
            s.line(px(ax_), py(ay_), px(bx_), py(by_), stroke=INK,
                   stroke_width=2.4, stroke_dasharray='14 6')
        s.text_rot(px(sx0) + 14, py((sy0 + sy1) / 2.0), '塀 H=1,200', -90,
                   size=8, fill='#333')
        # 道路
        if 'S' in side:
            ry_ = py(sy0)
            s.text(px((sx0 + sx1) / 2.0), ry_ + 30,
                   '道　路（幅員 %s）' % format(site['road'], ','), size=10,
                   weight='700')
        if 'N' in side:
            s.text(px((sx0 + sx1) / 2.0), py(sy1) - 26,
                   '道　路（幅員 %s）' % format(site['road'], ','), size=10,
                   weight='700')
        if 'E' in side:
            s.text_rot(px(sx1) + 30, py((sy0 + sy1) / 2.0),
                       '道　路（幅員 %s）' % format(site['road'], ','), -90,
                       size=10, weight='700')
        # ---- 屋外施設（道路のある面に置く） ----
        # 道路の面
        face = ('S' if 'S' in side else 'N' if 'N' in side
                else 'E' if 'E' in side else 'W')
        rface = face
        # 出入口（住宅玄関・店舗出入口）を道路の面から拾う
        ents = [(p_, l_, lab_) for f_, p_, l_, k_, lab_ in d['openings']
                if f_ == face and k_ == 'entry']
        ents.sort()
        house = None
        for p_, l_, lab_ in ents:
            if '玄関' in (lab_ or ''):
                house = (p_, l_)
        if house is None and ents:
            house = (ents[0][0], ents[0][1])

        # 面ごとの座標のとり方をそろえる
        if face in ('S', 'N'):
            edge = sy0 if face == 'S' else sy1
            wall = 0 if face == 'S' else ny
            sgn = 1 if face == 'S' else -1          # 敷地の外から建物へ向く向き

            def out(v, o):                          # 沿い座標 v、外へ o
                return px(v), py(edge + sgn * o)

            def to_wall(v, o):
                return px(v), py(wall - sgn * o)
            span = (0, nx)
        else:
            edge = sx1 if face == 'E' else sx0
            wall = nx if face == 'E' else 0
            sgn = -1 if face == 'E' else 1

            def out(v, o):
                return px(edge + sgn * o), py(v)

            def to_wall(v, o):
                return px(wall - sgn * o), py(v)
            span = (0, ny)

        yard = abs(edge - wall)                     # 道路側のあき（マス）

        # 門とアプローチ … 住宅の玄関の正面だけ。店舗の前には置かない
        if house:
            gc = house[0] + house[1] / 2.0
            gw = max(house[1], 1.0) / 2.0
            for dd in (-gw, gw):
                x1_, y1_ = out(gc + dd, -0.12)
                x2_, y2_ = out(gc + dd, 0.12)
                s.line(x1_, y1_, x2_, y2_, stroke=INK, stroke_width=2.6)
            tx_, ty_ = out(gc - gw - 0.5, 0.35)
            s.text(tx_, ty_ + 4, '門', size=8.5)
            for dd in (-gw, gw):
                a_ = out(gc + dd, 0.0)
                b_ = to_wall(gc + dd, 0.0)
                s.line(a_[0], a_[1], b_[0], b_[1], stroke='#666',
                       stroke_width=0.8)
            tx_, ty_ = out(gc, (yard - 1.0) / 2.0 + 0.15)
            s.text(tx_, ty_ + 4, 'アプローチ', size=8, fill='#333')
            tip = out(gc, 0.02)                # 先っぽは敷地の内がわ
            back = out(gc, -0.26)              # おしりは道路がわ
            if face in ('S', 'N'):
                s.polygon([tip, (back[0] - 6, back[1]),
                           (back[0] + 6, back[1])], fill=INK)
            else:
                s.polygon([tip, (back[0], back[1] - 6),
                           (back[0], back[1] + 6)], fill=INK)

        # 玄関ポーチ … 玄関の前に1マス。GL＋380（土間より20低くして雨を入れない）
        if house:
            gc = house[0] + house[1] / 2.0
            gw = max(house[1], 1.0) / 2.0
            c0, c1 = to_wall(gc - gw, 0.0), to_wall(gc + gw, 1.0)
            s.rect(min(c0[0], c1[0]), min(c0[1], c1[1]),
                   abs(c1[0] - c0[0]), abs(c1[1] - c0[1]),
                   fill='#fff', stroke=INK, stroke_width=1.0)
            tx_, ty_ = to_wall(gc, 0.62)
            s.text(tx_, ty_ - 1, 'ポーチ', size=8)
            s.text(tx_, ty_ + 9, DOMA['porch'], size=8, fill='#333')

        # 店舗出入口の段 … 売場の床は GL＋550 なので、外から3段（踏面270）
        shop = [(p_, l_) for p_, l_, lab_ in ents if (p_, l_) != house]
        shop = max(shop, key=lambda t_: t_[1]) if shop else None
        if shop:
            sp_, sl_ = shop
            n_step, tread = 3, 270 / 910.0
            for k in range(1, n_step + 1):
                a_ = to_wall(sp_, k * tread)
                b_ = to_wall(sp_ + sl_, k * tread)
                s.line(a_[0], a_[1], b_[0], b_[1], stroke=INK,
                       stroke_width=0.9)
            for v_ in (sp_, sp_ + sl_):
                a_ = to_wall(v_, 0.0)
                b_ = to_wall(v_, n_step * tread)
                s.line(a_[0], a_[1], b_[0], b_[1], stroke=INK,
                       stroke_width=0.9)
            tx_, ty_ = to_wall(sp_ + sl_ / 2.0, n_step * tread + 0.3)
            s.text(tx_, ty_ + 3, '3段', size=8, fill='#333')

        # 駐輪スペース … 店の出入口の横（客が使う）。段やアプローチには重ねない
        n_bike = 4
        bw_, bd_ = 600 / 910.0, 1800 / 910.0
        if yard > bd_ + 0.3:
            lo_, hi_ = ((sx0, sx1) if face in ('S', 'N') else (sy0, sy1))
            used = []
            if house:
                used.append((house[0] + house[1] / 2.0 - gw - 0.05,
                             house[0] + house[1] / 2.0 + gw + 0.05))
            if shop:
                used.append((shop[0] - 0.2, shop[0] + shop[1] + 0.2))
            cands = [span[1] - 0.4 - n_bike * bw_]
            if shop:
                cands = [shop[0] + shop[1] + 0.2, shop[0] - 0.2 - n_bike * bw_] + cands
            start = cands[-1]
            for c_ in cands:
                if c_ < lo_ + 0.3 or c_ + n_bike * bw_ > hi_ - 0.3:
                    continue
                if any(c_ < u1 and c_ + n_bike * bw_ > u0 for u0, u1 in used):
                    continue
                start = c_
                break
            for k in range(n_bike):
                v0 = start + k * bw_
                c0 = out(v0, 0.18)
                c1 = out(v0 + bw_, 0.18 + bd_)
                x_, y_ = min(c0[0], c1[0]), min(c0[1], c1[1])
                s.rect(x_, y_, abs(c1[0] - c0[0]), abs(c1[1] - c0[1]),
                       fill='#fff', stroke='#333', stroke_width=0.8)
            if face in ('S', 'N'):
                tx_, ty_ = out(start - 0.2, 0.18 + bd_ / 2.0)
                s.text(tx_, ty_ + 3, '駐輪スペース（%d台）' % n_bike, size=8,
                       anchor='end')
            else:                              # 東西の道路なら手前に横書き
                tx_, ty_ = out(start - 0.25, 0.18 + bd_ / 2.0)
                s.text(tx_, ty_ + 3, '駐輪スペース（%d台）' % n_bike, size=8)

        # 植栽 … 建物の横のあき（アプローチや駐輪とぶつからないところ）
        if face in ('S', 'N'):
            v0, oo = sx0 + 0.5, yard * 0.45
        else:
            v0, oo = sy0 + 0.5, yard * 0.45
        for k in range(3):
            cx_, cy_ = out(v0 + k * 0.62, oo)
            s.circle(cx_, cy_, 8, fill='#fff', stroke='#666',
                     stroke_width=0.8)
        tx_, ty_ = out(v0 + 0.62, oo + 0.42)
        s.text(tx_, ty_, '植栽', size=8)

        # あき寸法（敷地境界線と建築物との距離）
        s.dim_v(py(0), py(sy0), px(sx0) + 22,
                format(int(round(-sy0 * 910)), ','), size=8.5,
                anchor='start', dx=5)
        s.dim_v(py(sy1), py(ny), px(sx0) + 22,
                format(int(round((sy1 - ny) * 910)), ','), size=8.5,
                anchor='start', dx=5)
        s.dim_h(px(sx0), px(0), py(sy1) - 20,
                format(int(round(-sx0 * 910)), ','), size=8.5)
        s.dim_h(px(nx), px(sx1), py(sy1) - 20,
                format(int(round((sx1 - nx) * 910)), ','), size=8.5)
        s.text(px(sx1) - 10, py(sy0) - 12, '敷地面積 %s㎡' % site['area'],
               size=9, anchor='end', fill='#333')

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
        """引違い窓。壁の2本＋まん中に細い線1本、両はしに短いたて線。

        幅が2マスを超えるときは4枚建てになるので、ガラスの合わせ目の
        たて線を1/4ずつの位置に足す。
        """
        wall_line(ori, ln_, a, b, thin=True)
        if ori == 'V':
            s.line(px(ln_), py(a), px(ln_), py(b), stroke=INK,
                   stroke_width=0.7)
        else:
            s.line(px(a), py(ln_), px(b), py(ln_), stroke=INK,
                   stroke_width=0.7)
        jamb(ori, ln_, a)
        jamb(ori, ln_, b)
        if b - a > 2.05:                       # 4枚建て
            for k in (1, 2, 3):
                jamb(ori, ln_, a + (b - a) * k / 4.0)

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

    def single_slide(ori, ln_, a, b, side):
        """片引き戸。戸1枚を穴の中に太線、引込み側の壁ぞいに細線（戸のしまう場所）。

        side = +1 なら b のほうへ、-1 なら a のほうへしまう。
        """
        w_ = b - a
        jamb(ori, ln_, a)
        jamb(ori, ln_, b)
        q0, q1 = (b, b + w_) if side > 0 else (a - w_, a)
        off = h + 4.5                 # 戸の板は壁の面から少し出して描く（壁と区別がつく）
        if ori == 'V':
            s.line(px(ln_), py(a), px(ln_), py(b), stroke=INK,
                   stroke_width=0.6)                            # 穴の中のレール
            s.line(px(ln_) + off, py(a), px(ln_) + off, py(b), stroke=INK,
                   stroke_width=1.8)                            # 戸1枚
            s.line(px(ln_) + off, py(q0), px(ln_) + off, py(q1),
                   stroke='#777', stroke_width=0.7)             # 引込み
        else:
            s.line(px(a), py(ln_), px(b), py(ln_), stroke=INK,
                   stroke_width=0.6)
            s.line(px(a), py(ln_) - off, px(b), py(ln_) - off, stroke=INK,
                   stroke_width=1.8)
            s.line(px(q0), py(ln_) - off, px(q1), py(ln_) - off,
                   stroke='#777', stroke_width=0.7)

    def slide_room(ori, ln_, a, b):
        """片引き戸にできるか。壁ぞいに戸1枚ぶんの余白がある側を返す（なければ 0）。"""
        w_ = b - a
        segs = plans._wall_segments({0: d}).get((ori, ln_), [])
        seg = [(p_, q_) for p_, q_ in segs if p_ - 1e-6 <= a and b <= q_ + 1e-6]
        if not seg:
            return 0
        lo_, hi_ = seg[0]
        for p_, q_, k_, f_ in op.get((ori, ln_), []):
            if (p_, q_) == (a, b):
                continue
            if q_ <= a + 1e-6:
                lo_ = max(lo_, q_)
            if p_ >= b - 1e-6:
                hi_ = min(hi_, p_)
        # 直交する壁（柱）にぶつかる所までしか引き込めない
        for (o2, l2), s2 in plans._wall_segments({0: d}).items():
            if o2 == ori:
                continue
            if any(p_ - 1e-9 <= ln_ <= q_ + 1e-9 for p_, q_ in s2):
                if b - 1e-6 <= l2 < hi_:
                    hi_ = l2
                if lo_ < l2 <= a + 1e-6:
                    lo_ = l2
        if hi_ - b >= w_ - 1e-6:
            return 1
        if a - lo_ >= w_ - 1e-6:
            return -1
        return 0

    def hinged(ori, ln_, a, b, inward=1):
        """開き戸。戸の板と四分円の弧。（この教材の解答例では使わない）"""
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
                # 室内の建具はすべて引き戸（段差なし・開いた戸が通路をふさがない）。
                # 戸をしまう壁があれば片引き戸、なければ引違い戸
                side = slide_room(ori, ln_, a, b)
                if b - a >= 1.9 or side == 0:
                    slide(ori, ln_, a, b)
                else:
                    single_slide(ori, ln_, a, b, side)
                # 階段室（竪穴区画）の壁にある建具は防火設備
                fa, fb, fc, fd = d.get('stair_box', (0, 2, 2, 6))
                on_stair = ((ori == 'V' and ln_ in (fa, fc)
                             and a >= fb - 1e-6 and b <= fd + 1e-6) or
                            (ori == 'H' and ln_ in (fb, fd)
                             and a >= fa - 1e-6 and b <= fc + 1e-6))
                if on_stair:
                    if ori == 'V':                 # 東西の壁 → 階段室の内がわに
                        inside = ln_ >= fc
                        s.text(px(ln_) + (-6 if inside else 6),
                               py((a + b) / 2.0) + 3, '防火設備', size=6.5,
                               fill='#111', anchor='end' if inside else 'start')
                    elif ln_ <= fb:                # 南の壁 → 上（階段室の中）
                        s.text(px((a + b) / 2.0), py(ln_) - 5, '防火設備',
                               size=6.5, fill='#111')
                    else:                          # 北の壁 → 下（「竪穴区画」の次の行）
                        s.text(px((a + b) / 2.0), py(ln_) + 22, '防火設備',
                               size=6.5, fill='#111')
    # ---- バルコニー（壁の外に1マス張り出す。手すりは外側の2本線） ----
    for key, lst in op.items():
        ori, ln_ = key
        for a, b, kind, face in lst:
            if kind != 'balc':
                continue
            dep = 1.0
            if ori == 'H':
                out = -1 if face == 'S' else 1
                x0b, x1b = px(a), px(b)
                y_in = py(ln_)
                y_out = py(ln_ + out * dep)
                s.rect(min(x0b, x1b), min(y_in, y_out), abs(x1b - x0b),
                       abs(y_out - y_in), fill='none', stroke=INK,
                       stroke_width=1.0)
                s.line(x0b, y_out + (3 if out < 0 else -3) * -1,
                       x1b, y_out + (3 if out < 0 else -3) * -1,
                       stroke=INK, stroke_width=0.8)
                s.text((x0b + x1b) / 2.0, (y_in + y_out) / 2.0 + 3,
                       'バルコニー', size=7.5, fill='#111')
                s.text((x0b + x1b) / 2.0, (y_in + y_out) / 2.0 + 13,
                       '手すり H=1,100', size=6, fill='#333')
            else:
                out = 1 if face == 'E' else -1
                y0b, y1b = py(a), py(b)
                x_in = px(ln_)
                x_out = px(ln_ + out * dep)
                s.rect(min(x_in, x_out), min(y0b, y1b), abs(x_out - x_in),
                       abs(y1b - y0b), fill='none', stroke=INK,
                       stroke_width=1.0)
                s.line(x_out - out * 3, y0b, x_out - out * 3, y1b,
                       stroke=INK, stroke_width=0.8)
                s.text_rot((x_in + x_out) / 2.0, (y0b + y1b) / 2.0,
                           'バルコニー', -90, size=7.5, fill='#111')

    # ---- 家具・設備 ----
    # 実際に使えるように置く：戸の前（開口の幅 × 奥行0.9マス）と外の出入口の前には
    # 何も置かない。家具どうしも重ねない。置けなかったものは conflicts に記録する。
    cur = [None]                       # いま家具を描いている部屋
    ROOMS = [(r[2], r[3], r[4], r[5]) for r in d['rooms']]
    PLACED = {}                        # 部屋番号 → [(名前, a, b, c, e)]
    CLEAR = 0.9                        # 戸の前にあける奥行（マス）

    zones = []                         # （四角, 種類）戸・出入口の前の「あけておく」所
    for o_, w_, p_, l_ in d.get('doors', []):
        if o_ == 'H':
            zones.append(((p_, w_ - CLEAR, p_ + l_, w_ + CLEAR), 'door'))
        else:
            zones.append(((w_ - CLEAR, p_, w_ + CLEAR, p_ + l_), 'door'))
    for f_, p_, l_, k_, _lab in d['openings']:
        if k_ != 'entry':
            continue
        if f_ == 'S':
            zones.append(((p_, 0, p_ + l_, CLEAR), 'entry'))
        elif f_ == 'N':
            zones.append(((p_, ny - CLEAR, p_ + l_, ny), 'entry'))
        elif f_ == 'E':
            zones.append(((nx - CLEAR, p_, nx, p_ + l_), 'entry'))
        else:
            zones.append(((0, p_, CLEAR, p_ + l_), 'entry'))

    def hit(r1, r2, eps=1e-6):
        return (r1[0] < r2[2] - eps and r1[2] > r2[0] + eps
                and r1[1] < r2[3] - eps and r1[3] > r2[1] + eps)

    def ok_here(a, b, c, e):
        """他の部屋にかぶる家具は描かない（L字の部屋のはみ出しよけ）。"""
        me = ROOMS[cur[0]] if cur[0] is not None else None
        for i, (ra, rb, rc, re) in enumerate(ROOMS):
            if i == cur[0]:
                continue
            if me and ra <= me[0] and rb <= me[1] and rc >= me[2] and re >= me[3]:
                continue                       # 自分をすっぽり含む部屋（L字の親）は無視
            if a < rc - 1e-6 and c > ra + 1e-6 and b < re - 1e-6 \
                    and e > rb + 1e-6:
                return False
        return True

    def free(rect, room):
        """その四角に置けるか：部屋の中・戸の前でない・他の家具と重ならない。"""
        ra, rb, rc, re = room
        a, b, c, e = rect
        if a < ra - 1e-6 or c > rc + 1e-6 or b < rb - 1e-6 or e > re + 1e-6:
            return False
        if not ok_here(a, b, c, e):
            return False
        if any(hit(rect, z) for z, _ in zones):
            return False
        return not any(hit(rect, r[1:]) for r in PLACED.get(cur[0], []))

    def spots(room, w, hh, m=0.1, step=0.25):
        """置き場所の候補：四すみ → 4つの壁ぞいを 0.25マスきざみ → 中ほど。"""
        ra, rb, rc, re = room
        out = [(ra + m, rb + m), (rc - m - w, rb + m),
               (ra + m, re - m - hh), (rc - m - w, re - m - hh)]
        xx = ra + m
        while xx <= rc - m - w + 1e-6:
            out += [(xx, rb + m), (xx, re - m - hh)]
            xx += step
        yy = rb + m
        while yy <= re - m - hh + 1e-6:
            out += [(ra + m, yy), (rc - m - w, yy)]
            yy += step
        out.append(((ra + rc) / 2.0 - w / 2.0, (rb + re) / 2.0 - hh / 2.0))
        return out

    def on_wall(rect, room, w, hh, m=0.1):
        """長い辺が壁にくっついているか（流し台・棚・ベッドなどは壁づけ）。"""
        ra, rb, rc, re = room
        a, b, c, e = rect
        ys = abs(b - (rb + m)) < 1e-6 or abs(e - (re - m)) < 1e-6
        xs = abs(a - (ra + m)) < 1e-6 or abs(c - (rc - m)) < 1e-6
        if abs(w - hh) < 1e-6:
            return xs or ys
        return ys if w > hh else xs

    def zdist(rect, kind=None):
        """戸の前の四角までの近さ（小さいほど戸に近い）。その部屋にかかる戸だけ見る。"""
        room = ROOMS[cur[0]]
        ds = []
        for z, k_ in zones:
            if kind and k_ != kind:
                continue
            if not hit(z, room):
                continue
            cx, cy = (z[0] + z[2]) / 2.0, (z[1] + z[3]) / 2.0
            ds.append(abs((rect[0] + rect[2]) / 2.0 - cx)
                      + abs((rect[1] + rect[3]) / 2.0 - cy))
        return min(ds) if ds else 0.0

    def put(name, sizes, prefer='far', cands=None, kind=None, optional=False,
            wall=False):
        """家具を置く。sizes=[(幅, 奥行, 描く関数), ...]（向きちがいの候補）。

        候補の場所のうち、置ける最初の所に描く。
        prefer='far'  … 戸からいちばん遠い所から順に試す（便器・浴槽・ベッド）
        prefer='near' … 戸にいちばん近い所から順（レジ・収納）
        prefer='list' … cands の順のまま
        """
        room = ROOMS[cur[0]]
        for w, hh, fn in sizes:
            cs = cands if cands is not None else spots(room, w, hh)
            rects = [(x, y, x + w, y + hh) for x, y in cs]
            if wall:
                rects = [r for r in rects if on_wall(r, room, w, hh)]
            if prefer == 'far':       # 0.5マスきざみで見て、同じなら四すみ優先（候補の順）
                rects.sort(key=lambda r: -round(zdist(r, kind) * 2) / 2.0)
            elif prefer == 'near':
                rects.sort(key=lambda r: round(zdist(r, kind) * 2) / 2.0)
            for r in rects:
                if free(r, room):
                    fn(r[0], r[1])
                    PLACED.setdefault(cur[0], []).append((name,) + r)
                    return r
        if not optional:                   # 問題文で要求された家具だけ記録する
            conflicts.append('%s：「%s」を置く場所がない（戸の前をあけると入らない）'
                             % (d['rooms'][cur[0]][0].replace('　', ''), name))
        return None

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

    # ---- 家具の描き方（x, y は置く四角の左下） ----
    def toilet(x, y):                   # 0.85 × 0.95：洋式便器（タンク付き）と小さな手洗い
        R(x + .02, y + .72, x + .52, y + .90)
        ell(x + .27, y + .50, .17, .22)
        R(x + .62, y + .70, x + .85, y + .92)
        ell(x + .735, y + .81, .07, .07)

    def basin_h(x, y, w=.9):            # w × 0.5：洗面台（横向き）
        R(x, y, x + w, y + .5)
        ell(x + w / 2.0, y + .25, .16, .13)

    def basin_v(x, y, w=.9):            # 0.5 × w：洗面台（縦向き）
        R(x, y, x + .5, y + w)
        ell(x + .25, y + w / 2.0, .13, .16)

    def washer(x, y):                   # 0.7 × 0.7：洗濯機
        R(x, y, x + .7, y + .7)
        ell(x + .35, y + .35, .2, .2)

    def tub_v(x, y, ln=1.7):            # 0.8 × ln：浴槽（縦）
        R(x, y, x + .8, y + ln)
        R(x + .1, y + .1, x + .7, y + ln - .1)

    def tub_h(x, y, ln=1.7):            # ln × 0.8：浴槽（横）
        R(x, y, x + ln, y + .8)
        R(x + .1, y + .1, x + ln - .1, y + .7)

    def kitchen_h(x, y, ln):            # (ln+0.6) × 0.6：流し・調理台・コンロ＋冷蔵庫
        R(x, y, x + ln, y + .6)
        ell(x + .45, y + .3, .16, .16)
        for i in range(2):
            for j in range(2):
                ell(x + ln - .45 + i * .22, y + .18 + j * .24, .06, .06)
        R(x + ln, y, x + ln + .6, y + .6)
        T(x + ln, y, x + ln + .6, y + .6, '冷', 7.5)

    def kitchen_v(x, y, ln):            # 0.6 × (ln+0.6)
        R(x, y, x + .6, y + ln)
        ell(x + .3, y + ln - .45, .16, .16)
        for i in range(2):
            for j in range(2):
                ell(x + .18 + i * .24, y + .30 + j * .22, .06, .06)
        R(x, y + ln, x + .6, y + ln + .6)
        T(x, y + ln, x + .6, y + ln + .6, '冷', 7.5)

    def bed(x, y, w=1.0, hh=2.2):       # 1.0 × 2.2
        R(x, y, x + w, y + hh)
        s.line(px(x), py(y + hh - .35), px(x + w), py(y + hh - .35),
               stroke='#333', stroke_width=0.7)

    def desk(x, y, w=1.3, hh=.7):
        R(x, y, x + w, y + hh)

    def closet(x, y, w=.9, hh=.9, t='収納'):
        R(x, y, x + w, y + hh, dash='4 3')
        T(x, y, x + w, y + hh, t, 8)

    def sofa(x, y, w=2.0):              # w × 0.9
        R(x, y, x + w, y + .9)
        s.line(px(x), py(y + .62), px(x + w), py(y + .62), stroke='#333',
               stroke_width=0.7)

    def table(x, y, w=2.2, hh=1.2, n=3):   # w × hh（いすを含む）
        a, b, c, e = x, y, x + w, y + hh
        R(a + .25, b + .25, c - .25, e - .25)
        for i in range(n):
            t_ = a + .45 + i * ((c - a - .9) / max(1, n - 1))
            R(t_ - .16, b, t_ + .16, b + .22)
            R(t_ - .16, e - .22, t_ + .16, e)

    def shelf(x, y, w, hh=.25):
        R(x, y, x + w, y + hh)

    def counter(x, y, w=1.5, hh=.65):
        R(x, y, x + w, y + hh)
        T(x, y, x + w, y + hh, 'レジ', 8)

    def lockers(x, y):                  # 0.8 × 0.8：ロッカー2つ
        for i in range(2):
            R(x + i * .45, y, x + .35 + i * .45, y + .8)
        T(x - .05, y - .25, x + .85, y - .05, 'ロッカー', 6.5)

    def tatami(a, b, c, e):
        n = int(round((e - b) / 1.0))
        for i in range(1, n):
            s.line(px(a) + 2, py(b + i), px(c) - 2, py(b + i), stroke='#999',
                   stroke_width=0.6)
        s.line(px((a + c) / 2.0), py(b) - 2, px((a + c) / 2.0), py(e) + 2,
               stroke='#999', stroke_width=0.6)

    def furnish(name, a, b, c, e):
        w, hh = c - a, e - b
        room = (a, b, c, e)
        if '便所' in name:
            put('洋式便器', [(.85, .95, toilet)], 'far', wall=True)
            if '店舗' in name:
                put('手洗い器', [(.55, .5, lambda x, y: (R(x, y, x + .55, y + .5),
                                                    T(x, y, x + .55, y + .5, '手洗', 6.5)))],
                    'near', wall=True)
        elif '洗面' in name and '脱衣' in name:
            put('洗濯機', [(.7, .7, washer)], 'far', wall=True)
            put('洗面台', [(bw, .5, (lambda bw_: lambda x, y: basin_h(x, y, bw_))(bw))
                          for bw in (1.2, 1.0, .85) if bw <= w - .9] +
                         [(.5, bw, (lambda bw_: lambda x, y: basin_v(x, y, bw_))(bw))
                          for bw in (1.2, 1.0, .85) if bw <= hh - .9], 'far', wall=True)
        elif '浴室' in name:
            R(a + .06, b + .06, c - .06, e - .06)          # ユニットバスの外形
            ln_ = min(1.7, max(w, hh) - .3)
            put('浴槽', [(.8, ln_, lambda x, y: tub_v(x, y, ln_)),
                        (ln_, .8, lambda x, y: tub_h(x, y, ln_))], 'far', wall=True)
        elif '厨房' in name or '作業場' in name:
            sizes = []
            for ln_ in (2.0, 1.6, 1.4):          # 長い順に試す（戸の前をあけて入る長さ）
                sizes.append((ln_ + .6, .6, (lambda L: lambda x, y: kitchen_h(x, y, L))(ln_)))
                sizes.append((.6, ln_ + .6, (lambda L: lambda x, y: kitchen_v(x, y, L))(ln_)))
            put('流し台・調理台・コンロ台・冷蔵庫', sizes, 'far', wall=True)
            def box(lab, size):
                def fn(x, y):
                    R(x, y, x + size[0], y + size[1])
                    T(x, y, x + size[0], y + size[1], lab, size[2])
                return fn
            put('作業台', [(.7, 1.0, box('作業台', (.7, 1.0, 7.5))), (1.0, .7, box('作業台', (1.0, .7, 7.5))),
                          (.6, .9, box('作業台', (.6, .9, 6.5))), (.9, .6, box('作業台', (.9, .6, 6.5)))], 'far', wall=True)
            put('オーブン', [(.7, .7, box('ｵｰﾌﾞﾝ', (.7, .7, 6))), (.6, .6, box('ｵｰﾌﾞﾝ', (.6, .6, 5.5)))], 'far', wall=True)
        elif '売場' in name:
            # 陳列棚：壁ぎわと中ほどに長い棚を3本（戸と出入口の前はあける）。
            # レジは出入口の近く（ただし出入口の前はあける）
            L = min(3.0, max(w, hh) - 2.4)
            sz = []
            for L_ in (L, L - 1.0):
                sz += [(.32, L_, (lambda q: lambda x, y: shelf(x, y, .32, q))(L_)),
                       (L_, .32, (lambda q: lambda x, y: shelf(x, y, q, .32))(L_))]
            for i in range(3):
                put('陳列棚', sz, 'far', optional=(i == 2))
            put('レジカウンター', [(1.5, .65, lambda x, y: counter(x, y)),
                                  (.65, 1.5, lambda x, y: (R(x, y, x + .65, y + 1.5),
                                                          T(x, y, x + .65, y + 1.5, 'レジ', 8)))],
                'near', kind='entry')
        elif '居間' in name or 'ＬＤＫ' in name or 'LDK' in name:
            # 台所は北の壁（家事室・和室がわ）に。入らなければ西の壁の北寄り。ソファーは窓（南）がわ
            xs = [a + .1 + i * .25 for i in range(int((w - 2.6) / .25) + 1)]
            ys = [e - .1 - 2.4 - i * .25 for i in range(int((hh - 2.6) / .25) + 1)]
            r_ = put('台所設備機器', [(2.4, .6, lambda x, y: kitchen_h(x, y, 1.8))], 'list',
                     cands=[(x, e - .1 - .6) for x in xs], optional=True, wall=True)
            if r_ is None:
                put('台所設備機器', [(.6, 2.4, lambda x, y: kitchen_v(x, y, 1.8))], 'list',
                    cands=[(a + .1, y) for y in ys], wall=True)
            put('テーブル・椅子', [(2.2, 1.2, lambda x, y: table(x, y, 2.2, 1.2, 3)),
                                 (1.2, 2.2, lambda x, y: table(x, y, 1.2, 2.2, 2))],
                'list', cands=spots(room, 2.2, 1.2, .5))
            put('ソファー', [(2.0, .9, sofa), (.9, 2.0, lambda x, y: R(x, y, x + .9, y + 2.0))], 'far')
        elif '和室' in name:
            tatami(a, b, c, e)
            put('押入れ', [(.9, .9, lambda x, y: closet(x, y, .9, .9, '押入'))], 'far', wall=True)
        elif '寝室' in name:
            put('ベッド1', [(1.0, 2.2, bed), (2.2, 1.0, lambda x, y: bed(x, y, 2.2, 1.0))], 'far', wall=True)
            put('ベッド2', [(1.0, 2.2, bed), (2.2, 1.0, lambda x, y: bed(x, y, 2.2, 1.0))], 'far', wall=True)
            put('収納', [(.9, .9, closet)], 'near', wall=True)
        elif '子供室' in name or '子ども室' in name:
            put('ベッド', [(1.0, 2.2, bed), (2.2, 1.0, lambda x, y: bed(x, y, 2.2, 1.0))], 'far', wall=True)
            put('机', [(1.3, .7, desk), (.7, 1.3, lambda x, y: desk(x, y, .7, 1.3))], 'far', wall=True)
            put('収納', [(.9, .9, closet)], 'near', wall=True)
        elif '玄関' in name:
            put('下足入れ', [(.4, .8, lambda x, y: (R(x, y, x + .4, y + .8),
                                                  s.text_rot(px(x + .2) + 2.5, py(y + .4), '下足入れ', -90, size=6.5))),
                            (.8, .4, lambda x, y: (R(x, y, x + .8, y + .4),
                                                  T(x, y, x + .8, y + .4, '下足入れ', 6.5)))], 'far', wall=True)
        elif '倉庫' in name or '納戸' in name or '収納' in name:
            sw_ = max(.8, min(w, hh) - .3)
            put('棚', [(sw_, .3, lambda x, y: shelf(x, y, sw_, .3)),
                      (.3, sw_, lambda x, y: shelf(x, y, .3, sw_))], 'far', optional=True, wall=True)
            put('棚', [(sw_ - .5, .3, lambda x, y: shelf(x, y, sw_ - .5, .3)),
                      (.3, sw_ - .5, lambda x, y: shelf(x, y, .3, sw_ - .5))], 'far', optional=True, wall=True)
            T(a, b, c, e, '棚', 8)
        elif 'スタッフ' in name:
            put('テーブル・椅子', [(1.7, 1.1, lambda x, y: table(x, y, 1.7, 1.1, 2)),
                                 (1.1, 1.7, lambda x, y: table(x, y, 1.1, 1.7, 2)),
                                 (1.4, 1.0, lambda x, y: table(x, y, 1.4, 1.0, 2)),
                                 (1.0, 1.4, lambda x, y: table(x, y, 1.0, 1.4, 2))], 'far')
            put('ロッカー', [(.8, .8, lockers)], 'near', wall=True)
        elif '家事' in name:
            sw_ = max(.8, min(w, hh) - .3)
            put('棚', [(sw_, .5, lambda x, y: (shelf(x, y, sw_, .5), T(x, y, x + sw_, y + .5, '棚', 7.5))),
                      (.5, sw_, lambda x, y: (shelf(x, y, .5, sw_), T(x, y, x + .5, y + sw_, '棚', 7.5)))], 'far', wall=True)
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
    Tt = 0.25          # 踏面227.5mm（910÷4）。令23条の210mm以上を満たす
    flip = bool(d.get('stair_flip'))   # True: 北の玄関から上って南に踊り場（F型）
    land = (sb + 1) if flip else (sd - 1)
    sg = -1.0 if flip else 1.0         # 段の並ぶ向き（踊り場から見て）
    n1, n2 = d.get('stair_runs', (6, 7))
    mode = d.get('stair_mode') or (
        'top' if 'DN' in d.get('stair_up', '') else 'bottom')
    s.line(px(sa) + h, py(land), px(sc) - h, py(land), stroke=INK,
           stroke_width=1.2)
    s.text(px(mid), py(land + sg * 0.45) + (0 if not flip else 6), '踊場',
           size=8, fill='#333')
    s.line(px(mid), py(sd if flip else sb), px(mid), py(land), stroke=INK,
           stroke_width=1.5)
    if flip:                            # 段の途中に、手摺の線にそって縦書き
        s.text_rot(px(mid) - 5, py(land - sg * n1 * Tt / 2.0), '手摺', -90,
                   size=7.5, fill='#333')
    else:
        s.text(px(mid) + 12, py(land) + 12, '手摺', size=7.5, fill='#333')
    for k in range(1, n1 + 1):
        s.line(px(mid) + 1.5, py(land - sg * k * Tt), px(sc) - h,
               py(land - sg * k * Tt), stroke=INK, stroke_width=0.8)
    for k in range(1, n2 + 1):
        s.line(px(sa) + h, py(land - sg * k * Tt), px(mid) - 1.5,
               py(land - sg * k * Tt), stroke=INK, stroke_width=0.8)

    def arrow(gx, n, lab_):
        ax = px(gx)
        yb, yt = py(land - sg * (n * Tt + .22)), py(land - sg * .12)
        e_ = 8 if not flip else -8                 # 矢印は踊り場へ向く
        s.line(ax, yb, ax, yt + e_, stroke=INK, stroke_width=1.2)
        s.polygon([(ax, yt), (ax - 4, yt + e_), (ax + 4, yt + e_)], fill=INK)
        s.text(ax, yb + (12 if not flip else -6), lab_, size=9, weight='700')

    def brk(g0, g1, gy):
        x_0, x_1, yy = px(g0), px(g1), py(gy)
        s.line(x_0, yy + 6, x_1, yy - 6, stroke=INK, stroke_width=0.9)
        s.line(x_0, yy + 11, x_1, yy - 1, stroke=INK, stroke_width=0.9)

    if mode in ('bottom', 'middle'):
        arrow((mid + sc) / 2.0, n1, 'UP')
        brk(mid + .05, sc - .05, land - sg * (n1 - 1) * Tt)
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
        if fl and '玄関' in name:
            _draw_genkan(s, px, py, name, ar, a, b, c, e, genkan_face(d), fl)
            continue
        cx = (px(a) + px(c)) / 2.0
        cy = (py(e - 1.05 if d.get('stair_flip') else b + .62) if kind == 'stair'
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

    # ---- 寸法（通りごとのスパン＋全体） ----
    xs = [g for g, _ in xlines]
    ys = [g for g, _ in ylines]
    bal = G + 6 if any(k == 'balc' and f == 'S'
                       for lst in op.values() for _, _, k, f in lst) else 0
    # 道路がわはポーチ・段・駐輪で混むので、寸法は反対がわに出す
    if site and rface == 'S':
        dy1, dy2 = y0 - 66, y0 - 94
    else:
        dy1, dy2 = y1 + 34 + bal, y1 + 62 + bal
    for a, b in zip(xs[:-1], xs[1:]):
        s.dim_h(px(a), px(b), dy1, format(int((b - a) * 910), ','), size=9)
    s.dim_h(x0, x1, dy2, format(nx * 910, ','))
    if site and rface == 'E':
        dx1, dx2, anc, ddx = x0 - 66, x0 - 132, 'end', -6
    else:
        dx1, dx2, anc, ddx = x1 + 30, x1 + 96, 'start', 6
    for a, b in zip(ys[:-1], ys[1:]):
        s.dim_v(py(a), py(b), dx1, format(int((b - a) * 910), ','),
                size=9, anchor=anc, dx=ddx)
    s.dim_v(y1, y0, dx2, format(ny * 910, ','), anchor=anc, dx=ddx)

    # ---- 部分詳細図の切断位置と方向（1階平面図に記入する） ----
    if d.get('cut'):
        cx_ = px(d['cut'])
        s.line(cx_, py(0) - 30, cx_, py(0) + 40, stroke=INK,
               stroke_width=2.6)
        for yy_ in (py(0) - 26, py(0) + 34):
            s.line(cx_, yy_, cx_ + 22, yy_, stroke=INK, stroke_width=1.4)
            s.polygon([(cx_ + 22, yy_), (cx_ + 13, yy_ - 4),
                       (cx_ + 13, yy_ + 4)], fill=INK)
        s.text(cx_ - 8, py(0) - 34, 'Ｙ', size=10, anchor='end',
               weight='700')
        s.text(cx_ - 8, py(0) + 48, 'Ｙ', size=10, anchor='end',
               weight='700')
        s.text(cx_ + 26, py(0) + 52, '部分詳細図の切断位置', size=8,
               anchor='start', fill='#333')

    # ---- 方位・道路 ----
    if d.get('road', True) and not site:
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
    nxp, nyp = W - 34, 34
    s.circle(nxp, nyp, 12, fill='#fff', stroke='#444', stroke_width=0.9)
    s.polygon([(nxp, nyp - 9), (nxp - 4, nyp + 7), (nxp, nyp + 3),
               (nxp + 4, nyp + 7)], fill=INK)
    s.text(nxp, nyp + 24, 'N', size=9.5, weight='700')
    return s


def sheet_data(k, i):
    """予想問題 k（A〜F）の i 階（0始まり）の答案用紙データと図名。"""
    import answers
    import sitemap
    fl = answers.PLANS[k]
    f0 = fl[0]
    floors = {j + 1: e for j, e in enumerate(fl)}
    fits = plans.fit_all(floors, f0.get('nx', plans.NX), f0.get('ny', plans.NY),
                         f0.get('xlines', plans.XLINES), f0.get('ylines', plans.YLINES))
    ti = ('１階平面図 兼 配置図　縮尺1／100', '２階平面図　縮尺1／100',
          '３階平面図　縮尺1／100')[i]
    dd = dict(fl[i])
    dd['openings'] = fits[i + 1]
    dd['fitted'] = True
    dd['doors'] = plans.fit_doors(dd, floors)
    dd['fitted_doors'] = True
    dd['tooshi'], dd['kuda'] = plans.columns_of(
        i + 1, floors, f0.get('nx', plans.NX), f0.get('ny', plans.NY),
        f0.get('xlines', plans.XLINES), f0.get('ylines', plans.YLINES))
    dd['floor_label'] = 'GL＋550' if i == 0 else ''
    if i == 0:
        dd['cut'] = dd.get('cut', dd.get('nx', plans.NX) - 1.0)
        dd['site'] = sitemap.SITES[k]
    return dd, ti


def audit_all():
    """全6型×3階の家具を置いてみて、置けなかったものを返す（check.py から使う）。"""
    out = []
    for k in 'ABCDEF':
        for i in range(3):
            dd, ti = sheet_data(k, i)
            cf = []
            draw(dd, ti, conflicts=cf)
            out += ['%s型 %d階 %s' % (k, i + 1, m) for m in cf]
    return out


if __name__ == '__main__':
    bad = []
    for k in 'ABCDEF':
        for i in range(3):
            dd, ti = sheet_data(k, i)
            cf = []
            draw(dd, ti, conflicts=cf).save(os.path.join(OUT, 'ans2%s_%df.svg' % (k, i + 1)))
            bad += ['%s型 %d階 %s' % (k, i + 1, m) for m in cf]
    print('wrote ans2*_?f.svg')
    for m in bad:
        print('NG', m)
    if bad:
        raise SystemExit('家具の置き場所に問題 %d 件' % len(bad))
