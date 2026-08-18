# -*- coding: utf-8 -*-
"""オッズ時系列の自作収集（2026-08-18新設 / 08-18 実地検証で全面改修）。

   背景: netkeibaにもJRA公式にも「過去時点のオッズ」は存在しない(拡張側が全項目確認)。
   つまりオッズの時間変化は、発走前に自分でポーリングして作るしかない＝独自データになる。

   予備実測(n=20-34の小標本): 発走15-30分前→確定 のオッズ変化(中央値)
     単勝0.73倍 / 複勝0.69倍 / ワイド0.96倍 / 三連複1.91倍
   ★重要(設計上の訂正): パリミュチュエルなので**払戻は必ず確定オッズ**で決まる。
     「直前に買うと配当が伸びる」ということは起きない。この時系列が測るのは
     「**判定時刻に見えているオッズが、最終払戻オッズの偏った推定になっている**」度合いで、
     価値はそこ(=EV計算の系統誤差の補正と、過去ROIの先読みバイアスの実測)にある。
     詳細な事前登録は ODDS_DRIFT_PROTOCOL.md。

   usage:
     python3 odds_timeline.py watch [YYYYMMDD] [--profile full|lite|tan] [--dry]
     python3 odds_timeline.py snap <race_id> [--tag T-30] [--kind light|heavy|nk]
     python3 odds_timeline.py settle [YYYYMMDD]   # 確定オッズ(FINAL)と結果を追記
     python3 odds_timeline.py stats [--date …] [--pair T-30:FINAL]
     python3 odds_timeline.py probe               # 非開催日でも動く実地テスト
     python3 odds_timeline.py selftest            # 完全オフラインのロジック検査
     python3 odds_timeline.py compact [--keep-days 14]   # 古い日をgzipする

   記録先: odds_timeline/YYYYMMDD.jsonl (1行 = 1レース×1時点×1ソース)
     ※旧仕様の単一ファイル odds_timeline.jsonl があれば読み込みだけ互換で拾う。
"""
import argparse
import datetime
import gzip
import json
import os
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGDIR = os.path.join(_DIR, "odds_timeline")
LEGACY_LOG = os.path.join(_DIR, "odds_timeline.jsonl")
SCHEMA = 2

# ── ポーリング時点(発走までの分) ───────────────────────────────────────
# 決定根拠は ODDS_TIMELINE_NOTES.md §2。要点:
#  ・light(単勝・複勝・ワイド)は JRA公式で2リクエスト・約4秒 → 密に取れる。
#    終盤ほど資金流入が集中するので後半を密に(対数的に)配置する。
#  ・heavy(三連複)は軸ページ(出走頭数-2)本＝約30秒。lightの部分集合の時点だけに絞る。
#    T-3 は paper_rank.py の凍結時刻と一致させ、「凍結時に見えていた値」で直接比較できるようにした。
#  ・T-2 まで(T-1やT-0は取らない)。三連複は1回30秒かかるので T-2 に置くと締切をまたぐ。
#    最終値は settle が netkeiba の確定オッズ(FINAL)で無料で埋めるので、直前を削っても損はない。
SNAP_LIGHT = [180, 90, 60, 45, 30, 20, 15, 10, 7, 5, 3, 2]
SNAP_HEAVY = [60, 30, 15, 7, 3]
# netkeiba無料APIの遅延(実測40-50分・単勝)を組合せ券種でも実測するための併走サンプル。
# JRA公式の時点とわざとズラして、スケジューラの衝突を避ける。
SNAP_NK = [25, 6]

PROFILES = {
    "full": (SNAP_LIGHT, SNAP_HEAVY, SNAP_NK),
    "lite": ([60, 30, 20, 15, 10, 7, 5, 3, 2], [30, 15, 7, 3], [25, 6]),
    "tan":  (SNAP_LIGHT, [], [25, 6]),
}

# 許容遅れ(分)。この幅を過ぎた時点は「取り逃し」として捨てる(遅れた値を貼らない)
TOL = {"light": 2.0, "heavy": 3.0, "nk": 3.0}
# 概算所要秒(スケジューラの先読み用。実測: light 4.3s / heavy 28-32s / nk 9s)
COST = {"light": 5.0, "heavy": 32.0, "nk": 10.0}

DAY_TTL = 1200.0      # 開催ページHTMLのキャッシュ寿命(秒)
LIST_TTL = 600.0      # レース一覧(発走時刻)の再取得間隔(秒)。発走遅延に追従するため
MAX_FAIL = 3          # 同一レースで連続この回数失敗したら以後の予定を捨てる


# ── 基本ユーティリティ ────────────────────────────────────────────────
def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def log_path(date):
    return os.path.join(LOGDIR, "%s.jsonl" % date)


def append(rec):
    """1行追記。途中で落ちても既に書いた行が壊れないよう flush+fsync する。"""
    os.makedirs(LOGDIR, exist_ok=True)
    p = log_path(rec["date"])
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return p


