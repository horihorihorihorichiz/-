# -*- coding: utf-8 -*-
"""教材ぜんぶの数字の整合性をまとめて検算する。

    python3 scripts/check.py

図を作るスクリプトと、HTMLの本文の両方をつきあわせて、
食いちがいがあれば「NG」として並べる。ぜんぶ通れば最後に OK と出る。
"""
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import plans                                                  # noqa: E402
import answers                                                # noqa: E402

NG = []
OKN = [0]


def ck(cond, msg):
    if cond:
        OKN[0] += 1
    else:
        NG.append(msg)


def html(*names):
    out = {}
    for n in names:
        p = os.path.join(BASE, n)
        if os.path.exists(p):
            out[n] = io.open(p, encoding='utf-8').read()
    return out


# ---------------------------------------------------------------- 1 開口
def check_openings():
    sets = [('型', {n: d for n, d in plans.FLOORS.items()},
             plans.NX, plans.NY, plans.XLINES, plans.YLINES)]
    for k, v in answers.PLANS.items():
        f0 = v[0]
        sets.append((k, {i + 1: d for i, d in enumerate(v)},
                     f0.get('nx', plans.NX), f0.get('ny', plans.NY),
                     f0.get('xlines', plans.XLINES),
                     f0.get('ylines', plans.YLINES)))
    for tag, floors, nx, ny, xl, yl in sets:
        xs = [g for g, _ in xl]
        ys = [g for g, _ in yl]

        def bay(cross, m):
            for a, b in zip(cross[:-1], cross[1:]):
                if a - 1e-9 <= m <= b + 1e-9:
                    return (a, b)
            return None
        rec = {}
        for n, ops in plans.fit_all(floors, nx, ny, xl, yl).items():
            for f, p, l, kd, lab in ops:
                mm = round(l * 910)
                ck(mm % 455 == 0,
                   '%s %d階 %s 開口の幅 %dmm が455の倍数でない' % (tag, n, f, mm))
                ck(mm <= 1820,
                   '%s %d階 %s 開口の幅 %dmm が1,820をこえる' % (tag, n, f, mm))
                cross = xs if f in ('S', 'N') else ys
                rec.setdefault((f, bay(cross, p + l / 2.0)), {})[n] = \
                    (round(p, 2), round(l, 2))
        for key, v in rec.items():
            ck(len({g for g in v.values()}) == 1,
               '%s %s%s の窓が上下階でそろっていない %s' % (tag, key[0], key[1], v))


# ---------------------------------------------------------------- 2 柱
def check_columns():
    tooshi, kuda = plans.columns()
    ck(len(tooshi) == 4, '通し柱が4本でない（%d本）' % len(tooshi))
    ck(set(tooshi) == {(0, 0), (plans.NX, 0), (0, plans.NY),
                       (plans.NX, plans.NY)}, '通し柱が四隅にない')
    pts = set(tooshi) | set(kuda)
    W = plans._wall_segments(plans.FLOORS)
    for (ori, ln), segs in W.items():
        on = sorted({(y if ori == 'V' else x) for (x, y) in pts
                     if (x == ln if ori == 'V' else y == ln)})
        for a, b in zip(on[:-1], on[1:]):
            if any(q0 - 1e-9 <= a and b <= q1 + 1e-9 for q0, q1 in segs):
                ck(round((b - a) * 910) <= 1820,
                   '柱の間隔が %dmm（%s 通り %s）' %
                   (round((b - a) * 910), ori, ln))
    for x, y in pts:
        ck(abs(x * 2 - round(x * 2)) < 1e-6 and abs(y * 2 - round(y * 2)) < 1e-6,
           '柱が半マスの位置にない座標 (%s,%s)' % (x, y))
    # 室内の建具：幅は455の倍数で1,820以下、その開口の中に柱を立てない
    for n, d in plans.FLOORS.items():
        fd = plans.fit_doors(d, plans.FLOORS)
        ck(len(fd) == len(d.get('doors', [])),
           '%d階 置けなくなった建具がある' % n)
        for ori, wall, pos, ln in fd:
            mm = round(ln * 910)
            ck(mm % 455 == 0 and 910 <= mm <= 1820,
               '%d階 建具の幅 %dmm がおかしい' % (n, mm))
            on = [(y if ori == 'V' else x) for (x, y) in pts
                  if (x == wall if ori == 'V' else y == wall)]
            for m in on:
                ck(not (pos + 1e-6 < m < pos + ln - 1e-6),
                   '%d階 建具（%s通り%s の %.1f〜%.1f）の中に柱がある' %
                   (n, ori, wall, pos, pos + ln))
    return len(pts), len(tooshi), len(kuda)


