# -*- coding: utf-8 -*-
"""8/2 拡張台帳分析(使い捨てでなくlogs/へ残す):
   A) 新規区間(7/18以降=採掘に未使用の真の未来データ)での現行ルール成績
   B) 夏3場(新潟/中京/札幌)の場別成績(全期間+新規区間)
   C) WATCHLIST W1/W2/W3 の新規区間検証
   D) S階級悪化の内訳
   usage: python3 analysis_0802.py
"""
import glob, itertools, json
from collections import defaultdict

import sim_rank as SR
import patterns as JP

# rid→date
rid_date = {}
for f in glob.glob("hist/*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    rid_date[f.split("/")[-1][:12]] = d.get("date", "")

rows = SR.load()
for r in rows:
    r["date"] = rid_date.get(r["rid"], "")
fresh = [r for r in rows if r["date"] >= "20260718"]
print(f"全{len(rows)}R / 新規区間(7/18+) {len(fresh)}R")

def key_of(ns):
    return "-".join(str(x) for x in sorted(ns))

def settle_umaren12(r):
    return 1, float((r["pay"].get("馬連") or {}).get(key_of(r["order"][:2]), 0))

def settle_tan(r, pos):
    t = r["order"][pos]
    win = int(list(r["pay"]["単勝"].keys())[0])
    return (1, float((r["pay"]["単勝"] or {}).get(str(t), 0))) if t == win else (1, 0.0)

# ── A) 現行ルール: 新規区間の発火と成績(場別も) ──────────────────────
def run_rules(rs, label):
    inv = ret = hits = n = 0
    by_v = defaultdict(lambda: [0, 0, 0, 0])   # venue -> [n, inv, ret, hits]
    det = []
    for r in rs:
        buy, hc = SR.classify_race(r)
        if not buy:
            continue
        best = max(buy, key=lambda f: f[2])
        try:
            tier, yen, _ = JP.tier_of(best[2], hc, best[0], r["venue"])
        except TypeError:
            tier, yen, _ = JP.tier_of(best[2], hc, best[0])
        if yen <= 0:
            continue
        st = SR.settle_fire(r, best[0], best[3])
        if st is None:
            continue
        pts, pay100 = st
        cost = yen * pts
        gain = pay100 / 100.0 * yen
        n += 1; inv += cost; ret += gain; hits += (1 if gain > 0 else 0)
        v = by_v[r["venue"]]
        v[0] += 1; v[1] += cost; v[2] += gain; v[3] += (1 if gain > 0 else 0)
        det.append((r["date"], r["venue"], r["rid"][10:12], tier, best[0][:26], cost, gain))
    print(f"\n━━ {label}: 発火{n}R 的中{hits} 投下{inv:,.0f} 回収{ret:,.0f} "
          f"ROI {ret/inv*100 if inv else 0:.1f}% 損益{ret-inv:+,.0f}円")
    for v, (vn, vi, vr, vh) in sorted(by_v.items(), key=lambda x: -x[1][1]):
        print(f"   {v}: {vn}R 的中{vh} ROI {vr/vi*100 if vi else 0:.0f}% 損益{vr-vi:+,.0f}")
    return det

det = run_rules(fresh, "A) 新規区間(7/18-8/2)・現行ルール")
for d in det:
    print("   ", d[0], d[1], d[2]+"R", d[3], d[4], f"投{d[5]:,}", f"戻{d[6]:,.0f}")

# ── B) 夏3場の全期間成績(現行ルール) ─────────────────────────────
print()
run_rules([r for r in rows if r["venue"] in ("新潟", "中京", "札幌")],
          "B) 夏3場(新潟/中京/札幌)・全期間・現行ルール")

# ── C) WATCHLIST 新規区間検証 ──────────────────────────────────
def wl(rs, label, cond, settle):
    inv = ret = hits = n = 0
    for r in rs:
        if not cond(r):
            continue
        st = settle(r)
        if st is None:
            continue
        pts, pay100 = st
        n += 1; inv += pts * 100; ret += pay100; hits += (1 if pay100 > 0 else 0)
    roi = ret/inv*100 if inv else 0
    print(f"  {label}: {n}R 的中{hits} ROI {roi:.1f}% (100円/点換算 損益{ret-inv:+,.0f})")

def pop_rank(r, n):
    srt = sorted(r["odds"], key=lambda h: r["odds"][h])
    return srt.index(n) + 1 if n in srt else 99

print("\n━━ C) WATCHLIST(新規区間のみ=真の未来データ)")
wl(fresh, "W1 ダ中1301-1900×1勝×11頭+ 馬連1-2位",
   lambda r: r["surface"] == "ダ" and 1301 <= r["dist"] <= 1900 and r["tier"] == 6
             and r["field"] >= 11, settle_umaren12)
wl(fresh, "W2 芝長1901+×10頭以下×非未勝利 馬連1-2位",
   lambda r: r["surface"] == "芝" and r["dist"] >= 1901 and r["field"] <= 10
             and r["tier"] not in (3, 4), settle_umaren12)
wl(fresh, "W3 ダ短≤1300×1位2-3人気×混戦 単勝2位",
   lambda r: r["surface"] == "ダ" and r["dist"] <= 1300
             and 2 <= pop_rank(r, r["order"][0]) <= 3 and r["g12"] < 0.30,
   lambda r: settle_tan(r, 1))

# ── D) S階級の内訳(全期間) ─────────────────────────────────────
print("\n━━ D) S階級の発火内訳(全期間)")
for r in rows:
    buy, hc = SR.classify_race(r)
    if not buy:
        continue
    best = max(buy, key=lambda f: f[2])
    try:
        tier, yen, _ = JP.tier_of(best[2], hc, best[0], r["venue"])
    except TypeError:
        tier, yen, _ = JP.tier_of(best[2], hc, best[0])
    if tier != "S":
        continue
    st = SR.settle_fire(r, best[0], best[3])
    if st is None:
        continue
    pts, pay100 = st
    print(f"   {r['date']} {r['venue']} {r['rid'][10:]}R {best[0][:30]} "
          f"ROI主張{best[2]:.0f} 🔥{hc} → 戻{pay100*yen/100:,.0f}")