def _open_any(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def iter_rows(dates=None):
    """記録を読む。YYYYMMDD.jsonl と .jsonl.gz と旧単一ファイルを透過的に扱う。"""
    paths = []
    if os.path.isdir(LOGDIR):
        for fn in sorted(os.listdir(LOGDIR)):
            if not (fn.endswith(".jsonl") or fn.endswith(".jsonl.gz")):
                continue
            d = fn.split(".")[0]
            if dates and d not in dates:
                continue
            paths.append(os.path.join(LOGDIR, fn))
    if os.path.exists(LEGACY_LOG) and not dates:
        paths.append(LEGACY_LOG)
    for p in paths:
        with _open_any(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def ev_key(rid, tag, kind):
    """予定の一意キー。**kind を含めること**（light と heavy は同じ tag/src を持つので
    src で括ると三連複が単複ワイドに食われて永久に取れなくなる。2026-08-18 実地テストで検出）。"""
    return (rid, tag, kind)


def attempts_of(date):
    """再開用。{(rid, tag, kind): (成功回数, 試行回数)}。
    watch を落として上げ直しても、既に取れている時点は二度取らない。"""
    out = {}
    for r in iter_rows([date]):
        k = ev_key(r.get("rid"), r.get("tag"), r.get("kind"))
        ok, n = out.get(k, (0, 0))
        out[k] = (ok + (1 if r.get("ok") else 0), n + 1)
    return out


def _f(x):
    try:
        v = float(str(x).replace(",", ""))
        return v if v > 0 else None
    except Exception:
        return None


def _clean(d):
    """{key: odds} を float化しつつ 0/None を落とす。"""
    out = {}
    for k, v in (d or {}).items():
        fv = _f(v)
        if fv is not None:
            out[str(k)] = fv
    return out


# ── 開催ページ / 軸cname のキャッシュ ───────────────────────────────────
class Nav:
    """JRA公式のナビゲーション結果を使い回す。

    1リクエストの実測は約2.3秒。素の fetch_official は毎回
    「インデックス→開催ページ→レースページ」の3リクエスト(約6秒)を払うが、
    開催ページは1開催に1枚あれば全レース・全券種のcnameが載っている。
    キャッシュすると light が 11.7秒 → 4.3秒 になる(実測)。
    """

    def __init__(self, ttl=DAY_TTL):
        self.ttl = ttl
        self.day = {}     # kaikey -> (html, t)
        self.axis = {}    # rid -> axis_cnames

    @staticmethod
    def kaikey(rid):
        return rid[4:6] + rid[0:4] + rid[6:8] + rid[8:10]

    def day_html(self, rid, force=False):
        import jra_odds as JO
        k = self.kaikey(rid)
        hit = self.day.get(k)
        if hit and not force and (time.time() - hit[1]) < self.ttl:
            return hit[0], None
        html, reason = JO.fetch_day_page(rid)
        if html:
            self.day[k] = (html, time.time())
        return html, reason

    def drop(self, rid):
        self.day.pop(self.kaikey(rid), None)
        self.axis.pop(rid, None)


# ── 1時点の取得 ───────────────────────────────────────────────────────
def snap_jra_light(rid, nav):
    """JRA公式(1-2分毎更新)から 単勝・複勝(下限/上限)・ワイド(下限/上限)。2リクエスト。"""
    import jra_odds as JO
    day, reason = nav.day_html(rid)
    if not day:
        return dict(ok=False, reason=reason or "開催ページ取得失敗")
    d = JO.fetch_official(rid, day_html=day)
    if not d.get("tan"):
        # cname が古い可能性 → 開催ページを取り直して1回だけ再試行
        nav.drop(rid)
        day, reason2 = nav.day_html(rid, force=True)
        if day:
            d = JO.fetch_official(rid, day_html=day)
    if not d.get("tan"):
        return dict(ok=False, reason=d.get("reason") or "単複オッズ0件")
    c = JO.fetch_official_combo(rid, kinds=("wide",), day_html=day)
    tan = _clean(d.get("tan"))
    return dict(ok=True, reason=c.get("reason"),
                tan=tan, fuku=_clean(d.get("fuku")), fuku_max=_clean(d.get("fuku_max")),
                wide=_clean(c.get("wide")), wide_max=_clean(c.get("wide_max")),
                runners=sorted(int(k) for k in tan),
                asof=d.get("asof"), kai_nichi=d.get("kai_nichi"),
                names={str(k): v for k, v in (d.get("names") or {}).items()})


def snap_jra_heavy(rid, nav, max_axis=None):
    """JRA公式から三連複。軸ページ(出走頭数-2)本＝実測 約28-32秒。"""
    import jra_odds as JO
    day, reason = nav.day_html(rid)
    if not day:
        return dict(ok=False, reason=reason or "開催ページ取得失敗")
    c = JO.fetch_official_combo(rid, kinds=("sanrenpuku",), day_html=day,
                                axis_cnames=nav.axis.get(rid), max_axis=max_axis)
    if not c.get("sanrenpuku") and nav.axis.get(rid):
        nav.axis.pop(rid, None)     # 取消でセレクトが変わった等 → 軸を取り直して1回だけ再試行
        c = JO.fetch_official_combo(rid, kinds=("sanrenpuku",), day_html=day,
                                    max_axis=max_axis)
    if c.get("axis_cnames"):
        nav.axis[rid] = c["axis_cnames"]
    trio = _clean(c.get("sanrenpuku"))
    if not trio:
        return dict(ok=False, reason=c.get("reason") or "三連複0件")
    n_all = len(c.get("axis_cnames") or [])
    return dict(ok=True, reason=c.get("reason"), sanrenpuku=trio,
                trio_axes=c.get("trio_axes"), trio_axes_all=n_all,
                trio_full=bool(max_axis is None and n_all and
                               c.get("trio_axes") == max(n_all - 2, 1)),
                asof=c.get("asof"), kai_nichi=c.get("kai_nichi"))


def snap_netkeiba(rid):
    """netkeiba無料API。7リクエストで全券種。値は遅れている可能性があるが
    odds_time(=API の official_datetime) に**実際の時刻**が入るので、
    分析はwall clockではなく odds_time を軸にすれば遅延ごと正しく使える。"""
    import predict as PR
    o = PR.fetch_jra(rid)
    tan = _clean(o.get("tan"))
    if not tan:
        return dict(ok=False, reason=o.get("ng_reason") or "netkeiba単勝0件")
    return dict(ok=True, reason=o.get("ng_reason"),
                tan=tan, fuku=_clean(o.get("fuku")), fuku_max=_clean(o.get("fuku_max")),
                wide=_clean(o.get("wide")), wide_max=_clean(o.get("wide_max")),
                umaren=_clean(o.get("umaren")), sanrenpuku=_clean(o.get("sanrenpuku")),
                runners=sorted(int(k) for k in tan),
                odds_time=o.get("odds_time"),
                odds_time_by_type=o.get("odds_time_by_type"))


SNAPPERS = {"light": snap_jra_light, "heavy": snap_jra_heavy, "nk": snap_netkeiba}
SRC = {"light": "jra", "heavy": "jra", "nk": "netkeiba"}


def snap(rid, kind, tag, meta=None, nav=None, max_axis=None, write=True,
         prev_runners=None):
    """1レース1時点1ソースを取って1行に記録する。戻り=記録した行(dict)。"""
    meta = meta or {}
    nav = nav or Nav()
    t0 = time.time()
    now = jst_now()
    try:
        if kind == "heavy":
            got = snap_jra_heavy(rid, nav, max_axis=max_axis)
        elif kind == "light":
            got = snap_jra_light(rid, nav)
        else:
            got = snap_netkeiba(rid)
    except Exception as e:
        got = dict(ok=False, reason="例外: %s: %s" % (type(e).__name__, e))
    rec = dict(v=SCHEMA, rid=rid, date=meta.get("date") or now.strftime("%Y%m%d"),
               tag=tag, kind=kind, src=SRC[kind],
               at=now.strftime("%Y-%m-%d %H:%M:%S"),
               post=meta.get("post"), venue=meta.get("venue"), r=meta.get("r"),
               name=meta.get("name"), jump=meta.get("jump"),
               t_minus=meta.get("t_minus"),
               t_minus_end=None, elapsed=round(time.time() - t0, 1))
    rec.update(got)
    if rec.get("t_minus") is not None:
        rec["t_minus_end"] = round(rec["t_minus"] - rec["elapsed"] / 60.0, 2)
    # 取消・除外の検出: 前の時点と出走馬集合が変わっていたら印を付ける
    # (取消はプール全体を組み替えるのでドリフト分析では別扱いにする必要がある)
    if prev_runners and rec.get("runners") is not None:
        gone = sorted(set(prev_runners) - set(rec["runners"]))
        if gone:
            rec["scratched"] = gone
    if write:
        append(rec)
    return rec


# ── スケジューラ ──────────────────────────────────────────────────────
def parse_post(date, post):
    """'15:45' → datetime。取れなければ None。"""
    try:
        h, m = int(post[:2]), int(post[3:5])
        d = datetime.datetime.strptime(date, "%Y%m%d")
        return d.replace(hour=h, minute=m)
    except Exception:
        return None


def build_events(races, date, profile):
    """レース一覧 → 予定イベント一覧。純関数(テスト可能)。"""
    light, heavy, nk = PROFILES[profile]
    ev = []
    for it in races:
        post = parse_post(date, it.get("time") or "")
        if not post:
            continue
        for kind, mins in (("light", light), ("heavy", heavy), ("nk", nk)):
            for m in mins:
                ev.append(dict(rid=it["race_id"], kind=kind, m=m,
                               tag="T-%d" % m, due=post - datetime.timedelta(minutes=m),
                               post=it.get("time"), venue=it.get("venue"),
                               r=it.get("r"), name=it.get("name")))
    ev.sort(key=lambda e: e["due"])
    return ev


def cmd_watch(date, profile="full", dry=False, max_axis=None, rids=None,
              until=None, force=False):
    import pick_races as PKR
    import re as _re
    JUMP = _re.compile(r"障害|ジャンプ|JS(?![a-z])")

    os.makedirs(LOGDIR, exist_ok=True)
    lock = os.path.join(LOGDIR, ".watch_%s.lock" % date)
    if os.path.exists(lock) and not force:
        try:
            pid = int(open(lock).read().split()[0])
            os.kill(pid, 0)
            print("既に watch が動いている(pid %d)。二重収集を避けるため終了。"
                  "強制するなら --force" % pid, file=sys.stderr)
            return 2
        except Exception:
            pass
    if not dry:
        with open(lock, "w") as f:
            f.write("%d %s\n" % (os.getpid(), jst_now().strftime("%F %T")))

    try:
        nav = Nav()
        att = attempts_of(date)
        fails = {}
        last_runners = {}
        listed_at = 0.0
        races, events = [], []
        done = set()
        n_ok = n_ng = n_miss = 0

        while True:
            now = jst_now()
            # 発走時刻は当日変わりうる(遅延)。一覧を定期的に取り直して予定を作り直す
            if time.time() - listed_at > LIST_TTL:
                try:
                    got = PKR.fetch_list(date, nar=False)
                    if got:
                        races = got
                        listed_at = time.time()
                except Exception as e:
                    print("  レース一覧の取得失敗: %s" % e, file=sys.stderr)
                if time.time() - listed_at > LIST_TTL:
                    # 取れなかった時は60秒後に再試行(毎ループ叩きに行かない)
                    listed_at = time.time() - LIST_TTL + 60
                if rids:
                    races = [it for it in races if it["race_id"] in rids]
                for it in races:
                    it["jump"] = bool(JUMP.search(it.get("name") or ""))
                events = build_events(races, date, profile)
                if not events:
                    print("[%s] 対象レースなし(JRA非開催?)" % date, file=sys.stderr)
                    return 0
                print("[%s] %dレース / 予定%d時点 (%s) profile=%s"
                      % (date, len(races), len(events),
                         now.strftime("%H:%M"), profile), file=sys.stderr)
                if dry:
                    for e in events[:40]:
                        print("   %s %s %-6s %s" % (e["due"].strftime("%H:%M"), e["rid"],
                                                    e["tag"], e["kind"]), file=sys.stderr)
                    print("   ...(計%d件)" % len(events), file=sys.stderr)
                    return 0

            meta_of = {it["race_id"]: it for it in races}
            due, future = [], []
            for e in events:
                key = ev_key(e["rid"], e["tag"], e["kind"])
                if key in done:
                    continue
                ok, n = att.get(key, (0, 0))
                if ok or n >= 2:            # 再開: 取得済み / 2回失敗した時点は諦める
                    done.add(key)
                    continue
                if fails.get(e["rid"], 0) >= MAX_FAIL:
                    done.add(key)
                    continue
                late = (now - e["due"]).total_seconds() / 60.0
                if late > TOL[e["kind"]]:
                    done.add(key)
                    n_miss += 1
                    continue
                if late >= 0:
                    due.append(e)
                else:
                    future.append(e)

            if not due and not future:
                print("全予定を消化。ok=%d ng=%d 取り逃し=%d" % (n_ok, n_ng, n_miss),
                      file=sys.stderr)
                return 0
            if until and now.strftime("%H:%M") >= until:
                print("--until %s に到達。終了(残り%d時点)" % (until, len(future)),
                      file=sys.stderr)
                return 0

            if due:
                # 締切に近いものから。同時点なら安い方(light)を先に=精度の高い点を守る
                due.sort(key=lambda e: (e["m"], COST[e["kind"]]))
                e = due[0]
                it = meta_of.get(e["rid"], {})
                tmin = round((parse_post(date, e["post"]) - now).total_seconds() / 60.0, 2)
                rec = snap(e["rid"], e["kind"], e["tag"], nav=nav, max_axis=max_axis,
                           prev_runners=last_runners.get(e["rid"]),
                           meta=dict(date=date, post=e["post"], venue=it.get("venue"),
                                     r=it.get("r"), name=it.get("name"),
                                     jump=it.get("jump"), t_minus=tmin))
                done.add(ev_key(e["rid"], e["tag"], e["kind"]))
                if rec.get("ok"):
                    n_ok += 1
                    fails[e["rid"]] = 0
                    if rec.get("runners"):
                        last_runners[e["rid"]] = rec["runners"]
                    sz = len(json.dumps(rec, ensure_ascii=False).encode())
                    print("  ✓ %s %s %-5s %-6s %4.1fs %5.1fKB %s"
                          % (now.strftime("%H:%M:%S"), e["rid"], e["tag"], e["kind"],
                             rec["elapsed"], sz / 1024.0, rec.get("asof") or
                             rec.get("odds_time") or ""), file=sys.stderr)
                else:
                    n_ng += 1
                    fails[e["rid"]] = fails.get(e["rid"], 0) + 1
                    print("  ✗ %s %s %-5s %-6s %s" % (now.strftime("%H:%M:%S"), e["rid"],
                                                      e["tag"], e["kind"], rec.get("reason")),
                          file=sys.stderr)
                continue

            # 次の予定まで寝る(最大20秒。発走遅延・一覧更新に追従するため長く寝ない)
            wait = (future[0]["due"] - now).total_seconds()
            time.sleep(max(1.0, min(20.0, wait)))
    finally:
        if not dry:
            try:
                os.remove(lock)
            except OSError:
                pass


# ── 確定オッズ(FINAL)と結果の追記 ──────────────────────────────────────
def cmd_settle(date=None):
    """終わったレースに、netkeibaの確定オッズ(=実際の払戻の元)と着順・払戻を追記する。
    パリミュチュエルなので払戻は確定オッズで決まる。FINAL が分析の終点。"""
    import predict as PR
    import fetch_result as FRES
    dates = [date] if date else sorted({r["date"] for r in iter_rows() if r.get("date")})
    total = 0
    for d in dates:
        rows = list(iter_rows([d]))
        rids = sorted({r["rid"] for r in rows if r.get("rid")})
        have = {r["rid"] for r in rows if r.get("tag") == "FINAL" and r.get("ok")}
        todo = [x for x in rids if x not in have]
        print("[%s] %dレース中 FINAL未取得 %d" % (d, len(rids), len(todo)), file=sys.stderr)
        for rid in todo:
            meta = next((r for r in rows if r["rid"] == rid and r.get("post")), {})
            try:
                res = FRES.get_result(rid)
            except Exception as e:
                print("  結果取得失敗 %s: %s" % (rid, e), file=sys.stderr)
                continue
            if not res.get("top3"):
                print("  未確定/結果なし %s" % rid, file=sys.stderr)
                continue
            try:
                o = PR.fetch_jra(rid)
            except Exception as e:
                print("  確定オッズ失敗 %s: %s" % (rid, e), file=sys.stderr)
                continue
            tan = _clean(o.get("tan"))
            rec = dict(v=SCHEMA, rid=rid, date=d, tag="FINAL", kind="final",
                       src="netkeiba", at=jst_now().strftime("%Y-%m-%d %H:%M:%S"),
                       post=meta.get("post"), venue=meta.get("venue"), r=meta.get("r"),
                       name=meta.get("name"), jump=meta.get("jump"),
                       t_minus=0.0, t_minus_end=0.0, ok=bool(tan),
                       reason=o.get("ng_reason"),
                       tan=tan, fuku=_clean(o.get("fuku")), fuku_max=_clean(o.get("fuku_max")),
                       wide=_clean(o.get("wide")), wide_max=_clean(o.get("wide_max")),
                       umaren=_clean(o.get("umaren")), sanrenpuku=_clean(o.get("sanrenpuku")),
                       runners=sorted(int(k) for k in tan),
                       odds_time=o.get("odds_time"),
                       odds_time_by_type=o.get("odds_time_by_type"),
                       result=dict(top3=res.get("top3"), payout=res.get("payout"),
                                   order=[dict(num=x["num"], rank=x["rank"],
                                               ninki=x.get("ninki"), odds=x.get("odds"))
                                          for x in res.get("order", [])]))
            append(rec)
            total += 1
            print("  ✓ FINAL %s 3着内%s" % (rid, res.get("top3")), file=sys.stderr)
            time.sleep(1.0)
    print("FINAL追記 %d件" % total)
    return 0


# ── 集計 ──────────────────────────────────────────────────────────────
KINDS = ["tan", "fuku", "wide", "sanrenpuku"]
BANDS = [(0, 5), (5, 15), (15, 50), (50, 200), (200, 1000), (1000, 10 ** 9)]


def _q(v, p):
    if not v:
        return float("nan")
    i = min(int(p * (len(v) - 1) + 0.5), len(v) - 1)
    return v[i]


MERGE_FIELDS = ("tan", "fuku", "fuku_max", "wide", "wide_max", "umaren",
                "sanrenpuku", "runners", "names", "scratched",
                "asof", "odds_time", "trio_axes", "trio_full")


def index_rows(dates=None, src="jra"):
    """{rid: {tag: 統合row}}。

    同じ tag には light(単複ワイド) と heavy(三連複) の**別々の行**が来るので、
    上書きではなく券種フィールドごとに合流させる(上書きすると三連複か単複のどちらかが消える)。
    同一 (rid,tag,kind) が重複したら後勝ち。
    src: 既定 "jra"(=JRA公式のみ。FINALだけは常に通す)。
         **ソースを跨いで合流させてはいけない**（netkeibaは実時刻がずれているので、
         同じ T-30 でも中身の時刻が違う）。src=None にすると tag が "T-30@netkeiba"
         のようにソース付きになり、混ざらない。"""
    by = {}
    for r in iter_rows(dates):
        if not r.get("ok"):
            continue
        if src and r.get("src") != src and r.get("tag") != "FINAL":
            continue
        tag = r.get("tag") if (src or r.get("tag") == "FINAL") else \
            "%s@%s" % (r.get("tag"), r.get("src"))
        cur = by.setdefault(r["rid"], {}).setdefault(
            tag, dict(rid=r["rid"], tag=tag, date=r.get("date"),
                               post=r.get("post"), venue=r.get("venue"), r=r.get("r"),
                               jump=r.get("jump"), t_minus=r.get("t_minus"),
                               at=r.get("at"), result=None))
        for f in MERGE_FIELDS:
            if r.get(f):
                cur[f] = r[f]
        if r.get("result"):
            cur["result"] = r["result"]
    return by


def drift(by, a_tag, b_tag, kind, skip_scratch=True):
    """a_tag→b_tag の同一キーのオッズ比を集める。戻り=[(比, aのオッズ, rid, key)]"""
    out = []
    for rid, snaps in by.items():
        a, b = snaps.get(a_tag), snaps.get(b_tag)
        if not a or not b:
            continue
        if skip_scratch and (a.get("runners") and b.get("runners")
                             and set(a["runners"]) != set(b["runners"])):
            continue
        oa, ob = a.get(kind) or {}, b.get(kind) or {}
        for k, va in oa.items():
            vb = ob.get(k)
            if va and vb:
                out.append((vb / va, va, rid, k))
    return out


def report_pair(by, a_tag, b_tag, min_n=5):
    print("\n=== %s → %s ===" % (a_tag, b_tag))
    any_row = False
    for kind in KINDS:
        d = drift(by, a_tag, b_tag, kind)
        if len(d) < min_n:
            continue
        any_row = True
        v = sorted(x[0] for x in d)
        nr = len({x[2] for x in d})
        print("  %-11s n=%6d (%3dR)  中央値%.3f倍  平均%.3f  25%%%.3f 75%%%.3f  "
              "伸びた割合%.0f%%"
              % (kind, len(v), nr, _q(v, .5), sum(v) / len(v), _q(v, .25), _q(v, .75),
                 100.0 * sum(1 for x in v if x > 1) / len(v)))
        # オッズ帯別(=人気帯の代理)。ドリフトが帯で違うなら「補正」が設計できる
        for lo, hi in BANDS:
            g = sorted(x[0] for x in d if lo <= x[1] < hi)
            if len(g) >= min_n:
                print("      %5g-%-6g n=%6d 中央値%.3f" % (lo, hi, len(g), _q(g, .5)))
    if not any_row:
        print("  (この組の共通データがまだ無い)")


def overround(row, kind):
    """その時点の「暗黙確率の合計」= Σ(1/オッズ)。控除率の逆数に収束するはずの量。

    これが時点で動くなら、ドリフトの主因は「馬ごとの人気の入れ替わり」ではなく
    **プール全体の形成度合い(＝早い時点のオッズが系統的に短い/長い)**ということになる。
    予備実測の 単勝0.73倍 / 三連複1.91倍 が「馬券の妙味」なのか「ただの発売初期の歪み」なのかを
    モデル無しで切り分けられる、最も安い診断値。"""
    d = row.get(kind) or {}
    vals = [v for v in d.values() if v]
    if not vals:
        return None
    return sum(1.0 / v for v in vals)


def report_overround(by, min_n=3):
    print("\n=== 時点別の暗黙確率合計 Σ(1/オッズ) [控除率の逆数に一致するのが正常] ===")
    tags = {}
    for snaps in by.values():
        for tag, row in snaps.items():
            for kind in KINDS:
                o = overround(row, kind)
                if o:
                    tags.setdefault((tag, kind), []).append((o, len(row.get(kind) or {})))

    def order(t):
        return -int(t[2:]) if t.startswith("T-") and t[2:].isdigit() else 10 ** 6

    seen = sorted({t for t, _ in tags}, key=order)
    head = "  %-7s" % "時点" + "".join("%18s" % k for k in KINDS)
    print(head)
    for tag in seen:
        cells = []
        for kind in KINDS:
            v = tags.get((tag, kind))
            if not v or len(v) < min_n:
                cells.append("%18s" % "-")
                continue
            o = sorted(x[0] for x in v)
            keys = sorted(x[1] for x in v)
            cells.append("%18s" % ("%.3f(%dR,%d点)" % (_q(o, .5), len(o), _q(keys, .5))))
        print("  %-7s" % tag + "".join(cells))


def cmd_stats(dates=None, pairs=None, src="jra", min_n=5):
    by = index_rows(dates, src=src)
    rows = list(iter_rows(dates))
    if not rows:
        print("記録なし (%s)" % LOGDIR)
        return 0
    ok = [r for r in rows if r.get("ok")]
    tags = {}
    for r in ok:
        tags[r.get("tag")] = tags.get(r.get("tag"), 0) + 1
    print("記録: %d行(成功%d) / %dレース / %d日"
          % (len(rows), len(ok), len({r["rid"] for r in rows}),
             len({r["date"] for r in rows if r.get("date")})))
    print("時点別: " + " ".join("%s=%d" % (k, v) for k, v in
                                sorted(tags.items(), key=lambda x: -x[1])))
    fin = [r for r in ok if r.get("tag") == "FINAL"]
    print("FINAL(確定オッズ+結果): %dレース" % len({r["rid"] for r in fin}))
    if not pairs:
        # 事前登録の主要比較(ODDS_DRIFT_PROTOCOL.md §3)
        pairs = [("T-30", "T-3"), ("T-15", "T-3"), ("T-30", "FINAL"),
                 ("T-15", "FINAL"), ("T-3", "FINAL")]
    report_overround(by, min_n=min(3, min_n))
    for a, b in pairs:
        report_pair(by, a, b, min_n=min_n)
    # netkeiba の遅延実測
    lag = []
    for r in ok:
        # 発走前の併走サンプル(kind="nk")だけ。FINALは発走後なので遅延の意味が無い
        if r.get("kind") == "nk" and r.get("odds_time") and r.get("at"):
            try:
                t1 = datetime.datetime.strptime(r["odds_time"], "%Y-%m-%d %H:%M:%S")
                t0 = datetime.datetime.strptime(r["at"], "%Y-%m-%d %H:%M:%S")
                lag.append((t0 - t1).total_seconds() / 60.0)
            except Exception:
                pass
    if lag:
        lag.sort()
        print("\n=== netkeiba無料オッズの遅延(取得時刻 - official_datetime) ===")
        print("  n=%d 中央値%.1f分 最小%.1f 最大%.1f" % (len(lag), _q(lag, .5), lag[0], lag[-1]))
    return 0


# ── 実地テスト(非開催日でも動く) ────────────────────────────────────────
def cmd_probe(rid=None, heavy=True):
    """JRA公式のオッズ一覧に載っている「直近開催」のレースを実際に叩いて、
    取得・パース・記録・サイズ・所要時間を確認する。非開催日でも動く。
    記録は一時ファイルに書き、本番ログ(odds_timeline/)は汚さない。"""
    import re
    import jra_odds as JO
    global LOGDIR
    real = LOGDIR
    LOGDIR = os.path.join(_DIR, "odds_timeline_probe")
    try:
        if not rid:
            idx = JO._http(JO.ACCESS_O, "cname=" + JO.ODDS_INDEX_CNAME)
            keys = sorted(set(re.findall(r"sw15orl\d{2}(\d{10})\d{8}/", idx)))
            if not keys:
                print("⏭ JRA公式オッズ一覧に開催が無い(当日/前日がJRA非開催)。"
                      "週末は掲載されるのでその時に再実行。")
                return 0
            k = keys[-1]
            rid = k[2:6] + k[:2] + k[6:8] + k[8:10] + "11"
            print("掲載中の開催: %s → 検査対象 %s" % (keys, rid))
        nav = Nav()
        sizes = {}
        for kind in (["light", "heavy"] if heavy else ["light"]):
            rec = snap(rid, kind, "PROBE", nav=nav,
                       meta=dict(date=jst_now().strftime("%Y%m%d"), t_minus=None))
            n = len(json.dumps(rec, ensure_ascii=False).encode())
            sizes[kind] = n
            cnt = {c: len(rec.get(c) or {}) for c in
                   ("tan", "fuku", "wide", "wide_max", "sanrenpuku") if rec.get(c)}
            print("  %-6s ok=%s %.1fs %6.1fKB %s asof=%s %s"
                  % (kind, rec.get("ok"), rec["elapsed"], n / 1024.0, cnt,
                     rec.get("asof"), rec.get("reason") or ""))
            if not rec.get("ok"):
                print("  ❌ %s が取れない: %s" % (kind, rec.get("reason")))
                return 1
        rec = snap(rid, "nk", "PROBE", nav=nav,
                   meta=dict(date=jst_now().strftime("%Y%m%d"), t_minus=None))
        n = len(json.dumps(rec, ensure_ascii=False).encode())
        sizes["nk"] = n
        print("  %-6s ok=%s %.1fs %6.1fKB odds_time=%s"
              % ("nk", rec.get("ok"), rec["elapsed"], n / 1024.0, rec.get("odds_time")))
        # 1日分のディスク見積り(gzip率はこのprobeの実データで実測する)
        light, hv, nk = PROFILES["full"]
        per_race = (len(light) * sizes.get("light", 0) + len(hv) * sizes.get("heavy", 0)
                    + len(nk) * sizes.get("nk", 0) + sizes.get("nk", 0))
        ratio = 1.0
        try:
            p = os.path.join(LOGDIR, jst_now().strftime("%Y%m%d") + ".jsonl")
            raw = open(p, "rb").read()
            ratio = len(raw) / max(len(gzip.compress(raw, 9)), 1)
        except Exception:
            pass
        yr = per_race * 72 * 52 / 1024.0 ** 2
        print("\n見積り(profile=full・36レース/日): 1レース%.0fKB → 1日%.1fMB → "
              "1週末%.1fMB → 1年(52週)%.0fMB / gzip後%.0fMB(実測比 1/%.1f)"
              % (per_race / 1024.0, per_race * 36 / 1024.0 ** 2,
                 per_race * 72 / 1024.0 ** 2, yr, yr / ratio, ratio))
        print("✅ probe OK")
        return 0
    finally:
        LOGDIR = real


def cmd_selftest():
    """完全オフライン。スケジュール生成・再開判定・ドリフト集計の算数を検査する。"""
    import tempfile
    global LOGDIR
    real = LOGDIR
    fails = []

    def eq(name, got, want):
        if got != want:
            fails.append("%s: got=%r want=%r" % (name, got, want))

    races = [dict(race_id="202605010101", time="09:50", venue="東京", r=1, name="1歳新馬"),
             dict(race_id="202605010111", time="15:45", venue="東京", r=11, name="重賞")]
    ev = build_events(races, "20260822", "full")
    eq("イベント数", len(ev),
       len(races) * (len(SNAP_LIGHT) + len(SNAP_HEAVY) + len(SNAP_NK)))
    eq("時系列順", ev == sorted(ev, key=lambda e: e["due"]), True)
    e0 = [e for e in ev if e["rid"] == "202605010111" and e["tag"] == "T-3"
          and e["kind"] == "light"][0]
    eq("T-3の時刻", e0["due"].strftime("%H:%M"), "15:42")
    eq("post欠損は無視", len(build_events([dict(race_id="x", time="")], "20260822", "full")), 0)

    try:
        LOGDIR = tempfile.mkdtemp(prefix="ot_selftest_")
        a = dict(v=SCHEMA, rid="R1", date="20260822", tag="T-30", kind="light", src="jra",
                 at="2026-08-22 15:15:00", ok=True, runners=[1, 2, 3],
                 tan={"1": 2.0, "2": 10.0}, sanrenpuku={"1-2-3": 100.0})
        b = dict(a, tag="T-3", at="2026-08-22 15:42:00",
                 tan={"1": 1.0, "2": 20.0}, sanrenpuku={"1-2-3": 200.0})
        c = dict(a, rid="R2", tag="T-30", runners=[1, 2, 3], tan={"1": 4.0})
        d = dict(a, rid="R2", tag="T-3", runners=[1, 2], tan={"1": 8.0})   # 取消あり
        for r in (a, b, c, d):
            append(r)
        eq("再開キー", attempts_of("20260822")[("R1", "T-30", "light")], (1, 1))
        by = index_rows(["20260822"])
        dr = sorted(x[0] for x in drift(by, "T-30", "T-3", "tan"))
        eq("単勝ドリフト(取消レース除外)", dr, [0.5, 2.0])
        eq("取消を含めれば3点", len(drift(by, "T-30", "T-3", "tan", skip_scratch=False)), 3)
        eq("三連複ドリフト", [x[0] for x in drift(by, "T-30", "T-3", "sanrenpuku")], [2.0])
        eq("中央値", _q([1.0, 2.0, 3.0], .5), 2.0)
        # 二重起動しても既に取れている点は再取得しない
        eq("skip済み判定", attempts_of("20260822").get(("R1", "T-3", "light")), (1, 1))
        # light と heavy は同じ tag でも別イベント(2026-08-18に潰したバグの回帰テスト)
        append(dict(a, kind="heavy", tag="T-30", tan=None, sanrenpuku={"1-2-3": 50.0}))
        at2 = attempts_of("20260822")
        eq("light/heavy衝突なし",
           (at2.get(("R1", "T-30", "light")), at2.get(("R1", "T-30", "heavy"))),
           ((1, 1), (1, 1)))
        by2 = index_rows(["20260822"])
        eq("同tagのlight/heavyが合流", (len(by2["R1"]["T-30"]["tan"]),
                                        by2["R1"]["T-30"]["sanrenpuku"]["1-2-3"]), (2, 50.0))
    finally:
        LOGDIR = real

    if fails:
        for f in fails:
            print("  ❌ " + f)
        print("selftest: NG %d件" % len(fails))
        return 1
    print("selftest OK (スケジュール生成/再開判定/取消除外/ドリフト算術)")
    return 0


def health():
    """selfcheck.py が呼ぶ自己診断。**外部ネットワークを一切使わない**（週末朝に
    ネット都合で ❌ を出さないため）。ロジックの回帰と台帳の現況だけを見る。"""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_selftest()
    if rc:
        raise RuntimeError("odds_timeline のロジック検査に失敗: " + buf.getvalue().strip())
    days, rows, ok, rids = set(), 0, 0, set()
    for r in iter_rows():
        rows += 1
        days.add(r.get("date"))
        rids.add(r.get("rid"))
        ok += 1 if r.get("ok") else 0
    if not rows:
        return "ロジックOK / 収集はまだ0件(8/22の開催日から本番)"
    return ("ロジックOK / %d日 %dレース %d行(成功%d)" % (len(days), len(rids), rows, ok))


def cmd_compact(keep_days=14):
    """古い日の jsonl を gzip する(実測で約1/8)。読み出しは透過。"""
    if not os.path.isdir(LOGDIR):
        print("記録なし")
        return 0
    cut = (jst_now() - datetime.timedelta(days=keep_days)).strftime("%Y%m%d")
    n = 0
    for fn in sorted(os.listdir(LOGDIR)):
        if not fn.endswith(".jsonl"):
            continue
        d = fn.split(".")[0]
        if not (d.isdigit() and d < cut):
            continue
        p = os.path.join(LOGDIR, fn)
        with open(p, "rb") as fi, gzip.open(p + ".gz", "wb") as fo:
            fo.write(fi.read())
        before, after = os.path.getsize(p), os.path.getsize(p + ".gz")
        os.remove(p)
        n += 1
        print("  %s %.1fMB → %.1fMB (1/%.1f)" % (fn, before / 1024.0 ** 2,
                                                 after / 1024.0 ** 2,
                                                 before / max(after, 1)))
    print("gzip化 %d日分" % n)
    return 0


def main():
    ap = argparse.ArgumentParser(description="オッズ時系列の自作収集")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("watch", help="当日の全JRAレースを予定どおりポーリング")
    p.add_argument("date", nargs="?", default=None)
    p.add_argument("--profile", default="full", choices=sorted(PROFILES))
    p.add_argument("--max-axis", type=int, default=None, help="三連複の軸ページ上限(既定=全網羅)")
    p.add_argument("--rids", default=None, help="race_idをカンマ区切りで限定")
    p.add_argument("--until", default=None, help="HH:MM で打ち切り")
    p.add_argument("--dry", action="store_true", help="予定だけ表示して終了")
    p.add_argument("--force", action="store_true", help="ロックを無視して起動")

    p = sub.add_parser("snap", help="1レース1時点だけ取る")
    p.add_argument("race_id")
    p.add_argument("--tag", default="MANUAL")
    p.add_argument("--kind", default="light", choices=["light", "heavy", "nk"])
    p.add_argument("--max-axis", type=int, default=None)

    p = sub.add_parser("settle", help="確定オッズ(FINAL)と結果を追記")
    p.add_argument("date", nargs="?", default=None)

    p = sub.add_parser("stats", help="ドリフト集計")
    p.add_argument("--date", default=None, help="カンマ区切りで日付を限定")
    p.add_argument("--pair", action="append", default=None, help="例 T-30:FINAL")
    p.add_argument("--src", default="jra", choices=["jra", "netkeiba", "any"])
    p.add_argument("--min-n", type=int, default=5)

    p = sub.add_parser("probe", help="実地テスト(非開催日も可)")
    p.add_argument("--rid", default=None)
    p.add_argument("--no-heavy", action="store_true")

    sub.add_parser("selftest", help="オフラインのロジック検査")

    p = sub.add_parser("compact", help="古い日をgzip")
    p.add_argument("--keep-days", type=int, default=14)

    a = ap.parse_args()
    if a.cmd == "watch":
        return cmd_watch(a.date or jst_now().strftime("%Y%m%d"), profile=a.profile,
                         dry=a.dry, max_axis=a.max_axis, until=a.until, force=a.force,
                         rids=set(a.rids.split(",")) if a.rids else None)
    if a.cmd == "snap":
        rec = snap(a.race_id, a.kind, a.tag, max_axis=a.max_axis,
                   meta=dict(date=jst_now().strftime("%Y%m%d")))
        print(json.dumps({k: (len(v) if isinstance(v, dict) else v)
                          for k, v in rec.items()}, ensure_ascii=False))
        return 0 if rec.get("ok") else 1
    if a.cmd == "settle":
        return cmd_settle(a.date)
    if a.cmd == "stats":
        pairs = [tuple(x.split(":", 1)) for x in a.pair] if a.pair else None
        return cmd_stats(dates=a.date.split(",") if a.date else None, pairs=pairs,
                         src=None if a.src == "any" else a.src, min_n=a.min_n)
    if a.cmd == "probe":
        return cmd_probe(a.rid, heavy=not a.no_heavy)
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.cmd == "compact":
        return cmd_compact(a.keep_days)
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
