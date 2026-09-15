"""ハンドの種類とボードテクスチャの分類（ペアボードにも対応）。"""
import numpy as np
from evaluator import _STRAIGHT

HAND = [
    'ストレート以上',             # 0
    'セット',                         # 1
    'トリップス',                   # 2
    'ツーペア',                      # 3
    'オーバーペア QQ以上',       # 4
    'オーバーペア JJ以下',       # 5
    'ペア＋フラッシュドロー', # 6
    'トップペア（ボードのAをペア）', # 7
    'トップペア Aキッカー',     # 8
    'トップペア K・Qキッカー', # 9
    'トップペア J〜9キッカー', # 10
    'トップペア 8以下キッカー', # 11
    'ミドルペア',                   # 12
    'ボトムペア',                   # 13
    'アンダーペア（ボード中位）', # 14
    'アンダーペア（ボード下位）', # 15
    'コンボドロー（フラドロ＋ストレート）', # 16
    'ナッツフラッシュドロー', # 17
    'フラッシュドロー K・Qハイ', # 18
    'フラッシュドロー 弱い',   # 19
    'オープンエンダー A・K持ち', # 20
    'オープンエンダー Q〜T持ち', # 21
    'オープンエンダー 9以下',  # 22
    'ガットショット A・K持ち', # 23
    'ガットショット Q〜T持ち', # 24
    'ガットショット 9以下',     # 25
    'ツーオーバー（A含む）',   # 26
    'ツーオーバー（Aなし）',   # 27
    'Aハイ',                           # 28
    'ノーペア',                      # 29
]


TEXTURE = [
    'ペアボード・ハイ（A・K）',
    'ペアボード・ミドル（Q〜9）',
    'ペアボード・ロー（8以下）',
    'モノトーン（3枚同スート）',
    'ハイ（A・K）・ストレートあり',
    'ハイ（A・K）・ストレートなし',
    'ミドル（Q〜9）・ストレートあり',
    'ミドル（Q〜9）・ストレートなし',
    'ロー（8以下）・ストレートあり',
    'ロー（8以下）・ストレートなし',
]


def board_texture(flop):
    """ボードを10種類に分ける。

    効き具合を測ったうえで軸を選んだ。
      ・高さ（最高位）      … いちばん効く（トップペアで15ポイント差）
      ・ストレートの可能性  … 11ポイント差。フロップ3枚が5段以内かどうか
      ・モノトーン          … 11〜13ポイント差
    レインボーとツートーンの差は1〜2ポイントしかないので分けていない
    （フラッシュドローの有無はハンド側の分類で拾っている）。
    """
    flop = np.asarray(flop, dtype=np.int64)
    n = flop.shape[0]
    r = np.sort(flop >> 2, axis=1)[:, ::-1]
    s = flop & 3
    paired = (r[:, 0] == r[:, 1]) | (r[:, 1] == r[:, 2])
    same = np.array([np.bincount(row, minlength=4).max() for row in s])
    span = r[:, 0] - r[:, 2]
    span = np.where(r[:, 0] == 12, np.minimum(span, r[:, 1] - r[:, 2]), span)
    st = span <= 4                                   # ストレートが完成しうる
    hi = np.where(r[:, 0] >= 11, 0, np.where(r[:, 0] >= 7, 1, 2))   # 高さ 0=ハイ 1=ミドル 2=ロー

    t = np.where(st, 4 + hi * 2, 5 + hi * 2)
    t = np.where(same == 3, 3, t)
    t = np.where(paired, hi, t)
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

    # フラッシュドローと、その強さ（自分が持っているそのスートの最高位）
    suit_cnt = np.bincount(sflat, minlength=n * 4).reshape(n, 4)
    fs = suit_cnt.argmax(axis=1)
    fd = suit_cnt.max(axis=1) == 4
    my_suit = (hole & 3)
    my_rank = hole >> 2
    in_suit = my_suit == fs[:, None]
    fd_high = np.where(in_suit.any(axis=1),
                       np.where(in_suit, my_rank, -1).max(axis=1), -1)

    # オーバーカード（ボード最高位より上のホールカード）
    n_over = (hr > br[:, 0][:, None]).sum(axis=1)
    has_ace = (hr == 12).any(axis=1)

    hi_card = hr.max(axis=1)      # 自分の高いほうの札

    # ストレートドローは「自分の一番高い札」で3段に分ける。
    # 引いても上のストレートに負ける形（例：9TJ に 27）と、
    # 外しても高い札が残る形を切り分けるため。
    def sd_group(base):
        return np.where(hi_card >= 11, base, np.where(hi_card >= 8, base + 1, base + 2))

    t = np.full(n, 29, dtype=np.int64)
    t = np.where(has_ace, 28, t)
    t = np.where(n_over >= 2, np.where(has_ace, 26, 27), t)
    t = np.where(outs == 1, sd_group(23), t)
    t = np.where(outs >= 2, sd_group(20), t)
    t = np.where(fd, np.where(fd_high == 12, 17, np.where(fd_high >= 10, 18, 19)), t)
    t = np.where(fd & (outs >= 1), 16, t)

    # ペア系。ボードがペアでも同じ規則で通し、最後に上位役で上書きする
    t = np.where(pocket & (hr[:, 0] < br[:, 2]), 15, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 2]) & (hr[:, 0] < br[:, 0]), 14, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 2), 13, t)
    t = np.where((~pocket) & (n_hit == 1) & (top_pos == 1), 12, t)
    tp = (~pocket) & (n_hit == 1) & (top_pos == 0)
    t = np.where(tp & (kicker <= 6), 11, t)
    t = np.where(tp & (kicker >= 7) & (kicker <= 9), 10, t)
    t = np.where(tp & (kicker >= 10) & (kicker <= 11), 9, t)
    t = np.where(tp & (kicker == 12), 8, t)
    # ボードの最高位が A の場合は、A をペアにしているので別扱い
    t = np.where(tp & (br[:, 0] == 12), 7, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 0]) & (hr[:, 0] <= 9), 5, t)
    t = np.where(pocket & (hr[:, 0] > br[:, 0]) & (hr[:, 0] >= 10), 4, t)
    # ペアができていて、なおかつフラッシュドローもある
    is_pair = (t >= 4) & (t <= 15)
    t = np.where(is_pair & fd, 6, t)
    t = np.where((~pocket) & (n_hit == 2), 3, t)

    # セット（ポケットペア＋ボード1枚）とトリップス（ボードのペア＋ホールカード1枚）
    t = np.where(pocket & (n_trips >= 1), 1, t)
    t = np.where((~pocket) & (n_trips >= 1), 2, t)

    # 上位役
    t = np.where(has_quad | (n_trips >= 2) | ((n_trips >= 1) & (n_pairs >= 1)), 0, t)
    t = np.where(made_straight | made_flush, 0, t)
    return t
