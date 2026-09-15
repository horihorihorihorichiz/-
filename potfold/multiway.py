"""ハンドの型ごとに、相手が増えたときエクイティがどれだけ残るかを測る。

タイマン勝率だけで判断すると、ナッツフラッシュドローのように
「引けば人数に関係なく勝つ」手を過小評価する恐れがあるため。
"""
import numpy as np
from evaluator import evaluate7
from sampling import draw, to_mask
from classify2 import hand_type, board_texture, HAND

N_SEATS = 8


def run(n_deals=30000, opps=(1, 2, 3, 4), runouts=40, batch=300, seed=61, with_texture=False):
    rng = np.random.default_rng(seed)
    kmax = max(opps)
    T, EQ, TX = [], {k: [] for k in opps}, []
    done = 0
    while done < n_deals:
        b = min(batch, n_deals - done)
        cards, _ = draw(rng, b, 3 + 2 * N_SEATS)
        flop = cards[:, :3]
        hands = cards[:, 3:].reshape(b, N_SEATS, 2)
        T.append(hand_type(hands.reshape(b * N_SEATS, 2), np.repeat(flop, N_SEATS, axis=0)))
        if with_texture:
            TX.append(np.repeat(board_texture(flop), N_SEATS))

        fm = to_mask(flop)
        ro = np.stack([draw(rng, b, 2, fm)[0] for _ in range(runouts)], axis=1)       # (b,S,2)
        op = np.stack([draw(rng, b, 2, fm)[0] for _ in range(kmax)], axis=1)          # (b,K,2)
        ro_m = to_mask(ro.reshape(-1, 2)).reshape(b, runouts)
        op_m = to_mask(op.reshape(-1, 2)).reshape(b, kmax)
        hd_m = to_mask(hands.reshape(-1, 2)).reshape(b, N_SEATS)
        flop_rep = np.repeat(flop[:, None, :], runouts, axis=1)

        opp7 = np.concatenate([
            np.repeat(op[:, None, :, :], runouts, axis=1).reshape(b * runouts * kmax, 2),
            np.repeat(flop_rep.reshape(b * runouts, 3), kmax, axis=0),
            np.repeat(ro.reshape(b * runouts, 2), kmax, axis=0)], axis=1)
        osc = evaluate7(opp7).reshape(b, runouts, kmax)

        hero7 = np.concatenate([
            np.repeat(hands[:, :, None, :], runouts, axis=2).reshape(b * N_SEATS * runouts, 2),
            np.repeat(flop_rep[:, None, :, :], N_SEATS, axis=1).reshape(b * N_SEATS * runouts, 3),
            np.repeat(ro[:, None, :, :], N_SEATS, axis=1).reshape(b * N_SEATS * runouts, 2)], axis=1)
        hsc = evaluate7(hero7).reshape(b, N_SEATS, runouts)

        ok_ro_op = (ro_m[:, :, None] & op_m[:, None, :]) == 0
        ok_h_ro = (hd_m[:, :, None] & ro_m[:, None, :]) == 0
        ok_h_op = (hd_m[:, :, None] & op_m[:, None, :]) == 0
        for k in opps:
            valid = (ok_ro_op[:, None, :, :k].all(axis=3) & ok_h_ro
                     & ok_h_op[:, :, None, :k].all(axis=3))                  # (b,8,S)
            best = osc[:, None, :, :k].max(axis=3)                            # (b,1,S)
            ties = (osc[:, None, :, :k] == best[:, :, :, None]).sum(axis=3)
            h = hsc
            share = np.where(h > best, 1.0, np.where(h == best, 1.0 / (1 + ties), 0.0))
            EQ[k].append(((share * valid).sum(axis=2) / np.maximum(valid.sum(axis=2), 1)).reshape(-1))
        done += b
    res = np.concatenate(T), {k: np.concatenate(v) for k, v in EQ.items()}
    return res + (np.concatenate(TX),) if with_texture else res


if __name__ == '__main__':
    t, eq = run()
    print('%-34s %7s %7s %7s %7s   残り' % ('ハンドの型', '相手1', '相手2', '相手3', '相手4'))
    rows = []
    for i in range(len(HAND)):
        sel = t == i
        if sel.sum() < 400:
            continue
        v = [float(np.median(eq[k][sel])) for k in (1, 2, 3, 4)]
        rows.append((i, v, int(sel.sum())))
    for i, v, n in sorted(rows, key=lambda r: -r[1][0]):
        print('%-34s %6.1f%% %6.1f%% %6.1f%% %6.1f%%   %4.0f%%'
              % (HAND[i], 100*v[0], 100*v[1], 100*v[2], 100*v[3], 100*v[3]/v[0]))
