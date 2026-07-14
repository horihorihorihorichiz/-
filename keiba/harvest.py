# -*- coding: utf-8 -*-
"""過去レースの学習データ収穫（キャリブレーション用・リーク防止付き）。
   usage: python3 harvest.py <YYYYMMDD> [<YYYYMMDD>...] [--nar] [--workers 4] [--outdir hist]
   各レースを hist/<race_id>.json に保存: {"race": <race_json>, "result": <着順+払戻+全頭単勝オッズ>}
   リーク防止: 馬柱はレース当日を含めそれ以降の走を除外(days>0のみ)。
   ※過去レースでは公開タイム指数はほぼ取得不可 → tsi=Noneベースのデータになる点に注意。
"""
import argparse, datetime, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

import fetch_race as FR
import fetch_result as FRES
import pick_races as PR


def build_race_json(rid, su, race_date, workers):
    def one(hs):
        for attempt in range(2):
            try:
                career = FR.fetch_horse_results(hs["horse_id"], race_date,
                                                su["surface"], su["distance"])
                break
            except Exception:
                if attempt == 1:
                    career = []
                time.sleep(2)
        career = [r for r in career if r.get("days", 0) > 0]  # 当日以降を除外(リーク防止)
        off = FR.derive_off(career)
        csi = FR.derive_csi(career, su["venue"], su["distance"])
        races = career[:9]
        for r in races:
            r.pop("_baba", None)
            r.pop("_venue", None)
        return {
            "num": hs["num"], "name": hs["name"],
            "paper_style": FR.derive_style(races),
            "jockey_id": hs.get("jockey_id"),
            "trainer_id": hs.get("trainer_id"),
            "kinryo": hs["kin"], "weight": hs["weight"], "weight_change": hs["change"],
            "boost": 0,
            "last_race_days": races[0]["days"] if races else 30,
            "csi": csi, "offtrack_finishes": off, "races": races,
        }
    with ThreadPoolExecutor(max_workers=workers) as ex:
        horses = list(ex.map(one, su["horses"]))
    nar = rid[4:6] not in {"%02d" % i for i in range(1, 11)}
    return {
        "name": f"{su['race_name']} {su['surface']}{su['distance']}",
        "venue": rid[4:6] if nar else su["venue"],
        "surface": su["surface"], "distance": su["distance"], "field": su["field"],
        "baba": su["baba"], "today_vg": 2, "dist_cat": FR.dist_cat(su["distance"]),
        "dsi_haiten": 5, "today_tier": su["tier"], "nsi_haiten": 20,
        "race_id": rid, "horses": horses,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="+", help="YYYYMMDD")
    ap.add_argument("--nar", action="store_true", help="地方(既定はJRA)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--outdir", default="hist")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    total = ok = skip = fail = 0
    for date in args.dates:
        race_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
        try:
            lst = PR.fetch_list(date, nar=args.nar)
        except Exception as e:
            print(f"[{date}] レース一覧取得失敗: {e}", file=sys.stderr)
            continue
        print(f"[{date}] {len(lst)}レース", file=sys.stderr)
        for it in lst:
            rid = it["race_id"]
            total += 1
            path = os.path.join(args.outdir, f"{rid}.json")
            if os.path.exists(path):
                skip += 1
                continue
            try:
                su = FR.fetch_shutuba(rid, nar=args.nar)
                race = build_race_json(rid, su, race_date, args.workers)
                res = FRES.get_result(rid)
                if not res.get("payout", {}).get("単勝"):
                    raise RuntimeError("払戻なし(未確定?)")
                json.dump({"race": race, "result": res, "date": date},
                          open(path, "w", encoding="utf-8"), ensure_ascii=False)
                ok += 1
                print(f"  {rid} {it.get('venue','')}{it.get('r','')}R "
                      f"{su['field']}頭 OK ({ok}件目)", file=sys.stderr)
            except Exception as e:
                fail += 1
                print(f"  {rid} FAIL: {e}", file=sys.stderr)
            time.sleep(0.3)
    print(f"\n収穫完了: 対象{total} 成功{ok} 既存{skip} 失敗{fail} → {args.outdir}/",
          file=sys.stderr)


if __name__ == "__main__":
    main()
