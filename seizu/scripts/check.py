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
    """柱は階ごと。通り芯の交点は全階共通、あとはその階の壁に合わせる。"""
    xs = [g for g, _ in plans.XLINES]
    ys = [g for g, _ in plans.YLINES]
    counts = []
    sets = {}
    for n, d in plans.FLOORS.items():
        tooshi, kuda = plans.columns_of(n)
        pts = set(tooshi) | set(kuda)
        sets[n] = pts
        counts.append(len(pts))
        ck(len(tooshi) == 4, '%d階 通し柱が4本でない（%d本）' % (n, len(tooshi)))
        ck(set(tooshi) == {(0, 0), (plans.NX, 0), (0, plans.NY),
                           (plans.NX, plans.NY)}, '%d階 通し柱が四隅にない' % n)
        for x in xs:
            for y in ys:
                ck((x, y) in pts, '%d階 通り芯の交点(%s,%s)に柱がない' % (n, x, y))
        for x, y in pts:
            ck(abs(x * 2 - round(x * 2)) < 1e-6 and
               abs(y * 2 - round(y * 2)) < 1e-6,
               '%d階 柱が半マスの位置にない (%s,%s)' % (n, x, y))
        W = plans._wall_segments({0: d})
        for (ori, ln), segs in W.items():
            on = sorted({(y if ori == 'V' else x) for (x, y) in pts
                         if (x == ln if ori == 'V' else y == ln)})
            for a, b in zip(on[:-1], on[1:]):
                if any(q0 - 1e-9 <= a and b <= q1 + 1e-9 for q0, q1 in segs):
                    ck(round((b - a) * 910) <= 1820,
                       '%d階 壁の中の柱の間隔が %dmm（%s通り %s）' %
                       (n, round((b - a) * 910), ori, ln))
        # 壁のない所に立つ柱は、通り芯の交点だけ
        for (x, y) in pts:
            okv = any(a - 1e-9 <= y <= b + 1e-9 for a, b in W.get(('V', x), []))
            okh = any(a - 1e-9 <= x <= b + 1e-9 for a, b in W.get(('H', y), []))
            ck(okv or okh or (x in xs and y in ys),
               '%d階 壁のない所に柱がある (%s,%s)' % (n, x, y))
        # 室内の建具：幅と、開口の中に柱がないこと
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
                   '%d階 建具（%s通り%s %.1f〜%.1f）の中に柱がある' %
                   (n, ori, wall, pos, pos + ln))
    common = sets[1] & sets[2] & sets[3]
    ck(len(common) >= 28, '3階とも同じ位置の柱が少ない（%d本）' % len(common))
    ck(len(sets[2] & sets[1]) / float(len(sets[2])) >= 0.8,
       '2階の柱の直下率が8割を切っている')
    return counts, len(common)


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


# ---------------------------------------------------------------- 7b 伏図の梁
def check_framing():
    """壁の上下に梁があるか、梁の両端が受けられているか、スパンが3,640以下か。"""
    nx, ny = plans.NX, plans.NY
    for lo, up, name in ((2, 3, '3階床伏図'), (3, None, '小屋伏図')):
        mem = plans.framing(lo, up)
        cov = {}
        for ori, ln, a, b, size, kd in mem:
            cov.setdefault((ori, ln), []).append((a, b))
            ck(b - a <= 4.0 + 1e-9, '%s：スパン%.0fの梁がある（3,640超）' %
               (name, (b - a) * 910))
            ck(re.match(r'120×(180|240|300)$', size) is not None,
               '%s：断面寸法 %s が型にない' % (name, size))
        cov = {k: plans._union(v) for k, v in cov.items()}

        def covered(ori, ln, a, b):
            return any(p - 1e-9 <= a and b <= q + 1e-9
                       for p, q in cov.get((ori, float(ln)), []))
        fl = {k: plans.FLOORS[k] for k in (lo, up) if k is not None}
        for (ori, ln), segs in plans._wall_segments(fl).items():
            for a, b in segs:
                ck(covered(ori, ln, a, b),
                   '%s：%s通り %s の壁の上下に梁がない' % (name, ori, ln))
        for ori, ln, a, b, size, kd in mem:            # 両端は梁か外周で受ける
            other = 'V' if ori == 'H' else 'H'
            lim = nx if ori == 'H' else ny
            for e in (a, b):
                ok = e in (0.0, float(lim)) or any(
                    p - 1e-9 <= ln <= q + 1e-9
                    for p, q in cov.get((other, float(e)), []))
                ck(ok, '%s：%s通り %s の梁の端 %s に受けがない' %
                   (name, ori, ln, e))
        rows = range(2, ny, 2) if up is None else range(1, ny)
        for y in rows:                                  # 梁のピッチ
            ck(covered('H', y, 0.0, float(nx)),
               '%s：%s通りに梁が通っていない' % (name, y))


