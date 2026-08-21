# -*- coding: utf-8 -*-
"""全コース×全距離の完全統計を列挙する（2026-08-21）。
   指示「コースや距離ごとに全て分けて」の実装。人手の解釈を挟まず、素の統計を全部出す。
   買い方は市場人気ベースで固定（モデルを挟むと選択の恣意が入るため）。"""
import json, collections, statistics as st, itertools, sys


def load():
    return json.load(open('/tmp/allrows.json'))


def k2(a, b):
    return "%d-%d" % tuple(sorted((int(a), int(b))))


def k3(t):
    return "-".join(str(x) for x in sorted(int(v) for v in t))


def plans(r):
    """市場人気ベースの標準的な買い方。(名前, 点数, 払戻合計, 的中か)"""
    mk, pay = r['mk'], r['pay']
    out = {}
    f = {int(k): float(v) for k, v in (pay.get('複勝') or {}).items()}
    t = {int(k): float(v) for k, v in (pay.get('単勝') or {}).items()}
    W = {k: float(v) for k, v in (pay.get('ワイド') or {}).items()}
    U = {k: float(v) for k, v in (pay.get('馬連') or {}).items()}
    S = {k: float(v) for k, v in (pay.get('三連複') or {}).items()}
    out['単勝1人気'] = (1, t.get(mk[0], 0), mk[0] in t)
    out['複勝1人気'] = (1, f.get(mk[0], 0), mk[0] in f)
    ret2 = sum(f.get(h, 0) for h in mk[:2])
    out['複勝1-2人気'] = (2, ret2, ret2 > 0)
    if len(mk) >= 2:
        v = W.get(k2(mk[0], mk[1]), 0); out['ワイド1-2'] = (1, v, v > 0)
        v = U.get(k2(mk[0], mk[1]), 0); out['馬連1-2'] = (1, v, v > 0)
    if len(mk) >= 3:
        v = S.get(k3(mk[:3]), 0); out['三連複1-2-3'] = (1, v, v > 0)
    if len(mk) >= 4:
        rr = sum(S.get(k3(c), 0) for c in itertools.combinations(mk[:4], 3))
        out['三連複上位4BOX'] = (4, rr, rr > 0)
    return out


PLANS = ['単勝1人気', '複勝1人気', '複勝1-2人気', 'ワイド1-2', '馬連1-2',
         '三連複1-2-3', '三連複上位4BOX']


def agg(rs):
    """レース群 → 買い方ごとの (n, 的中率, ROI, 損益, 平均払戻)"""
    acc = {p: [0, 0, 0, 0] for p in PLANS}      # n, cost, ret, hit
    for r in rs:
        for p, (pts, ret, hit) in plans(r).items():
            a = acc[p]; a[0] += 1; a[1] += pts * 100; a[2] += ret; a[3] += bool(hit)
    out = {}
    for p, (n, c, ret, hit) in acc.items():
        if not n:
            continue
        out[p] = dict(n=n, hit=hit / n * 100, roi=ret / c * 100 if c else 0,
                      pl=ret - c, avg=ret / hit if hit else 0)
    return out


def main():
    rows = load()
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['venue'], r['surface'], r['dist'])].append(r)
    ven_order = ['札幌', '函館', '福島', '新潟', '東京', '中山', '中京', '京都', '阪神', '小倉']
    print(f"# 全コース×全距離 完全統計（{len(rows)}R / {len(by)}コース）\n")
    print("買い方は全て市場人気ベース（モデルを挟まない素の統計）。1点100円。\n")
    for v in ven_order:
        ks = sorted([k for k in by if k[0] == v], key=lambda k: (k[1], k[2]))
        if not ks:
            continue
        print(f"\n## {v}\n")
        print("| コース | R数 | 平均頭数 | 単勝1人気 | 複勝1人気 | 複勝1-2 | ワイド1-2 | 馬連1-2 | 三連複123 | 三連複4BOX |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for k in ks:
            rs = by[k]; a = agg(rs)
            fld = st.mean(r['field'] for r in rs)
            cells = []
            for p in PLANS:
                d = a.get(p)
                cells.append(f"{d['hit']:.0f}%/{d['roi']:.0f}%" if d else "—")
            print(f"| {k[1]}{k[2]} | {len(rs)} | {fld:.1f} | " + " | ".join(cells) + " |")
    # 全体
    print("\n\n## 全コース合計\n")
    a = agg(rows)
    print("| 買い方 | R数 | 的中率 | ROI | 損益 | 的中1回の平均払戻 |")
    print("|---|---|---|---|---|---|")
    for p in PLANS:
        d = a[p]
        print(f"| {p} | {d['n']:,} | {d['hit']:.1f}% | {d['roi']:.1f}% | {d['pl']:+,.0f}円 | {d['avg']:,.0f}円 |")


if __name__ == "__main__":
    main()
