# -*- coding: utf-8 -*-
"""通知台帳（2026-08-15新設）。「送るべき通知」と「送った実績」をファイルで機械照合する。

   背景: 8/15に中京12Rの買い通知が「別報告のついで1行」に混ざって正規送信されず、
   ワーカー再起動で予定自体が消える事故も複数回発生。人間(モデル)の記憶に頼らず、
   心拍が毎回 check() を呼んで欠落を検出→即送信する運用にするための土台。

   usage(セッション内から):
     import notify
     notify.plan("202601010708", "pre15", "13:35")    # 予定登録(レースID×種別×期限HH:MM)
     notify.mark("202601010708", "pre15")             # 送信実績を記録(プッシュ+チャット送信直後に呼ぶ)
     notify.check()                                    # 期限超過で未送信の予定を返す(心拍が毎回呼ぶ)
     python3 notify.py                                 # CLI: 現在の欠落一覧を表示

   種別: pre15(15分前通知) / freeze(3分前凍結) / result(当落報告) / recheck(大井等の再判定)
   台帳: notify_log.jsonl (1行={race_id, kind, due, planned_at, sent_at})
"""
import datetime, json, os, sys

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_log.jsonl")


def _now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def _load():
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]


def _save(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def plan(race_id, kind, due_hhmm, note=""):
    """通知予定を登録。due_hhmm='13:35' はJST当日。既存(同race_id×kind×当日)はスキップ"""
    rows = _load()
    today = _now().strftime("%Y%m%d")
    for r in rows:
        if r["race_id"] == race_id and r["kind"] == kind and r["date"] == today:
            return False
    rows.append(dict(race_id=race_id, kind=kind, date=today, due=due_hhmm,
                     note=note, planned_at=_now().strftime("%H:%M"), sent_at=None))
    _save(rows)
    return True


def mark(race_id, kind):
    """送信実績を記録(通知を出した直後に必ず呼ぶ)"""
    rows = _load()
    today = _now().strftime("%Y%m%d")
    hit = False
    for r in rows:
        if r["race_id"] == race_id and r["kind"] == kind and r["date"] == today:
            r["sent_at"] = _now().strftime("%H:%M")
            hit = True
    if not hit:   # 予定なしで送った場合も実績として残す(照合の土台を汚さない)
        rows.append(dict(race_id=race_id, kind=kind, date=today, due=None,
                         note="unplanned", planned_at=None, sent_at=_now().strftime("%H:%M")))
    _save(rows)
    return hit


def check(grace_min=2):
    """期限をgrace_min分以上過ぎて未送信の予定を返す。心拍が毎回呼び、返り値があれば即送信する"""
    rows = _load()
    now = _now()
    today = now.strftime("%Y%m%d")
    overdue = []
    for r in rows:
        if r["date"] != today or r["sent_at"] or not r.get("due"):
            continue
        h, m = map(int, r["due"].split(":"))
        due = now.replace(hour=h, minute=m, second=0)
        if (now - due).total_seconds() >= grace_min * 60:
            overdue.append(r)
    return overdue


if __name__ == "__main__":
    od = check()
    if not od:
        print("欠落なし")
    else:
        for r in od:
            print(f"⚠未送信: {r['race_id']} {r['kind']} 期限{r['due']} {r.get('note','')}")
    sys.exit(1 if od else 0)
