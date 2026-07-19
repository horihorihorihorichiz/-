# -*- coding: utf-8 -*-
"""NAR平場の大量収穫（地方専用システム用・7/19ユーザー指示「地方用に作り替えてもいい」）。
   南関東4場(大井/船橋/川崎/浦和)の全レースを日次で収穫し hist_nar_flat/ に保存。
   結果着順+最終単勝オッズはNAR結果ページから直接パース。
   usage: python3 harvest_nar_year.py [--start 20250719] [--end 20260718] [--venues 大井,船橋,川崎,浦和]
   再実行で続きから。commit/pushは外側で。"""
import argparse, datetime, json, os, sys, time

import pick_races as PK
import fetch_race as FR
import fetch_result as FRES
import harvest as HV
from fix_nar_orders import parse_nar_result

OUT = "hist_nar_flat"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20250719")
    ap.add_argument("--end", default="20260718")
    ap.add_argument("--venues", default="大井,船橋,川崎,浦和",
                    help="'ALL'で帯広ばんえい以外の全場")
    a = ap.parse_args()
    venues = None if a.venues == "ALL" else set(a.venues.split(","))
    os.makedirs(OUT, exist_ok=True)
    state_f = "harvest_nar_year.state"
    done = set()
    if os.path.exists(state_f):
        done = set(json.load(open(state_f)).get("done", []))
    d = datetime.date(int(a.start[:4]), int(a.start[4:6]), int(a.start[6:8]))
    d1 = datetime.date(int(a.end[:4]), int(a.end[4:6]), int(a.end[6:8]))
    total = 0
    while d <= d1:
        date = d.strftime("%Y%m%d")
        d += datetime.timedelta(days=1)
        if date in done:
            continue
        try:
            lst = PK.fetch_list(date, nar=True)
        except Exception as e:
            print(f"[{date}] 一覧失敗 {e}", file=sys.stderr)
            continue
        if venues is None:
            lst = [it for it in lst if "帯広" not in it.get("venue", "")]
        else:
            lst = [it for it in lst if it.get("venue") in venues]
        ok = 0
        for it in lst:
            rid = it["race_id"]
            path = os.path.join(OUT, f"{rid}.json")
            if os.path.exists(path):
                continue
            try:
                rd = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
                su = FR.fetch_shutuba(rid, nar=True)
                race = HV.build_race_json(rid, su, rd, workers=3)
                res = FRES.get_result(rid)
                order = parse_nar_result(rid)
                if len(order) < 5 or not res.get("payout", {}).get("単勝"):
                    raise RuntimeError("結果不備")
                res["order"] = order
                json.dump(dict(race=race, result=res, date=date, nar=True),
                          open(path, "w", encoding="utf-8"), ensure_ascii=False)
                ok += 1
            except Exception as e:
                print(f"  FAIL {rid} {e}", file=sys.stderr)
            time.sleep(0.25)
        done.add(date)
        json.dump({"done": sorted(done)}, open(state_f, "w"))
        if ok:
            total += ok
            print(f"[{date}] +{ok}R (計{len(os.listdir(OUT))})", file=sys.stderr)
    print(f"完了: {len(os.listdir(OUT))}R", file=sys.stderr)


if __name__ == "__main__":
    main()
