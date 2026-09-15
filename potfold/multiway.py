"""ハンドの型ごとに、相手が増えたときエクイティがどれだけ残るかを測る。

相手の手札は1組だけだと「引き運」を測ることになってしまうので、
1回の配札につき相手候補を12組引き、k人ずつの組に分けて平均する。
"""
import numpy as np
from evaluator import evaluate7
from sampling import draw, to_mask
from classify2 import hand_type, board_texture, HAND

N_SEATS = 8
OPPN = 12          # 相手候補の数。k人ずつの組に分けて使う


def run(n_deals=30000, opps=(1, 2, 3, 4), runouts=40, batch=200, seed=61, with_texture=False):
    rng = np.random.default_rng(seed)
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
        ro = np.stack([draw(rng, b, 2, fm)[0] for _ in range(runouts)], axis=1)
        op = np.stack([draw(rng, b, 2, fm)[0] for _ in range(OPPN)], axis=1)
        ro_m = to_mask(ro.reshape(-1, 2)).reshape(b, runouts)
        op_m = to_mask(op.reshape(-1, 2)).reshape(b, OPPN)
        hd_m = to_mask(hands.reshape(-1, 2)).reshape(b, N_SEATS)
        flop_rep = np.repeat(flop[:, None, :], runouts, axis=1)

        opp7 = np.concatenate([
            np.repeat(op[:, None, :, :], runouts, axis=1).reshape(b * runouts * OPPN, 2),
            np.repeat(flop_rep.reshape(b * runouts, 3), OPPN, axis=0),
            np.repeat(ro.reshape(b * runouts, 2), OPPN, axis=0)], axis=1)
        osc = evaluate7(opp7).reshape(b, runouts, OPPN)

        hero7 = np.concatenate([
            np.repeat(hands[:, :, None, :], runouts, axis=2).reshape(b * N_SEATS * runouts, 2),
            np.repeat(flop_rep[:, None, :, :], N_SEATS, axis=1).reshape(b * N_SEATS * runouts, 3),
            np.repeat(ro[:, None, :, :], N_SEATS, axis=1).reshape(b * N_SEATS * runouts, 2)], axis=1)
        hsc = evaluate7(hero7).reshape(b, N_SEATS, runouts)

        ok_h_ro = (hd_m[:, :, None] & ro_m[:, None, :]) == 0                  # (b,8,S)
        for k in opps:
            groups = OPPN // k
            num = np.zeros((b, N_SEATS, runouts))
            den = np.zeros((b, N_SEATS, runouts))
            for g in range(groups):
                sl = slice(g * k, (g + 1) * k)
                sub = osc[:, :, sl]                                            # (b,S,k)
                ok_ro = (ro_m[:, :, None] & op_m[:, None, sl]).sum(axis=2) == 0   # (b,S)
                ok_h = (hd_m[:, :, None] & op_m[:, None, sl]).sum(axis=2) == 0    # (b,8)
                best = sub.max(axis=2)                                         # (b,S)
                ties = (sub == best[:, :, None]).sum(axis=2)
                h = hsc
                share = np.where(h > best[:, None, :], 1.0,
                                 np.where(h == best[:, None, :], 1.0 / (1 + ties[:, None, :]), 0.0))
                valid = ok_h_ro & ok_ro[:, None, :] & ok_h[:, :, None]
                num += share * valid
                den += valid
            EQ[k].append((num.sum(axis=2) / np.maximum(den.sum(axis=2), 1)).reshape(-1))
        done += b
    res = np.concatenate(T), {k: np.concatenate(v) for k, v in EQ.items()}
    return res + (np.concatenate(TX),) if with_texture else res


if __name__ == '__main__':
    t, eq = run(n_deals=12000)
    print('%-34s %7s %7s %7s %7s' % ('ハンドの型', '相手1', '相手2', '相手3', '相手4'))
    for i in range(len(HAND)):
        sel = t == i
        if sel.sum() < 300:
            continue
        v = [np.percentile(eq[k][sel], [25, 50, 75]) for k in (1, 2, 3, 4)]
        print('%-34s %s' % (HAND[i], ' '.join('%3.0f(%2.0f〜%2.0f)' % (100*x[1], 100*x[0], 100*x[2]) for x in v)))
