# -*- coding: utf-8 -*-
"""部材ずかん ── 伏図の線が「どの木の棒」なのかを立体で見せる図。

伏図は真上から見た図なので、初めて見る人には
「どの線が何なのか」がまったく分からない。
そこで **立体の絵** と **伏図** を左右に並べ、同じ番号をふって
「この棒 ＝ この線」を一対一で結ぶ。

出力：
  figures/buzai_yuka.svg   床のしくみ（床伏図）
  figures/buzai_koya.svg   屋根のしくみ（小屋伏図）
"""
import math
import os
from svgkit import Svg

# ------------------------------------------------------------------ 色
C_DOU = '#c0392b'      # 胴差・軒桁（外周をぐるり）
C_OO = '#1f6fb2'       # 大梁・小屋梁
C_KO = '#2e8b57'       # 床小梁・母屋
C_MUNE = '#7d3c98'     # 棟木
C_HI = '#e67e22'       # 火打梁
C_TARUKI = '#b0651a'   # 垂木
C_TSUKA = '#4a4a4a'    # 柱・小屋束（＝短い柱）
C_TOOSHI = '#b03060'   # 通し柱
C_ITA = '#c8ab72'      # 構造用合板・屋根面

# 立体の見え方。ぴったり45度だと斜めの部材（火打梁）がまっすぐに
# つぶれてしまうので、22度／38度にずらしてある。
A, B = math.radians(22.0), math.radians(38.0)
CA, SA, CB, SB = math.cos(A), math.sin(A), math.cos(B), math.sin(B)
VIEW = {'ox': 0.0, 'oy': 0.0, 'k': 0.15}


def setview(ox, oy, k):
    VIEW['ox'], VIEW['oy'], VIEW['k'] = ox, oy, k


def iso(x, y, z):
    """立体の座標（mm）を、画面の座標に直す。

    x ＝ 東へ（画面では右下へ）、y ＝ 北へ（画面では左下へ）、z ＝ 上。
    つまり建物を「南西の角の上空」から見おろしている。
    """
    k = VIEW['k']
    return (VIEW['ox'] + (x * CA - y * CB) * k,
            VIEW['oy'] + (x * SA + y * SB) * k - z * k)


def mix(col, f):
    """f>0 で白に近づけ（明るく）、f<0 で黒に近づける（暗く）。"""
    r, g, b = (int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16))
    if f >= 0:
        r, g, b = [int(c + (255 - c) * f) for c in (r, g, b)]
    else:
        r, g, b = [int(c * (1 + f)) for c in (r, g, b)]
    return '#%02x%02x%02x' % (r, g, b)


def twidth(t, size):
    """文字の横はばのめやす（全角は1文字ぶん、半角は約0.55文字ぶん）。"""
    w = 0.0
    for ch in t:
        w += 0.56 if ord(ch) < 0x2E80 else 1.0
    return w * size


# ------------------------------------------------------------- 立体の部品
def prism(s, poly, z0, z1, col, lw=0.7, op=None):
    """平面のかたち poly を z0〜z1 まで押し出して、木の棒に見せる。"""
    edge = mix(col, -0.45)
    faces = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        faces.append((a[0] + a[1] + b[0] + b[1], a, b))
    faces.sort(key=lambda e: e[0])          # 遠い面から先に描く
    for _, a, b in faces:
        sh = mix(col, -0.08 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else -0.28)
        s.polygon([iso(a[0], a[1], z1), iso(b[0], b[1], z1),
                   iso(b[0], b[1], z0), iso(a[0], a[1], z0)],
                  fill=sh, stroke=edge, stroke_width=lw, fill_opacity=op)
    s.polygon([iso(p[0], p[1], z1) for p in poly], fill=mix(col, 0.28),
              stroke=edge, stroke_width=lw, fill_opacity=op)


def bar_x(s, x0, x1, y, d, z0, z1, col):
    """東西方向（横）にわたす棒。d は南北の幅。"""
    prism(s, [(x0, y - d / 2.0), (x1, y - d / 2.0),
              (x1, y + d / 2.0), (x0, y + d / 2.0)], z0, z1, col)


def bar_y(s, y0, y1, x, w, z0, z1, col):
    """南北方向（たて）にわたす棒。"""
    prism(s, [(x - w / 2.0, y0), (x + w / 2.0, y0),
              (x + w / 2.0, y1), (x - w / 2.0, y1)], z0, z1, col)


def post(s, x, y, z0, z1, col, a=120.0):
    """柱・小屋束。a は角の1辺。"""
    prism(s, [(x - a / 2.0, y - a / 2.0), (x + a / 2.0, y - a / 2.0),
              (x + a / 2.0, y + a / 2.0), (x - a / 2.0, y + a / 2.0)],
          z0, z1, col)


# ---------------------------------------------------------------- 見出し
def mark(s, wx, wy, wz, n, col, label, dx, dy, anchor='start'):
    """立体の絵の中の1点に、番号の丸と名前をつける。"""
    x, y = iso(wx, wy, wz)
    tx, ty = x + dx, y + dy
    s.line(x, y, tx, ty, stroke=col, stroke_width=1.0, stroke_dasharray='3 2')
    w = twidth(label, 11.5) + 12
    bx = tx + 14 if anchor == 'start' else tx - 14 - w
    s.rect(bx, ty - 10, w, 20, fill='#ffffff', fill_opacity=0.88,
           stroke='none', rx=5)
    s.text(tx + (20 if anchor == 'start' else -20), ty + 4.5, label,
           size=11.5, anchor=anchor, fill=col, weight='700')
    s.circle(tx, ty, 10.5, fill='#fff', stroke=col, stroke_width=2.0)
    s.text(tx, ty + 4.5, str(n), size=12, weight='700', fill=col)


def pmark(s, x, y, n, col, r=10.5):
    """伏図のほうにつける番号の丸。"""
    s.circle(x, y, r + 2.5, fill='#fff', fill_opacity=0.9, stroke='none')
    s.circle(x, y, r, fill='#fff', stroke=col, stroke_width=2.0)
    s.text(x, y + 4.5, str(n), size=12, weight='700', fill=col)


def panel(s, x, y, w, h, title, sub=''):
    s.rect(x, y, w, h, fill='#fcfcfb', stroke='#e0ded8', stroke_width=1.0,
           rx=10)
    s.text(x + 16, y + 26, title, size=15, anchor='start', weight='700')
    if sub:
        s.text(x + 16, y + 46, sub, size=11.5, anchor='start', fill='#777')


def compass_iso(s, x, y):
    """立体のほうの方位。北は左下、東は右下へ向かう。"""
    s.text(x, y - 16, '立体を見ている向き', size=10, anchor='start',
           fill='#999')
    for dx, dy, nm in ((-CB * 34, SB * 34, '北'), (CA * 34, SA * 34, '東')):
        s.line(x, y, x + dx, y + dy, stroke='#999', stroke_width=1.2)
        s.polygon([(x + dx, y + dy), (x + dx * 0.82 - dy * 0.12,
                                      y + dy * 0.82 + dx * 0.12),
                   (x + dx * 0.82 + dy * 0.12,
                    y + dy * 0.82 - dx * 0.12)], fill='#999')
        s.text(x + dx * 1.32, y + dy * 1.32 + 4, nm, size=11, fill='#777',
               weight='700')


