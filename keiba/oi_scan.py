# -*- coding: utf-8 -*-
"""今日の大井を全レーススキャンし、確定パターンの発火を判定する。
   本命=三連複「1人気外し×モデル6位内」/ 既知=単勝15倍+×混戦。
   usage: python3 oi_scan.py <YYYYMMDD>"""
import datetime, sys
import pick_races as PK, fetch_race as FR, harvest as HV
import calc, v2_live, predict as PR, oi_patterns

date = sys.argv[1] if len(sys.argv) > 1 else "20260720"
d = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
lst = [it for it in PK.fetch_list(date, nar=True) if it.get("venue") == "大井"]
print(f"大井 {len(lst)}R スキャン開始 {datetime.datetime.utcnow()+datetime.timedelta(hours=9)} JST\n", flush=True)

for it in lst:
    rid = it["race_id"]
    try:
        su = FR.fetch_shutuba(rid, nar=True)
        race = HV.build_race_json(rid, su, d, workers=4)
        res = calc.run(race)
        v2_live.rescore(race, res["rows"])
        rows = res["rows"]
        order = [r["num"] for r in rows]
        g12 = (rows[0]["wavg"] - rows[1]["wavg"]) / 12.0 if len(rows) > 1 else None
        od = PR.fetch_nar(rid, race.get("field", len(order)))
        tan = {int(k): v for k, v in od.get("tan", {}).items() if v}
        if not tan:
            print(f"{it['r']:>2}R {it.get('time')} オッズ未取得(前売り前)", flush=True)
            continue
        pops = {n: i+1 for i, n in enumerate(sorted(tan, key=lambda h: tan[h]))}
        names = {h["num"]: h["name"] for h in race["horses"]}
        m1 = order[0]
        fires = oi_patterns.classify(order, tan, pops, g12=g12,
                                     dist=race.get("distance"), tier=race.get("today_tier"))
        head = (f"{it['r']:>2}R {it.get('time')} {it.get('name','')[:14]} "
                f"モデル1位={m1}{names.get(m1,'')[:6]}({tan.get(m1)}倍/{pops.get(m1)}人気) g12={g12:.3f}")
        if fires:
            print("★ " + head, flush=True)
            for f in fires:
                print(f"     {f[3]} {f[0]} ROI{f[2]:.0f}% | {f[1]}", flush=True)
        else:
            print("  " + head + " → 発火なし", flush=True)
    except Exception as e:
        print(f"{it['r']:>2}R err {repr(e)[:70]}", flush=True)
print("\nスキャン完了", flush=True)
