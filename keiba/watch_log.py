# -*- coding: utf-8 -*-
"""W10/W11 ライブwatch記録（2026-08-17新設・賭け金ゼロ）。

   WATCHLIST.md の
     W10 = モデル1位 ∧ 前走tsi最高1位 が一致した「合議」レース
     W11 = W10 かつ そのモデル1位の単勝が10倍以上
   を、当日の全JRAレースについて自動判定し、**1円も張らずに**記録するだけの台帳。

   なぜ独立ログか: paper_rank.py は「凍結ルールブックの発火レース」だけを記帳する実弾候補台帳。
   W10/W11 は候補(=買いルールではない)なので、混ぜると凍結後成績が汚れる。
   ログは watch_log.jsonl（paper_rank_log.jsonl には一切触れない）。

   usage:
     python3 watch_log.py run [YYYYMMDD] [--fast] [--rids id,id]  # 当日の全JRAを判定して記録
     python3 watch_log.py settle [--date YYYYMMDD]                # 結果・払戻を埋める
     python3 watch_log.py stats [--min-cov 0.5]                   # W別の成績
     python3 watch_log.py probe                                   # 自己診断(selfcheckが呼ぶ)

   記録項目(1行=1レース): race_id/日時/モデル1位/tsi1位/一致有無/モデル1位オッズ/該当W番号/(後で)結果・払戻
   ※馬柱は day_board.load_or_fetch のキャッシュ(race_{rid}.json)を共有する。**day_board.py の後に回す**と速い。
     パトロール中の再実行は --fast(キャッシュ済みのみ)推奨。
   ※賭け金ゼロ。ROIは「単勝100円・複勝100円を仮に買っていたら」の名目値。実弾には使わない。
   ※判定ライン(WATCHLIST): W10はn>=30、W11は台帳54Rと同規模のn>=50で VALIDATE 相当の判定。
"""
import argparse, datetime, json, os, re, sys

_DIR = os.path.dirname(os.path.abspath(__file__))

# 障害レースはモデル対象外(paper_rank.py と同一の除外規則)
JUMP_RE = re.compile(r"障害|ジャンプ|JS(?![a-z])")

LOG = os.path.join(_DIR, "watch_log.jsonl")

# W11 の「10倍+」境界。WATCHLIST W11 の定義(台帳5,882R検証)と同値。
W11_ODDS = 10.0
# tsi が全頭のこれ未満しか無いレースは合議の判定が不安定 → stats の既定で除外
MIN_COV = 0.5


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def load_log(path=None):
    p = path or LOG
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def save_log(rows, path=None):
    p = path or LOG
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ── 判定の中核(純関数・テスト可能) ────────────────────────────────────
def prev_tsi_map(race):
    """{馬番: 前走tsi}。hist/{rid}.json 形式({'race':...})とライブの race_{rid}.json の両対応。"""
    if "race" in race and isinstance(race.get("race"), dict):
        race = race["race"]
    out = {}
    for h in race.get("horses", []):
        rs = h.get("races") or []
        t = (rs[0] or {}).get("tsi") if rs else None
        if t is not None:
            out[h["num"]] = float(t)
    return out


def tsi_top(tsi):
    """(tsi最高の馬番, その値, 同値タイか) を返す。タイ(単独1位でない)は合議の判定不能とする。"""
    if not tsi:
        return None, None, False
    best = max(tsi.values())
    tops = [n for n, v in tsi.items() if v == best]
    return (tops[0] if len(tops) == 1 else None), best, len(tops) > 1


def tags_for(model1, tsi1, o1, tie=False):
    """該当W番号のリスト。W10=合議一致 / W11=合議一致かつモデル1位10倍+。"""
    if tie or not model1 or not tsi1:
        return []
    if model1 != tsi1:
        return []
    tags = ["W10"]
    if o1 is not None and o1 >= W11_ODDS:
        tags.append("W11")
    return tags


