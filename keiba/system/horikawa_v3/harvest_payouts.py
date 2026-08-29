# -*- coding: utf-8 -*-
"""払戻を取得して保管庫に足す。

保管庫には単勝オッズしか入っておらず、複勝・ワイドの払戻が無いので
「3着以内に来る馬を当てる」という、このモデルが実際に狙っているものを
回収率で測れない。それを埋める。

db.netkeiba.com のレースページにある払い戻し表を読む。ログインは要らない。

  python harvest_payouts.py 20250801 20260221     期間を指定して取得
  python harvest_payouts.py --status               取得済みの件数を見る

途中で止めても、同じコマンドで続きから再開する。
取得の速さは config.RATE_RESULT に従う（既定 毎秒2件）。上げないこと。
"""
import json
import os
import re
import sqlite3
import sys
import time

import requests

sys.path.insert(0, os.getcwd())
import config  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/144.0 Safari/537.36")
BLOCK = re.compile(r'<dl class="pay_block">([\s\S]*?)</dl>')
ROW = re.compile(r'<th class="(\w+)"[^>]*>[^<]*</th>\s*<td[^>]*>([\s\S]*?)</td>\s*'
                 r'<td class="txt_r">([\s\S]*?)</td>')
KIND = {"tan": "単勝", "fuku": "複勝", "uren": "馬連", "wide": "ワイド",
        "utan": "馬単", "sanfuku": "三連複", "santan": "三連単"}


def parse(html):
    """{券種: [(組, 払戻円), ...]}。読めなければ None。"""
    m = BLOCK.search(html)
    if not m:
        return None
    out = {}
    for cls, combo, pay in ROW.findall(m.group(1)):
        k = KIND.get(cls)
        if not k:
            continue
        cs = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", x))
              for x in re.split(r"<br\s*/?>", combo)]
        ps = [re.sub(r"[^\d]", "", re.sub(r"<[^>]+>", "", x))
              for x in re.split(r"<br\s*/?>", pay)]
        out[k] = [(c, int(p)) for c, p in zip(cs, ps) if c and p]
    return out or None


def main():
    db = sqlite3.connect(config.DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS payouts (id TEXT PRIMARY KEY, body TEXT)")
    db.commit()

    if "--status" in sys.argv:
        n = db.execute("SELECT COUNT(*) FROM payouts").fetchone()[0]
        tot = db.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        print(f"払戻あり {n} / 保管庫のレース {tot}")
        for lo, hi, lab in [("20250801", "20260221", "探索窓"),
                            (config.CUT_VAL, "99999999", "未知期間")]:
            a = db.execute("SELECT COUNT(*) FROM races WHERE date>=? AND date<?",
                           (lo, hi)).fetchone()[0]
            b = db.execute("SELECT COUNT(*) FROM races r JOIN payouts p ON r.id=p.id "
                           "WHERE r.date>=? AND r.date<?", (lo, hi)).fetchone()[0]
            print(f"  {lab}: {b}/{a}")
        return

    lo = sys.argv[1] if len(sys.argv) > 1 else "20250801"
    hi = sys.argv[2] if len(sys.argv) > 2 else "20260221"
    have = {x[0] for x in db.execute("SELECT id FROM payouts")}
    ids = [x[0] for x in db.execute(
        "SELECT id FROM races WHERE date>=? AND date<? ORDER BY date, id", (lo, hi))
        if x[0] not in have]
    print(f"{lo}〜{hi}: 取得対象 {len(ids)}レース（取得済みは飛ばす）", flush=True)

    wait = 1.0 / max(config.RATE_RESULT, 0.1)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    ok = ng = 0
    for i, rid in enumerate(ids, 1):
        t0 = time.time()
        try:
            r = s.get(f"https://db.netkeiba.com/race/{rid}/", timeout=20)
            r.encoding = "euc-jp"
            p = parse(r.text) if r.status_code == 200 else None
        except Exception:
            p = None
        if p:
            db.execute("INSERT OR REPLACE INTO payouts VALUES (?,?)",
                       (rid, json.dumps(p, ensure_ascii=False)))
            ok += 1
        else:
            ng += 1
        if i % 100 == 0:
            db.commit()
            print(f"  {i}/{len(ids)}  取得 {ok} / 失敗 {ng}", flush=True)
        d = wait - (time.time() - t0)
        if d > 0:
            time.sleep(d)
    db.commit()
    print(f"完了 取得 {ok} / 失敗 {ng}", flush=True)


if __name__ == "__main__":
    main()
