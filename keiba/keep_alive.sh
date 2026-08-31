#!/bin/bash
# 番人: 子プロセスが死んだら新しいログインシェルで再起動する（2026-08-21新設）。
#
# なぜ必要か: この環境のエージェントプロキシは再起動のたびにポートが変わる
# （実測: 33007→36237→33231、1日で2回）。nohupで起動した長時間プロセスは
# 起動時の HTTPS_PROXY を掴んだまま死ぬ。ログインシェル(bash -lc)はプロファイルから
# 現在のポートを引き直すので、「死んだら bash -lc で再起動」が最も単純で確実。
# 収穫(harvest_year)もオッズ収集(odds_timeline)も取得済みをスキップするので再起動は安全。
#
# usage: nohup bash keep_alive.sh <name> <最大再起動回数> <コマンド...> >> logs/keep_<name>.log 2>&1 &
#   例:  nohup bash keep_alive.sh odds822 200 python3 -u odds_timeline.py watch 20260822 \
#          >> logs/keep_odds822.log 2>&1 &
set -u
NAME="$1"; MAXRETRY="$2"; shift 2
CD="$(cd "$(dirname "$0")" && pwd)"
n=0
while [ "$n" -lt "$MAXRETRY" ]; do
  echo "[keep_alive:$NAME] $(TZ=Asia/Tokyo date '+%m/%d %H:%M') 起動 #$((n+1)) (proxy=$(bash -lc 'echo $HTTPS_PROXY'))"
  ( cd "$CD" && bash -lc "$(printf '%q ' "$@")" )
  rc=$?
  echo "[keep_alive:$NAME] $(TZ=Asia/Tokyo date '+%m/%d %H:%M') 終了 rc=$rc"
  # rc=0(正常完了)は再起動しない。
  # rc=3(odds_timelineの非開催日判定)は **JST6時以降のみ** 終了扱い。
  # 深夜はJRAのオッズ一覧がメンテで空になり偽の「非開催日」判定が出るため
  # (実測 2026-08-22 01:10)、朝までは20分待って再起動する。
  if [ "$rc" -eq 0 ]; then
    echo "[keep_alive:$NAME] 正常終了のため番人も終了"
    exit 0
  fi
  if [ "$rc" -eq 3 ]; then
    hh=$(TZ=Asia/Tokyo date +%H)
    if [ "$hh" -ge 6 ] && [ "$hh" -lt 22 ]; then
      echo "[keep_alive:$NAME] rc=3(非開催日判定・昼間)のため番人も終了"
      exit 0
    fi
    echo "[keep_alive:$NAME] rc=3だが深夜帯(メンテで一覧が空の可能性)。20分後に再試行"
    sleep 1200
  fi
  n=$((n+1))
  sleep 60
done
echo "[keep_alive:$NAME] 再起動上限 $MAXRETRY 回に到達。放置は危険なので目視確認が必要"