# ── 当日判定 ─────────────────────────────────────────────────────
def eval_race(it, date, fast=False, fresh=False):
    """1レースを判定して記録用dictを返す。判定不能なら None。"""
    import calc
    import v2_live
    import day_board as DB
    import predict as PR

    rid = it["race_id"]
    race = DB.load_or_fetch(rid, date, nar=False, fast=fast)
    if race is None:
        return None
    DB.refresh_weights(race, rid, nar=False)
    res = calc.run(race)
    v2_live.rescore(race, res["rows"])
    rows = res["rows"]
    order = [r["num"] for r in rows]
    names = {h["num"]: h.get("name", "") for h in race.get("horses", [])}
    field = race.get("field", len(order))

    tsi = prev_tsi_map(race)
    t1, t1v, tie = tsi_top(tsi)
    m1 = order[0]

    od = PR.fetch_jra(rid, fresh=fresh)
    tan = {int(k): v for k, v in od.get("tan", {}).items() if v}
    if not tan:
        return None
    o1 = tan.get(m1)
    pops = {n: i + 1 for i, n in enumerate(sorted(tan, key=lambda h: tan[h]))}
    tags = tags_for(m1, t1, o1, tie)

    return dict(
        race_id=rid, date=date, venue=it.get("venue"), r=it.get("r"),
        post=it.get("time"), judged=jst_now().strftime("%m%d %H:%M"),
        surface=race.get("surface"), dist=race.get("distance"),
        tier=race.get("today_tier"), baba=race.get("baba"), field=field,
        model1=m1, model1_name=names.get(m1, ""), o1=o1, pop1=pops.get(m1),
        tsi1=t1, tsi1_name=names.get(t1, "") if t1 else "", tsi1_val=t1v,
        model1_tsi=tsi.get(m1), tsi_tie=tie,
        tsi_cov=round(len(tsi) / max(field, 1), 3),
        match=bool(t1 and m1 == t1), tags=tags,
        odds_src=od.get("tan_source"),
        stake=0,                    # ★賭け金ゼロ(記録のみ)
        settled=False,
    )


def cmd_run(date, fast=False, rids=None, fresh_min=30, allow_past=False):
    import pick_races as PKR

    now = jst_now()
    logs = load_log()
    byrid = {r["race_id"]: r for r in logs}
    # 過去日付は既定で記録しない(発走後オッズ=結果を見た後の値で W11の10倍+判定をすると後知恵になる)
    if date < now.strftime("%Y%m%d") and not allow_past:
        print(f"[{date}] 過去日付のため新規記録なし(既存は保持)。意図的な追記は --allow-past",
              file=sys.stderr)
        return
    lst = [it for it in PKR.fetch_list(date, nar=False)
           if not JUMP_RE.search(it.get("name", ""))]
    if rids:
        want = set(rids)
        lst = [it for it in lst if it["race_id"] in want]
    print(f"[{date}] W10/W11 watch: JRA {len(lst)}レース ({now.strftime('%H:%M')} JST)",
          file=sys.stderr)
    n_new = n_upd = n_skip = 0
    for it in lst:
        rid = it["race_id"]
        post = it.get("time") or "99:99"
        prev = byrid.get(rid)
        if prev and (prev.get("frozen") or prev.get("settled")):
            continue
        # 発走3分前で凍結(それ以降はオッズが確定値になるので判定を固定)
        try:
            ph, pm = int(post[:2]), int(post[3:5])
            tminus = (ph * 60 + pm) - (now.hour * 60 + now.minute)
        except Exception:
            tminus = 999
        started = (date == now.strftime("%Y%m%d") and tminus <= 3)
        if started and not prev:
            n_skip += 1                # 未判定のまま発走 → 記録しない(後知恵防止)
            continue
        try:
            # 直前(既定30分以内)はJRA公式オッズ。netkeiba無料オッズは40-50分遅れ(RULES §7)
            fresh = (date == now.strftime("%Y%m%d") and 0 < tminus <= fresh_min)
            e = eval_race(it, date, fast=fast, fresh=fresh)
            if e is None:
                n_skip += 1
                continue
            e["tminus"] = tminus
            if started:
                e["frozen"] = True
            if prev:
                e["first_judged"] = prev.get("first_judged", prev.get("judged"))
                for k in ("settled", "ret_tan", "ret_fuku", "win", "model1_rank"):
                    if k in prev:
                        e.setdefault(k, prev[k])
                n_upd += 1
            else:
                e["first_judged"] = e["judged"]
                n_new += 1
            byrid[rid] = e
            if e["tags"]:
                print(f"  👁 {it.get('venue')}{it.get('r')}R {post} "
                      f"{'/'.join(e['tags'])} モデル1位={e['model1']}{e['model1_name']} "
                      f"({e['o1']}倍) =tsi1位(前走{e['tsi1_val']})", file=sys.stderr)
        except Exception as ex:
            n_skip += 1
            print(f"  {rid} watch判定失敗: {ex}", file=sys.stderr)
    keep = [r for r in logs if r["race_id"] not in byrid]
    save_log(keep + list(byrid.values()))
    hit = sum(1 for r in byrid.values() if r.get("date") == date and r.get("tags"))
    print(f"watch記録 新規{n_new} 更新{n_upd} 対象外{n_skip} / 当日W該当{hit}件 → {LOG}",
          file=sys.stderr)