def compass_plan(s, x, y):
    """伏図のほうの方位。伏図はいつも北が上。"""
    s.line(x, y + 26, x, y - 20, stroke='#999', stroke_width=1.2)
    s.polygon([(x, y - 26), (x - 5, y - 14), (x + 5, y - 14)], fill='#999')
    s.text(x, y - 32, '北', size=11, fill='#777', weight='700')


# ============================================================ 床のしくみ
def yuka():
    """床伏図。建物の南西のすみ 2マス×2マス（1,820×1,820）を取り出す。"""
    W, H = 1240, 760
    s = Svg(W, H)
    s.text(W / 2.0, 40, '部材ずかん ①　床のしくみ（床伏図）', size=22,
           weight='700')
    s.text(W / 2.0, 66,
           '建物の南西のすみ 2マス×2マス（1,820×1,820mm）だけを取り出した。'
           '左の棒 ＝ 右の線。番号が同じものが同じ部材。',
           size=12.5, fill='#666')

    panel(s, 20, 86, 640, 600, 'よこななめから見ると（本当の姿）',
          '床の板をはがして、骨だけにした状態')
    panel(s, 676, 86, 544, 600, '真上から見ると（＝床伏図）',
          '棒を上から押しつぶすと、ぜんぶ「線」になる')

    # ---------------- 立体
    setview(307, 316, 0.180)
    Z = 700.0                       # 梁の上ば（ここに床板がのる）
    G = 910.0
    ZB = 200.0                      # 柱はここで切って見せる

    # 遠いほう（南西のすみ）から順に描く
    post(s, 2 * G, 0, ZB, Z - 300, C_TSUKA)              # 管柱（下）
    post(s, 0, 2 * G, ZB, Z - 300, C_TSUKA)
    bar_x(s, -60, 2 * G, 0, 120, Z - 300, Z, C_DOU)      # 胴差（東西・南面）
    bar_y(s, -60, 2 * G, 0, 120, Z - 300, Z, C_DOU)      # 胴差（南北・西面）
    # 火打梁 90×90（すみの斜め材。上ばは梁とそろえる）
    prism(s, [(G - 45, 60), (G + 45, 60), (60, G + 45), (60, G - 45)],
          Z - 90, Z, C_HI)
    bar_x(s, 60, 2 * G - 60, G, 120, Z - 180, Z, C_KO)   # 床小梁 @910
    bar_y(s, 60, 2 * G, 2 * G, 120, Z - 300, Z, C_OO)    # 大梁（南北）
    bar_x(s, 60, 2 * G - 60, 2 * G, 120, Z - 240, Z, C_OO)   # 大梁（東西）
    post(s, 2 * G, 2 * G, ZB, Z - 300, C_TSUKA)
    # 上の階の管柱（胴差の上でいったん切れて、また立つ）
    for gx, gy in ((2 * G, 0), (0, 2 * G), (2 * G, 2 * G)):
        post(s, gx, gy, Z, 980, C_TSUKA)
    # 構造用合板（手前の1マスだけ張ってみせる）
    prism(s, [(G, G), (2 * G, G), (2 * G, 2 * G), (G, 2 * G)], Z, Z + 24,
          C_ITA)
    # 通し柱は最後に。梁の高さを通りぬけて1本で立っているのが見える
    post(s, 0, 0, ZB, 980, C_TOOSHI)

    mark(s, 0, 0, 900, 1, C_TOOSHI, '通し柱 120×120', -52, 12, 'end')
    mark(s, 2 * G, 0, 940, 2, C_TSUKA, '管柱 120×120', -34, -34, 'end')
    mark(s, G, 0, Z, 3, C_DOU, '胴差 120×300', 34, -40)
    mark(s, 2 * G, G, Z, 4, C_OO, '大梁 120×300', 56, -34)
    mark(s, 1.4 * G, G, Z, 5, C_KO, '床小梁 120×180', 40, 44)
    mark(s, G * 0.5, G * 0.5, Z, 6, C_HI, '火打梁 90×90', -40, -18, 'end')
    mark(s, 1.5 * G, 1.5 * G, Z + 24, 7, '#8a7027', '構造用合板 t=24',
         14, 62)
    compass_iso(s, 92, 588)

    s.text(40, 664,
           '★ 梁の「上ば」はぜんぶ同じ高さ。'
           'だから合板をペタッと直接張れる（根太レス＝剛床）。',
           size=11.5, anchor='start', fill='#555')

    # ---------------- 伏図（北が上）
    px0, py0, g = 800.0, 210.0, 150.0

    def PX(gx):
        return px0 + gx * g

    def PY(gy):
        return py0 + (2 - gy) * g

    for i in range(3):
        s.line(PX(0), PY(i), PX(2), PY(i), stroke='#eee', stroke_width=0.8)
        s.line(PX(i), PY(0), PX(i), PY(2), stroke='#eee', stroke_width=0.8)
    s.line(PX(0), PY(0), PX(2), PY(0), stroke=C_DOU, stroke_width=6.0)
    s.line(PX(0), PY(0), PX(0), PY(2), stroke=C_DOU, stroke_width=6.0)
    s.line(PX(2), PY(0), PX(2), PY(2), stroke=C_OO, stroke_width=5.2)
    s.line(PX(0), PY(2), PX(2), PY(2), stroke=C_OO, stroke_width=4.4)
    s.line(PX(0), PY(1), PX(2), PY(1), stroke=C_KO, stroke_width=2.4)
    s.line(PX(1), PY(0), PX(0), PY(1), stroke=C_HI, stroke_width=2.8)
    for gx, gy in ((2, 0), (0, 2), (2, 2)):
        s.rect(PX(gx) - 5, PY(gy) - 5, 10, 10, fill='#111')
    s.circle(PX(0), PY(0), 9.5, fill='#fff', stroke=C_TOOSHI,
             stroke_width=2.6)
    s.circle(PX(0), PY(0), 4.5, fill=C_TOOSHI)

    pmark(s, PX(0) - 28, PY(0) + 28, 1, C_TOOSHI)
    pmark(s, PX(2) + 28, PY(0) + 28, 2, C_TSUKA)
    pmark(s, PX(1.45), PY(0) + 24, 3, C_DOU)
    pmark(s, PX(2) + 28, PY(1), 4, C_OO)
    pmark(s, PX(1.5), PY(1) - 22, 5, C_KO)
    pmark(s, PX(0.44), PY(0.44), 6, C_HI)
    s.text(PX(1.5), PY(1.5), '合板は伏図には', size=10.5, fill='#a08a4a')
    s.text(PX(1.5), PY(1.5) + 15, '描かない（⑦）', size=10.5, fill='#a08a4a')
    s.dim_h(PX(0), PX(1), PY(2) - 20, '910')
    s.dim_h(PX(1), PX(2), PY(2) - 20, '910')
    compass_plan(s, PX(2) + 60, PY(2) + 6)

    for i, row in enumerate((
            '★ ③④⑤ はどれも「梁」。せい（たての寸法）の順は',
            '　　胴差300 ＞ 大梁300・240 ＞ 床小梁180。線の太さもこの順に。',
            '★ 柱は伏図では「点」になる。上から見た柱は、ただの四角だから。',
            '　　■＝管柱、◎＝通し柱。')):
        s.text(694, 616 + i * 20, row, size=11.5, anchor='start',
               fill='#555')

    s.text(W / 2.0, H - 22,
           '床伏図に出てくるのは 6 種類だけ：'
           '柱・胴差・大梁・床小梁・火打梁（＋合板は文字で注記）',
           size=13, weight='700', fill='#333')
    return s


