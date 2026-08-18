# -*- coding: utf-8 -*-
"""オッズ時系列の自作収集（2026-08-18新設）。

   背景: netkeibaにもJRA公式にも「過去時点のオッズ」は存在しない(拡張側が全項目確認)。
   つまりオッズの時間変化は、発走前に自分でポーリングして作るしかない＝独自データになる。

   実測(n=20-34の予備調査): 発走15-30分前→確定 のオッズ変化(中央値)
     単勝0.73倍 / 複勝0.69倍 / ワイド0.96倍 / 三連複1.91倍
   三連複だけ逆方向に伸びる＝締切間際の資金が人気サイドに偏る市場の癖。
   これはモデルの予測精度に依存しない構造的な歪みで、現時点で最有望の攻め口。

   usage:
     python3 odds_timeline.py snap <race_id> [--tag T-30]   # 1レース1時点を記録
     python3 odds_timeline.py watch <YYYYMMDD>              # 当日の全レースを自動ポーリング
     python3 odds_timeline.py stats                          # 貯まった時系列の分析

   記録先: odds_timeline.jsonl (1行=1レース1時点・全券種)
   ※発走前のみ記録。確定後は fetch_result/hist_odds 側が持つ。
"""
import argparse, datetime, json, os, sys, time

LOG = "odds_timeline.jsonl"
# ポーリング時点(発走までの分)。市場の資金流入は締切直前に集中するため後半を密に取る
SNAP_MINUTES = [60, 45, 30, 20, 15, 10, 5, 3]


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def snap(race_id, tag=None, minutes_to_post=None):
    """1レース1時点の全券種オッズを記録する"""
    import predict as PR
    od = PR.fetch_jra(race_id)
    tan = {k: v for k, v in (od.get("tan") or {}).items() if v}
    if not tan:
        return None
    rec = dict(rid=race_id, at=jst_now().strftime("%Y-%m-%d %H:%M"),
               tag=tag, t_minus=minutes_to_post,
               tan=tan, fuku=od.get("fuku"), umaren=od.get("umaren"),
               wide=od.get("wide"), sanrenpuku=od.get("sanrenpuku"),
               odds_time=od.get("odds_time"))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def cmd_watch(date):
    """当日の全JRAレースについて、発走前の複数時点を自動記録する"""
    import pick_races as PKR
    lst = PKR.fetch_list(date, nar=False)
    print(f"[{date}] {len(lst)}レースを監視", file=sys.stderr)
    done = set()
    while True:
        now = jst_now()
        pending = 0
        for it in lst:
            rid = it["race_id"]
            post = it.get("time")
            if not post:
                continue
            try:
                ph, pm = int(post[:2]), int(post[3:5])
            except Exception:
                continue
            tmin = (ph*60+pm) - (now.hour*60+now.minute)
            if tmin < 0:
                continue
            pending += 1
            for m in SNAP_MINUTES:
                key = (rid, m)
                # その時点を過ぎた直後(誤差2分以内)に1回だけ記録
                if key not in done and m-2 <= tmin <= m:
                    r = snap(rid, tag=f"T-{m}", minutes_to_post=tmin)
                    done.add(key)
                    if r:
                        print(f"  {rid} T-{m} 記録", file=sys.stderr)
                    time.sleep(1)
        if pending == 0:
            print("全レース発走済み。終了", file=sys.stderr)
            break
        time.sleep(60)


def cmd_stats():
    """時点間のオッズ変化を券種別に集計する"""
    if not os.path.exists(LOG):
        print("記録なし")
        return
    from collections import defaultdict
    rows = [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    by = defaultdict(dict)
    for r in rows:
        by[r["rid"]][r.get("tag") or "?"] = r
    print(f"記録: {len(rows)}件 / {len(by)}レース")
    # 早い時点 → 遅い時点 の変化率を券種別に
    kinds = ["tan", "fuku", "umaren", "wide", "sanrenpuku"]
    pairs = defaultdict(list)
    for rid, snaps in by.items():
        tags = sorted(snaps, key=lambda t: -int(t[2:]) if t.startswith("T-") else 0)
        if len(tags) < 2:
            continue
        a, b = snaps[tags[0]], snaps[tags[-1]]
        for k in kinds:
            oa, ob = a.get(k) or {}, b.get(k) or {}
            for key in oa:
                try:
                    va, vb = float(str(oa[key]).replace(",", "")), float(str(ob[key]).replace(",", ""))
                    if va > 0:
                        pairs[k].append(vb/va)
                except Exception:
                    pass
    print(f"\n=== {tags[0] if by else ''} → {tags[-1] if by else ''} のオッズ変化 ===")
    for k in kinds:
        v = sorted(pairs[k])
        if v:
            print(f"  {k}: n={len(v)} 中央値{v[len(v)//2]:.3f}倍 平均{sum(v)/len(v):.3f}倍")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("snap")
    p1.add_argument("race_id")
    p1.add_argument("--tag", default=None)
    p2 = sub.add_parser("watch")
    p2.add_argument("date", nargs="?", default=None)
    sub.add_parser("stats")
    a = ap.parse_args()
    if a.cmd == "snap":
        r = snap(a.race_id, a.tag)
        print("記録:", r["at"] if r else "失敗", file=sys.stderr)
    elif a.cmd == "watch":
        cmd_watch(a.date or jst_now().strftime("%Y%m%d"))
    else:
        cmd_stats()


if __name__ == "__main__":
    main()
