# -*- coding: utf-8 -*-
"""通過順(全区間)・ペース前後半3F・走破タイム・着差 の再収穫 — CORNER_PROTOCOL.md §1 の実装。

背景: fetch_race.py は 2026-08-18 に拡張済みだが、既存 hist/*.json は旧パーサ製で
      corner_all / pace_first / pace_last / run_time / margin を持たない。

設計（レート制限を最小化する）:
  step1  各レースの出馬表(1リクエスト)から horse_id を集める     → corner_ids.json
  step2  ユニークな horse_id ごとに全キャリアを1回だけ取得        → horse_cache/{id}.json
  step3  キャッシュから「レース日より前の9走」を切り出し、
         hist/<rid>.json の races[] に days で照合して新4項目を**追記**（既存キーは不変）

usage:
  python3 corner_backfill.py ids     [--limit N] [--all]   # step1
  python3 corner_backfill.py careers [--limit N]           # step2
  python3 corner_backfill.py apply                         # step3（何度でも再実行可）
  python3 corner_backfill.py status                        # 進捗だけ表示

中断再開可（済んだものはスキップ）。書き込みは一時ファイル→os.replace の原子書き込み。
"""
import argparse
import datetime
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

IDS = "corner_ids.json"
CACHE = "horse_cache"
HIST = "hist"
WF = "wf_preds_v3ext2.jsonl"
REF = datetime.date(2030, 1, 1)      # キャッシュ取得の基準日（レース日に依存させない）
NEW_KEYS = ("corner_all", "pace_first", "pace_last", "run_time", "margin")
SLEEP = float(os.environ.get("CORNER_SLEEP", "0.35"))
WORKERS = int(os.environ.get("CORNER_WORKERS", "6"))

_lock = threading.Lock()


def atomic_json(path, obj):
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_ids():
    if os.path.exists(IDS):
        try:
            return json.load(open(IDS, encoding="utf-8"))
        except Exception:
            pass
    return {}


def target_rids(use_all):
    """優先=wf_preds_v3ext2.jsonl の評価対象。--all で hist 全体。"""
    have = {fn[:-5] for fn in os.listdir(HIST) if fn.endswith(".json")}
    pri = []
    if os.path.exists(WF):
        seen = set()
        for line in open(WF, encoding="utf-8"):
            try:
                r = json.loads(line)["rid"]
            except Exception:
                continue
            if r in have and r not in seen:
                seen.add(r)
                pri.append(r)
    rest = sorted(have - set(pri), reverse=True)   # 新しい順（MINE後半から埋める）
    return pri + rest if use_all else pri


# ── step1: 出馬表から horse_id ─────────────────────────────────────────
def step_ids(limit, use_all):
    import fetch_race as FR
    ids = load_ids()
    todo = [r for r in target_rids(use_all) if r not in ids]
    print(f"[ids] 対象 {len(todo)}R (取得済 {len(ids)}R)", file=sys.stderr)
    if limit:
        todo = todo[:limit]
    n_ok = n_ng = 0
    t0 = time.time()

    def one(rid):
        nar = rid[4:6] not in {"%02d" % i for i in range(1, 11)}
        try:
            su = FR.fetch_shutuba(rid, nar=nar)
            m = {str(h["num"]): h["horse_id"] for h in su["horses"] if h.get("horse_id")}
        except Exception:
            m = None
        time.sleep(SLEEP + random.random() * 0.2)
        return rid, m

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (rid, m) in enumerate(ex.map(one, todo)):
            if m:
                ids[rid] = m
                n_ok += 1
            else:
                ids[rid] = {}          # 恒久失敗も記録（再試行の無限ループを避ける）
                n_ng += 1
            if (i + 1) % 200 == 0:
                with _lock:
                    atomic_json(IDS, ids)
                el = time.time() - t0
                print(f"[ids] {i+1}/{len(todo)} ok={n_ok} ng={n_ng} "
                      f"{el/ (i+1):.2f}s/R 残り{(len(todo)-i-1)*el/(i+1)/60:.0f}分",
                      file=sys.stderr, flush=True)
    atomic_json(IDS, ids)
    print(f"[ids] 完了 ok={n_ok} ng={n_ng} 総計{len(ids)}R", file=sys.stderr)