# ============================================================ 屋根のしくみ
def koya():
    """小屋伏図。西のはし（軒）から棟をこえた所までを取り出す。"""
    W, H = 1240, 780
    s = Svg(W, H)
    s.text(W / 2.0, 40, '部材ずかん ②　屋根のしくみ（小屋伏図）', size=22,
           weight='700')
    s.text(W / 2.0, 66,
           '西のはし（軒）から、まん中の棟をこえた所までを取り出した。'
           '屋根は棟から東西の2方向へ、テントのように流れ落ちる。',
           size=12.5, fill='#666')

    panel(s, 20, 86, 700, 620, 'よこななめから見ると（本当の姿）',
          '屋根の板をはずして、骨だけにした状態')
    panel(s, 736, 86, 484, 620, '真上から見ると（＝小屋伏図）',
          'ななめの棒も、上から見ればまっすぐな線になる')

    setview(268, 214, 0.108)
    G = 910.0
    DY = 2 * G                     # 南北の奥ゆき（小屋梁2本ぶん）
    XR = 3640.0                    # 棟の位置（西のはしから4マス）
    XE = 4550.0                    # 図に描くいちばん東
    NOKI = 600.0                   # 軒の出

    def roof(x):
        """軒桁の上ばから測った、屋根の面の高さ。4寸勾配。"""
        return 0.4 * (XR - abs(x - XR))

    # --- 軒桁・妻梁・小屋梁（下の段） ---------------------------------
    for gx in (0.0, 1820.0, XE):                     # A・B・C通りの桁
        bar_y(s, -60, DY + 60, gx, 120, -240, 0, C_DOU)
    for gy in (0.0, DY):                             # 小屋梁（東西・@1,820）
        for a, b in ((0.0, 1820.0), (1820.0, XE)):
            bar_x(s, a + 60, b - 60, gy, 120, -240, 0, C_OO)
    # 火打梁（すみの斜め材）
    prism(s, [(G - 45, 60), (G + 45, 60), (60, G + 45), (60, G - 45)],
          -90, 0, C_HI)

    # --- 小屋束＋母屋＋棟木（遠いものから） ----------------------------
    for gx in (910.0, 1820.0, 2730.0, XR, 4550.0):
        h = roof(gx)
        col = C_MUNE if gx == XR else C_KO
        a = 120.0 if gx == XR else 90.0
        for gy in (0.0, DY):
            post(s, gx, gy, 0, h - a, C_TSUKA, a=90.0)   # 小屋束
        bar_y(s, -170, DY + 170, gx, a, h - a, h, col)   # 母屋／棟木

    # --- 屋根の面（うすい色。テントの形が一目で分かるように） ----------
    for x0, x1 in ((-NOKI, XR), (XR, XE + 300)):
        s.polygon([iso(x0, -170, roof(x0) + 50), iso(x1, -170,
                                                     roof(x1) + 50),
                   iso(x1, DY + 170, roof(x1) + 50),
                   iso(x0, DY + 170, roof(x0) + 50)],
                  fill=C_ITA, fill_opacity=0.22, stroke='#a08a4a',
                  stroke_width=1.0, stroke_dasharray='6 4')
    # --- 垂木（棟から軒へ。屋根の面にのる） ----------------------------
    for gy in (120.0, 910.0, 1700.0):
        s.poly([iso(-NOKI, gy, roof(-NOKI) + 50), iso(XR, gy, roof(XR) + 50),
                iso(XE + 300, gy, roof(XE + 300) + 50)],
               stroke=C_TARUKI, stroke_width=3.2, stroke_linecap='round',
               stroke_linejoin='round')

    mark(s, 0, G, -120, 1, C_DOU, '軒桁 120×240', 34, 46)
    mark(s, 3100, DY, -120, 2, C_OO, '小屋梁 120×240', 28, 42)
    mark(s, 1820, 0, roof(1820) * 0.45, 3, C_TSUKA, '小屋束 90×90',
         30, -16)
    mark(s, 2730, DY, roof(2730), 4, C_KO, '母屋 90×90', -34, 40, 'end')
    mark(s, XR, 0, roof(XR), 5, C_MUNE, '棟木 120×120', 8, -46)
    mark(s, 1500, 120, roof(1500) + 50, 6, C_TARUKI, '垂木 45×105',
         -22, -44, 'end')
    mark(s, G * 0.5, G * 0.5, 0, 7, C_HI, '火打梁 90×90', -34, 30, 'end')
    compass_iso(s, 96, 610)

    s.text(40, 668,
           '★ 高さのしくみ：軒桁の上ばから、棟まで 3,640 × 0.4 ＝ '
           '1,456mm 上がる（4寸勾配）。母屋はその坂の上に等間かくで並ぶ。',
           size=11.5, anchor='start', fill='#555')
    s.text(40, 690,
           '★ 小屋束は「屋根の坂」を作るための背くらべ。棟に近いほど長い。'
           '棟木の下の束だけ「棟束」と呼ぶ。',
           size=11.5, anchor='start', fill='#555')

    # ---------------- 小屋伏図（北が上） -----------------------------
    px0, py0, g = 806.0, 168.0, 45.0
    NX, NY = 8, 10

    def PX(gx):
        return px0 + gx * g

    def PY(gy):
        return py0 + (NY - gy) * g

    for i in range(NX + 1):
        s.line(PX(i), PY(0), PX(i), PY(NY), stroke='#f0f0f0',
               stroke_width=0.7)
    for j in range(NY + 1):
        s.line(PX(0), PY(j), PX(NX), PY(j), stroke='#f0f0f0',
               stroke_width=0.7)
    for gx in (0, 2, 5, 8):                       # 軒桁（南北）
        s.line(PX(gx), PY(0), PX(gx), PY(NY), stroke=C_DOU, stroke_width=4.6)
    for gy in (0, NY):                            # 妻梁（東西）
        s.line(PX(0), PY(gy), PX(NX), PY(gy), stroke=C_DOU, stroke_width=4.6)
    for gy in range(2, NY, 2):                    # 小屋梁
        s.line(PX(0), PY(gy), PX(NX), PY(gy), stroke=C_OO, stroke_width=3.6)
    for gx in (1, 2, 3, 5, 6, 7):                 # 母屋
        s.line(PX(gx), PY(-0.5), PX(gx), PY(NY + 0.5), stroke=C_KO,
               stroke_width=2.0)
    s.line(PX(4), PY(-0.5), PX(4), PY(NY + 0.5), stroke=C_MUNE,
           stroke_width=4.0)
    for gx, gy, dx, dy in ((0, 0, 1, 1), (8, 0, -1, 1), (0, 10, 1, -1),
                           (8, 10, -1, -1)):      # 火打梁
        s.line(PX(gx + dx), PY(gy), PX(gx), PY(gy + dy), stroke=C_HI,
               stroke_width=2.4)
    for gx in range(1, 8):                        # 小屋束
        for gy in range(2, NY, 2):
            s.circle(PX(gx), PY(gy), 4.0, fill='#fff', stroke=C_TSUKA,
                     stroke_width=1.6)
    # 立体で見せている範囲
    s.rect(PX(0) - 9, PY(4) - 9, PX(5) - PX(0) + 18, PY(2) - PY(4) + 18,
           fill='none', stroke='#999', stroke_width=1.4,
           stroke_dasharray='6 4')
    s.text(PX(2.5), PY(4) - 16, '← 左の立体はこの範囲', size=10.5,
           fill='#888')

    pmark(s, PX(0) - 24, PY(7), 1, C_DOU, r=9.5)
    pmark(s, PX(6.5), PY(8) + 16, 2, C_OO, r=9.5)
    pmark(s, PX(3), PY(6), 3, C_TSUKA, r=9.5)
    pmark(s, PX(6), PY(5) + 16, 4, C_KO, r=9.5)
    pmark(s, PX(4), PY(1) - 18, 5, C_MUNE, r=9.5)
    pmark(s, PX(0.5), PY(9.5), 7, C_HI, r=9.5)
    s.rect(PX(5.6), PY(2.4) - 13, 116, 32, fill='#fff', fill_opacity=0.92,
           stroke='none', rx=4)
    s.text(PX(5.7), PY(2.4), '⑥ 垂木は', size=10.5, anchor='start',
           fill=C_TARUKI, weight='700')
    s.text(PX(5.7), PY(2.4) + 14, '描かない（文字だけ）', size=10.5,
           anchor='start', fill=C_TARUKI)
    compass_plan(s, PX(8) + 44, PY(10) + 24)

    s.text(752, 668,
           '★ たての線（母屋・棟木）と、よこの線（小屋梁）が'
           'ごばんの目に組み合わさっている。',
           size=11.5, anchor='start', fill='#555')
    s.text(752, 690,
           '★ 交点の小さい○が小屋束。母屋と小屋梁が交わる所すべてに立つ。',
           size=11.5, anchor='start', fill='#555')

    s.text(W / 2.0, H - 22,
           '小屋伏図に出てくるのは 6 種類だけ：'
           '軒桁（妻梁）・小屋梁・小屋束・母屋・棟木・火打梁'
           '（＋垂木は文字で注記）',
           size=13, weight='700', fill='#333')
    return s




