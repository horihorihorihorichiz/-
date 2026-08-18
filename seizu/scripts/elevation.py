# -*- coding: utf-8 -*-
"""南立面図（妻面）と、階段の段数の割付図。"""
import os
from svgkit import Svg

# ---- 高さの決め方 ----
FL1 = 550.0           # 1FL = GL+550
H1, H2, H3 = 3100.0, 2900.0, 2800.0
FL2 = FL1 + H1        # 3,650
FL3 = FL2 + H2        # 6,550
NOKI = FL3 + H3       # 9,350 ＝ 軒高
WIDTH = 7280.0
EAVE = 600.0          # 軒の出
PITCH = 0.4           # 4寸勾配
RISE = (WIDTH / 2.0) * PITCH          # 1,456
TOP = NOKI + RISE                     # 10,806


def elevation():
    S = 0.055
    ML, MT = 150, 116
    dw = (WIDTH + 2 * EAVE) * S
    dh = (TOP + 400) * S
    W, H = int(ML + dw + 220), int(MT + dh + 118)
    s = Svg(W, H)

    def X(mm):
        return ML + (mm + EAVE) * S

    def Y(mm):
        return MT + (TOP - mm) * S

    s.text(W / 2.0, 36, '南立面図（妻面） 1/100', size=21, weight='700')
    s.text(W / 2.0, 58, '棟が南北方向なので、南から見ると屋根は三角形に見える',
           size=11.5, fill='#666')
    s.text(W / 2.0, 78, '切妻・4寸勾配　／　軒の出 600', size=11.5, fill='#666')

    # 地面
    s.rect(X(-EAVE) - 40, Y(0), dw + 80, 26, fill='#f2ece0', stroke='none')
    s.line(X(-EAVE) - 40, Y(0), X(WIDTH + EAVE) + 40, Y(0), stroke='#333',
           stroke_width=2.0)

    # 屋根
    s.polygon([(X(-EAVE), Y(NOKI - EAVE * PITCH)), (X(WIDTH / 2.0), Y(TOP)),
               (X(WIDTH + EAVE), Y(NOKI - EAVE * PITCH)),
               (X(WIDTH + EAVE), Y(NOKI - EAVE * PITCH - 120)),
               (X(WIDTH / 2.0), Y(TOP - 120)),
               (X(-EAVE), Y(NOKI - EAVE * PITCH - 120))],
              fill='#5b6b7a', stroke='#33414d', stroke_width=1.4)
    # 妻壁
    s.polygon([(X(0), Y(NOKI)), (X(WIDTH / 2.0), Y(TOP - 130)),
               (X(WIDTH), Y(NOKI))], fill='#e9e4da', stroke='#8b8377',
              stroke_width=1.2)
    # 外壁
    s.rect(X(0), Y(NOKI), WIDTH * S, (NOKI - 0) * S, fill='#f3efe7',
           stroke='#8b8377', stroke_width=1.6)
    # 各階の床ライン
    for mm, lab in ((FL1, '1FL'), (FL2, '2FL'), (FL3, '3FL')):
        s.line(X(0), Y(mm), X(WIDTH), Y(mm), stroke='#c7bfb2',
               stroke_width=0.9, stroke_dasharray='6 4')

    # 開口部
    def win(x0, x1, y0, y1, kind='win'):
        col = '#2f7fd0' if kind == 'win' else '#d0342f'
        s.rect(X(x0), Y(y1), (x1 - x0) * S, (y1 - y0) * S, fill='#dff0fb',
               stroke=col, stroke_width=1.4)
    win(1820, 5460, FL1 + 100, FL1 + 2300, 'door')     # 店舗の出入口
    win(300, 1500, FL1 + 700, FL1 + 2100)              # 住宅玄関まわり
    win(5900, 7000, FL1 + 800, FL1 + 2100)
    win(1000, 3200, FL2 + 300, FL2 + 2100)             # 2階 掃出し窓
    win(3700, 5900, FL2 + 800, FL2 + 2100)
    win(6200, 7000, FL2 + 800, FL2 + 1900)
    win(900, 2900, FL3 + 800, FL3 + 2000)              # 3階 子供室
    win(4300, 6300, FL3 + 800, FL3 + 2000)
    # バルコニー
    s.rect(X(800), Y(FL2 + 1100), 2600 * S, 1100 * S, fill='none',
           stroke='#6b8fa8', stroke_width=1.6)

    # 寸法（右側）
    dx = X(WIDTH + EAVE) + 46
    for a, b, lab in ((0, FL1, '550'), (FL1, FL2, '3,100'),
                      (FL2, FL3, '2,900'), (FL3, NOKI, '2,800')):
        s.line(dx, Y(a), dx, Y(b), stroke='#444', stroke_width=0.8)
        for m in (a, b):
            s.line(dx - 4, Y(m), dx + 4, Y(m), stroke='#444',
                   stroke_width=0.8)
        s.text_rot(dx - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=10.5,
                   fill='#444')
    dx2 = dx + 52
    for a, b, lab, col in ((0, NOKI, '軒高 9,350', '#b03060'),
                           (0, TOP, '最高高さ 10,806', '#1f6fb2')):
        s.line(dx2, Y(a), dx2, Y(b), stroke=col, stroke_width=1.0)
        for m in (a, b):
            s.line(dx2 - 4, Y(m), dx2 + 4, Y(m), stroke=col,
                   stroke_width=1.0)
        s.text_rot(dx2 - 6, (Y(a) + Y(b)) / 2.0, lab, -90, size=11,
                   fill=col, weight='700')
        dx2 += 56

    # レベル表示（左側）
    for mm, lab in ((0, 'GL ±0'), (FL1, '1FL  +550'), (FL2, '2FL  +3,650'),
                    (FL3, '3FL  +6,550'), (NOKI, '軒桁天端  +9,350'),
                    (TOP, '最高  +10,806')):
        s.line(X(-EAVE) - 34, Y(mm), X(0), Y(mm), stroke='#b03060',
               stroke_width=0.7, stroke_dasharray='8 3 2 3')
        s.text(X(-EAVE) - 38, Y(mm) - 4, lab, size=10.5, anchor='end',
               fill='#b03060', weight='700')

    # 幅の寸法
    s.dim_h(X(0), X(WIDTH), Y(0) + 46, '7,280')
    # 勾配記号
    gx, gy = X(WIDTH / 2.0) + 30, Y(TOP) + 26
    s.poly([(gx, gy), (gx + 50, gy + 20), (gx, gy + 20), (gx, gy)],
           stroke='#33414d', stroke_width=1.2)
    s.text(gx + 26, gy + 34, '4 / 10（4寸勾配）', size=10.5, fill='#33414d')

    s.text(W / 2.0, H - 34,
           '棟までの高さ ＝ 3,640 × 0.4 ＝ 1,456 → 9,350 ＋ 1,456 ＝ 10,806',
           size=11.5, fill='#555')
    s.text(W / 2.0, H - 14,
           '※ 1FL を GL+400 とする型では 軒高 9,200 / 最高 10,656 になる。'
           'どちらか一方に必ずそろえること。', size=11, fill='#999')
    return s


