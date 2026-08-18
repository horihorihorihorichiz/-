# -*- coding: utf-8 -*-
"""組合せオッズ(複勝/ワイド/三連複/馬連)の一括収穫。2026-08-18新設。
   3着内特化システム(α_place=+0.04)の期待値検証には実オッズが必須。
   netkeiba JRA API type=2複勝/4馬連/5ワイド/7三連複 から全組合せを取得し hist_combo/ に保存。
   ※確定後のレースは確定オッズ、発走前は現在オッズ。台帳のレースは全て確定済み。
   usage: python3 harvest_combo_odds.py [--limit N] [--workers 1]"""
import argparse, json, os, sys, time
from predict import _http

OUT = "hist_combo"
BASE = "https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=%s&type=%d&action=init"
TYPES = {2: "fuku", 4: "umaren", 5: "wide", 7: "trio"}


def fetch_one(rid):
    out = {}
    for t, key in TYPES.items():
        try:
            d = json.loads(_http(BASE % (rid, t)))
            odds = (d.get("data") or {}).get("odds", {}).get(str(t), {})
            if odds:
                # 複勝(2)/ワイド(5)は[下限,上限,人気]の3要素。両方保存する
                if t in (2, 5):
                    out[key] = {k: [v[0], v[1]] for k, v in odds.items()}
                else:
                    out[key] = {k: v[0] for k, v in odds.items()}
        except Exception:
            pass
        time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ledger", default="wf_preds_v3ext2.jsonl")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rids = [json.loads(l)["rid"] for l in open(a.ledger, encoding="utf-8")]
    todo = [r for r in rids if not os.path.exists(f"{OUT}/{r}.json")]
    if a.limit:
        todo = todo[:a.limit]
    print(f"対象 {len(todo)}R (既取得 {len(rids)-len(todo)}R)", file=sys.stderr)
    ok = 0
    for i, rid in enumerate(todo):
        d = fetch_one(rid)
        if d.get("trio"):
            json.dump(d, open(f"{OUT}/{rid}.json", "w", encoding="utf-8"), ensure_ascii=False)
            ok += 1
        if (i+1) % 50 == 0:
            print(f"  {i+1}/{len(todo)} 成功{ok}", file=sys.stderr)
    print(f"完了 {ok}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main()
