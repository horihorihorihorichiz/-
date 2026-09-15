"""重複なしでカードを引く処理（乱数の引き直し方式。numpy で速い）。"""
import numpy as np


def draw(rng, n_rows, k, dead_mask=None):
    """各行につき k 枚を、dead_mask で禁止された札を避けて重複なく引く。

    dead_mask: (n_rows,) の int64。52 ビットで使用済みの札を表す。
    戻り値: (out (n_rows,k), 更新後の dead_mask)
    """
    mask = np.zeros(n_rows, dtype=np.int64) if dead_mask is None else dead_mask.copy()
    out = np.empty((n_rows, k), dtype=np.int64)
    for j in range(k):
        col = rng.integers(0, 52, n_rows).astype(np.int64)
        bad = ((mask >> col) & 1).astype(bool)
        while bad.any():
            idx = np.where(bad)[0]
            col[idx] = rng.integers(0, 52, idx.size)
            hit = ((mask[idx] >> col[idx]) & 1).astype(bool)
            bad[:] = False
            bad[idx[hit]] = True
        out[:, j] = col
        mask |= (np.int64(1) << col)
    return out, mask


def to_mask(cards):
    """(n_rows,k) のカード配列を 52 ビットのマスクにする。"""
    return np.bitwise_or.reduce(np.int64(1) << np.asarray(cards, dtype=np.int64), axis=1)