def stairs():
    S = 0.070
    W, H = 760, 512
    s = Svg(W, H)
    s.text(W / 2.0, 34, '階段の段数の割付（ここを間違えると不適合）', size=20,
           weight='700')
    s.text(W / 2.0, 57,
           '階高 ÷ 段数 ＝ 蹴上（1段の高さ）。踏面はどちらも 210mm でそろえる',
           size=11.5, fill='#666')

    def one(ox, oy, rise_total, steps, title, ok_shop, note):
        tread = 210.0
        r = rise_total / steps
        run = tread * (steps - 1)
        # 階段の輪郭
        pts = [(ox, oy)]
        x, y = ox, oy
        for i in range(steps):
            y -= r * S
            pts.append((x, y))
            if i < steps - 1:
                x += tread * S
                pts.append((x, y))
        s.poly(pts, stroke='#8a6d00', stroke_width=2.0)
        s.line(ox, oy, ox + run * S, oy, stroke='#ccc', stroke_width=0.8)
        s.line(ox, oy, ox, oy - rise_total * S, stroke='#ccc',
               stroke_width=0.8)
        # 床
        s.line(ox - 30, oy, ox, oy, stroke='#333', stroke_width=2.4)
        s.line(ox + run * S, oy - rise_total * S, ox + run * S + 34,
               oy - rise_total * S, stroke='#333', stroke_width=2.4)
        # 見出し
        s.text(ox + run * S / 2.0, oy + 34, title, size=13, weight='700')
        # 寸法
        s.dim_v(oy, oy - rise_total * S, ox - 46,
                '階高 %s' % format(int(rise_total), ','), color='#444')
        s.text(ox + run * S / 2.0, oy - rise_total * S - 14,
               '%d段　／　蹴上 %.1f　／　踏面 210' % (steps, r), size=13,
               weight='700', fill='#8a6d00')
        # 判定
        col = '#1e7e34' if ok_shop else '#c0392b'
        s.text(ox + run * S / 2.0, oy + 56, note, size=11.5, fill=col,
               weight='700')

    one(110, 340, 3100, 15, '1階 → 2階（階高 3,100）', True,
        '蹴上 206.7 ≦ 220　→ 店舗の基準もOK')
    one(430, 340, 2900, 14, '2階 → 3階（階高 2,900）', True,
        '蹴上 207.1 ≦ 220　→ 店舗の基準もOK')

    s.rect(40, 414, W - 80, 82, fill='#f6f9f4', stroke='#bcd4bc',
           stroke_width=1, rx=6)
    s.text(56, 436, '住宅の階段　　： 幅 750以上 ／ 蹴上 230以下 ／ 踏面 150以上',
           size=11.5, anchor='start', fill='#245a2c')
    s.text(56, 458,
           '店舗の階段　　： 幅 750以上 ／ 蹴上 220以下 ／ 踏面 210以上'
           '（物品販売 1,500㎡以下）', size=11.5, anchor='start',
           fill='#245a2c')
    s.text(56, 482,
           '★ 1階を14段にすると 3,100÷14＝221.4 で店舗の220を超える。'
           'だから1階だけ15段にする。', size=11.5, anchor='start',
           fill='#c0392b', weight='700')
    return s


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                       'figures')
    elevation().save(os.path.join(out, 'elevation_s.svg'))
    stairs().save(os.path.join(out, 'stair.svg'))
    print('wrote elevation_s.svg / stair.svg')
