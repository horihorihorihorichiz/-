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


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    yuka().save(os.path.join(out, 'buzai_yuka.svg'))
    koya().save(os.path.join(out, 'buzai_koya.svg'))
    print('wrote buzai_yuka.svg / buzai_koya.svg')
