# -*- coding: utf-8 -*-
"""全馬モデル価値スイープ用: calc+v2_liveで大井2171Rを再スコアし全頭pを保存"""
import json, sys, time

import calc, v2_live

rows = json.load(open("oi_model_rows.json", encoding="utf-8"))
out = {}
t0 = time.time()
n_fail = 0
for i, r in enumerate(rows):
    rid = r["rid"]
    try:
        d = json.load(open(f"hist_nar_flat/{rid}.json", encoding="utf-8"))
        race = d["race"]
        res = calc.run(race)
        info = v2_live.rescore(race, res["rows"])
        out[rid] = {
            "engine": (info or {}).get("engine", "calc-only"),
            "p": {str(row["num"]): round(row["pwin"] / 100.0, 5) for row in res["rows"]},
        }
    except Exception as e:
        n_fail += 1
        out[rid] = {"engine": "FAIL", "err": str(e)[:80], "p": {}}
    if (i + 1) % 200 == 0:
        el = time.time() - t0
        print(f"{i+1}/{len(rows)} {el:.0f}s fail={n_fail}", flush=True)
json.dump(out, open("oi_pscores.json", "w", encoding="utf-8"))
print(f"done {len(out)} fail={n_fail} {time.time()-t0:.0f}s")
