"""ペア系を細かく分けた手の分類と、場札の型の分類。"""
import numpy as np
from evaluator import _STRAIGHT

HAND = [
    'ストレート以上',            # 0
    'セット（手札ペア）',        # 1
    '場札ペア＋手札一致',        # 2
    'ツーペア（手札2枚）',       # 3
    'オーバーペア AA〜QQ',       # 4
    'オーバーペア JJ以下',       # 5
    'トップペア Aキッカー',      # 6
    'トップペア K・Qキッカー',   # 7
    'トップペア J〜9キッカー',   # 8
    'トップペア 8以下キッカー',  # 9
    'ミドルペア',                # 10
    'ボトムペア',                # 11
    'ポケット（場札の間）',      # 12
    'ポケット（場札より下）',    # 13
    'ノーペア＋フラッシュ待ち',  # 14
    'ノーペア＋両側待ち',        # 15
    'ノーペア＋片側待ち',        # 16
    'ノーペア Aハイ',            # 17
    'ノーペア その他',           # 18
]

TEXTURE = [
    'ペアボード',          # 0
    'マーク3枚',           # 1
    'マーク2枚・つながり', # 2
    'マーク2枚・乾いた',   # 3
    'マーク違い・つながり',# 4
    'マーク違い・乾いた',  # 5
]


def board_texture(flop):
    flop = np.asarray(flop, dtype=np.int64)
    n = flop.shape[0]
    r = np.sort(flop >> 2, axis=1)[:, ::-1]
    s = flop & 3
    paired = (r[:, 0] == r[:, 1]) | (r[:, 1] == r[:, 2])
    same = np.array([np.bincount(row, minlength=4).max() for row in s])
    span = r[:, 0] - r[:, 2]
    # A を1として扱った場合の幅も見る（A23 などを拾う）
    span_low = np.where(r[:, 0] == 12, np.maximum(r[:, 1], 0) - r[:, 2], span)
    conn = (np.minimum(span, np.where(r[:, 0] == 12, span_low, span)) <= 4)
    t = np.full(n, 5, dtype=np.int64)
    t = np.where(conn, 4, t)
    t = np.where(same == 2, np.where(conn, 2, 3), t)
    t = np.where(same == 3, 1, t)
    t = np.where(paired, 0, t)
    return t


def hand_type(hole, flop):
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
    max_suit = np.bincount(sflat, minlength=n * 4).reshape(n, 4).max(axis=1)

    hr = ranks[:, :2]
    br = np.sort(ranks[:, 2:], axis=1)[:, ::-1]
    board_paired = (br[:, 0] == br[:, 1]) | (br[:, 1] == br[:, 2])
    pocket = hr[:, 0] == hr[:, 1]
    hi = hr.max(axis=1)
    lo = hr.min(axis=1)

    made_straight = _STRAIGHT[rank_mask] >= 0
    made_flush = max_suit >= 5
    n_trips = (counts == 3).sum(axis=1)
    n_pairs = (counts == 2).sum(axis=1)
    has_quad = (counts == 4).any(axis=1)

    hit = (hr[:, :, None] == br[:, None, :])
    hit_any = hit.any(axis=2)
    n_hit = hit_any.sum(axis=1)
    pos = np.argmax(hit, axis=2)
    first = np.argmax(hit_any, axis=1)
    top_pos = pos[np.arange(n), first]
    kicker = np.where(hr[:, 0] == br[np.arange(n), top_pos], hr[:, 1], hr[:, 0])

    # ドロー
    outs = np.zeros(n, dtype=np.int64)
    for r in range(13):
        outs += (_STRAIGHT[rank_mask | (np.int64(1) << r)] >= 0)
    outs = np.where(made_straight, 0, outs)
    fd = max_suit == 4

    t = np.full(n, 18, dtype=np.int64)
    t = np.where(hi == 12, 17, t)                                  # A ハイ
    t = np.where(outs == 1, 16, t)
    t = np.where(outs >= 2, 15, t)
    t = np.where(fd, 14, t)
    # ペア系
    t = np.where(pocket & (hr[:, 0] < br[:, 2]), 13, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 2]) & (hr[:, 0] < br[:, 0]), 12, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 2) & (~board_paired), 11, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 1) & (~board_paired), 10, t)
    tp = (~pocket) & (n_hit == 1) & (top_pos == 0) & (~board_paired)
    t = np.where(tp & (kicker <= 6), 9, t)
    t = np.where(tp & (kicker >= 7) & (kicker <= 9), 8, t)
    t = np.where(tp & (kicker >= 10) & (kicker <= 11), 7, t)
    t = np.where(tp & (kicker == 12), 6, t)
    op = pocket & (hr[:, 0] > br[:, 0])
    t = np.where(op & (hr[:, 0] <= 9), 5, t)
    t = np.where(op & (hr[:, 0] >= 10), 4, t)
    # 2枚以上絡み
    t = np.where((~pocket) & (n_hit == 2) & (~board_paired), 3, t)
    t = np.where(board_paired & (n_hit >= 1) & (~pocket) & (n_trips >= 1), 2, t)
    t = np.where(board_paired & pocket & (n_trips == 0), 3, t)      # 場ペア＋手札ペア＝2ペア
    t = np.where(pocket & (n_trips >= 1), 1, t)                     # セット
    t = np.where((~pocket) & (n_trips >= 1) & (~board_paired), 1, t)
    t = np.where(has_quad | (n_trips >= 2) | ((n_trips >= 1) & (n_pairs >= 1)), 0, t)
    t = np.where(made_straight | made_flush, 0, t)
    return t
