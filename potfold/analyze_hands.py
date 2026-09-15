"""役の型ごとの平均勝率を出し、「必要勝率」を実際の手に翻訳する表を作る。"""
import numpy as np
from gen_data import generate, N_SEATS
from sampling import draw as sdraw
from classify import classify, MADE, DRAW
from evaluator import evaluate7

# gen_data と同じ手順で、カードも保存しながら生成する
import gen_data


def run(n_deals=30000, seed=11):
    rng = np.random.default_rng(seed)
    holes, flops, eqs = [], [], []
    batch = 400
    done = 0
    while done < n_deals:
        b = min(batch, n_deals - done)
        cards, _ = sdraw(rng, b, 5 + 2 * N_SEATS)
        flop = cards[:, :3]
        hands = cards[:, 5:].reshape(b, N_SEATS, 2)
        eq = gen_data._equity_batch(rng, flop, hands)
        holes.append(hands.reshape(b * N_SEATS, 2))
        flops.append(np.repeat(flop, N_SEATS, axis=0))
        eqs.append(eq.reshape(b * N_SEATS))
        done += b
    return np.concatenate(holes), np.concatenate(flops), np.concatenate(eqs)


if __name__ == '__main__':
    hole, flop, eq = run()
    made, dr = classify(hole, flop)
    print('手の総数: %d\n' % eq.size)
    print('%-22s %-14s %8s %10s' % ('役', 'ドロー', '出現率', '平均勝率'))
    rows = []
    for m in range(9):
        for d in range(5):
            sel = (made == m) & (dr == d)
            if sel.sum() < 200:
                continue
            rows.append((sel.mean(), MADE[m], DRAW[d], eq[sel].mean(), eq[sel].std()))
    for f, m, d, e, s in sorted(rows, key=lambda r: -r[3]):
        print('%-22s %-14s %7.2f%% %9.1f%%' % (m, d, 100 * f, 100 * e))
