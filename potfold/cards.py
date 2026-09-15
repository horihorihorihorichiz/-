"""カードの文字列表現と整数表現の変換。"""
RANKS = '23456789TJQKA'
SUITS = 'cdhs'          # クラブ/ダイヤ/ハート/スペード


def parse_card(s):
    s = s.strip()
    if len(s) != 2:
        raise ValueError('カード表記が不正です: %r' % s)
    r = RANKS.index(s[0].upper())
    u = SUITS.index(s[1].lower())
    return r * 4 + u


def parse_cards(s):
    """'As Kd' や 'AsKd' のような文字列を整数の配列にする。"""
    if isinstance(s, (list, tuple)):
        toks = list(s)
    else:
        s = s.replace(',', ' ').strip()
        toks = s.split() if ' ' in s else [s[i:i + 2] for i in range(0, len(s), 2)]
    out = [parse_card(t) for t in toks]
    if len(set(out)) != len(out):
        raise ValueError('同じカードが重複しています: %r' % s)
    return out


def card_str(c):
    return RANKS[c >> 2] + SUITS[c & 3]


def cards_str(cs):
    return ' '.join(card_str(c) for c in cs)
