#!/bin/bash
# 明日(8/22)の36レースの出馬表+過去9走を夜のうちに取得しておく(朝の時間節約)。
# 取得済み(race_<rid>.json有り)はスキップ。オッズは朝どうせ取り直すので無くてよい。
cd "$(dirname "$0")"
for rid in $(python3 -c "import json;print(' '.join(json.load(open('tomorrow_rids.json'))))"); do
  if [ -f "race_${rid}.json" ]; then echo "skip $rid"; continue; fi
  echo "== fetch $rid =="
  timeout 300 python3 fetch_race.py "$rid" --jra --out "race_${rid}.json" || echo "FAIL $rid"
  sleep 3
done
echo "prefetch done $(TZ=Asia/Tokyo date '+%H:%M')"