# ---------------------------------------------------------------- 3 採光
def check_light():
    H = {'win': 1300, 'balc': 2000, 'entry': 2000}
    FIT = plans.fit_all(plans.FLOORS)
    for n, d in plans.FLOORS.items():
        ops = FIT[n]
        for name, ar, a, b, c, e, kind in d['rooms']:
            if kind != 'living':
                continue
            need = float(ar) / 7.0
            tot = 0.0
            for f, p, l, k, lab in ops:
                ok = ((f == 'S' and b == 0 and a - 1e-6 <= p
                       and p + l <= c + 1e-6) or
                      (f == 'N' and e == plans.NY and a - 1e-6 <= p
                       and p + l <= c + 1e-6) or
                      (f == 'W' and a == 0 and b - 1e-6 <= p
                       and p + l <= e + 1e-6) or
                      (f == 'E' and c == plans.NX and b - 1e-6 <= p
                       and p + l <= e + 1e-6))
                if ok:
                    tot += l * 910 * H[k] / 1e6
            ck(tot >= need,
               '%d階 %s の採光が不足 必要%.2f 実際%.2f' % (n, name, need, tot))


# ---------------------------------------------------------------- 4 面積
def check_area():
    one = round(plans.NX * 910 / 1000.0 * plans.NY * 910 / 1000.0, 4)
    ck(abs(one - 66.2480) < 1e-3, '1階の面積が66.24でない（%.4f）' % one)
    total = int(one * 3 * 100) / 100.0
    ck(abs(total - 198.74) < 0.03, '延べ面積が198.72前後でない（%.2f）' % total)
    return one, total


# ---------------------------------------------------------------- 5 高さ
def check_height():
    parts = [('基礎の立上り', 371), ('パッキン', 20), ('土台', 120),
             ('合板', 24), ('仕上げ', 15)]
    fl1 = sum(v for _, v in parts)
    ck(fl1 == 550, '1FLの積み上げが550にならない（%d）' % fl1)
    noki = fl1 + 3100 + 2900 + 2800
    ck(noki == 9350, '軒高が9,350にならない（%d）' % noki)
    top = noki + int(3640 * 0.4)
    ck(top == 10806, '最高の高さが10,806にならない（%d）' % top)
    return fl1, noki, top


# ---------------------------------------------------------------- 6 階段
def check_stair():
    for kai, dan in ((3100, 15), (2900, 14), (2800, 14)):
        ke = kai / float(dan)
        ck(ke <= 220.0001, '階高%d を %d段にすると蹴上%.1f（220超）' %
           (kai, dan, ke))
    ck(910 / 4.0 >= 210, '踏面227.5が210未満')


# ---------------------------------------------------------------- 7 梁せい
def check_beam():
    import ansframe
    import buzai
    for span, want in ((1820, 180), (2730, 240), (3640, 300)):
        ck(ansframe.sei(span / 910.0) == want,
           'ansframe：スパン%d の梁せいが%dでない' % (span, want))
        ck(buzai._sei(span / 910.0) == want,
           'buzai：スパン%d の梁せいが%dでない' % (span, want))


# ---------------------------------------------------------------- 8 本文
def check_text(ncol):
    pages = html('kaisetsu.src.html', 'onepage.src.html', 'buzai.src.html',
                 'shousai_howto.src.html', '02-katachi.html',
                 'checkrun.html', 'onsei.html', 'sotomawari.src.html',
                 'kotoshi.src.html')
    for name, t in pages.items():
        ck('16本' not in t, '%s に古い「16本」が残っている' % name)
        for bad, why in ((r'200㎡未満', '階数3以下の条件がない令128条の書き方'),):
            for m in re.finditer(bad, t):
                near = t[max(0, m.start() - 60):m.end() + 140]
                ck('階数3以下' in near or '200㎡を超え' in near or
                   '200㎡以内' in near or '延べ' in near,
                   '%s：%s' % (name, why))
    txt = ''.join(pages.values())
    for num in ('9,350', '10,806', '198.72', '66.24', '1,820'):
        ck(num in txt, '本文に %s が出てこない' % num)


def main():
    check_openings()
    n, t, k = check_columns()
    check_light()
    one, total = check_area()
    fl1, noki, top = check_height()
    check_stair()
    check_beam()
    check_text(n)
    print('柱 %d本（通し柱%d＋管柱%d）／1階%.2f㎡・延べ%.2f㎡／'
          '1FL+%d・軒%d・最高%d' % (n, t, k, one, total, fl1, noki, top))
    print('検算した項目 %d件' % (OKN[0] + len(NG)))
    if NG:
        print('NG %d件' % len(NG))
        for m in NG:
            print('  ×', m)
        return 1
    print('OK ぜんぶ通りました')
    return 0


if __name__ == '__main__':
    sys.exit(main())
