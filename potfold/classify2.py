"""ハンドの種類とボードテクスチャの分類（ペアボードにも対応）。"""
import numpy as np
from evaluator import _STRAIGHT

HAND = [
    'ストレート以上',              # 0  フラッシュ・フルハウス・クアッズ含む
    'セット',                      # 1  ポケットペア＋ボードに1枚
    'トリップス',                  # 2  ボードのペア＋ホールカード1枚
    'ツーペア',                    # 3  ホールカード2枚がボードに絡む
    'オーバーペア QQ以上',         # 4
    'オーバーペア JJ以下',         # 5
    'トップペア Aキッカー',        # 6
    'トップペア K・Qキッカー',     # 7
    'トップペア J〜9キッカー',     # 8
    'トップペア 8以下キッカー',    # 9
    'ミドルペア',                  # 10
    'ボトムペア',                  # 11
    'アンダーペア（ボード中位）',  # 12
    'アンダーペア（ボード下位）',  # 13
    'フラッシュドロー',            # 14
    'オープンエンダー',            # 15
    'ガットショット',              # 16
    'Aハイ',                       # 17
    'ノーペア',                    # 18
]

TEXTURE = [
    'ペアボード・ストレートあり',
    'ペアボード・ストレートなし',
    'モノトーン',
    'ツートーン・ストレートあり',
    'ツートーン・ストレートなし',
    'レインボー・ストレートあり',
    'レインボー・ストレートなし',
]


def board_texture(flop):
    """ボードを7種類に分ける。

    「ストレートあり」＝フロップ3枚が5段以内に収まる。ホールカード2枚で
    すでにストレートが完成しうる状態（フロップ全体の31.5%）。
    """
    flop = np.asarray(flop, dtype=np.int64)
    n = flop.shape[0]
    r = np.sort(flop >> 2, axis=1)[:, ::-1]
    s = flop & 3
    paired = (r[:, 0] == r[:, 1]) | (r[:, 1] == r[:, 2])
    same = np.array([np.bincount(row, minlength=4).max() for row in s])
    span = r[:, 0] - r[:, 2]
    span = np.where(r[:, 0] == 12, np.minimum(span, r[:, 1] - r[:, 2]), span)
    st = span <= 4                       # ストレートが完成しうる

    t = np.where(st, 5, 6)               # レインボー
    t = np.where(same == 2, np.where(st, 3, 4), t)
    t = np.where(same == 3, 2, t)
    t = np.where(paired, np.where(st, 0, 1), t)
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

    outs = np.zeros(n, dtype=np.int64)
    for r in range(13):
        outs += (_STRAIGHT[rank_mask | (np.int64(1) << r)] >= 0)
    outs = np.where(made_straight, 0, outs)
    fd = max_suit == 4

    t = np.full(n, 18, dtype=np.int64)
    t = np.where(hi == 12, 17, t)
    t = np.where(outs == 1, 16, t)
    t = np.where(outs >= 2, 15, t)
    t = np.where(fd, 14, t)

    # ペア系。ボードがペアでも同じ規則で通し、最後に上位役で上書きする
    t = np.where(pocket & (hr[:, 0] < br[:, 2]), 13, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 2]) & (hr[:, 0] < br[:, 0]), 12, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 2), 11, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 1), 10, t)
    tp = (~pocket) & (n_hit == 1) & (top_pos == 0)
    t = np.where(tp & (kicker <= 6), 9, t)
    t = np.where(tp & (kicker >= 7) & (kicker <= 9), 8, t)
    t = np.where(tp & (kicker >= 10) & (kicker <= 11), 7, t)
    t = np.where(tp & (kicker == 12), 6, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 0]) & (hr[:, 0] <= 9), 5, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 0]) & (hr[:, 0] >= 10), 4, t)
    t = np.where((~pocket) & (n_hit == 2), 3, t)

    # セット（ポケットペア＋ボード1枚）とトリップス（ボードのペア＋ホールカード1枚）
    t = np.where(pocket & (n_trips >= 1), 1, t)
    t = np.where((~pocket) & (n_trips >= 1), 2, t)

    # 上位役
    t = np.where(has_quad | (n_trips >= 2) | ((n_trips >= 1) & (n_pairs >= 1)), 0, t)
    t = np.where(made_straight | made_flush, 0, t)
    return t