# ======================================================== 家1けんまるごと
# 型の通り芯（framing.py と同じ）
XL = (0, 2, 5, 8)          # A・B・C・D通り
YL = (0, 2, 6, 10)         # 1・2・3・4通り
TOOSHI4 = ((0, 0), (8, 0), (0, 10), (8, 10))
KUDA12 = ((2, 0), (5, 0), (0, 2), (8, 2), (0, 6), (8, 6),
          (2, 10), (5, 10), (2, 2), (5, 2), (2, 6), (5, 6))
HIUCHI8 = ((0, 0, 1, 1), (8, 0, -1, 1), (0, 10, 1, -1), (8, 10, -1, -1),
           (2, 2, 1, 1), (5, 2, -1, 1), (2, 6, 1, -1), (5, 6, -1, -1))
C_DODAI = '#8a6d3b'
C_KISO = '#9aa0a6'
G = 910.0
BW, BD = 8 * G, 10 * G     # 7,280 × 9,100


def _hiuchi_layer(s, z0, z1):
    for gx, gy, dx, dy in HIUCHI8:
        ax, ay = (gx + dx) * G, gy * G
        bx, by = gx * G, (gy + dy) * G
        nx, ny = (by - ay), -(bx - ax)
        ln = (nx * nx + ny * ny) ** 0.5
        nx, ny = nx / ln * 45.0, ny / ln * 45.0
        prism(s, [(ax + nx, ay + ny), (bx + nx, by + ny),
                  (bx - nx, by - ny), (ax - nx, ay - ny)], z0, z1, C_HI)


def _posts_under(s, tall=1300.0, top=-300.0):
    """その階の床を下からささえている柱。短く切って見せる。"""
    for gx, gy in KUDA12:
        post(s, gx * G, gy * G, top - tall, top, C_TSUKA)
    for gx, gy in TOOSHI4:
        post(s, gx * G, gy * G, top - tall, top, C_TOOSHI)


def _floor_layer(s, posts=True):
    """2階・3階の床の骨組み（＝床伏図）を1枚ぶん描く。"""
    if posts:
        _posts_under(s)
    _hiuchi_layer(s, -90, 0)
    for gy in (1, 3, 4, 5, 7, 8, 9):                     # 床小梁 @910
        bar_x(s, 0, BW, gy * G, 120, -180, 0, C_KO)
    for gy in (2, 6):                                    # 大梁（東西）
        bar_x(s, 0, BW, gy * G, 120, -240, 0, C_OO)
    for gx in (2, 5):                                    # 大梁（南北）
        bar_y(s, 0, BD, gx * G, 120, -300, 0, C_OO)
    for gy in (0, 10):                                   # 胴差（外周）
        bar_x(s, -60, BW + 60, gy * G, 120, -300, 0, C_DOU)
    for gx in (0, 8):
        bar_y(s, -60, BD + 60, gx * G, 120, -300, 0, C_DOU)
    for gx, gy in TOOSHI4:
        s.circle(iso(gx * G, gy * G, 0)[0], iso(gx * G, gy * G, 0)[1], 5.5,
                 fill='none', stroke=C_TOOSHI, stroke_width=1.8)


def _dodai_layer(s):
    """1階の床（土台と基礎）。"""
    for gy in YL:
        bar_x(s, -60, BW + 60, gy * G, 120, -420, -120, C_KISO)
    for gx in XL:
        bar_y(s, -60, BD + 60, gx * G, 120, -420, -120, C_KISO)
    for gy in YL:
        bar_x(s, -60, BW + 60, gy * G, 120, -120, 0, C_DODAI)
    for gx in XL:
        bar_y(s, -60, BD + 60, gx * G, 120, -120, 0, C_DODAI)


def _koya_layer(s):
    """屋根の骨組み（＝小屋伏図）＋屋根の面。"""
    def rf(x):
        return 0.4 * (3640.0 - abs(x - 3640.0))

    _posts_under(s)
    _hiuchi_layer(s, -90, 0)
    for gy in (2, 4, 6, 8):                              # 小屋梁 @1,820
        bar_x(s, 0, BW, gy * G, 120, -240, 0, C_OO)
    for gy in (0, 10):                                   # 妻梁
        bar_x(s, -60, BW + 60, gy * G, 120, -240, 0, C_DOU)
    for gx in XL:                                        # 軒桁
        bar_y(s, -60, BD + 60, gx * G, 120, -240, 0, C_DOU)
    for gx in (1, 2, 3, 4, 5, 6, 7):                     # 小屋束
        for gy in (2, 4, 6, 8):
            post(s, gx * G, gy * G, 0, rf(gx * G) - 90, C_TSUKA, a=90.0)
    for gx in (1, 2, 3, 5, 6, 7):                        # 母屋 @910
        h = rf(gx * G)
        bar_y(s, -455, BD + 455, gx * G, 90, h - 90, h, C_KO)
    bar_y(s, -455, BD + 455, 3640, 120, rf(3640) - 120, rf(3640), C_MUNE)
    for x0, x1 in ((-600, 3640), (3640, 7880)):          # 屋根の面
        s.polygon([iso(x0, -455, rf(x0) + 60), iso(x1, -455, rf(x1) + 60),
                   iso(x1, BD + 455, rf(x1) + 60),
                   iso(x0, BD + 455, rf(x0) + 60)],
                  fill=C_ITA, fill_opacity=0.20, stroke='#a08a4a',
                  stroke_width=1.0, stroke_dasharray='6 4')


