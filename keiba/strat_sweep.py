# -*- coding: utf-8 -*-
"""全レースを条件で総当たりに切って、的中率とROIを3期並べて見る。
   ユーザー指示「一回全レース分けて統計分けて、的中率と回収率がどうしたら上がるか確認」の実装。
   買い方は固定（複勝・市場上位2頭2点）。切り方だけを動かす。
   これは探索であって採用判断ではない。3期そろって良い区分だけが候補になる。"""
import json, collections, os, sys

rows = [json.loads(l) for l in open('bsd16_races.jsonl')]
ex = json.load(open('/tmp/extra.json'))
for r in rows:
    e = ex.get(r['rid'], {})
    r['venue'] = e.get('venue'); r['baba'] = e.get('baba')
    r['dist'] = e.get('dist'); r['rno'] = e.get('rno')

seg = lambda lo, hi: [r for r in rows if lo <= r['month'] <= hi]
MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')


def mkt(r):
    return [int(n) for n, _ in sorted(r['odds'].items(), key=lambda kv: kv[1])]


def fuku2(r):
    f = {int(k): v for k, v in (r['payout'].get('複勝') or {}).items()}
    ret = got = 0
    for h in mkt(r)[:2]:
        v = f.get(h)
        if v:
            ret += v; got = 1
    return 200, ret, got


def stat(rs):
    if not rs:
        return None
    c = ret = hit = 0
    for r in rs:
        a, b, h = fuku2(r); c += a; ret += b; hit += h
    return dict(n=len(rs), hit=hit / len(rs) * 100, roi=ret / c * 100, pl=ret - c)


def band(v, edges, labels):
    for e, l in zip(edges, labels):
        if v is not None and v <= e:
            return l
    return labels[-1]


CUTS = {
 "会場": lambda r: r['venue'] or "?",
 "芝ダ": lambda r: r['sd'][0],
 "距離帯": lambda r: r['sd'],
 "頭数": lambda r: band(r['field'], [8, 10, 12, 14, 16], ["〜8", "9-10", "11-12", "13-14", "15-16", "17+"]),
 "クラス": lambda r: {10: "未勝利/新馬", 6: "1勝", 5: "2勝", 4: "3勝", 3: "OP/重賞"}.get(r['tier'], f"tier{r['tier']}"),
 "馬場": lambda r: r.get('baba') or "?",
 "R番号": lambda r: band(r['rno'] or 0, [4, 8, 10, 12], ["1-4R", "5-8R", "9-10R", "11-12R", "13R+"]),
 "1人気implied": lambda r: band(r['fav_p'], [.20, .28, .34, .42, .55], ["〜.20", ".20-.28", ".28-.34", ".34-.42", ".42-.55", ".55+"]),
 "市場の割れ(ent)": lambda r: band(r['ent'], [1.6, 1.8, 1.95, 2.1, 2.3], ["〜1.6", "1.6-1.8", "1.8-1.95", "1.95-2.1", "2.1-2.3", "2.3+"]),
 "モデル得点差": lambda r: band(r['sgap16'], [.1, .25, .45, .75, 1.2], ["〜.10", ".10-.25", ".25-.45", ".45-.75", ".75-1.2", "1.2+"]),
 "1人気オッズ": lambda r: band(min(r['odds'].values()) if r['odds'] else 99, [1.5, 2.0, 2.5, 3.5, 5.0], ["〜1.5", "1.5-2.0", "2.0-2.5", "2.5-3.5", "3.5-5.0", "5.0+"]),
}

if __name__ == "__main__":
    print("=" * 96)
    print("全レース総当たり  買い方=複勝・市場上位2頭(2点)固定  切り方だけを変える")
    print("=" * 96)
    good = []
    for cname, f in CUTS.items():
        g = collections.defaultdict(lambda: {'M': [], 'V': [], 'C': []})
        for r in MINE: g[f(r)]['M'].append(r)
        for r in VAL: g[f(r)]['V'].append(r)
        for r in CONF: g[f(r)]['C'].append(r)
        print(f"\n■ {cname}")
        print(f"{'区分':<13}{'MINE':>22}{'VALIDATE':>22}{'CONFIRM':>22}")
        for k in sorted(g, key=lambda k: -len(g[k]['M'])):
            d = g[k]; cells = []; ss = []
            for w in ('M', 'V', 'C'):
                s = stat(d[w]); ss.append(s)
                cells.append(f"{s['n']:>5} {s['hit']:>5.1f}% {s['roi']:>6.1f}%" if s else "          —")
            mark = ""
            if all(s and s['n'] >= 30 for s in ss):
                if all(s['roi'] >= 95 for s in ss):
                    mark = " ★3期とも95%+"
                    good.append((cname, k, [round(s['roi'], 1) for s in ss], [s['n'] for s in ss]))
            print(f"{str(k):<13}" + "".join(f"{c:>22}" for c in cells) + mark)
    print("\n" + "=" * 96)
    print("★ 3期すべてでROI95%以上・各期n>=30 の区分")
    if good:
        for c, k, roi, n in good:
            print(f"  {c} = {k}   ROI {roi}  n {n}")
    else:
        print("  該当なし")
