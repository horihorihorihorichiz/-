"""ハンドの型 × ボードの型ごとに、相手人数別のエクイティを作る。

タイマン勝率だけで並べると、ナッツフラッシュドローのように
「引けば人数に関係なく勝つ」手を大きく取りこぼすため。
あわせて、母集団での「タイマン勝率 → k人相手の勝率」の対応表も作る。
必要エクイティ（タイマン単位で求めてある）を k 人相手の単位に直すのに使う。
"""
import json
import numpy as np
from multiway import run
from classify2 import hand_type, board_texture, HAND, TEXTURE

KS = (1, 2, 3, 4)
NB = 24                      # 母集団の対応表の刻み


if __name__ == '__main__':
    t, eq, tx = run(n_deals=150000, opps=KS, runouts=40, batch=300, seed=91, with_texture=True)
    out = {'hands': HAND, 'textures': TEXTURE, 'ks': list(KS), 'rows': {}}

    def stats(sel):
        d = {}
        for k in KS:
            v = eq[k][sel]
            d[str(k)] = [round(float(np.median(v)), 4),
                         round(float(np.percentile(v, 25)), 4),
                         round(float(np.percentile(v, 75)), 4)]
        d['n'] = int(sel.sum())
        return d

    for h in range(len(HAND)):
        sel = t == h
        if sel.sum() >= 400:
            d = stats(sel); d['f'] = round(float(sel.mean()), 5)
            out['rows']['all-%d' % h] = d
    for x in range(len(TEXTURE)):
        base = tx == x
        for h in range(len(HAND)):
            sel = base & (t == h)
            if sel.sum() >= 400:
                d = stats(sel); d['f'] = round(float(sel.sum()) / max(1, int(base.sum())), 5)
                out['rows']['%d-%d' % (x, h)] = d
    out['texShare'] = [round(float((tx == x).mean()), 5) for x in range(len(TEXTURE))]

    # 母集団の対応表：タイマン勝率の帯ごとに、k人相手での中央値
    e1 = eq[1]
    edges = np.linspace(0, 1, NB + 1)
    curve = {str(k): [] for k in KS}
    centers = []
    for i in range(NB):
        m = (e1 >= edges[i]) & (e1 < edges[i + 1])
        if m.sum() < 300:
            continue
        centers.append(round(float(e1[m].mean()), 4))
        for k in KS:
            curve[str(k)].append(round(float(np.median(eq[k][m])), 4))
    out['curveX'] = centers
    out['curve'] = curve
    json.dump(out, open('multiway.json', 'w'), ensure_ascii=False)
    print('保存: multiway.json  行 %d' % len(out['rows']))
    print('母集団の対応表（タイマン → 相手2/3/4人）')
    for i, c in enumerate(centers):
        print('  %.0f%% → %.0f%% / %.0f%% / %.0f%%'
              % (100*c, 100*curve['2'][i], 100*curve['3'][i], 100*curve['4'][i]))