def _layer_label(s, x, y, no, title, height, rows, draw=None):
    s.circle(x + 13, y + 13, 13, fill='#fff', stroke='#bbb',
             stroke_width=1.6)
    s.text(x + 13, y + 18, str(no), size=13.5, weight='700', fill='#666')
    s.text(x + 36, y + 19, title, size=17, anchor='start', weight='700')
    s.text(x + 36, y + 40, height, size=12.5, anchor='start', fill='#888')
    yy = y + 62
    if draw:
        col = '#1e7e34' if draw[0] == '★' else '#999'
        bg = '#eef7ef' if draw[0] == '★' else '#f2f2f0'
        w = twidth(draw, 12.5) + 30
        s.rect(x + 36, yy - 15, w, 23, fill=bg, stroke=col,
               stroke_width=1.0, rx=6)
        s.text(x + 46, yy + 1, draw, size=12.5, anchor='start', fill=col,
               weight='700')
        yy += 32
    for r in rows:
        s.text(x + 36, yy, r, size=12.5, anchor='start', fill='#555')
        yy += 19


def zentai():
    """家1けんぶんの骨組みを、4つの層にばらして積みなおした図。"""
    W, H = 1240, 1720
    s = Svg(W, H)
    s.text(W / 2.0, 42, '部材ずかん ⓪　家1けんまるごとの骨組み', size=23,
           weight='700')
    s.text(W / 2.0, 70,
           '同じ骨組みが4段つみ重なっているだけ。'
           'ばらして横から見ると、答案で描く2枚がどこなのかが分かる。',
           size=12.5, fill='#666')

    K, OX = 0.032, 330.0
    LY = {'koya': 230.0, 'f3': 570.0, 'f2': 910.0, 'do': 1250.0}

    # 通し柱＝ぜんぶの層をたてにつらぬく1本
    for gx, gy in TOOSHI4:
        setview(OX, 0.0, K)
        x, dy = iso(gx * G, gy * G, 0)
        s.line(x, LY['koya'] + dy - 60, x, LY['do'] + dy + 20,
               stroke=C_TOOSHI, stroke_width=1.0, stroke_dasharray='5 4')

    for key, fn in (('do', _dodai_layer), ('f2', _floor_layer),
                    ('f3', _floor_layer), ('koya', _koya_layer)):
        setview(OX, LY[key], K)
        fn(s)

    LX = 600.0
    _layer_label(s, LX, LY['koya'] - 34, 4, '小屋組（屋根の骨）',
                 '軒 GL+9,350　／　棟 GL+10,806',
                 ['軒桁・妻梁／小屋梁／小屋束／母屋／棟木／火打梁',
                  '棟から東西の2方向へ、4寸勾配で流れ落ちる'],
                 draw='★ 答案で描く ── ⑷ 小屋伏図')
    _layer_label(s, LX, LY['f3'] - 34, 3, '3階の床',
                 '3FL ＝ GL+6,550',
                 ['胴差／大梁／床小梁／火打梁／柱',
                  'この床を下からささえているのが「2階の柱」'],
                 draw='★ 答案で描く ── ⑷ 3階床伏図')
    _layer_label(s, LX, LY['f2'] - 34, 2, '2階の床',
                 '2FL ＝ GL+3,650',
                 ['骨組みは3階の床と まったく同じ',
                  'だから覚えるのは1つでいい'],
                 draw='描かない（要求図書は3階床伏図のみ）')
    _layer_label(s, LX, LY['do'] - 34, 1, '1階の床（土台・基礎）',
                 '1FL ＝ GL+550',
                 ['べた基礎の立上りの上に、土台120×120をぐるり',
                  'アンカーボルト M12 ＠2,730以下で緊結'],
                 draw='描かない（1階平面図兼配置図で表す）')

    # 「①で拡大したのはここ」
    setview(OX, LY['f3'], K)
    s.polygon([iso(0, 0, 40), iso(2 * G, 0, 40), iso(2 * G, 2 * G, 40),
               iso(0, 2 * G, 40)], fill='#ffe9a8', fill_opacity=0.55,
              stroke='#c8912a', stroke_width=1.6)
    ax, ay = iso(G, G, 40)
    s.line(ax, ay, ax - 130, ay + 34, stroke='#c8912a', stroke_width=1.2,
           stroke_dasharray='3 2')
    s.text(ax - 136, ay + 38, '図① で拡大したのは、ここ', size=11.5,
           anchor='end', fill='#a8761c', weight='700')

    # 全体の寸法（土台の層に）
    setview(OX, LY['do'], K)
    p0, p1 = iso(0, BD, 0), iso(BW, BD, 0)
    s.text((p0[0] + p1[0]) / 2.0, p1[1] + 42,
           '東西 7,280（8マス）　×　南北 9,100（10マス）', size=12,
           fill='#777')

    setview(OX, LY['koya'], K)
    s.text(iso(-1500, 0, 900)[0], iso(-1500, 0, 900)[1],
           '通し柱＝四すみ4本。', size=11.5, anchor='end', fill=C_TOOSHI,
           weight='700')
    s.text(iso(-1500, 0, 900)[0], iso(-1500, 0, 900)[1] + 17,
           '点線のように、1階から', size=11.5, anchor='end', fill=C_TOOSHI)
    s.text(iso(-1500, 0, 900)[0], iso(-1500, 0, 900)[1] + 34,
           '3階まで1本で通る', size=11.5, anchor='end', fill=C_TOOSHI)

    s.rect(60, H - 110, W - 120, 60, fill='#f1f8f2', stroke='#b9d8bd',
           stroke_width=1.0, rx=8)
    s.text(W / 2.0, H - 84,
           '★ おぼえることは2つだけ。「床の骨組み」と「屋根の骨組み」。',
           size=14, weight='700', fill='#1e7e34')
    s.text(W / 2.0, H - 62,
           '2階の床と3階の床は同じもの。1階の床は土台。'
           'つまり4段あっても、形は2種類しかない。',
           size=12.5, fill='#3d6b46')
    return s


