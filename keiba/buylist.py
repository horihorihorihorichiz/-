# -*- coding: utf-8 -*-
"""
買い目アロケータ（標準ロジックを固定）
入力: 各馬のFinal_PWin(%) と オッズ（単勝/馬連/ワイド/三連複）
方針:
  1. モデル上位N頭を軸候補にする
  2. 全候補券種のEV = modelProb × オッズ を計算（Harville で連系確率を推定）
  3. EVプラス(>=EV_MIN)だけ採用し、EV降順に並べる
  4. 各点を「当たれば FLOOR% 以上」になる最小額(UNIT単位で切上げ)で置く
  5. 予算が余れば、確率の高い軸(上位ペア/単勝)から UNIT ずつ上乗せ
  6. 予算を超えたらEVの低い点から落とす
使い方(例):
  from buylist import allocate
  allocate(pwin, tan=..., b4=..., b5=..., trip=...,
           budget=10000, floor=2.5, unit=100)
"""
import itertools

def _um(pwin, i, j):
    pi, pj = pwin[i], pwin[j]
    return pi*pj/(1-pi) + pj*pi/(1-pj)

def _top3(pwin, i, j):
    hs = list(pwin); tot = 0.0
    for a, b, c in itertools.permutations(hs, 3):
        if i in (a, b, c) and j in (a, b, c):
            tot += pwin[a]*(pwin[b]/(1-pwin[a]))*(pwin[c]/(1-pwin[a]-pwin[b]))
    return tot

def _p3(pwin, a, b, c):
    tot = 0.0
    for x, y, z in itertools.permutations([a, b, c]):
        tot += pwin[x]*(pwin[y]/(1-pwin[x]))*(pwin[z]/(1-pwin[x]-pwin[y]))
    return tot

def allocate(pwin, tan=None, b4=None, b5=None, trip=None,
             budget=10000, floor=2.5, unit=100, ev_min=1.0,
             n_axis=4, n_field=8, max_points=18):
    """pwin: {umaban: prob(0-1)}  tan/b4/b5/trip: {key: odds}
       b4/b5 key = (i,j) sorted tuple ; trip key = (i,j,k) sorted tuple
       tan key = umaban(int)"""
    tan = tan or {}; b4 = b4 or {}; b5 = b5 or {}; trip = trip or {}
    order = sorted(pwin, key=lambda h: -pwin[h])
    axis = order[:n_axis]; field = order[:n_field]
    cands = []  # (ev, prob, odds, kind, key, label)
    for h in axis:
        if h in tan:
            p = pwin[h]; cands.append((p*tan[h], p, tan[h], '単勝', h, f"単{h}"))
    for i, j in itertools.combinations(field, 2):
        k = tuple(sorted((i, j)))
        if k in b4:
            p = _um(pwin, i, j); cands.append((p*b4[k], p, b4[k], '馬連', k, f"{k[0]}-{k[1]}"))
        if k in b5:
            p = _top3(pwin, i, j); cands.append((p*b5[k], p, b5[k], 'ワイド', k, f"{k[0]}-{k[1]}"))
    for i, j, l in itertools.combinations(field, 3):
        # 三連複は軸を1頭以上含むものだけ（点数爆発を防ぐ）
        if not (set((i, j, l)) & set(axis[:3])):
            continue
        k = tuple(sorted((i, j, l)))
        if k in trip:
            p = _p3(pwin, i, j, l); cands.append((p*trip[k], p, trip[k], '三連複', k, '-'.join(map(str, k))))
    # EVプラスのみ, EV降順
    cands = [c for c in cands if c[0] >= ev_min]
    cands.sort(key=lambda c: -c[0])
    cands = cands[:max_points]
    # floor最小額(UNIT切上げ)
    need = floor * budget
    picks = []
    for ev, p, o, kind, key, lbl in cands:
        st = -(-int(need / o) // unit) * unit  # ceil to unit
        if st <= 0: st = unit
        picks.append([kind, lbl, o, st, p, ev])
    total = sum(x[3] for x in picks)
    # 予算オーバーならEV低い順に落とす
    while total > budget and picks:
        picks.pop()  # 末尾=EV最低
        total = sum(x[3] for x in picks)
    # 余りを高確率の軸(単勝/上位ペア)から上乗せ
    picks.sort(key=lambda x: -x[4])  # prob降順
    idx = 0
    while total + unit <= budget and picks:
        picks[idx % min(3, len(picks))][3] += unit
        total += unit; idx += 1
    # 表示整形（EV降順で出す）
    picks.sort(key=lambda x: -x[5])
    print(f"{'券種':<5}{'買い目':<10}{'オッズ':>8}{'金額':>7}{'払戻':>9}{'対総':>6}{'EV':>6}")
    exp = 0.0
    for kind, lbl, o, st, p, ev in picks:
        pay = o*st; exp += st*p*o
        flag = "" if pay >= need else " ★floor割れ"
        print(f"{kind:<5}{lbl:<10}{o:>8}{st:>7}{pay:>9.0f}{pay/budget*100:>5.0f}%{ev*100:>5.0f}%{flag}")
    print(f"\n合計{total}円 期待払戻{exp:.0f}円 期待回収{exp/total*100:.0f}% 点数{len(picks)}")
    return picks
