"""実戦用の判定。自分の2枚と場札3枚から「続けるか降りるか」を答える。

例:
  python3 check.py --hand AsKd --flop Ah7c2d --players 6 --seat 3 --continued 1
"""
import argparse
import json
import numpy as np
from equity import equity
from classify import classify, MADE, DRAW
from cards import parse_cards


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--hand', required=True, help='自分の2枚 例: AsKd')
    p.add_argument('--flop', required=True, help='場札3枚 例: Ah7c2d')
    p.add_argument('--players', type=int, required=True, help='卓の人数 (2〜8)')
    p.add_argument('--seat', type=int, required=True, help='自分は何番目に行動するか (1が最初)')
    p.add_argument('--continued', type=int, default=0, help='自分より前で続けた人数')
    p.add_argument('--trials', type=int, default=60000)
    a = p.parse_args()

    if not 2 <= a.players <= 8:
        raise SystemExit('人数は2〜8で指定してください')
    if not 1 <= a.seat <= a.players:
        raise SystemExit('順番は1〜%d で指定してください' % a.players)
    if not 0 <= a.continued <= a.seat - 1:
        raise SystemExit('前で続けた人数は 0〜%d です' % (a.seat - 1))

    rng = np.random.default_rng(0)
    e = equity(a.hand, a.flop, 1, a.trials, rng)

    hole = np.array([parse_cards(a.hand)])
    flop = np.array([parse_cards(a.flop)])
    m, d = classify(hole, flop)

    th = json.load(open('thresholds.json'))[str(a.players)]['thresholds']
    bar = th[a.seat - 1][a.continued]

    print('手札 %s / 場札 %s' % (a.hand, a.flop))
    print('  役      : %s / %s' % (MADE[int(m[0])], DRAW[int(d[0])]))
    print('  勝率    : %.1f%% (相手1人に対して)' % (100 * e))
    print('  必要勝率: %.1f%% (%d人卓・%d番目・前で%d人継続)'
          % (100 * bar, a.players, a.seat, a.continued))
    print('  判定    : %s' % ('続ける' if e >= bar else '降りる'))
    print('  差      : %+.1f ポイント' % (100 * (e - bar)))

    print('\n  参考: 続けた人数ごとの損益分岐（相手が k 人続けたときに必要な勝率）')
    for k in range(0, min(4, a.players - 1) + 1):
        eq_k = equity(a.hand, a.flop, k, max(a.trials // 3, 8000), rng) if k else 1.0
        print('    相手 %d 人 → 必要 %.1f%% / 実際 %.1f%%'
              % (k, 100 / (k + 2), 100 * eq_k))


if __name__ == '__main__':
    main()