# ---------------------------------------------------------------- 7c 階段室のドアと到達
def check_stair_access():
    """折り返し階段のドアは上りはじめ側（踊り場の反対）だけ。全室に階段や入口からドアで行ける。"""
    import answers
    sets = [('型', {1: plans.FLOORS[1], 2: plans.FLOORS[2], 3: plans.FLOORS[3]})]
    for k, fl in sorted(answers.PLANS.items()):
        sets.append(('予想問題' + k, {1: fl[0], 2: fl[1], 3: fl[2]}))
    for name, fl in sets:
        for n, d in fl.items():
            sa, sb, sc, sd = d.get('stair_box', (0, 2, 2, 6))
            flip = bool(d.get('stair_flip'))
            nx, ny = d.get('nx', plans.NX), d.get('ny', plans.NY)
            hall = (sd - 1.5, sd) if flip else (sb, sb + 1.5)
            land_wall, hall_wall = (sb, sd) if flip else (sd, sb)
            rooms = d['rooms']

            def rid(x, y):          # 点を含む部屋（重なっていたら小さいほう）
                best = None
                for i, (_, _, a, b, c, e, _) in enumerate(rooms):
                    if a - 1e-6 <= x <= c + 1e-6 and b - 1e-6 <= y <= e + 1e-6:
                        if best is None or (c - a) * (e - b) < best[1]:
                            best = (i, (c - a) * (e - b))
                return None if best is None else best[0]
            adj = {i: set() for i in range(len(rooms))}
            for o, w, p, l in d.get('doors', []):
                mid = p + l / 2.0
                r1, r2 = ((rid(w - .01, mid), rid(w + .01, mid)) if o == 'V'
                          else (rid(mid, w - .01), rid(mid, w + .01)))
                if r1 is not None and r2 is not None and r1 != r2:
                    adj[r1].add(r2)
                    adj[r2].add(r1)
                if o == 'V' and w in (sa, sc) and p < sd and p + l > sb:
                    ck(hall[0] - 1e-6 <= p and p + l <= hall[1] + 1e-6,
                       '%s %d階：階段室の横のドア(%s,%s)が上りはじめ側（%s〜%s）にない'
                       % (name, n, w, p, hall[0], hall[1]))
                elif o == 'H' and w == land_wall and p < sc and p + l > sa:
                    ck(False, '%s %d階：踊り場側の壁(%s)にドアがある' % (name, n, w))
            start = {i for i, r in enumerate(rooms) if r[6] == 'stair'}
            if n == 1:
                for f, p, l, k, lab in d.get('openings', []):
                    if k != 'entry':
                        continue
                    m = p + l / 2.0
                    r = {'S': rid(m, .01), 'N': rid(m, ny - .01),
                         'W': rid(.01, m), 'E': rid(nx - .01, m)}[f]
                    if r is not None:
                        start.add(r)
            seen, q = set(start), list(start)
            while q:
                i = q.pop()
                for j in adj[i]:
                    if j not in seen:
                        seen.add(j)
                        q.append(j)
            for i, r in enumerate(rooms):
                ck(i in seen, '%s %d階：%s に階段・入口からドアで行けない' % (name, n, r[0]))


# ---------------------------------------------------------------- 8 本文
def check_furniture():
    """家具・設備：戸の前（開口幅×奥行0.9マス）と出入口の前に置かない、家具どうし重ねない。"""
    import anssheet
    bad = anssheet.audit_all()
    for m in bad:
        ck(False, '家具の置き場所：' + m)
    ck(not bad, '家具の置き場所に問題なし（全6型×3階）')



def check_kaitou_figs():
    """予想問題A〜Fの標準解答例に、要求図書が7つ全部そろっているか。"""
    import io as _io
    import os as _os
    base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')
    need = ('１階平面図兼配置図', '２階平面図', '３階平面図',
            '3階床伏図', '小屋伏図', '南側立面図', '部分詳細図')
    for t in 'ABCDEF':
        p = _os.path.join(base, 'kaitou_%s.html' % t)
        src = _io.open(p, encoding='utf-8').read()
        for nm in need:
            ck(nm in src, '解答例%s に %s がない' % (t, nm))
        for nm in ('ans%s_1f' % t, 'ans%sfuse_floor' % t,
                   'ans%sfuse_roof' % t, 'ans%selev_s' % t):
            if t == 'A':
                continue
            ck(_os.path.exists(_os.path.join(base, 'figures', nm + '.svg')),
               'figures/%s.svg がない' % nm)

def check_elevation():
    """立面図の窓が平面図とずれていないか。

    どちらの立面図も plans.fit_all から開口を拾っていること（手で書いた数字を
    使っていないこと）と、A型の答案の南面の開口が型と同じであること
    （anselev_s.svg を A の解答例の立面図として使っているため）を見る。
    """
    import io as _io
    import os as _os
    here = _os.path.dirname(_os.path.abspath(__file__))
    for nm in ('elevation.py', 'anselev.py'):
        src = _io.open(_os.path.join(here, nm), encoding='utf-8').read()
        ck('fit_all' in src, '%s が平面図から開口を拾っていない' % nm)
    fl = plans.FLOORS
    kata = {n: sorted((p, l, k) for f, p, l, k, _ in
                      plans.fit_all(fl)[n] if f == 'S') for n in (1, 2, 3)}
    A = {i + 1: d for i, d in enumerate(answers.PLANS['A'])}
    f0 = A[1]
    fa = plans.fit_all(A, f0.get('nx', plans.NX), f0.get('ny', plans.NY),
                       f0.get('xlines', plans.XLINES),
                       f0.get('ylines', plans.YLINES))
    for n in (1, 2, 3):
        got = sorted((p, l, k) for f, p, l, k, _ in fa[n] if f == 'S')
        ck(got == kata[n],
           'A型%d階の南面の開口が型とちがう（立面図は型で描いている）%s / %s'
           % (n, got, kata[n]))


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
    counts, common = check_columns()
    check_light()
    one, total = check_area()
    fl1, noki, top = check_height()
    check_stair()
    check_beam()
    check_framing()
    check_stair_access()
    check_furniture()
    check_elevation()
    check_kaitou_figs()
    check_text(0)
    print('柱 1階%d・2階%d・3階%d本（うち3階とも同じ位置 %d本）／'
          '1階%.2f㎡・延べ%.2f㎡／1FL+%d・軒%d・最高%d'
          % (counts[0], counts[1], counts[2], common, one, total,
             fl1, noki, top))
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