# ── step2: 馬キャリアのキャッシュ ──────────────────────────────────────
def step_careers(limit):
    import fetch_race as FR
    ids = load_ids()
    uniq = []
    seen = set()
    for rid in sorted(ids, reverse=True):
        for hid in (ids[rid] or {}).values():
            if hid not in seen:
                seen.add(hid)
                uniq.append(hid)
    os.makedirs(CACHE, exist_ok=True)
    have = {fn[:-5] for fn in os.listdir(CACHE) if fn.endswith(".json")}
    todo = [h for h in uniq if h not in have]
    print(f"[careers] ユニーク馬 {len(uniq)}頭 / 取得済 {len(have)} / 未取得 {len(todo)}",
          file=sys.stderr)
    if limit:
        todo = todo[:limit]
    t0 = time.time()
    cnt = [0, 0]

    def one(hid):
        try:
            rs = FR.fetch_horse_results(hid, REF, "ダ", 1700)
            for r in rs:
                r["_pdate"] = (REF - datetime.timedelta(days=r["days"])).isoformat()
                r.pop("days", None)
            atomic_json(os.path.join(CACHE, hid + ".json"), rs)
            ok = True
        except Exception:
            ok = False
        time.sleep(SLEEP + random.random() * 0.2)
        return ok

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, ok in enumerate(ex.map(one, todo)):
            cnt[0 if ok else 1] += 1
            if (i + 1) % 200 == 0:
                el = time.time() - t0
                print(f"[careers] {i+1}/{len(todo)} ok={cnt[0]} ng={cnt[1]} "
                      f"{el/(i+1):.2f}s/頭 残り{(len(todo)-i-1)*el/(i+1)/60:.0f}分",
                      file=sys.stderr, flush=True)
    print(f"[careers] 完了 ok={cnt[0]} ng={cnt[1]}", file=sys.stderr)


# ── step3: hist へ追記 ────────────────────────────────────────────────
def step_apply():
    ids = load_ids()
    n_race = n_horse = n_run = n_skip = 0
    touched = 0
    for rid in sorted(ids):
        m = ids.get(rid) or {}
        if not m:
            continue
        path = os.path.join(HIST, rid + ".json")
        if not os.path.exists(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        date = d.get("date") or ""
        if len(date) != 8:
            continue
        rd = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
        changed = False
        got_any = False
        for h in (d.get("race") or {}).get("horses") or []:
            hid = m.get(str(h.get("num")))
            if not hid:
                continue
            if h.get("horse_id") != hid:
                h["horse_id"] = hid
                changed = True
            cp = os.path.join(CACHE, hid + ".json")
            if not os.path.exists(cp):
                n_skip += 1
                continue
            try:
                car = json.load(open(cp, encoding="utf-8"))
            except Exception:
                continue
            # レース日より前の走だけを days 付きで並べる（fetch_race と同じ規約）
            by_days = {}
            for r in car:
                pd = r.get("_pdate")
                if not pd:
                    continue
                y, mo, dy = pd.split("-")
                dd = (rd - datetime.date(int(y), int(mo), int(dy))).days
                if dd > 0:
                    by_days.setdefault(dd, r)
            hit = False
            for rr in h.get("races") or []:
                src = by_days.get(rr.get("days"))
                if not src:
                    continue
                for k in NEW_KEYS:
                    if src.get(k) is not None and rr.get(k) is None:
                        rr[k] = src[k]
                        changed = True
                        hit = True
                        n_run += 1
            if hit:
                got_any = True
                n_horse += 1
        if changed:
            atomic_json(path, d)
            touched += 1
        if got_any:
            n_race += 1
    print(f"[apply] 新項目が入ったレース {n_race}R / 馬 {n_horse}頭 / 過去走 {n_run}走 "
          f"（書換 {touched}ファイル・キャッシュ未取得 {n_skip}頭分）", file=sys.stderr)


def step_status():
    ids = load_ids()
    n_id = sum(1 for v in ids.values() if v)
    have = len([x for x in os.listdir(CACHE)]) if os.path.isdir(CACHE) else 0
    uniq = {h for v in ids.values() for h in (v or {}).values()}
    print(f"ids: {len(ids)}R記録 / うちID取得成功 {n_id}R", file=sys.stderr)
    print(f"careers: ユニーク {len(uniq)}頭 / キャッシュ {have}", file=sys.stderr)
    # hist 側の被覆
    n_tot = n_new = 0
    for fn in sorted(os.listdir(HIST)):
        if not fn.endswith(".json"):
            continue
        n_tot += 1
        try:
            d = json.load(open(os.path.join(HIST, fn), encoding="utf-8"))
        except Exception:
            continue
        for h in (d.get("race") or {}).get("horses") or []:
            if any(r.get("corner_all") for r in (h.get("races") or [])):
                n_new += 1
                break
    print(f"hist: {n_tot}R 中 {n_new}R に corner_all あり", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ids", "careers", "apply", "status"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.cmd == "ids":
        step_ids(a.limit, a.all)
    elif a.cmd == "careers":
        step_careers(a.limit)
    elif a.cmd == "apply":
        step_apply()
    else:
        step_status()


if __name__ == "__main__":
    main()
