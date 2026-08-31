# -*- coding: utf-8 -*-
"""JOCKEY_RAW_PROTOCOL.md Step A — jockey_id 欠損レースの回収 (side file, hist不変更).

usage: python3 jraw_fetch.py [--limit N] [--verify]
出力: jockey_fill.json  {rid: {num(str): jockey_id or None}}
"""
import argparse
import glob
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import fetch_race as FR

OUT = "jockey_fill.json"
SLEEP = float(os.environ.get("JRAW_SLEEP", "0.35"))
WORKERS = int(os.environ.get("JRAW_WORKERS", "6"))
_lock = threading.Lock()


def atomic_json(path, obj):
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_hist():
    recs = []
    for fp in sorted(glob.glob(os.path.join("hist", "*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        rid = os.path.basename(fp)[:-5]
        recs.append((rid, d))
    return recs


def one(rid):
    try:
        su = FR.fetch_shutuba(rid, nar=False)
        m = {str(h["num"]): h.get("jockey_id") for h in su["horses"]}
    except Exception:
        m = None
    time.sleep(SLEEP + random.random() * 0.2)
    return rid, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    recs = load_hist()

    fill = {}
    if os.path.exists(OUT):
        fill = json.load(open(OUT, encoding="utf-8"))

    if a.verify:
        # 既に jockey_id を持つレースから 50R 抽出し、shutuba再取得と一致率を測る
        random.seed(20260820)
        have = [(rid, d) for rid, d in recs
                if (d["race"].get("horses") or [])
                and all(h.get("jockey_id") for h in d["race"]["horses"])]
        sample = random.sample(have, 50)
        n_pair = n_match = 0
        miss = []
        for rid, d in sample:
            _, m = one(rid)
            if not m:
                miss.append(rid)
                continue
            for h in d["race"]["horses"]:
                jk = m.get(str(h["num"]))
                if jk is None:
                    continue
                n_pair += 1
                if jk == h["jockey_id"]:
                    n_match += 1
                else:
                    miss.append((rid, h["num"], h["jockey_id"], jk))
        print(f"[verify] pairs={n_pair} match={n_match} "
              f"rate={n_match/max(n_pair,1):.4f} mismatches={miss[:10]}")
        return

    todo = []
    for rid, d in recs:
        hs = d["race"].get("horses") or []
        if hs and not all(h.get("jockey_id") for h in hs) and rid not in fill:
            todo.append(rid)
    if a.limit:
        todo = todo[: a.limit]
    print(f"[fetch] todo={len(todo)} done={len(fill)}", file=sys.stderr)
    t0 = time.time()
    n_ok = n_ng = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (rid, m) in enumerate(ex.map(one, todo)):
            if m:
                fill[rid] = m
                n_ok += 1
            else:
                fill[rid] = {}
                n_ng += 1
            if (i + 1) % 200 == 0:
                with _lock:
                    atomic_json(OUT, fill)
                el = time.time() - t0
                print(f"[fetch] {i+1}/{len(todo)} ok={n_ok} ng={n_ng} "
                      f"{el/(i+1):.2f}s/R 残り{(len(todo)-i-1)*el/(i+1)/60:.0f}分",
                      file=sys.stderr, flush=True)
    atomic_json(OUT, fill)
    print(f"[fetch] 完了 ok={n_ok} ng={n_ng} total={len(fill)}")


if __name__ == "__main__":
    main()
