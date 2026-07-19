# -*- coding: utf-8 -*-
"""発走前パターン番人（7/18ユーザー指摘「9時はオッズが安定してない」対応）。
   各レースの発走12分前にオッズを取り直し、その時点で乖離パターンが
   生きているレースだけ pattern_fires.log に書き出す（Monitorが拾って通知）。

   usage: python3 watch_day.py <YYYYMMDD> [--lead 12]
"""
import argparse, datetime, json, re, sys, time, urllib.request

import pick_races as PK
import fetch_race as FR
import harvest as HV
import calc
import v2_live
import patterns
import predict as PR

UA = {"User-Agent": "Mozilla/5.0"}


def post_time(rid):
    h = urllib.request.urlopen(urllib.request.Request(
        f"https://race.netkeiba.com/race/shutuba.html?race_id={rid}",
        headers=UA), timeout=30).read().decode("utf-8", "replace")
    m = re.search(r"(\d{1,2}:\d{2})発走", h)
    return m.group(1) if m else None


def check_race(rid, it, date, logf):
    """発走前判定: 乖離パターンの生死をその場のオッズで確定"""
    try:
        su = FR.fetch_shutuba(rid, nar=False)
        race = HV.build_race_json(rid, su, datetime.date(
            int(date[:4]), int(date[4:6]), int(date[6:8])), workers=4)
        res = calc.run(race)
        v2 = v2_live.rescore(race, res["rows"])
        odds = PR.fetch_jra(rid)
        tan = {int(k): v for k, v in odds.get("tan", {}).items() if v}
        if not tan or not v2:
            return
        order = [r["num"] for r in res["rows"]]
        gap12 = (res["rows"][0]["wavg"] - res["rows"][1]["wavg"])/12.0 if len(res["rows"]) > 1 else None
        pats = patterns.classify(order, tan, race.get("field", len(order)),
                                 surface=race.get("surface"), dist=race.get("distance"),
                                 tier=race.get("today_tier"), gap12=gap12)
        fires = [p for p in pats if p[3].startswith("◎") or p[3].startswith("△")]
        names = {h["num"]: h["name"] for h in race["horses"]}
        t1 = order[0]
        mr = sorted(tan, key=lambda h: tan[h]).index(t1)+1 if t1 in tan else 99
        if fires and tan.get(t1, 0) >= 7.0:
            best = fires[0]
            line = (f"FIRE {it.get('venue')}{it.get('r')}R {race.get('name','')[:14]} "
                    f"軸{t1}{names.get(t1,'')[:8]}({tan.get(t1)}倍{mr}人気) "
                    f"{best[0]} [{best[3]}] ROI{best[2]:.0f}% | {best[1]}")
        else:
            line = (f"pass {it.get('venue')}{it.get('r')}R 1位{t1}{names.get(t1,'')[:8]}"
                    f"={mr}人気 乖離なし")
        print(line, file=logf, flush=True)
    except Exception as e:
        print(f"err {rid} {e}", file=logf, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--lead", type=int, default=12, help="発走何分前に判定するか")
    a = ap.parse_args()
    lst = PK.fetch_list(a.date, nar=False)
    lst = [it for it in lst if "障害" not in it.get("name", "")]
    sched = []
    for it in lst:
        pt = post_time(it["race_id"])
        if not pt:
            continue
        hh, mm = map(int, pt.split(":"))
        sched.append((hh*60+mm, pt, it))
        time.sleep(0.2)
    sched.sort()
    logf = open("pattern_fires.log", "a", encoding="utf-8")
    print(f"WATCH開始 {a.date} 対象{len(sched)}R (発走{a.lead}分前判定)", file=logf, flush=True)
    for tmin, pt, it in sched:
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)  # JST
        now_min = now.hour*60 + now.minute
        target = tmin - a.lead
        if now_min > tmin:
            continue    # もう発走済み
        wait = (target - now_min)*60 - now.second
        if wait > 0:
            time.sleep(wait)
        check_race(it["race_id"], it, a.date, logf)
    print("WATCH終了", file=logf, flush=True)


if __name__ == "__main__":
    main()
