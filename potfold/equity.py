"""場札3枚が見えている状態での勝率を乱数試行で求める。"""
import numpy as np
from evaluator import evaluate7
from cards import parse_cards, cards_str

DECK = np.arange(52)


def _draw(rng, dead, trials, need):
    """dead を除いた山札から、各試行 need 枚を重複なく引く。戻り値 (trials, need)。"""
    remain = np.setdiff1d(DECK, np.asarray(dead, dtype=np.int64))
    keys = rng.random((trials, remain.size))
    idx = np.argpartition(keys, need - 1, axis=1)[:, :need]
    return remain[idx]


def equity(hero, board, n_opp, trials=20000, rng=None):
    """自分の2枚と場札3枚を与え、相手 n_opp 人（手札はランダム）に対する勝率を返す。

    引き分けは人数で割った取り分として数える。
    """
    rng = rng or np.random.default_rng()
    hero = np.asarray(parse_cards(hero) if isinstance(hero, str) else hero, dtype=np.int64)
    board = np.asarray(parse_cards(board) if isinstance(board, str) else board, dtype=np.int64)
    assert hero.size == 2 and board.size == 3

    need = 2 + 2 * n_opp                      # ターン・リバー + 相手の手札
    drawn = _draw(rng, np.concatenate([hero, board]), trials, need)
    runout = drawn[:, :2]                     # ターン, リバー
    full_board = np.concatenate(
        [np.repeat(board[None, :], trials, axis=0), runout], axis=1)   # (T,5)

    hero7 = np.concatenate([np.repeat(hero[None, :], trials, axis=0), full_board], axis=1)
    hs = evaluate7(hero7)

    opp = np.stack([
        evaluate7(np.concatenate([drawn[:, 2 + 2 * j: 4 + 2 * j], full_board], axis=1))
        for j in range(n_opp)], axis=1)               # (T, n_opp)
    best = opp.max(axis=1)
    ties = ((opp == best[:, None]) & (best == hs)[:, None]).sum(axis=1)

    win = hs > best
    tie = hs == best
    share = np.where(win, 1.0, np.where(tie, 1.0 / (1 + ties), 0.0))
    return float(share.mean())


if __name__ == '__main__':
    import sys
    rng = np.random.default_rng(1)
    hero, board = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    print('手札 %s / 場札 %s / 相手 %d 人 → 勝率 %.1f%%'
          % (hero, board, n, 100 * equity(hero, board, n, 50000, rng)))
