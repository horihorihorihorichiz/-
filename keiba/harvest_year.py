# -*- coding: utf-8 -*-
"""過去1年分のJRAレースを収穫→オッズ盤取得→(完走時)再学習まで自動で回すドライバ。
   中断されても再実行すれば続きから走る（日付・レース単位でスキップ）。
   数日ごとに git commit+push してデータを保全する。

   usage: python3 harvest_year.py [--start 20250713] [--end 20260705] [--commit-every 6]
"""
import argparse, datetime, json, os, subprocess, sys, time

import harvest as HV
import fetch_result as FRES
import pick_races as PKR
import predict as PR


def git(*args):
    try:
        return subprocess.run(["git"] + list(args), capture_output=True,
                              text=True, timeout=300, cwd=os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        print(f"  git {' '.join(args)} failed: {e}", file=sys.stderr)


def commit_push(msg):
    git("add", "hist", "hist_odds", "harvest_year.state")
    r = git("commit", "-m", msg)
    if r and r.returncode == 0:
        for i in range(4):
            p = git("push", "-u", "origin", "claude/stoic-ride-p35k9n")
            if p and p.returncode == 0:
                return True
            time.sleep(2*(i+1))
    return False


FORCE = False


def harvest_date(date, workers=3):
    """1日分: レース一覧→各レース収穫→オッズ盤。返り値=(成功数, 失敗数)"""
    race_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
    try:
        lst = PKR.fetch_list(date, nar=False)
    except Exception as e:
        print(f"[{date}] 一覧取得失敗: {e}", file=sys.stderr)
        return 0, 0
    ok = fail = 0
    for it in lst:
        rid = it["race_id"]
        name = it.get("name", "")
        if "障害" in name or "ジャンプS" in name:
            continue   # 障害レースはモデル対象外
        hpath = os.path.join("hist", f"{rid}.json")
        opath = os.path.join("hist_odds", f"{rid}.json")
        if FORCE or not os.path.exists(hpath):
            try:
                su = HV.FR.fetch_shutuba(rid, nar=False)
                race = HV.build_race_json(rid, su, race_date, workers)
                res = FRES.get_result(rid)
                if not res.get("payout", {}).get("単勝"):
                    raise RuntimeError("払戻なし")
                json.dump({"race": race, "result": res, "date": date},
                          open(hpath, "w", encoding="utf-8"), ensure_ascii=False)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"  {rid} FAIL: {e}", file=sys.stderr)
                time.sleep(1)
                continue
        if not os.path.exists(opath):
            try:
                o = PR.fetch_jra(rid)
                if o.get("tan"):
                    json.dump(o, open(opath, "w", encoding="utf-8"), ensure_ascii=False)
            except Exception as e:
                print(f"  {rid} odds FAIL: {e}", file=sys.stderr)
        time.sleep(0.25)
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20250713")
    ap.add_argument("--end", default="20260705")
    ap.add_argument("--commit-every", type=int, default=6, help="N開催日ごとにcommit+push")
    ap.add_argument("--force", action="store_true", help="既存ファイルも再取得(パーサ更新時)")
    ap.add_argument("--no-refit", action="store_true")
    a = ap.parse_args()
    global FORCE
    FORCE = getattr(a, "force", False)
    os.makedirs("hist", exist_ok=True)
    os.makedirs("hist_odds", exist_ok=True)

    state_f = "harvest_year.state"
    done_dates = set()
    if os.path.exists(state_f):
        done_dates = set(json.load(open(state_f)).get("done", []))

    d0 = datetime.date(int(a.start[:4]), int(a.start[4:6]), int(a.start[6:8]))
    d1 = datetime.date(int(a.end[:4]), int(a.end[4:6]), int(a.end[6:8]))
    total_ok = 0
    n_kaisai = 0
    d = d0
    while d <= d1:
        date = d.strftime("%Y%m%d")
        d += datetime.timedelta(days=1)
        # JRA開催は土日祝中心だが、非開催日は一覧1リクエストで空が返るだけなので全日なめる
        if date in done_dates:
            continue
        ok, fail = harvest_date(date)
        done_dates.add(date)
        json.dump({"done": sorted(done_dates)}, open(state_f, "w"))
        if ok:
            n_kaisai += 1
            total_ok += ok
            print(f"[{date}] +{ok}R (累計{total_ok}R)", file=sys.stderr)
        if n_kaisai and n_kaisai % a.commit_every == 0 and ok:
            commit_push(f"収穫: {date}まで 累計{len(os.listdir('hist'))}R")
    commit_push(f"収穫完了: {a.start}-{a.end} 全{len(os.listdir('hist'))}R")
    print(f"\n★収穫完了: 累計{len(os.listdir('hist'))}R", file=sys.stderr)

    if not a.no_refit:
        print("\n── 再学習パイプライン ──", file=sys.stderr)
        logf = open("refit_report.txt", "w", encoding="utf-8")
        for cmd in (
            [sys.executable, "fit_score.py", "--l2", "0.05", "--write"],
            [sys.executable, "fit_score.py", "--surface", "芝", "--l2", "0.08", "--write"],
            [sys.executable, "fit_score.py", "--surface", "ダ", "--l2", "0.08", "--write"],
            [sys.executable, "fit.py", "--test", "20260704,20260705,20260711,20260712", "--write"],
            [sys.executable, "validate.py", "--test", "20260704,20260705,20260711,20260712",
             "--scales", "0.9,1.0,1.1"],
        ):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=36000)
            logf.write(f"\n$ {' '.join(cmd[1:])}\n{r.stdout}\n{r.stderr[-2000:] if r.stderr else ''}")
            logf.flush()
        logf.close()
        git("add", "params.json", "refit_report.txt")
        git("commit", "-m", "過去1年データで再学習(fit_score/fit/validate) 結果=refit_report.txt")
        git("push", "-u", "origin", "claude/stoic-ride-p35k9n")
        print("★再学習完了: refit_report.txt 参照", file=sys.stderr)


if __name__ == "__main__":
    main()
