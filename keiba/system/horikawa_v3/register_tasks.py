# -*- coding: utf-8 -*-
"""レースごとに「発走10分前」に notify を1回起動する Windows タスクを登録する。

常駐プロセスは、途中で落ちるとそれ以降が全部止まる。レースごとに独立した
単発タスクにすれば、1つ転んでも次は動く。alerts JSON の各レースの発走時刻を
読み、その10分前ちょうどに python notify.py --race <id> を叩くタスクを作る。

  python register_tasks.py ../../data/alerts_20260830.json          登録
  python register_tasks.py ../../data/alerts_20260830.json --delete  当日分を消す
  python register_tasks.py ../../data/alerts_20260830.json --list     一覧

各タスクは判定に必要なものを引数で渡す:
  notify.py <alerts> --race <id> --odds-file <odds> --viz <viz> --board <board>
オッズは Chrome 側が odds ファイルに書き出したものを読む（notify の saved_odds）。
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

LEAD_MIN = 15
PREFIX = "HorikawaNotify"


def main():
    alerts = os.path.abspath(sys.argv[1])
    here = os.path.dirname(os.path.abspath(__file__))
    plan = json.load(open(alerts, encoding="utf-8"))
    date = plan["date"]
    day = f"{date[:4]}/{date[4:6]}/{date[6:8]}"

    py = sys.executable
    notify = os.path.join(here, "notify.py")
    data = os.path.normpath(os.path.join(here, "..", "..", "data"))
    odds = os.path.join(data, f"odds_live_{date}.json")
    viz = os.path.join(data, f"viz_{date}.json")
    board = os.path.join(data, f"board_{date}.html")

    if "--list" in sys.argv:
        subprocess.run(["schtasks", "/query", "/fo", "table"], check=False)
        return

    if "--delete" in sys.argv:
        for r in plan["races"]:
            name = f"{PREFIX}_{date}_{r['place']}{r['r']}"
            subprocess.run(["schtasks", "/delete", "/tn", name, "/f"],
                           capture_output=True)
        print("当日分のタスクを削除した")
        return

    now = datetime.now()
    made = skipped = 0
    for r in plan["races"]:
        hh, mm = r["post"].split(":")
        fire = (datetime.strptime(date, "%Y%m%d")
                .replace(hour=int(hh), minute=int(mm)) - timedelta(minutes=LEAD_MIN))
        if fire <= now:
            skipped += 1
            continue
        name = f"{PREFIX}_{date}_{r['place']}{r['r']}"
        # working dir を here にするため cmd /c cd ... で包む
        cmd = (f'cmd /c cd /d "{here}" ^& '
               f'"{py}" "{notify}" "{alerts}" --race {r["id"]} '
               f'--odds-file "{odds}" --viz "{viz}" --board "{board}" --lead {LEAD_MIN}')
        subprocess.run(
            ["schtasks", "/create", "/tn", name, "/tr", cmd,
             "/sc", "once", "/st", fire.strftime("%H:%M"), "/sd", day, "/f"],
            capture_output=True)
        made += 1
    print(f"タスクを {made}件 登録した（過ぎていた {skipped}件はとばした）")
    print(f"  オッズの置き場: {odds}")
    print("  ↑ このファイルに Chrome がオッズを書き出す前提。"
          "取れていないレースは通知されない。")


if __name__ == "__main__":
    main()
