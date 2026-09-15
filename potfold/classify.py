"""場札3枚の時点で、自分の手がどの型かを分類する（一括処理）。"""
import numpy as np
from evaluator import _STRAIGHT

MADE = ['ストレート以上', 'スリーカード', 'ツーペア', 'オーバーペア',
        'トップペア', 'ミドルペア', 'ボトムペア', 'ポケット(場札より下)', 'ノーペア']
DRAW = ['ドローなし', 'ガットショット', 'オープンエンド', 'フラッシュドロー', '複合ドロー']


def classify(hole, flop):
    """hole (N,2), flop (N,3) → (made 番号, draw 番号)"""
    hole = np.asarray(hole, dtype=np.int64)
    flop = np.asarray(flop, dtype=np.int64)
    n = hole.shape[0]
    five = np.concatenate([hole, flop], axis=1)
    ranks = five >> 2
    suits = five & 3

    flat = (np.arange(n, dtype=np.int64)[:, None] * 13 + ranks).ravel()
    counts = np.bincount(flat, minlength=n * 13).reshape(n, 13)
    rank_mask = np.bitwise_or.reduce(np.int64(1) << ranks, axis=1)

    sflat = (np.arange(n, dtype=np.int64)[:, None] * 4 + suits).ravel()
    scounts = np.bincount(sflat, minlength=n * 4).reshape(n, 4)
    max_suit = scounts.max(axis=1)

    hr = ranks[:, :2]
    br = np.sort(ranks[:, 2:], axis=1)[:, ::-1]        # 場札を高い順に
    is_pocket = hr[:, 0] == hr[:, 1]
    made_straight = _STRAIGHT[rank_mask] >= 0
    made_flush = max_suit >= 5

    n_pairs = (counts == 2).sum(axis=1)
    n_trips = (counts == 3).sum(axis=1)
    has_quad = (counts == 4).any(axis=1)

    # 自分の札が場札と合っているか
    hit = (hr[:, :, None] == br[:, None, :])            # (n,2,3)
    hit_any = hit.any(axis=2)
    n_hit = hit_any.sum(axis=1)

    made = np.full(n, 8, dtype=np.int64)                # 既定はノーペア
    # ポケットペア
    made = np.where(is_pocket & (hr[:, 0] > br[:, 0]), 3, made)     # オーバーペア
    made = np.where(is_pocket & (hr[:, 0] < br[:, 0]), 7, made)     # 場札より下のポケット
    # 場札と合った
    pos = np.argmax(hit, axis=2)                        # 合った場札の位置(0=最上位)
    first = np.argmax(hit_any, axis=1)
    top_pos = pos[np.arange(n), first]
    made = np.where((~is_pocket) & (n_hit == 1) & (top_pos == 0), 4, made)
    made = np.where((~is_pocket) & (n_hit == 1) & (top_pos == 1), 5, made)
    made = np.where((~is_pocket) & (n_hit == 1) & (top_pos == 2), 6, made)
    made = np.where((~is_pocket) & (n_hit == 2), 2, made)           # ツーペア
    # 場札がペアでこちらもペア
    made = np.where(n_pairs >= 2, 2, made)
    made = np.where(n_trips >= 1, 1, made)
    made = np.where((n_trips >= 1) & (n_pairs >= 1), 0, made)       # フルハウス
    made = np.where(n_trips >= 2, 0, made)
    made = np.where(has_quad, 0, made)
    made = np.where(made_straight | made_flush, 0, made)

    # ドロー
    fd = (max_suit == 4)
    outs = np.zeros(n, dtype=np.int64)
    for r in range(13):
        add = rank_mask | (np.int64(1) << r)
        outs += (_STRAIGHT[add] >= 0) & (~made_straight)
    sd = np.where(outs >= 2, 2, np.where(outs == 1, 1, 0))
    draw = np.where(fd & (sd > 0), 4, np.where(fd, 3, sd))
    draw = np.where(made_straight | made_flush, 0, draw)
    return made, draw
