"""学習用データの生成。

1回の配札ごとに
  ・場札3枚、ターン、リバー、8人分の手札
  ・各手の「場札3枚時点での、相手1人に対する勝率」（以下タイマン勝率）
  ・実際の出来上がり（5枚確定後）の役の強さ
を求めて保存する。

タイマン勝率は、同じ配札の中でターン/リバー候補と相手手札候補を使い回すことで
評価回数を大きく減らしている。
"""
import time
import numpy as np
from evaluator import evaluate7
from sampling import draw, to_mask

N_SEATS = 8


def _equity_batch(rng, flop, hands, runouts=80, opps=12):
    """場札3枚に対し、各手の「相手1人に対する勝率」を推定する。 (b, 人数) を返す。

    同じ配札の中でターン/リバー候補と相手手札候補を使い回すので、
    1手あたり実質 800〜1000 通り近く試しても評価回数が少なくて済む。
    """
    b, seats = hands.shape[0], hands.shape[1]
    flop_mask = to_mask(flop)
    ro = np.stack([draw(rng, b, 2, flop_mask)[0] for _ in range(runouts)], axis=1)
    op = np.stack([draw(rng, b, 2, flop_mask)[0] for _ in range(opps)], axis=1)
    ro_mask = to_mask(ro.reshape(b * runouts, 2)).reshape(b, runouts)
    op_mask = to_mask(op.reshape(b * opps, 2)).reshape(b, opps)
    hd_mask = to_mask(hands.reshape(b * seats, 2)).reshape(b, seats)

    flop_rep = np.repeat(flop[:, None, :], runouts, axis=1)

    opp7 = np.concatenate([
        np.repeat(op[:, None, :, :], runouts, axis=1).reshape(b * runouts * opps, 2),
        np.repeat(flop_rep.reshape(b * runouts, 3), opps, axis=0),
        np.repeat(ro.reshape(b * runouts, 2), opps, axis=0)], axis=1)
    opp_sc = evaluate7(opp7).reshape(b, runouts, opps)

    hero7 = np.concatenate([
        np.repeat(hands[:, :, None, :], runouts, axis=2).reshape(b * seats * runouts, 2),
        np.repeat(flop_rep[:, None, :, :], seats, axis=1).reshape(b * seats * runouts, 3),
        np.repeat(ro[:, None, :, :], seats, axis=1).reshape(b * seats * runouts, 2),
    ], axis=1)
    hero_sc = evaluate7(hero7).reshape(b, seats, runouts)

    # 札のかぶりを除く
    ok_ro_op = (ro_mask[:, :, None] & op_mask[:, None, :]) == 0
    ok_h_ro = (hd_mask[:, :, None] & ro_mask[:, None, :]) == 0
    ok_h_op = (hd_mask[:, :, None] & op_mask[:, None, :]) == 0
    valid = (ok_ro_op[:, None, :, :] & ok_h_ro[:, :, :, None] & ok_h_op[:, :, None, :])

    h = hero_sc[:, :, :, None]
    o = opp_sc[:, None, :, :]
    share = np.where(h > o, 1.0, np.where(h == o, 0.5, 0.0))
    return (share * valid).sum(axis=(2, 3)) / valid.sum(axis=(2, 3))


def generate(n_deals, runouts=80, opps=12, batch=400, seed=0, verbose=True):
    rng = np.random.default_rng(seed)
    eq_all, sc_all = [], []
    done = 0
    t0 = time.time()
    while done < n_deals:
        b = min(batch, n_deals - done)

        # --- 配札 ---
        cards, _ = draw(rng, b, 5 + 2 * N_SEATS)
        flop = cards[:, :3]
        board5 = cards[:, :5]                      # 場札3 + ターン + リバー
        hands = cards[:, 5:].reshape(b, N_SEATS, 2)

        # 実際の出来上がりの強さ
        seven = np.concatenate(
            [hands.reshape(b * N_SEATS, 2),
             np.repeat(board5, N_SEATS, axis=0)], axis=1)
        sc = evaluate7(seven).reshape(b, N_SEATS)

        eq = _equity_batch(rng, flop, hands, runouts, opps)

        eq_all.append(eq.astype(np.float32))
        sc_all.append(sc)
        done += b
        if verbose and (done % (batch * 20) == 0 or done == n_deals):
            el = time.time() - t0
            print('  %d / %d 配札  (%.0f 秒, 残り約 %.0f 秒)'
                  % (done, n_deals, el, el / done * (n_deals - done)), flush=True)

    return np.concatenate(eq_all), np.concatenate(sc_all)


if __name__ == '__main__':
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    out = sys.argv[2] if len(sys.argv) > 2 else 'deals.npz'
    eq, sc = generate(n)
    np.savez_compressed(out, equity=eq, score=sc)
    print('保存:', out, eq.shape, sc.shape)
