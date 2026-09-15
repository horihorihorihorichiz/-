"""7枚判定器の検算。5枚の総当たり判定と突き合わせる。"""
import itertools, random
import numpy as np
from evaluator import evaluate7

def slow5(cards):
    """5枚を素直に判定して (役種, キッカー列) を返す。"""
    ranks = sorted((c >> 2 for c in cards), reverse=True)
    suits = [c & 3 for c in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    groups = sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape = [g[1] for g in groups]
    vals = [g[0] for g in groups]
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight_high = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:
            straight_high = 3
    if flush and straight_high is not None:
        return (8, [straight_high])
    if shape == [4, 1]:
        return (7, vals)
    if shape == [3, 2]:
        return (6, vals)
    if flush:
        return (5, ranks)
    if straight_high is not None:
        return (4, [straight_high])
    if shape == [3, 1, 1]:
        return (3, vals)
    if shape == [2, 2, 1]:
        return (2, vals)
    if shape == [2, 1, 1, 1]:
        return (1, vals)
    return (0, ranks)

def slow7(cards):
    return max(slow5(list(c)) for c in itertools.combinations(cards, 5))

random.seed(7)
hands = [random.sample(range(52), 7) for _ in range(4000)]
fast = evaluate7(np.array(hands))
slow = [slow7(h) for h in hands]

order_fast = np.argsort(fast, kind='stable')
order_slow = sorted(range(len(hands)), key=lambda i: slow[i])

bad = 0
for i in range(len(hands) - 1):
    a, b = order_slow[i], order_slow[i + 1]
    same_slow = slow[a] == slow[b]
    if same_slow and fast[a] != fast[b]:
        bad += 1
    if not same_slow and fast[a] >= fast[b]:
        bad += 1
print("不一致:", bad, "/", len(hands) - 1)

# 役の種類も突き合わせる
cat_fast = (fast // (13**5)).astype(int)
cat_slow = np.array([s[0] for s in slow])
print("役種の不一致:", int((cat_fast != cat_slow).sum()))
