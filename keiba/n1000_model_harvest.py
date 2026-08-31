# -*- coding: utf-8 -*-
"""新潟芝1000直の過去レース(n1000_races.jsonl)にV3モデルを遡及適用。
   各rid: 出馬表+各馬の過去走を取得→calc+v2_live→モデル順位/得点/PWinを保存。
   出力: n1000_model.jsonl {rid, date, model:[{num,wavg,pwin,rank}], g12}
   途中再開可。usage: python3 n1000_model_harvest.py"""
import datetime, json, os, sys
import fetch_race as FR
import harvest as HV
import calc, v2_live

OUT = "n1000_model.jsonl"
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["rid"])
        except Exception: pass

races = [json.loads(l) for l in open("n1000_races.jsonl", encoding="utf-8")]
seen = set(); targets = []
for r in races:
    if r["rid"] in seen or r["rid"] in done: continue
    seen.add(r["rid"]); targets.append(r)
print(f"targets={len(targets)} (done={len(done)})", flush=True)

with open(OUT, "a", encoding="utf-8") as f:
    for i, r in enumerate(targets):
        rid, date = r["rid"], r["date"]
        try:
            su = FR.fetch_shutuba(rid, nar=False)
            dd = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
            race = HV.build_race_json(rid, su, dd, workers=3)
            res = calc.run(race)
            v2_live.rescore(race, res["rows"])
            rows = res["rows"]
            g12 = (rows[0]["wavg"] - rows[1]["wavg"]) / 12.0 if len(rows) > 1 else 0
            rec = dict(rid=rid, date=date, g12=round(g12, 3),
                       model=[dict(num=x["num"], wavg=x["wavg"], pwin=round(x["pwin"], 1),
                                   rank=x.get("rank", "")) for x in rows])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            print(f"[{i+1}/{len(targets)}] OK {rid} {date} g12={g12:.2f}", flush=True)
        except Exception as e:
            print(f"[{i+1}/{len(targets)}] FAIL {rid} {repr(e)[:60]}", flush=True)
print("DONE", flush=True)
