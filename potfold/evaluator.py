"""7枚から最強の5枚役を評価する（numpyで一括処理）。

カード表現: 0-51 の整数。 rank = card >> 2 (0=2, 12=A), suit = card & 3。
戻り値: 大きいほど強い int64 のスコア。同じ値なら引き分け。

13ビットのランク集合を添字にした表引きで、ソートを使わずに速く求める。
"""
import numpy as np

# 役の種類（大きいほど強い）
HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)

_P = [13 ** 4, 13 ** 3, 13 ** 2, 13, 1]      # キッカーの桁の重み
_CAT = np.int64(13 ** 5)
_BITS = (np.int64(1) << np.arange(13, dtype=np.int64))


def _build_tables():
    size = 1 << 13
    top1 = np.full(size, 0, dtype=np.int64)
    # top_k_at[j][mask] = 上位k個のランクを桁 j, j+1, ... に置いたスコア
    topk = {k: np.zeros((5, size), dtype=np.int64) for k in (1, 2, 3, 5)}
    straight = np.full(size, -1, dtype=np.int64)

    pats = []
    for high in range(12, 3, -1):            # A(12) から 6(4) まで
        m = 0
        for i in range(5):
            m |= 1 << (high - i)
        pats.append((m, high))
    pats.append(((1 << 12) | 0b1111, 3))     # A-2-3-4-5（5ハイ）

    for mask in range(size):
        rs = [r for r in range(12, -1, -1) if mask >> r & 1]
        if rs:
            top1[mask] = rs[0]
        for k in (1, 2, 3, 5):
            take = rs[:k]
            for start in range(5):
                if start + len(take) > 5:
                    continue
                topk[k][start, mask] = sum(r * _P[start + i] for i, r in enumerate(take))
        for m, high in pats:
            if mask & m == m:
                straight[mask] = high
                break
    return top1, topk, straight


_TOP1, _TOPK, _STRAIGHT = _build_tables()


CHUNK = 50_000   # キャッシュに収まる大きさに切って処理すると数倍速い


def evaluate7(cards):
    """cards: (N,7) の int 配列。戻り値: (N,) の int64 スコア。"""
    cards = np.asarray(cards, dtype=np.int64)
    if cards.shape[0] > CHUNK:
        return np.concatenate([_evaluate7(cards[i:i + CHUNK])
                               for i in range(0, cards.shape[0], CHUNK)])
    return _evaluate7(cards)


def _evaluate7(cards):
    n = cards.shape[0]
    ranks = cards >> 2
    suits = cards & 3

    # --- ランクごとの枚数 → 4種類のビット列 ---
    flat = (np.arange(n, dtype=np.int64)[:, None] * 13 + ranks).ravel()
    counts = np.bincount(flat, minlength=n * 13).reshape(n, 13)
    rank_mask = (counts > 0) @ _BITS
    pair_mask = (counts == 2) @ _BITS
    trip_mask = (counts == 3) @ _BITS
    quad_mask = (counts == 4) @ _BITS

    n_pairs = (counts == 2).sum(axis=1)
    n_trips = (counts == 3).sum(axis=1)
    has_quad = quad_mask > 0

    # --- 役の種類を決める ---
    st_high = _STRAIGHT[rank_mask]

    sflat = (np.arange(n, dtype=np.int64)[:, None] * 4 + suits).ravel()
    scounts = np.bincount(sflat, minlength=n * 4).reshape(n, 4)
    has_flush = scounts.max(axis=1) >= 5

    flush_mask = np.zeros(n, dtype=np.int64)
    sf_high = np.full(n, -1, dtype=np.int64)
    if has_flush.any():
        rows = np.where(has_flush)[0]
        fs = scounts[rows].argmax(axis=1)
        bit = np.int64(1) << ranks[rows]
        fm = np.bitwise_or.reduce(np.where(suits[rows] == fs[:, None], bit, 0), axis=1)
        flush_mask[rows] = fm
        sf_high[rows] = _STRAIGHT[fm]

    cat = np.full(n, HIGH, dtype=np.int64)
    cat = np.where(n_pairs >= 1, PAIR, cat)
    cat = np.where(n_pairs >= 2, TWO_PAIR, cat)
    cat = np.where(n_trips >= 1, TRIPS, cat)
    cat = np.where((n_trips >= 2) | ((n_trips >= 1) & (n_pairs >= 1)), FULL_HOUSE, cat)
    cat = np.where(has_quad, QUADS, cat)
    cat = np.where((st_high >= 0) & (cat < STRAIGHT), STRAIGHT, cat)
    cat = np.where(has_flush & (cat < FLUSH), FLUSH, cat)
    cat = np.where(sf_high >= 0, STRAIGHT_FLUSH, cat)

    # --- キッカーを役ごとに組み立てる ---
    score = np.zeros(n, dtype=np.int64)

    # ハイカード / フラッシュ
    score = np.where(cat == HIGH, _TOPK[5][0][rank_mask], score)
    score = np.where(cat == FLUSH, _TOPK[5][0][flush_mask], score)

    # ストレート系
    score = np.where(cat == STRAIGHT, st_high * _P[0], score)
    score = np.where(cat == STRAIGHT_FLUSH, sf_high * _P[0], score)

    # ワンペア
    p1 = _TOP1[pair_mask]
    rest1 = rank_mask & ~(np.int64(1) << p1)
    score = np.where(cat == PAIR, p1 * _P[0] + _TOPK[3][1][rest1], score)

    # ツーペア
    pm2 = pair_mask & ~(np.int64(1) << p1)
    p2 = _TOP1[pm2]
    rest2 = rest1 & ~(np.int64(1) << p2)
    score = np.where(cat == TWO_PAIR, p1 * _P[0] + p2 * _P[1] + _TOPK[1][2][rest2], score)

    # スリーカード
    t1 = _TOP1[trip_mask]
    rest3 = rank_mask & ~(np.int64(1) << t1)
    score = np.where(cat == TRIPS, t1 * _P[0] + _TOPK[2][1][rest3], score)

    # フルハウス（スリーカードが2組ならもう一方をペア扱い）
    fh_pairs = pair_mask | (trip_mask & ~(np.int64(1) << t1))
    score = np.where(cat == FULL_HOUSE, t1 * _P[0] + _TOP1[fh_pairs] * _P[1], score)

    # フォーカード
    q1 = _TOP1[quad_mask]
    restq = rank_mask & ~(np.int64(1) << q1)
    score = np.where(cat == QUADS, q1 * _P[0] + _TOP1[restq] * _P[1], score)

    return cat * _CAT + score
