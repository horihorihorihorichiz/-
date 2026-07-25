# -*- coding: utf-8 -*-
"""新潟芝1000m直線 専用パターン採掘。
   n1000_races.jsonl(5年分)を dev=2021-2023 / conf=2024-2025 に分割し、
   枠帯×人気帯×オッズ帯の単勝ルールを全走査。合格= dev>=110 & conf>=100 & n>=40 & hits>=5。
   単勝ROIは実オッズ×100円で精算(払戻テーブル不要)。"""
import json, itertools, sys

races = [json.loads(l) for l in open("n1000_races.jsonl", encoding="utf-8")]
seen = set(); uniq = []
for r in races:
    if r["rid"] in seen: continue
    seen.add(r["rid"]); uniq.append(r)
races = uniq
print(f"races={len(races)}  期間: {min(r['date'] for r in races)}-{max(r['date'] for r in races)}")

WAKU = {"内(1-3枠)": (1, 3), "中(4-6枠)": (4, 6), "外(7-8枠)": (7, 8),
        "全枠": (1, 8)}
POP = {"1人気": (1, 1), "2-3人気": (2, 3), "4-6人気": (4, 6), "7-9人気": (7, 9),
       "10人気-": (10, 99), "全人気": (1, 99)}
ODZ = {"~4.9": (0, 4.9), "5-9.9": (5, 9.9), "10-19.9": (10, 19.9),
       "20-49.9": (20, 49.9), "50+": (50, 9999), "全オッズ": (0, 9999)}

def roi(rs, wk, pp, oz, field_min=0):
    bet = pays = hits = 0
    for r in rs:
        if r["field"] < field_min: continue
        for h in r["rows"]:
            if h["odds"] is None or h["pop"] is None: continue
            if not (wk[0] <= h["waku"] <= wk[1]): continue
            if not (pp[0] <= h["pop"] <= pp[1]): continue
            if not (oz[0] <= h["odds"] <= oz[1]): continue
            bet += 100
            if h["fin"] == "1":
                pays += h["odds"] * 100
                hits += 1
    return (bet // 100, hits, 100.0 * pays / bet if bet else 0)

dev = [r for r in races if r["date"] < "20240101"]
conf = [r for r in races if r["date"] >= "20240101"]
print(f"dev={len(dev)}R conf={len(conf)}R")

res = []
for (wn, wk), (pn, pp), (on, oz) in itertools.product(WAKU.items(), POP.items(), ODZ.items()):
    if pn == "全人気" and on == "全オッズ" and wn == "全枠": continue
    dn, dh, dr = roi(dev, wk, pp, oz)
    cn, ch, cr = roi(conf, wk, pp, oz)
    n = dn + cn; hits = dh + ch
    if n < 40 or hits < 5: continue
    allr = (dr * dn + cr * cn) / n if n else 0
    ok = dr >= 110 and cr >= 100
    res.append(dict(rule=f"{wn}×{pn}×{on}", dev=f"{dr:.1f}%/{dn}", conf=f"{cr:.1f}%/{cn}",
                    dev_roi=dr, conf_roi=cr, n=n, hits=hits, all_roi=allr, ok=ok))
res.sort(key=lambda x: -x["all_roi"])
print("\n=== 合格(dev>=110 & conf>=100 & n>=40 & hits>=5) ===")
for x in res:
    if x["ok"]:
        print(f"◎ {x['rule']:<28} 通算{x['all_roi']:6.1f}% n={x['n']:4d} hits={x['hits']:2d} dev{x['dev']} conf{x['conf']}")
print("\n=== 上位20(参考・不合格含む) ===")
for x in res[:20]:
    m = "◎" if x["ok"] else " "
    print(f"{m} {x['rule']:<28} 通算{x['all_roi']:6.1f}% n={x['n']:4d} hits={x['hits']:2d} dev{x['dev']} conf{x['conf']}")

# 基礎統計: 枠帯別の勝率・複勝圏率(全期間)
print("\n=== 枠帯の基礎バイアス(全期間) ===")
for wn, wk in [("内(1-3)", (1, 3)), ("中(4-6)", (4, 6)), ("外(7-8)", (7, 8))]:
    starts = wins = top3 = 0
    for r in races:
        for h in r["rows"]:
            if wk[0] <= h["waku"] <= wk[1]:
                starts += 1
                if h["fin"] == "1": wins += 1
                if h["fin"] in ("1", "2", "3"): top3 += 1
    print(f"{wn}: 出走{starts} 勝率{100*wins/starts:.1f}% 複勝圏率{100*top3/starts:.1f}%")
json.dump(res, open("n1000_mine_result.json", "w", encoding="utf-8"), ensure_ascii=False)
print("\nWROTE n1000_mine_result.json")