def cmd_settle(date=None):
    import fetch_result as FRES

    logs = load_log()
    n = 0
    for r in logs:
        if r.get("settled"):
            continue
        if date and r.get("date") != date:
            continue
        try:
            res = FRES.get_result(r["race_id"])
        except Exception:
            continue
        pay = res.get("payout") or {}
        if not pay.get("単勝"):
            continue
        m1 = r["model1"]
        rank = {o["num"]: o["rank"] for o in res.get("order", [])}
        r["win"] = int(list(pay["単勝"].keys())[0])
        r["model1_rank"] = rank.get(m1)
        r["tsi1_rank"] = rank.get(r["tsi1"]) if r.get("tsi1") else None
        # 名目100円(単勝/複勝)。実弾ではない
        r["ret_tan"] = int(pay["単勝"].get(str(m1), 0))
        r["ret_fuku"] = int((pay.get("複勝") or {}).get(str(m1), 0))
        r["settled"] = True
        n += 1
        mark = "🎯" if r["ret_tan"] else ("○" if r["ret_fuku"] else "…")
        tg = "/".join(r.get("tags") or []) or "-"
        print(f"  {mark} {r['venue']}{r['r']}R [{tg}] モデル1位{m1} {r['model1_rank']}着 "
              f"単{r['ret_tan']} 複{r['ret_fuku']}", file=sys.stderr)
    save_log(logs)
    print(f"watch精算 {n}件", file=sys.stderr)


def _agg(rows, label):
    if not rows:
        print(f"  {label}: 0R")
        return
    n = len(rows)
    w = sum(1 for r in rows if r.get("ret_tan"))
    p = sum(1 for r in rows if r.get("ret_fuku"))
    rt = sum(r.get("ret_tan", 0) for r in rows)
    rf = sum(r.get("ret_fuku", 0) for r in rows)
    print(f"  {label}: {n}R 勝{w}({w/n*100:.0f}%) 複{p}({p/n*100:.0f}%) "
          f"単ROI {rt/(n*100)*100:.1f}% 複ROI {rf/(n*100)*100:.1f}%")


def cmd_stats(min_cov=MIN_COV):
    logs = [r for r in load_log() if r.get("settled")]
    if not logs:
        print("watch: 精算済みレコードなし(週末のライブ運用で貯まる)")
        return
    tie = [r for r in logs if r.get("tsi_tie")]
    low = [r for r in logs if not r.get("tsi_tie") and (r.get("tsi_cov") or 0) < min_cov]
    use = [r for r in logs if not r.get("tsi_tie") and (r.get("tsi_cov") or 0) >= min_cov]
    match = [r for r in use if r.get("match")]
    miss = [r for r in use if not r.get("match")]
    w11 = [r for r in match if (r.get("o1") or 0) >= W11_ODDS]
    w11n = [r for r in miss if (r.get("o1") or 0) >= W11_ODDS]

    print(f"W10/W11 ライブwatch(賭け金ゼロ・名目100円): {len(logs)}R精算 "
          f"(判定可{len(use)} / tsiタイ除外{len(tie)} / 低被覆除外{len(low)})")
    _agg(match, "W10 合議一致        [ライブ実測]")
    _agg(miss, "　　不一致(対照)     [ライブ実測]")
    _agg(w11, f"W11 合議×{W11_ODDS:.0f}倍+     [ライブ実測]")
    _agg(w11n, f"　　不一致×{W11_ODDS:.0f}倍+   [対照]")
    for s in ("芝", "ダ"):
        _agg([r for r in match if r.get("surface") == s], f"　W10×{s}")
    print(f"  進捗: W10 {len(match)}/30R ・ W11 {len(w11)}/50R "
          f"(WATCHLIST判定ライン)。台帳側の数値(W10 85.1%/W11 192.2%)は[窓内=参考値]。")
    print("  ※賭け金ゼロの記録。買いルールには入れない(WATCHLIST W10/W11は[候補]止まり)。")


