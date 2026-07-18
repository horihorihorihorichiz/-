# -*- coding: utf-8 -*-
"""地方重賞+Jpn1-3の1年分収穫（7/18ユーザー指示・NAR検証用）。
   nar.netkeiba日程ページ→日付ごとのレース一覧でrace_id解決→hist_nar/に保存。
   ※JRA学習データ(hist/)とは分離。usage: python3 harvest_nar_grade.py
"""
import datetime, json, os, re, sys, time, urllib.request

import pick_races as PK
import fetch_race as FR
import fetch_result as FRES
import harvest as HV

UA = {"User-Agent": "Mozilla/5.0"}
OUT = "hist_nar"


def schedule(year, month):
    h = urllib.request.urlopen(urllib.request.Request(
        f"https://nar.netkeiba.com/top/schedule.html?year={year}&month={month}",
        headers=UA), timeout=30).read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(
            r'<td>(\d+)/(\d+)\([^)]+\)</td>\s*<td class="Race_Name">(?:<a[^>]*>)?([^<]+)'
            r'(?:</a>)?</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>(\d+)m</td>', h):
        mo, day, name, grade, venue, dist = m.groups()
        out.append(dict(date=f"{year}{int(mo):02d}{int(day):02d}",
                        name=name.strip(), grade=grade.strip(),
                        venue=venue.strip(), dist=int(dist)))
    return out


def norm(s):
    return re.sub(r"[\s第\d回]", "", s or "")


def main():
    os.makedirs(OUT, exist_ok=True)
    # 2025/7〜2026/7 の日程を集める
    entries = []
    for y, m in [(2025, mm) for mm in range(7, 13)] + [(2026, mm) for mm in range(1, 8)]:
        try:
            es = schedule(y, m)
            entries += es
            print(f"{y}-{m}: {len(es)}件", file=sys.stderr)
        except Exception as e:
            print(f"{y}-{m} 失敗 {e}", file=sys.stderr)
        time.sleep(0.3)
    entries = [e for e in entries if "20250719" <= e["date"] <= "20260718"]
    print(f"対象重賞: {len(entries)}件", file=sys.stderr)

    list_cache = {}
    ok = fail = 0
    for e in entries:
        try:
            date = e["date"]
            if date not in list_cache:
                list_cache[date] = PK.fetch_list(date, nar=True)
                time.sleep(0.3)
            cand = [it for it in list_cache[date]
                    if e["venue"] in it.get("venue", "") and
                    (norm(e["name"])[:5] in norm(it.get("name", "")) or
                     norm(it.get("name", ""))[:5] in norm(e["name"]))]
            if not cand:
                fail += 1
                print(f"  未解決: {date} {e['venue']} {e['name']}", file=sys.stderr)
                continue
            rid = cand[0]["race_id"]
            path = os.path.join(OUT, f"{rid}.json")
            if os.path.exists(path):
                continue
            rd = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
            su = FR.fetch_shutuba(rid, nar=True)
            race = HV.build_race_json(rid, su, rd, workers=3)
            res = FRES.get_result(rid)
            if not res.get("payout", {}).get("単勝"):
                raise RuntimeError("払戻なし")
            json.dump(dict(race=race, result=res, date=date,
                           grade=e["grade"], nar=True),
                      open(path, "w", encoding="utf-8"), ensure_ascii=False)
            ok += 1
            if ok % 25 == 0:
                print(f"  {ok}件収穫", file=sys.stderr)
            time.sleep(0.3)
        except Exception as ex:
            fail += 1
            print(f"  FAIL {e['date']} {e['name']}: {ex}", file=sys.stderr)
    print(f"完了: 成功{ok} 失敗{fail} (既存含む計{len(os.listdir(OUT))})", file=sys.stderr)


if __name__ == "__main__":
    main()
