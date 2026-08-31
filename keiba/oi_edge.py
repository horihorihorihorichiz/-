# -*- coding: utf-8 -*-
"""大井×システムのエッジ精算（実オッズ oi_odds.json 使用）。
   - 乖離単勝(モデル1位オッズ7倍+)のROI
   - 三連複軸ながし(軸10-30倍・相手市場1-3)のROI
   - オッズ帯別・頭数別の内訳
   前提: oi_odds_fetch.py 完了後に実行"""
import json
from collections import defaultdict

rows = json.load(open("oi_model_rows.json", encoding="utf-8"))
odds_db = json.load(open("oi_odds.json", encoding="utf-8"))

# 払戻はhistファイルから
import glob
pays = {}
for f in glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json"):
    rid = f.split("/")[-1][:12]
    if rid[4:6] != "44" or rid in pays:
        continue
    try:
        d = json.load(open(f, encoding="utf-8"))
        pays[rid] = d["result"].get("payout", {})
    except Exception:
        pass

tan = defaultdict(lambda: [0, 0, 0])     # band -> [cost, ret, n]
trio = defaultdict(lambda: [0, 0, 0])
fuku_like = [0, 0, 0]
n_fire = 0
for r in rows:
    rid = r["rid"]
    od = odds_db.get(rid)
    if not od:
        continue
    o1 = (od.get(str(r["model1"])) or {}).get("odds")
    if not o1:
        continue
    pay = pays.get(rid, {})
    win = r["top3"][0]
    if o1 >= 7.0:
        n_fire += 1
        band = "7-10" if o1 < 10 else "10-15" if o1 < 15 else "15-30" if o1 <= 30 else "30+"
        t = tan[band]
        t[0] += 100
        t[2] += 1
        if r["model1"] == win:
            t[1] += int(o1 * 100)
        # 三連複: 軸10-30倍 相手=市場人気1-3(軸除く)
        if 10 <= o1 <= 30:
            mkt = sorted((h for h in od if od[h].get("odds")), key=lambda h: od[h]["odds"])
            partners = [int(h) for h in mkt if int(h) != r["model1"]][:3]
            combos = {tuple(sorted([r["model1"], a, b]))
                      for i, a in enumerate(partners) for b in partners[i+1:]}
            tk = tuple(sorted(r["top3"]))
            tr = trio["10-30"]
            tr[0] += 300
            tr[2] += 1
            if tk in combos:
                tp = pay.get("三連複", {})
                tr[1] += int(list(tp.values())[0]) if tp else 0
        # モデル1位の複勝的中(3着内)率も出す
        fuku_like[2] += 1
        fuku_like[0] += (r["model1"] in r["top3"])

print(f"大井 発火(モデル1位 実オッズ7倍+): {n_fire}R / {len(rows)}R = {100*n_fire/len(rows):.1f}%")
print()
print("乖離単勝 帯別ROI:")
tot = [0, 0, 0]
for band in ["7-10", "10-15", "15-30", "30+"]:
    c, ret, n = tan[band]
    if n:
        print(f"  {band}倍: 回収{100*ret/c:6.1f}% ({n}R)")
        tot[0] += c; tot[1] += ret; tot[2] += n
print(f"  合計: 回収{100*tot[1]/tot[0]:6.1f}% ({tot[2]}R)")
print()
c, ret, n = trio["10-30"]
if n:
    print(f"三連複軸ながし3点(軸10-30倍): 回収{100*ret/c:6.1f}% ({n}R)")
print(f"発火時モデル1位の3着内率: {100*fuku_like[0]/max(fuku_like[2],1):.1f}%")