# ================================================== 柱の切れ方・名前の変わり方
def hashira():
    """たて割りにして、通し柱と管柱のちがいをはっきり見せる図。

    たてに立つ部材と、よこにぐるり1周する部材の両方を、
    同じ高さのものさしの上にならべてある。
    """
    W, H = 1240, 880
    s = Svg(W, H)
    s.text(W / 2.0, 40, '部材ずかん ③　柱の切れ方と、部材の名前の変わり方',
           size=22, weight='700')
    s.text(W / 2.0, 66,
           '建物をたてにスパッと切ったところ。'
           '左右の図は同じ高さのものさしの上にのっている。',
           size=12.5, fill='#666')

    K, GL = 0.050, 740.0

    def Y(z):
        return GL - z * K

    # 型の高さ（mm）。1FL=550＝基礎371＋パッキン20＋土台120＋合板24＋仕上15
    DODAI = (391.0, 511.0)          # 土台 120
    DOU2 = (3311.0, 3611.0)         # 2階と3階のさかい目の胴差 300
    DOU3 = (6211.0, 6511.0)         # 3階の床の胴差 300
    NOKI = (9110.0, 9350.0)         # 軒桁 240

    panel(s, 20, 86, 680, 684, 'たてに立つもの',
          '通し柱と管柱のちがいは「切れているか、いないか」だけ')
    panel(s, 716, 86, 504, 684, 'よこにぐるり1周するもの',
          'ちがうのは高さだけ ── だから名前が変わる')

    # ---------------- 高さのものさし（左はし）
    for z, lab in ((0.0, 'GL'), (550.0, '1FL  GL+550'),
                   (3650.0, '2FL  GL+3,650'), (6550.0, '3FL  GL+6,550'),
                   (9350.0, '軒高  GL+9,350')):
        s.line(96, Y(z), 676, Y(z), stroke='#e2ded6', stroke_width=0.8,
               stroke_dasharray='4 4')
        s.text(92, Y(z) + 4, lab, size=10.5, anchor='end', fill='#999')
    s.line(96, Y(0), 96, Y(9350), stroke='#ddd', stroke_width=1.0)
    s.rect(96, Y(0), 580, 22, fill='#efece6', stroke='none')      # 地面
    for x in range(100, 676, 16):
        s.line(x, Y(0) + 22, x + 8, Y(0) + 8, stroke='#cfc9bd',
               stroke_width=1.0)

    # ---------------- 通し柱（左）と管柱（右）
    CW = 44.0

    def yoko(cx, z0, z1, col, through):
        """胴差など、よこにわたす部材。through=Trueなら柱を切って通る。"""
        if through:
            s.rect(cx - 105, Y(z1), 210, Y(z0) - Y(z1), fill=mix(col, 0.20),
                   stroke=mix(col, -0.35), stroke_width=1.2, rx=2)
        else:
            for sgn in (-1, 1):
                x0 = cx + sgn * CW / 2.0
                s.rect(min(x0, x0 + sgn * 80), Y(z1), 80, Y(z0) - Y(z1),
                       fill=mix(col, 0.20), stroke=mix(col, -0.35),
                       stroke_width=1.2)

    def tate(cx, z0, z1, col, tone):
        s.rect(cx - CW / 2.0, Y(z1), CW, Y(z0) - Y(z1), fill=mix(col, tone),
               stroke=mix(col, -0.4), stroke_width=1.4, rx=2)

    # 通し柱：よこ材を先に描き、そのうえに柱を1本かぶせる＝切れていない
    CX1 = 210.0
    yoko(CX1, DODAI[0], DODAI[1], C_DODAI, False)
    for z0, z1 in (DOU2, DOU3, NOKI):
        yoko(CX1, z0, z1, C_DOU, False)
    tate(CX1, DODAI[1], 9350.0, C_TOOSHI, 0.30)
    s.text(CX1, Y(4800), '1', size=34, weight='800', fill='#fff')
    s.text(CX1, Y(4400), '本', size=17, weight='700', fill='#fff')

    # 管柱：柱を先に3本ぶん描き、そのうえによこ材をかぶせる＝切れている
    CX2 = 450.0
    for i, (z0, z1) in enumerate(((DODAI[1], DOU2[0]), (DOU2[1], DOU3[0]),
                                  (DOU3[1], NOKI[0]))):
        tate(CX2, z0, z1, C_TSUKA, 0.62 if i % 2 else 0.50)
        s.text(CX2, (Y(z0) + Y(z1)) / 2.0 + 6, '%d階' % (i + 1), size=15,
               weight='700', fill='#fff')
    yoko(CX2, DODAI[0], DODAI[1], C_DODAI, True)
    for z0, z1 in (DOU2, DOU3, NOKI):
        yoko(CX2, z0, z1, C_DOU, True)
    # 切れ目を赤い太線で強調する（胴差のふちに重ならない長さで）
    for z0, z1 in ((DODAI[1], DOU2[0]), (DOU2[1], DOU3[0]),
                   (DOU3[1], NOKI[0])):
        for z in (z0, z1):
            s.line(CX2 - CW / 2.0 - 13, Y(z), CX2 + CW / 2.0 + 13, Y(z),
                   stroke='#c0392b', stroke_width=3.0)
    # 通し柱のほうは、つぎ目がないことを1本の矢印で見せる
    s.line(CX1 - 62, Y(DODAI[1]), CX1 - 62, Y(9350), stroke=C_TOOSHI,
           stroke_width=1.4)
    for z, d in ((DODAI[1], 1), (9350.0, -1)):
        s.polygon([(CX1 - 62, Y(z)), (CX1 - 67, Y(z) - d * 11),
                   (CX1 - 57, Y(z) - d * 11)], fill=C_TOOSHI)
    s.text(CX1 - 70, Y(5600), 'つぎ目なし', size=11, anchor='end',
           fill=C_TOOSHI, weight='700')
    s.text(CX2 + 114, Y(DOU3[1]) - 6, 'ここで切れて', size=11,
           anchor='start', fill='#c0392b', weight='700')
    s.text(CX2 + 114, Y(DOU3[1]) + 9, '上にまた立つ', size=11,
           anchor='start', fill='#c0392b', weight='700')

    s.text(CX1, 160, '通し柱', size=19, weight='700', fill=C_TOOSHI)
    s.text(CX1, 183, '土台から軒桁まで 1本の木', size=12, fill='#666')
    s.text(CX1, 201, '四すみ 4本だけ', size=12, fill='#666')
    s.text(CX2, 160, '管柱', size=19, weight='700', fill=C_TSUKA)
    s.text(CX2, 183, '階ごとに 3本に切れている', size=12, fill='#666')
    s.text(CX2, 201, '四すみ以外ぜんぶ（型では12本）', size=12, fill='#666')

    s.text(30, 796,
           '★ 太さはどちらも同じ120×120。ちがうのは「1本か、3本か」だけ。',
           size=12, anchor='start', fill='#555')
    s.text(30, 816,
           '★ 通し柱は、つぎ目がないぶん強い。'
           'だからいちばん力のかかる四すみに置く。',
           size=12, anchor='start', fill='#555')
    s.text(30, 836,
           '★ 平面図では、通し柱の■を○で囲む。これが書きわすれ第1位。',
           size=12, anchor='start', fill='#555')

    # ---------------- 右：ぐるり1周する部材
    BX0, BX1 = 790.0, 940.0
    s.rect(BX0, Y(9350), BX1 - BX0, Y(0) - Y(9350), fill='#faf8f4',
           stroke='#d8d2c6', stroke_width=1.2)
    s.polygon([(BX0 - 26, Y(9350)), ((BX0 + BX1) / 2.0, Y(10806)),
               (BX1 + 26, Y(9350))], fill='#f3efe7', stroke='#d8d2c6',
              stroke_width=1.2)
    s.rect(BX0, Y(0), BX1 - BX0, 22, fill='#efece6', stroke='none')
    for z, lab in ((2100.0, '1階'), (5100.0, '2階'), (7900.0, '3階')):
        s.text((BX0 + BX1) / 2.0, Y(z), lab, size=14, fill='#b8b2a6',
               weight='700')

    def yobi(z0, z1, col, name, size_txt, note):
        s.rect(BX0 - 14, Y(z1), BX1 - BX0 + 28, Y(z0) - Y(z1),
               fill=mix(col, 0.18), stroke=mix(col, -0.35), stroke_width=1.4)
        my = (Y(z0) + Y(z1)) / 2.0
        s.line(BX1 + 20, my, BX1 + 50, my, stroke=col, stroke_width=1.2)
        s.text(BX1 + 58, my - 3, name, size=15, anchor='start', fill=col,
               weight='700')
        s.text(BX1 + 58 + twidth(name, 15) + 10, my - 3, size_txt, size=12,
               anchor='start', fill='#888')
        s.text(BX1 + 58, my + 15, note, size=11.5, anchor='start',
               fill='#666')

    yobi(NOKI[0], NOKI[1], C_DOU, '軒桁', '120×240',
         '壁のてっぺん。屋根を受ける')
    yobi(DOU3[0], DOU3[1], C_DOU, '胴差', '120×300', '2階と3階のさかい目')
    yobi(DOU2[0], DOU2[1], C_DOU, '胴差', '120×300', '1階と2階のさかい目')
    yobi(DODAI[0], DODAI[1], C_DODAI, '土台', '120×120',
         '基礎の上。いちばん下')
    s.rect(BX0 - 24, Y(391), BX1 - BX0 + 48, Y(-300) - Y(391),
           fill='#e8e6e2', stroke='#b9b4ab', stroke_width=1.2)
    s.text((BX0 + BX1) / 2.0, Y(0) + 16, 'べた基礎', size=11.5, fill='#7a746a')

    s.text(726, 796,
           '★ ぜんぶ外周をぐるり1周する仲間。高さで名前が変わるだけ。',
           size=12, anchor='start', fill='#555')
    s.text(726, 816,
           '★ 見分けは「せい」。胴差300 ＞ 軒桁240 ＞ 土台120。',
           size=12, anchor='start', fill='#555')
    s.text(726, 836,
           '★ 桁と梁のちがいは向き。棟と平行が桁、直角が梁。',
           size=12, anchor='start', fill='#555')

    s.text(W / 2.0, H - 18,
           'たてに立つもの＝柱・束　／　よこにわたすもの＝土台・胴差・桁・梁。'
           'まずこの2つに分けると、名前は迷わない。',
           size=13, weight='700', fill='#333')
    return s


