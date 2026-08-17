# -*- coding: utf-8 -*-
"""通知台帳（2026-08-15新設）。「送るべき通知」と「送った実績」をファイルで機械照合する。

   背景: 8/15に中京12Rの買い通知が「別報告のついで1行」に混ざって正規送信されず、
   ワーカー再起動で予定自体が消える事故も複数回発生。人間(モデル)の記憶に頼らず、
   心拍が毎回 check() を呼んで欠落を検出→即送信する運用にするための土台。

   usage(セッション内から):
     import notify
     notify.plan("202601010708", "pre15", "13:35", post="13:50")  # 予定登録(レースID×種別×期限)
     notify.mark("202601010708", "pre15")             # 送信実績を記録(プッシュ+チャット送信直後に呼ぶ)
     notify.check()                                    # 期限超過で未送信の予定を返す(心拍が毎回呼ぶ)
     notify.heartbeat()                                # ★心拍の刻印+停止ギャップ検出(毎回呼ぶ)
     notify.sweep()                                    # 欠落+ギャップを1発で(心拍/復帰時はこれ)
     notify.close(rid, "pre15", reason="発走済み")     # もう送る意味が無い予定を明示的に取り下げ
     python3 notify.py                                 # CLI: 現在の欠落一覧を表示
     python3 notify.py --heartbeat                     # CLI: 心拍を刻んでギャップ+欠落を表示(cron用)

   種別: pre15(15分前通知) / freeze(3分前凍結) / result(当落報告) / recheck(大井等の再判定)
   台帳: notify_log.jsonl (1行={race_id, kind, due, planned_at, sent_at, post, closed})
   心拍: notify_state.json ({last_beat, beats[], gaps[]})

   ★2026-08-17追加(8/16の28分停止で中京12Rの通知が飛んだ事故の再発防止):
     1. check() は日付をまたいだ遅延分も拾う(stale_hours以内・closedのみ除外)。
        「復帰した時に期限がとっくに過ぎている」通知を静かに落とさない。
     2. heartbeat() が最終実行時刻を刻み、次回実行時のギャップ(既定20分以上)を実行基盤停止として
        検出。ギャップ中に期限を迎えた予定を missed として列挙する。
"""
import datetime, json, os, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(_DIR, "notify_log.jsonl")
STATE = os.path.join(_DIR, "notify_state.json")

# 心拍は8分間隔(RULES §通知2)。20分空いたら「実行基盤が止まっていた」と見なす(2.5拍分)
GAP_MIN = 20
# 期限切れ通知を拾い続ける時間窓(時間)。日付をまたぐ夜間停止でも取りこぼさない
STALE_HOURS = 18


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


def _state():
    if not os.path.exists(STATE):
        return {}
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _dt(date8, hhmm):
    """'20260816','13:35' → datetime。不正なら None"""
    try:
        h, m = map(int, hhmm.split(":"))
        return datetime.datetime(int(date8[:4]), int(date8[4:6]), int(date8[6:8]), h, m)
    except Exception:
        return None


