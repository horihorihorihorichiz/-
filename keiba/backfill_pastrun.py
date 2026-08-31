# -*- coding: utf-8 -*-
"""過去走の欠落フィールドを後追いで埋める（2026-08-18新設）。

   背景: fetch_race.py が db.netkeiba の馬個別ページを取得していたのに、
   「通過順」を4角だけ残して捨て、ペース前後半3F・走破タイム・着差を
   まったく保存していなかった（拡張側の手集めデータで発覚）。
   fetch_race は修正済みだが、既存 hist/ の8,700レースには入っていない。

   全レース再収穫は1レース十数リクエストで数日かかるため、
   **馬単位でキャッシュして重複を排除**する。同じ馬が複数レースに
   出ているので、馬IDでユニーク化すれば実リクエスト数は大幅に減る。

   usage:
     python3 backfill_pastrun.py --scan          # 対象馬数を数えるだけ
     python3 backfill_pastrun.py [--limit N]     # 実行(中断再開可)
   保存先: horse_cache/{horse_id}.json （全キャリアの走破成績）
"""
import argparse, datetime, json, os, sys, time

CACHE = "horse_cache"


def horse_ids_from_hist(hist_dir="hist"):
    """hist/ の各レースから出走馬のIDを集める。
       ※hist には horse_id が入っていない可能性があるため、
         その場合は出馬表から引き直す必要がある。まず構造を確認する。"""
    ids = {}
    for fn in os.listdir(hist_dir):
        try:
            d = json.load(open(os.path.join(hist_dir, fn), encoding="utf-8"))
        except Exception:
            continue
        for h in (d.get("race") or {}).get("horses") or []:
            hid = h.get("horse_id") or h.get("hid")
            if hid:
                ids[hid] = h.get("name")
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    ids = horse_ids_from_hist()
    print(f"hist から回収できた馬ID: {len(ids)}頭", file=sys.stderr)
    if not ids:
        print("※ hist に horse_id が保存されていない。"
              "出馬表(fetch_shutuba)から引き直す必要がある", file=sys.stderr)
        return
    os.makedirs(CACHE, exist_ok=True)
    todo = [h for h in ids if not os.path.exists(f"{CACHE}/{h}.json")]
    print(f"未取得: {len(todo)}頭", file=sys.stderr)
    if a.scan:
        return
    import fetch_race
    if a.limit:
        todo = todo[:a.limit]
    ok = 0
    for i, hid in enumerate(todo):
        try:
            rs = fetch_race.fetch_horse_results(hid, datetime.date.today(), "ダ", 1700)
            if rs:
                json.dump(rs, open(f"{CACHE}/{hid}.json", "w", encoding="utf-8"),
                          ensure_ascii=False)
                ok += 1
        except Exception as e:
            print(f"  {hid} 失敗: {e}", file=sys.stderr)
        time.sleep(0.5)
        if (i+1) % 100 == 0:
            print(f"  {i+1}/{len(todo)} 成功{ok}", file=sys.stderr)
    print(f"完了 {ok}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main()
