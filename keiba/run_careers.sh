#!/bin/sh
# careers を「未取得ゼロになるまで」繰り返す（corner_ids.json が育つのに追従する）
cd /home/user/-/keiba
for i in $(seq 1 200); do
  CORNER_WORKERS=8 CORNER_SLEEP=0.3 python3 corner_backfill.py careers 2>&1
  n=$(python3 - <<'PY'
import json,os
ids=json.load(open('corner_ids.json'))
u={h for v in ids.values() for h in (v or {}).values()}
have={f[:-5] for f in os.listdir('horse_cache')} if os.path.isdir('horse_cache') else set()
print(len(u-have))
PY
)
  echo "=== round $i 未取得 $n ==="
  [ "$n" = "0" ] && sleep 60
done
