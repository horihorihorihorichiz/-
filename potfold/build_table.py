"""手の型 × 場札の型ごとの勝率を出し、早見表（何人まで入っていてもコールできるか）を作る。"""
import json
import numpy as np
from sampling import draw
from classify2 import hand_type, board_texture, HAND, TEXTURE
from gen_data import _equity_batch

N_SEATS = 8
SYM_COLS = [7, 5, 3, 1, 0]          # 自分の後ろに残っている人数


def collect(n_deals=150000, seed=21, batch=400):
    rng = np.random.default_rng(seed)
    H, F, E = [], [], []
    done = 0
    while done < n_deals:
        b = min(batch, n_deals - done)
        cards, _ = draw(rng, b, 5 + 2 * N_SEATS)
        flop = cards[:, :3]
        hands = cards[:, 5:].reshape(b, N_SEATS, 2)
        eq = _equity_batch(rng, flop, hands)
        H.append(hands.reshape(b * N_SEATS, 2))
        F.append(np.repeat(flop, N_SEATS, axis=0))
        E.append(eq.reshape(b * N_SEATS))
        done += b
        if done % 8000 == 0:
            print('  %d / %d' % (done, n_deals), flush=True)
    return np.concatenate(H), np.concatenate(F), np.concatenate(E)


def verdict(med, grid_row):
    """その手が、前に何人入っていてもコールできるかを記号にする。"""
    avail = [c for c in range(len(grid_row)) if grid_row[c] is not None]
    cmax = min(4, max(avail))
    best = -1
    for c in range(cmax + 1):
        if grid_row[c] is None or med < grid_row[c]:
            break
        best = c
    if best < 0:
        return '×'
    if cmax == 0:
        return '○'          # 自分が最初 → 前に入る人がいないので「入る／降りる」だけ
    if best >= cmax:
        return '全'
    return str(best)


if __name__ == '__main__':
    hole, flop, eq = collect()
    ht = hand_type(hole, flop)
    tx = board_texture(flop)
    grid = json.load(open('grid.json'))['grid']

    out = {'hands': HAND, 'textures': TEXTURE, 'cols': SYM_COLS, 'rows': {}}
    print('\n全体（場札の型をまとめた場合）')
    print('%-24s %6s %7s   %s' % ('手の型', '出現率', '勝率', '　'.join('後ろ%d' % c for c in SYM_COLS)))
    for h in range(len(HAND)):
        sel = ht == h
        if sel.sum() < 300:
            continue
        med = float(np.median(eq[sel]))
        syms = [verdict(med, grid[c]) for c in SYM_COLS]
        print('%-24s %5.2f%% %6.1f%%   %s' % (HAND[h], 100 * sel.mean(), 100 * med, '　　'.join(syms)))
        out['rows']['all-%d' % h] = {'n': int(sel.sum()), 'eq': round(med, 4), 'sym': syms}

    for t in range(len(TEXTURE)):
        for h in range(len(HAND)):
            sel = (ht == h) & (tx == t)
            if sel.sum() < 400:
                continue
            med = float(np.median(eq[sel]))
            out['rows']['%d-%d' % (t, h)] = {'n': int(sel.sum()), 'eq': round(med, 4),
                                             'sym': [verdict(med, grid[c]) for c in SYM_COLS]}
    json.dump(out, open('handtable.json', 'w'), ensure_ascii=False, indent=1)
    print('\n保存: handtable.json')