def plan(race_id, kind, due_hhmm, note="", post=None):
    """通知予定を登録。due_hhmm='13:35' はJST当日。既存(同race_id×kind×当日)はスキップ。
       post='13:50' を渡すと、遅延検出時に「まだ発走前(送れる)/発走後(手遅れ)」を区別できる。"""
    rows = _load()
    today = _now().strftime("%Y%m%d")
    for r in rows:
        if r["race_id"] == race_id and r["kind"] == kind and r["date"] == today:
            if post and not r.get("post"):
                r["post"] = post
                _save(rows)
            return False
    rows.append(dict(race_id=race_id, kind=kind, date=today, due=due_hhmm, post=post,
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


def close(race_id, kind, date=None, reason=""):
    """もう送る意味が無くなった予定を明示的に取り下げる(発走後の15分前通知など)。
       ★取り下げも記録に残す。「黙って消える」を作らないための明示操作。"""
    rows = _load()
    d = date or _now().strftime("%Y%m%d")
    n = 0
    for r in rows:
        if r["race_id"] == race_id and r["kind"] == kind and r["date"] == d and not r["sent_at"]:
            r["closed"] = _now().strftime("%m%d %H:%M")
            r["closed_reason"] = reason
            n += 1
    _save(rows)
    return n


def check(grace_min=2, stale_hours=STALE_HOURS):
    """期限をgrace_min分以上過ぎて未送信の予定を返す。心拍が毎回呼び、返り値があれば即送信する。

       2026-08-17強化: 当日分だけでなく stale_hours 以内の**日付をまたいだ遅延分も返す**
       (実行基盤が深夜停止→翌朝復帰でも取りこぼさない)。各行に late_min(遅延分)と
       stage(未発走/発走後/不明)を付与し、遅い順に並べて返す。close()済みは除外。"""
    rows = _load()
    now = _now()
    out = []
    for r in rows:
        if r.get("sent_at") or r.get("closed") or not r.get("due"):
            continue
        due = _dt(r.get("date", ""), r["due"])
        if due is None:
            continue
        late = (now - due).total_seconds() / 60.0
        if late < grace_min or late > stale_hours * 60:
            continue
        post = _dt(r.get("date", ""), r["post"]) if r.get("post") else None
        stage = "不明" if post is None else ("未発走(まだ送れる)" if now < post else "発走後(手遅れ)")
        e = dict(r)
        e["late_min"] = int(late)
        e["stage"] = stage
        out.append(e)
    return sorted(out, key=lambda r: -r["late_min"])


def heartbeat(source="cron", gap_min=GAP_MIN, record=True):
    """心拍の刻印＋実行基盤停止(ギャップ)の検出。心拍cron・セッション復帰時に毎回呼ぶ。

       返り値: dict(now, prev, elapsed_min, gap=None or {from,to,minutes,missed:[...]})
       gap が非Noneなら「その間、通知を出せる者が居なかった」＝ missed を必ず点検・送信する。"""
    st = _state()
    now = _now()
    now_s = now.strftime("%Y-%m-%d %H:%M")
    prev_s = st.get("last_beat")
    prev = None
    if prev_s:
        try:
            prev = datetime.datetime.strptime(prev_s, "%Y-%m-%d %H:%M")
        except Exception:
            prev = None
    gap = None
    elapsed = None
    if prev:
        elapsed = (now - prev).total_seconds() / 60.0
        if elapsed >= gap_min:
            missed = []
            for r in _load():
                if r.get("sent_at") or r.get("closed") or not r.get("due"):
                    continue
                due = _dt(r.get("date", ""), r["due"])
                if due and prev <= due <= now:
                    missed.append(dict(race_id=r["race_id"], kind=r["kind"],
                                       date=r["date"], due=r["due"], note=r.get("note", "")))
            gap = dict(**{"from": prev_s}, to=now_s, minutes=int(elapsed),
                       source=source, missed=missed)
            st.setdefault("gaps", []).append(gap)
            st["gaps"] = st["gaps"][-200:]
    st["last_beat"] = now_s
    st["last_source"] = source
    st["beats"] = (st.get("beats", []) + [now_s])[-500:]
    if record:
        _save_state(st)
    return dict(now=now_s, prev=prev_s, elapsed_min=(int(elapsed) if elapsed is not None else None),
                gap=gap, gap_min=gap_min)


def gaps(date=None):
    """記録済みの停止ギャップ一覧(date='YYYYMMDD'で当日分のみ)"""
    g = _state().get("gaps", [])
    if date:
        d = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        g = [x for x in g if str(x.get("to", "")).startswith(d) or str(x.get("from", "")).startswith(d)]
    return g


def sweep(source="cron", record=True):
    """心拍が毎回呼ぶ入口。{'gap':..., 'overdue':[...]} を返す。両方とも「即送信対象」。"""
    hb = heartbeat(source=source, record=record)
    return dict(gap=hb["gap"], elapsed_min=hb["elapsed_min"], last_beat=hb["prev"],
                overdue=check())


def selftest():
    """自己診断(selfcheck.pyが呼ぶ)。実台帳には触れず一時ファイルで検査する。"""
    global LOG, STATE
    import tempfile
    keep = (LOG, STATE)
    d = tempfile.mkdtemp(prefix="notify_selftest_")
    LOG, STATE = os.path.join(d, "l.jsonl"), os.path.join(d, "s.json")
    try:
        today = _now().strftime("%Y%m%d")
        now = _now()
        past = (now - datetime.timedelta(minutes=40)).strftime("%H:%M")
        fut = (now + datetime.timedelta(minutes=40)).strftime("%H:%M")
        plan("900000000001", "pre15", past, note="t", post=fut)
        plan("900000000002", "pre15", fut, note="t")
        od = check()
        assert [r["race_id"] for r in od] == ["900000000001"], f"期限超過の抽出が壊れた: {od}"
        assert od[0]["late_min"] >= 35 and od[0]["stage"].startswith("未発走"), od[0]
        # 送信実績を入れたら消える
        mark("900000000001", "pre15")
        assert not check(), "mark後も欠落として残る"
        # 前日分の遅延も拾う(日跨ぎ停止の再現)
        y = (now - datetime.timedelta(hours=5))
        rows = _load()
        rows.append(dict(race_id="900000000003", kind="result", date=y.strftime("%Y%m%d"),
                         due=y.strftime("%H:%M"), post=None, note="stale",
                         planned_at="00:00", sent_at=None))
        _save(rows)
        assert any(r["race_id"] == "900000000003" for r in check()), "日跨ぎの遅延を拾えない"
        # close したら消える
        close("900000000003", "result", date=y.strftime("%Y%m%d"), reason="test")
        assert not any(r["race_id"] == "900000000003" for r in check()), "close が効かない"
        # ギャップ検出: 28分前の心拍を偽装 → 8/16事故と同じ長さ
        st = _state()
        st["last_beat"] = (now - datetime.timedelta(minutes=28)).strftime("%Y-%m-%d %H:%M")
        _save_state(st)
        plan("900000000004", "pre15", (now - datetime.timedelta(minutes=10)).strftime("%H:%M"))
        hb = heartbeat(source="selftest")
        assert hb["gap"] and hb["gap"]["minutes"] >= 27, f"28分停止を検出できない: {hb}"
        assert any(m["race_id"] == "900000000004" for m in hb["gap"]["missed"]), \
            f"停止中に期限を迎えた予定を列挙できない: {hb['gap']}"
        hb2 = heartbeat(source="selftest")
        assert hb2["gap"] is None, "連続心拍で誤検出"
        assert gaps(today), "ギャップが記録されていない"
        return "欠落検出/日跨ぎ/close/28分ギャップ検出OK"
    finally:
        LOG, STATE = keep
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def _cli():
    args = sys.argv[1:]
    if "--selftest" in args:
        print(selftest())
        return 0
    hb = None
    if "--heartbeat" in args:
        hb = heartbeat(source="cli")
        if hb["gap"]:
            g = hb["gap"]
            print(f"⚠実行基盤停止を検出: {g['from']} → {g['to']} ({g['minutes']}分)")
            for m in g["missed"]:
                print(f"   停止中に期限超過: {m['race_id']} {m['kind']} 期限{m['due']} {m.get('note','')}")
        else:
            print(f"心拍OK (前回{hb['prev']} / 経過{hb['elapsed_min']}分)")
    if "--gaps" in args:
        for g in gaps():
            print(f"gap {g['from']} → {g['to']} ({g['minutes']}分) missed={len(g.get('missed', []))}")
    od = check()
    if not od:
        print("欠落なし")
    else:
        for r in od:
            print(f"⚠未送信: {r['race_id']} {r['kind']} 期限{r['due']}({r['date']}) "
                  f"{r['late_min']}分遅延 [{r['stage']}] {r.get('note','')}")
    return 1 if (od or (hb and hb["gap"])) else 0


if __name__ == "__main__":
    sys.exit(_cli())
