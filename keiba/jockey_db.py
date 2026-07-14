# -*- coding: utf-8 -*-
"""騎手ファクター（Ver.101 A2）。
   hist_enrich/の1年分を日付順に走査し、各レース時点(as-of=リーク無し)の
   騎手の複勝率・勝率・騎乗数を hist_feat/<race_id>.json に保存する。
   予測時（未来のレース）用には全期間の集計 jockey_stats.json も出力。

   usage: python3 jockey_db.py build
"""
import glob, json, os, sys
from collections import defaultdict

PRIOR_N = 40        # 平滑化: 事前分布の擬似騎乗数
def build():
    files = []
    for f in glob.glob("hist_enrich/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        files.append((d.get("date", ""), d["race_id"], d))
    files.sort()
    # 全期間の平均(平滑化の事前分布に使う)
    tot_rides = tot_top3 = tot_win = 0
    for _, _, d in files:
        for h in d["horses"]:
            if h.get("rank", "").isdigit():
                tot_rides += 1
                tot_top3 += (1 if int(h["rank"]) <= 3 else 0)
                tot_win += (1 if int(h["rank"]) == 1 else 0)
    g_top3 = tot_top3/tot_rides
    g_win = tot_win/tot_rides
    print(f"全体: {tot_rides}騎乗 複勝率{g_top3*100:.1f}% 勝率{g_win*100:.1f}%", file=sys.stderr)

    os.makedirs("hist_feat", exist_ok=True)
    acc = defaultdict(lambda: [0, 0, 0])   # jid -> [rides, top3, win]
    n_out = 0
    for date, rid, d in files:
        feat = {}
        for h in d["horses"]:
            jid = h.get("jockey_id")
            if not jid:
                continue
            r, t3, w = acc[jid]
            feat[str(h["num"])] = dict(
                jid=jid, j_n=r,
                j_top3=(t3 + g_top3*PRIOR_N)/(r + PRIOR_N),
                j_win=(w + g_win*PRIOR_N)/(r + PRIOR_N))
        json.dump(dict(race_id=rid, date=date, jockey=feat),
                  open(f"hist_feat/{rid}.json", "w", encoding="utf-8"),
                  ensure_ascii=False)
        n_out += 1
        # レース確定後に累積へ反映(as-of保証)
        for h in d["horses"]:
            jid = h.get("jockey_id")
            if not jid or not h.get("rank", "").isdigit():
                continue
            acc[jid][0] += 1
            acc[jid][1] += (1 if int(h["rank"]) <= 3 else 0)
            acc[jid][2] += (1 if int(h["rank"]) == 1 else 0)
    # 予測時用: 全期間集計
    out = {jid: dict(n=r, top3=(t3 + g_top3*PRIOR_N)/(r + PRIOR_N),
                     win=(w + g_win*PRIOR_N)/(r + PRIOR_N))
           for jid, (r, t3, w) in acc.items()}
    json.dump(dict(global_top3=g_top3, global_win=g_win, jockeys=out),
              open("jockey_stats.json", "w", encoding="utf-8"), ensure_ascii=False)
    top = sorted(out.items(), key=lambda x: -x[1]["top3"]*min(x[1]["n"], 200))[:5]
    print(f"as-of特徴 {n_out}レース分 / 騎手{len(out)}人", file=sys.stderr)
    for jid, s in sorted(out.items(), key=lambda x: -x[1]["top3"])[:8]:
        if s["n"] >= 100:
            print(f"  jid{jid}: 騎乗{s['n']} 複勝率{s['top3']*100:.1f}%", file=sys.stderr)


if __name__ == "__main__":
    build()