# ── 自己診断(selfcheck.py が呼ぶ) ────────────────────────────────
def probe():
    """タグ判定ロジックとログの健全性を検査。異常は例外。戻り値は1行サマリ。"""
    # (a) 合議一致→W10、10倍+ならW11も
    assert tags_for(5, 5, 12.0) == ["W10", "W11"], "W10/W11が発火しない"
    assert tags_for(5, 5, 9.9) == ["W10"], "10倍未満でW11が発火してはいけない"
    assert tags_for(5, 3, 12.0) == [], "不一致で発火してはいけない"
    assert tags_for(5, 5, 12.0, tie=True) == [], "tsiタイは判定不能のはず"
    assert tags_for(5, None, 12.0) == [], "tsi欠損で発火してはいけない"
    # (b) tsi最高の抽出(タイ検出込み)
    assert tsi_top({1: 70.0, 2: 88.0, 3: 80.0})[:2] == (2, 88.0)
    assert tsi_top({1: 88.0, 2: 88.0})[0] is None and tsi_top({1: 88.0, 2: 88.0})[2]
    assert tsi_top({}) == (None, None, False)
    # (c) 前走tsiの取り出しが hist形式/ライブ形式の両方で動く
    live = {"horses": [{"num": 1, "races": [{"tsi": 76.0}]},
                       {"num": 2, "races": [{}]}, {"num": 3, "races": []}]}
    assert prev_tsi_map(live) == {1: 76.0}, "ライブ形式のtsi抽出が壊れた"
    assert prev_tsi_map({"race": live}) == {1: 76.0}, "hist形式のtsi抽出が壊れた"
    # (d) 台帳が読める・壊れていない(1行1レース・必須キー)
    rows = load_log()
    for r in rows:
        for k in ("race_id", "model1", "tags"):
            if k not in r:
                raise RuntimeError(f"watch_log.jsonl に壊れた行: {r.get('race_id')} ({k}欠落)")
        if r.get("stake"):
            raise RuntimeError(f"watch記録に賭け金が入っている(ゼロのはず): {r['race_id']}")
    ids = [r["race_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("watch_log.jsonl に race_id 重複")
    st = sum(1 for r in rows if r.get("settled"))
    return f"判定ロジック4仕様OK / 台帳{len(rows)}R(精算{st})"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run")
    p1.add_argument("date", nargs="?", default=None)
    p1.add_argument("--fast", action="store_true", help="馬柱キャッシュ済みのみ(未取得はスキップ)")
    p1.add_argument("--rids", default=None, help="race_idカンマ区切りで対象を限定")
    p1.add_argument("--fresh-min", type=int, default=30,
                    help="発走この分数以内はJRA公式オッズを使う(既定30)")
    p1.add_argument("--allow-past", action="store_true",
                    help="過去日付でも記録する(発走後オッズ=後知恵になるため通常は使わない)")
    p2 = sub.add_parser("settle")
    p2.add_argument("--date", default=None)
    p3 = sub.add_parser("stats")
    p3.add_argument("--min-cov", type=float, default=MIN_COV)
    sub.add_parser("probe")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a.date or jst_now().strftime("%Y%m%d"), fast=a.fast,
                rids=(a.rids.split(",") if a.rids else None), fresh_min=a.fresh_min,
                allow_past=a.allow_past)
    elif a.cmd == "settle":
        cmd_settle(a.date)
    elif a.cmd == "stats":
        cmd_stats(a.min_cov)
    else:
        print(probe())


if __name__ == "__main__":
    main()
