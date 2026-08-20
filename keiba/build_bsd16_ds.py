# -*- coding: utf-8 -*-
"""B-sd16スコア入り共有データセットを生成する。
ポートフォリオ分析(見習い42名)の共通入力: bsd16_races.jsonl
各行: rid, month, sd(芝ダ+距離帯), tier, field, nums, bsd16スコア, bsd16順位,
      市場オッズ・人気, 払戻(全券種), 3指標(fav_p/ent/sgap16)
検算: v99w2_result.pkl の指紋レース 202610020612 の top3 = [5,8,15] を照合。
"""
import json, pickle, math, numpy as np
import v99w_fit as V
import v99w2_fit as V2

races = V.load_races()
V2.attach_corner(races)
res = pickle.load(open("v99w2_result.pkl", "rb"))
wg16 = np.array(res["arm2_w"]["wg16"])
import ast
ws16 = {ast.literal_eval(k): np.array(v) for k, v in res["arm2_w"]["ws16"].items()}

def score(r):
    w = ws16.get(V.axis_key(r, "sd"), wg16)
    return r["Z16"] @ w

out = open("bsd16_races.jsonl", "w")
chk = None
n = 0
for r in races:
    s = score(r)
    # タイブレーク: スコア降順 → WAvg降順 → 馬番昇順 (v99w_rank.pyと同一)
    key = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
    rank = [int(r["nums"][i]) for i in key]
    odds = r.get("odds", {}) or {}
    iv = {int(k): 1.0/float(v) for k, v in odds.items() if v}
    tot = sum(iv.values())
    fav_p = max(iv.values())/tot if tot else None
    ent = -sum((x/tot)*math.log(x/tot) for x in iv.values()) if tot else None
    ss = sorted(s, reverse=True)
    sgap16 = float(ss[0]-ss[1]) if len(ss) > 1 else None
    row = dict(rid=r["rid"], month=r["month"], sd="".join(map(str, V.axis_key(r, "sd"))),
               tier=r["tier"], field=len(r["nums"]),
               nums=[int(x) for x in r["nums"]],
               score=[round(float(x), 5) for x in s],
               rank16=rank,
               odds={str(k): float(v) for k, v in odds.items()},
               ninki=r.get("ninki", {}),
               payout=r.get("payout", {}),
               finish_top3=[int(x) for x in r["top3"]],
               fav_p=round(fav_p, 5) if fav_p else None,
               ent=round(ent, 5) if ent else None, sgap16=sgap16)
    out.write(json.dumps(row, ensure_ascii=False)+"\n")
    n += 1
    if r["rid"] == "202610020612":
        chk = rank[:3]
out.close()
print("wrote", n, "races; fingerprint 202610020612 top3 =", chk, "(expect [5,8,15])")
