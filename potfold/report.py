"""2〜8人卓の継続基準を求めて表にする。"""
import json
import numpy as np
from solve import solve, evaluate_strategy, cell_counts

d = np.load('deals.npz')
eq, sc = d['equity'].astype(np.float64), d['score']
print('配札数: %d' % eq.shape[0])

result = {}
for n in range(2, 9):
    th = solve(eq, sc, n, rounds=16, damping=0.45)
    stats = evaluate_strategy(eq, sc, n, th)
    counts = cell_counts(eq, sc, n, th)
    result[n] = {'thresholds': [t.tolist() for t in th],
                 'stats': stats,
                 'counts': [c.tolist() for c in counts]}
    print('\n=== %d人卓 ===' % n)
    print('  席   前で続けた人数 0,1,2,... ごとの「続ける最低勝率」        継続率   1ハンド損得')
    for i, t in enumerate(th):
        cells = ' '.join('%5.1f%%' % (100 * v) for v in t)
        cnt = ' '.join('%6d' % c for c in counts[i])
        print('  %d番目 %-46s  %5.1f%%   %+.4f' % (i + 1, cells, 100 * stats[i][0], stats[i][1]))
        print('        %-46s  (場面の出現数)' % cnt)

with open('thresholds.json', 'w') as f:
    json.dump({str(k): v for k, v in result.items()}, f, ensure_ascii=False, indent=1)
print('\n保存: thresholds.json')