# ============================================ 本番の答案ではこう描く
def toban():
    """教材の色つきの図と、答案の黒鉛筆の図をならべて対応させる。

    記号の描き方は ansframe.py（標準解答例と同じ描き方）にそろえてある。
    """
    W, H = 1240, 1070
    s = Svg(W, H)
    s.text(W / 2.0, 42, '部材ずかん ④　本番の答案では、こう描く', size=22,
           weight='700')
    s.text(W / 2.0, 68,
           'この教材の図は色を使っているが、本番は黒鉛筆だけ。'
           '色のかわりに「線の種類」と「記号」で見分ける。',
           size=12.5, fill='#666')

    panel(s, 20, 92, 588, 474, 'この教材の図（色つき）',
          '色で部材を見分けている。おぼえるための図')
    panel(s, 624, 92, 596, 474, '本番の答案（黒鉛筆だけ）',
          'ぜんぶ2本線。柱は記号。寸法は1本ずつ書きこむ')

    g = 132.0

    # ---------------------------------------------------- 左：色つき
    lx, ly = 196.0, 200.0

    def LX(gx):
        return lx + gx * g

    def LY(gy):
        return ly + (2 - gy) * g

    for i in range(3):
        s.line(LX(0), LY(i), LX(2), LY(i), stroke='#eee', stroke_width=0.8)
        s.line(LX(i), LY(0), LX(i), LY(2), stroke='#eee', stroke_width=0.8)
    s.line(LX(0), LY(0), LX(2), LY(0), stroke=C_DOU, stroke_width=6.0)
    s.line(LX(0), LY(0), LX(0), LY(2), stroke=C_DOU, stroke_width=6.0)
    s.line(LX(2), LY(0), LX(2), LY(2), stroke=C_OO, stroke_width=5.2)
    s.line(LX(0), LY(2), LX(2), LY(2), stroke=C_OO, stroke_width=4.4)
    s.line(LX(0), LY(1), LX(2), LY(1), stroke=C_KO, stroke_width=2.4)
    s.line(LX(1), LY(0), LX(0), LY(1), stroke=C_HI, stroke_width=2.8)
    for gx, gy in ((2, 0), (0, 2), (2, 2)):
        s.rect(LX(gx) - 5, LY(gy) - 5, 10, 10, fill='#111')
    s.circle(LX(0), LY(0), 9.5, fill='#fff', stroke=C_TOOSHI,
             stroke_width=2.6)
    s.circle(LX(0), LY(0), 4.5, fill=C_TOOSHI)
    s.text(LX(1), LY(0) + 34, '色で見分けている', size=12, fill='#999')

    # ---------------------------------------------------- 右：答案
    ax, ay = 812.0, 200.0
    HW = 120.0 / 910.0 * g / 2.0        # 部材120mmの半分
    CH = min(HW, 3.4)                   # はしの面取り

    def AX(gx):
        return ax + gx * g

    def AY(gy):
        return ay + (2 - gy) * g

    # 答案用紙の目盛（4.55mm＝455mm。1マス910は目盛2つぶん）
    for i in range(5):
        s.line(AX(0) - 20, AY(0) - i * g / 2.0, AX(2) + 20,
               AY(0) - i * g / 2.0, stroke='#dedede', stroke_width=0.7)
        s.line(AX(0) + i * g / 2.0, AY(0) + 20, AX(0) + i * g / 2.0,
               AY(2) - 20, stroke='#dedede', stroke_width=0.7)
    s.text(AX(2) + 26, AY(2) - 6, '答案用紙の目盛', size=9.5, anchor='start',
           fill='#bbb')
    s.text(AX(2) + 26, AY(2) + 8, '4.55mm＝455mm', size=9.5, anchor='start',
           fill='#bbb')
    s.text(AX(2) + 26, AY(2) + 22, '（1マス910＝目盛2つ）', size=9.5,
           anchor='start', fill='#bbb')

    dims = []

    def mem(ori, ln, a, b, dim, side=1):
        """答案の描き方：2本線＋はしを斜めに落とす＋わきに断面寸法。"""
        if ori == 'H':
            y = AY(ln)
            for d in (-HW, HW):
                s.line(AX(a) + CH, y + d, AX(b) - CH, y + d, stroke='#111',
                       stroke_width=1.2)
            for xx, sg in ((AX(a), 1), (AX(b), -1)):
                s.line(xx, y - HW + CH, xx, y + HW - CH, stroke='#111',
                       stroke_width=1.2)
                s.line(xx, y - HW + CH, xx + sg * CH, y - HW, stroke='#111',
                       stroke_width=1.2)
                s.line(xx, y + HW - CH, xx + sg * CH, y + HW, stroke='#111',
                       stroke_width=1.2)
            dims.append(('H', (AX(a) + AX(b)) / 2.0,
                         y - HW - 6 if side > 0 else y + HW + 14, dim))
        else:
            x = AX(ln)
            for d in (-HW, HW):
                s.line(x + d, AY(a) - CH, x + d, AY(b) + CH, stroke='#111',
                       stroke_width=1.2)
            for yy, sg in ((AY(a), -1), (AY(b), 1)):
                s.line(x - HW + CH, yy, x + HW - CH, yy, stroke='#111',
                       stroke_width=1.2)
                s.line(x - HW + CH, yy, x - HW, yy + sg * CH, stroke='#111',
                       stroke_width=1.2)
                s.line(x + HW - CH, yy, x + HW, yy + sg * CH, stroke='#111',
                       stroke_width=1.2)
            dims.append(('V', x + (HW + 13) * side,
                         (AY(a) + AY(b)) / 2.0, dim))

    mem('H', 0, 0, 2, '120×300', side=-1)          # 胴差（東西）
    mem('V', 0, 0, 2, '120×300', side=-1)          # 胴差（南北）
    mem('V', 2, 0, 2, '120×300')                   # 大梁（南北）
    mem('H', 2, 0, 2, '120×240')                   # 大梁（東西）
    mem('H', 1, 0, 2, '120×180')                   # 床小梁
    s.line(AX(1), AY(0), AX(0), AY(1), stroke='#111', stroke_width=1.3,
           stroke_dasharray='9 5')                 # 火打梁は破線
    s.text(AX(0.62), AY(0.62) + 4, '火打梁', size=9, fill='#111')

    r = 6.0
    for gx, gy in ((2, 0), (0, 2), (2, 2)):        # 管柱＝四角の中にバツ
        x, y = AX(gx), AY(gy)
        s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke='#111',
               stroke_width=1.1)
        s.line(x - r, y - r, x + r, y + r, stroke='#111', stroke_width=1.3)
        s.line(x - r, y + r, x + r, y - r, stroke='#111', stroke_width=1.3)
    x, y = AX(0), AY(0)                            # 通し柱＝四角を○で囲む
    s.rect(x - r, y - r, 2 * r, 2 * r, fill='#fff', stroke='#111',
           stroke_width=1.1)
    s.circle(x, y, r + 4.5, fill='none', stroke='#111', stroke_width=1.3)

    for k, a, b, txt in dims:
        if k == 'H':
            s.text(a, b, txt, size=9.5, fill='#111')
        else:
            s.text_rot(a, b, txt, -90, size=9.5, fill='#111')
    s.dim_h(AX(0), AX(1), AY(0) + 46, '910', size=9.5)
    s.dim_h(AX(1), AX(2), AY(0) + 46, '910', size=9.5)
    s.dim_v(AY(0), AY(1), AX(0) - 52, '910', size=9.5)
    s.dim_v(AY(1), AY(2), AX(0) - 52, '910', size=9.5)
    s.text(AX(1), AY(0) + 74, '線の種類と記号で見分ける', size=12,
           fill='#999')

    s.text(636, 548,
           '★ 2本線のすきまは、実際の1／100では 1.2mm。'
           'ほとんどくっついて見えるくらいでよい。',
           size=11.5, anchor='start', fill='#555')
    s.text(32, 548,
           '★ 本番で色は使わない。色えんぴつも不要。',
           size=11.5, anchor='start', fill='#555')

    # ---------------------------------------------------- 対応表
    TY = 604.0
    s.text(30, TY - 8, '色 → 記号の対応表', size=15, anchor='start',
           weight='700')
    COL = (40.0, 210.0, 400.0, 560.0, 940.0)
    HEAD = ('この教材の色', '答案の記号', '部材', '答案での描き方',
            '断面寸法はどこに書くか')
    s.rect(30, TY + 6, W - 60, 30, fill='#f3efe7', stroke='#ddd',
           stroke_width=0.8)
    for cx, h in zip(COL, HEAD):
        s.text(cx + 6, TY + 26, h, size=11.5, anchor='start', weight='700',
               fill='#555')

    def sw_line(x, y, col, wdt, dash=None):
        s.line(x + 6, y, x + 96, y, stroke=col, stroke_width=wdt,
               stroke_dasharray=dash)

    def sy_double(x, y, dash=None):
        for d in (-3.6, 3.6):
            s.line(x + 6, y + d, x + 96, y + d, stroke='#111',
                   stroke_width=1.2, stroke_dasharray=dash)

    def sy_chain(x, y):
        s.line(x + 6, y, x + 96, y, stroke='#111', stroke_width=1.1,
               stroke_dasharray='14 3 2 3')
        s.circle(x + 51, y, 4, fill='#111')

    ROWS = (
        (lambda x, y: (s.circle(x + 51, y, 8, fill='#fff', stroke=C_TOOSHI,
                                stroke_width=2.4),
                       s.circle(x + 51, y, 4, fill=C_TOOSHI)),
         lambda x, y: (s.rect(x + 45, y - 6, 12, 12, fill='#fff',
                              stroke='#111', stroke_width=1.1),
                       s.circle(x + 51, y, 10.5, fill='none', stroke='#111',
                                stroke_width=1.3)),
         '通し柱', '四角を○で囲む（四すみ4か所）', '凡例欄に 120×120'),
        (lambda x, y: s.rect(x + 45, y - 5, 10, 10, fill='#111'),
         lambda x, y: (s.rect(x + 44, y - 7, 14, 14, fill='#fff',
                              stroke='#111', stroke_width=1.1),
                       s.line(x + 44, y - 7, x + 58, y + 7, stroke='#111',
                              stroke_width=1.3),
                       s.line(x + 44, y + 7, x + 58, y - 7, stroke='#111',
                              stroke_width=1.3)),
         '管柱', '四角の中にバツ（上下階が重なる管柱）', '凡例欄に 120×120'),
        (lambda x, y: sw_line(x, y, C_DOU, 6.0), sy_double,
         '胴差', '2本線。はしは斜めに落とす', '図の中、梁のわきに 120×300'),
        (lambda x, y: sw_line(x, y, C_OO, 5.0), sy_double,
         '大梁・桁・小屋梁', '2本線（胴差と同じ描き方）',
         '図の中、梁のわきに 120×300／240'),
        (lambda x, y: sw_line(x, y, C_KO, 2.4), sy_double,
         '床小梁', '2本線。線を細めに', '図の中、梁のわきに 120×180'),
        (lambda x, y: sw_line(x, y, C_HI, 2.8),
         lambda x, y: s.line(x + 6, y, x + 96, y, stroke='#111',
                             stroke_width=1.3, stroke_dasharray='9 5'),
         '火打梁', '破線1本（2本線にしない）', '凡例欄に 90×90'),
        (lambda x, y: sw_line(x, y, C_KO, 2.0), sy_chain,
         '母屋・小屋束', '一点鎖線＋交点に黒丸（＝小屋束）',
         '凡例欄に 90×90（小屋束は書かない）'),
        (lambda x, y: sw_line(x, y, C_MUNE, 4.6), sy_double,
         '棟木', '2本線（母屋より太め）', '凡例欄に 120×120'),
    )
    for i, (a, b, name, how, where) in enumerate(ROWS):
        y = TY + 36 + i * 40
        if i % 2:
            s.rect(30, y, W - 60, 40, fill='#fbfaf8', stroke='none')
        s.line(30, y + 40, W - 30, y + 40, stroke='#eee', stroke_width=0.8)
        a(COL[0], y + 20)
        b(COL[1], y + 20)
        s.text(COL[1] - 24, y + 25, '→', size=15, fill='#bbb')
        s.text(COL[2] + 6, y + 25, name, size=12.5, anchor='start',
               weight='700')
        s.text(COL[3] + 6, y + 25, how, size=12, anchor='start', fill='#333')
        s.text(COL[4] + 6, y + 25, where, size=12, anchor='start',
               fill='#333')
    s.rect(30, TY + 6, W - 60, 36 + len(ROWS) * 40 - 6, fill='none',
           stroke='#ddd', stroke_width=1.0)

    s.text(W / 2.0, H - 22,
           '★ 平角材（120×300 など）の寸法は凡例欄ではなく、'
           '図の中の梁1本ずつのわきに書く。ここを取りちがえる人が多い。',
           size=13, weight='700', fill='#c0392b')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    zentai().save(os.path.join(out, 'buzai_zentai.svg'))
    hashira().save(os.path.join(out, 'buzai_hashira.svg'))
    toban().save(os.path.join(out, 'buzai_toban.svg'))
    yuka().save(os.path.join(out, 'buzai_yuka.svg'))
    koya().save(os.path.join(out, 'buzai_koya.svg'))
    print('wrote buzai_zentai / _hashira / _toban / _yuka / _koya .svg')
