# -*- coding: utf-8 -*-
"""紙上運用（ペーパートレード）Ver.100。実弾を張らずに新エンジンの成績を蓄積する。

   python3 paper.py run <YYYYMMDD> [--nar] [--budget 10000]   # その日の全レースを予想して記録
   python3 paper.py settle                                    # 結果が出たレースを精算
   python3 paper.py stats                                     # 集計（判定ライン: 150Rで回収90%超）

   記録先: paper_log.jsonl（1行=1レース。picks/edge/GO/精算結果）"""
import argparse, datetime, json, os, sys, time

import calc
import predict as PR
import fetch_result as FRES
import pick_races as PKR
import harvest as HV

LOG = "paper_log.jsonl"


def load_log():
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]


def save_log(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_run(date, nar, budget):
    done = {r["race_id"] for r in load_log()}
    lst = PKR.fetch_list(date, nar=nar)
    race_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
    print(f"[{date}] {len(lst)}レースを紙上運用", file=sys.stderr)
    logs = load_log()
    for it in lst:
        rid = it["race_id"]
        if rid in done:
            continue
        try:
            su = HV.FR.fetch_shutuba(rid, nar=nar)
            race = HV.build_race_json(rid, su, race_date, workers=4)
            with_hist = sum(1 for h in race["horses"] if h["races"])
            if with_hist < len(race["horses"]) * 0.7:
                logs.append(dict(race_id=rid, date=date, name=race.get("name", ""),
                                 venue=it.get("venue", ""), r=it.get("r", 0),
                                 ts=datetime.datetime.now().isoformat(timespec="seconds"),
                                 verdict="見送り", note="新馬/走歴不足でモデル対象外",
                                 edge=0, total=0, picks=[], settled=True, returned=0))
                save_log(logs)
                print(f"  {rid} 見送り(新馬/走歴不足)", file=sys.stderr)
                continue
            res = calc.run(race)
            try:
                import v2_live
                v2_live.rescore(race, res["rows"])   # 紙上運用もV2得点で
            except Exception:
                pass
            odds = (PR.fetch_nar(rid, race.get("field", 16))
                    if nar else PR.fetch_jra(rid))
            picks, total, dec = PR.build_buylist_ev(res["rows"], odds, budget=budget)
            edge = (sum(st*p*o for _, _, o, st, p, _ in picks)/(total or 1)) if picks else 0
            rec = dict(race_id=rid, date=date, name=race.get("name", ""),
                       venue=it.get("venue", ""), r=it.get("r", 0),
                       ts=datetime.datetime.now().isoformat(timespec="seconds"),
                       verdict=("GO" if picks else "見送り"),
                       edge=round(edge, 3), total=total,
                       picks=[[k, l, o, st, round(p, 4), round(ev, 3)]
                              for k, l, o, st, p, ev in picks],
                       # オッズドリフト研究用: 実行時点の単勝スナップショット(最終オッズとの差=スマートマネー)
                       odds_snap=odds.get("tan", {}),
                       settled=False, returned=None)
            logs.append(rec)
            save_log(logs)
            print(f"  {rid} {it.get('venue','')}{it.get('r','')}R "
                  f"{rec['verdict']} {len(picks)}点 {total}円", file=sys.stderr)
        except Exception as e:
            print(f"  {rid} FAIL: {e}", file=sys.stderr)
        time.sleep(0.3)


def cmd_settle():
    logs = load_log()
    n = 0
    for r in logs:
        if r.get("settled"):
            continue
        try:
            res = FRES.get_result(r["race_id"])
            if not res.get("payout", {}).get("単勝"):
                continue
            picks = [tuple(p) for p in r.get("picks", [])]
            import validate as V
            ret = V.settle(picks, res["payout"])
            r["settled"] = True
            r["returned"] = ret
            r["result_top3"] = res.get("top3", [])
            n += 1
        except Exception as e:
            print(f"  {r['race_id']} settle失敗: {e}", file=sys.stderr)
    save_log(logs)
    print(f"精算: {n}レース", file=sys.stderr)


def cmd_stats():
    logs = load_log()
    go = [r for r in logs if r["verdict"] == "GO"]
    settled = [r for r in go if r.get("settled")]
    staked = sum(r["total"] for r in settled)
    returned = sum(r.get("returned") or 0 for r in settled)
    hits = sum(1 for r in settled if (r.get("returned") or 0) > 0)
    print("=" * 56)
    print(" 紙上運用成績 (Ver.100 / paper_log.jsonl)")
    print("=" * 56)
    print(f" 記録レース   : {len(logs)}R（GO {len(go)} / 見送り {len(logs)-len(go)}）")
    print(f" 精算済みGO   : {len(settled)}R 的中{hits}R")
    if staked:
        print(f" 紙上投資     : {staked}円 / 紙上払戻 {returned}円 / 回収率 {returned/staked*100:.1f}%")
    remain = max(0, 150 - len(settled))
    print(f" 判定ラインまで: あと{remain}R（150R精算時点で回収90%超→少額実弾を検討、"
          f"70%未満→設計に戻る）")
    print("=" * 56)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run")
    p1.add_argument("date")
    p1.add_argument("--nar", action="store_true")
    p1.add_argument("--budget", type=int, default=10000)
    sub.add_parser("settle")
    sub.add_parser("stats")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a.date, a.nar, a.budget)
    elif a.cmd == "settle":
        cmd_settle()
    else:
        cmd_stats()


if __name__ == "__main__":
    main()
