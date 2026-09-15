"""表の矛盾を洗い出す検査。

1. 並び順の逆転  : 強いはずの行が、下の行よりエクイティが低い
2. ばらつきの大きい行 : 中央値だけ見ると判断を誤る行（四分位範囲が広い）
3. 判定が割れる場面 : 必要エクイティが行の四分位範囲の内側に入る（手によって答えが変わる）
"""
import json
import numpy as np
from classify2 import HAND, TEXTURE

WIDE = 0.15          # 四分位範囲がこれ以上なら「中央値では語れない」


def load():
    return json.load(open('handtable.json'))['rows'], json.load(open('fields.json'))


def inversions(rows, key):
    """表示順（強い順）に対して、エクイティが逆転している隣り合う行を拾う。"""
    out = []
    prev = None
    for i in range(len(HAND)):
        r = rows.get('%s-%d' % (key, i))
        if not r:
            continue
        if prev is not None and r['eq'] > prev[1]['eq'] + 0.005:
            out.append((prev[0], prev[1]['eq'], i, r['eq']))
        prev = (i, r)
    return out


def wide_rows(rows, key):
    out = []
    for i in range(len(HAND)):
        r = rows.get('%s-%d' % (key, i))
        if not r or 'q1' not in r:
            continue
        w = r['q3'] - r['q1']
        if w >= WIDE:
            out.append((i, r['q1'], r['eq'], r['q3'], w))
    return out


if __name__ == '__main__':
    rows, fields = load()
    keys = [('all', 'まとめて')] + [(str(i), TEXTURE[i]) for i in range(len(TEXTURE))]

    print('■ 並び順の逆転（下の行のほうが強い）')
    total = 0
    for k, name in keys:
        inv = inversions(rows, k)
        total += len(inv)
        if inv:
            print(' %s' % name)
            for a, ea, b, eb in inv:
                print('   %-28s %.0f%%  ＜  %-28s %.0f%%' % (HAND[a], 100*ea, HAND[b], 100*eb))
    if not total:
        print('   なし')

    print('\n■ 中央値では語れない行（四分位範囲 %d ポイント以上）' % (100*WIDE))
    for k, name in keys:
        w = wide_rows(rows, k)
        if w:
            print(' %s' % name)
            for i, q1, med, q3, width in w:
                print('   %-28s %.0f〜%.0f%%（中央 %.0f%%、幅 %.0f）'
                      % (HAND[i], 100*q1, 100*q3, 100*med, 100*width))

    print('\n■ 判定が割れる場面（BTN が CO のポットを受ける・標準の卓）')
    thr = fields['標準']['grid'][1][0]
    print('   必要エクイティ %.0f%%' % (100*thr))
    for i in range(len(HAND)):
        r = rows.get('all-%d' % i)
        if not r or 'q1' not in r:
            continue
        if r['q1'] < thr < r['q3']:
            print('   %-28s %.0f〜%.0f%% → 手によってコールとフォールドに分かれる'
                  % (HAND[i], 100*r['q1'], 100*r['q3']))
