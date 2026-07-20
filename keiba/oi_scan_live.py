# -*- coding: utf-8 -*-
"""大井の指定レース群を今のオッズでスキャンし、確定パターンの発火＋惜しい不発を判定。
   usage: python3 oi_scan_live.py <rid1> <rid2> ..."""
import datetime, sys
import fetch_race as FR, harvest as HV
import calc, v2_live, predict as PR, oi_patterns

d = datetime.date(2026, 7, 20)
for rid in sys.argv[1:]:
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
        names = {h["num"]: h["name"] for h in race["horses"]}
        r = rid[-2:] + "R"
        if not tan:
            print(f"{r} オッズ未取得", flush=True)
            continue
        pops = {n: i+1 for i, n in enumerate(sorted(tan, key=lambda h: tan[h]))}
        m1 = order[0]
        fires = oi_patterns.classify(order, tan, pops, g12=g12,
                                     dist=race.get("distance"), tier=race.get("today_tier"))
        head = (f"{r} {race.get('name','')[:12]} モデル1位={m1}{names.get(m1,'')[:6]}"
                f"({tan.get(m1)}倍/{pops.get(m1)}人気) g12={g12:.3f}")
        if fires:
            print("★発火 " + head, flush=True)
            for f in fires:
                print(f"    {f[3]} {f[0]} ROI{f[2]:.0f}% | {f[1]}", flush=True)
        else:
            # 惜しい不発の理由を明示
            o1 = tan.get(m1, 0)
            top6 = set(order[:6])
            cand = [n for n in tan if n != m1 and pops.get(n) in (2, 3, 4) and n in top6]
            why = []
            if not (2.5 <= o1 < 7.0):
                why.append(f"軸オッズ{o1}倍が範囲外(2.5-7)")
            elif g12 is None or not (0.15 <= g12 < 0.30):
                why.append(f"g12={g12:.3f}が範囲外(0.15-0.30)")
            elif len(cand) < 2:
                why.append(f"紐候補が{len(cand)}頭(市場2-4人気∩モデル6位内で2頭必要)")
            print(f"  不発 {head} → {'/'.join(why) or '条件外'}", flush=True)
    except Exception as e:
        print(f"{rid[-2:]}R err {repr(e)[:60]}", flush=True)
print("完了", flush=True)
