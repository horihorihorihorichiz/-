# -*- coding: utf-8 -*-
"""W12 紙上フォワード台帳（ダ短距離×選別×B-sd16上位2頭。2026-08-20新設・掛け金ゼロ）。

   WATCHLIST.md W12（2026-08-20登録）の凍結仕様をモデル非依存でコード化する。
   どのモデル（Opus等）がセッションを担当しても、このスクリプトを叩けば同じ判定が出る。

   発火条件（凍結。出所: WATCHLIST.md W12 / PORTFOLIO_REPORT_20260820.md）:
     ダート かつ 距離<=1400m かつ fav_p>=0.341 かつ ent<=1.904
     fav_p/ent は**判定時点の単勝オッズ**で計算（発走3分前凍結＝v99w_rank --post と同じ流儀。
     閾値は exclusion.py の凍結定数＝EXCLUSION_REPORT_20260818.md）。

   発火時に記録する買い目（掛け金ゼロ・名目100円/点）:
     主: B-sd16上位2頭のワイド1点
     副: 同2頭軸-3..6位の三連複4点
     各買い目に判定時オッズを保存（ライブ=predict.fetch_jraのワイド/三連複。取れなければ null。
     --allow-past のhist追記は単勝＝確定オッズの代理値・組合せオッズは null）。

   判定（凍結）: 前向き（ライブ記帳）n>=80 精算で ROI>=100% なら昇格検討 / <100% なら棄却。
     **n<80 のうちは ROI がいくつでも「検証中」としか表示しない**
     （PORTFOLIO_REPORT_20260820: n=49/32・多重比較696案の生き残り＝偶然の可能性が高い前提）。

   usage:
     python3 w12_watch.py run <race_json|race_id> [...] [--allow-past] [--no-record]
                              [--post HH:MM] [--fresh-combo] [--no-odds]
     python3 w12_watch.py settle          # 確定払戻のみ取り込み（v99w_rank.settleと同経路）
     python3 w12_watch.py stats           # n/的中率/ROI（判定時オッズ基準と確定払戻基準）
     python3 w12_watch.py probe           # 自己診断（selfcheckが呼ぶ・既知レース指紋）

   台帳: w12_log.jsonl（発火レースのみ1行1レース）。実弾禁止・購入機能なし。
   本番エンジン（calc/params/patterns/day_board/predict/fetch_race）は無変更。"""
import argparse, datetime, json, os, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import exclusion as EX

LOG = os.path.join(_DIR, "w12_log.jsonl")

# ── 凍結定数（WATCHLIST.md W12 2026-08-20登録） ──
SURFACE = "ダ"          # ダートのみ
MAX_DIST = 1400         # 距離1400m以下（=B-sd16群の「ダS」）
N_LEGS = 4              # 三連複の相手 = B-sd16 3..6位（頭数不足時はある分だけ）
N_JUDGE = 80            # 前向き精算がこの数に達するまで昇格・棄却の判断をしない


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


# ── 判定の中核（純関数・テスト可能） ─────────────────────────────
def fire(surface, distance, fav_p, ent):
    """W12発火判定。オッズ由来指標が無い(None)場合は発火しない（判定不能≠発火）。"""
    if surface != SURFACE or not distance or distance > MAX_DIST:
        return False
    if fav_p is None or ent is None:
        return False
    return fav_p >= EX.FAV_P_MIN and ent <= EX.ENT_MAX


def bets_for(rank16):
    """B-sd16順位（馬番リスト）→ (ワイドペアkey, 三連複相手list, 三連複comboリスト)。
       key書式は predict.fetch_jra / fetch_result payout と同じ「昇順ハイフン結合」。"""
    a, b = rank16[0], rank16[1]
    wide = "%d-%d" % tuple(sorted((a, b)))
    legs = rank16[2:2 + N_LEGS]
    trio = ["-".join(str(x) for x in sorted((a, b, c))) for c in legs]
    return wide, legs, trio


def verdict(n_live_settled, roi_wide_actual):
    """WATCHLIST W12の判定行。n<80では ROI に関わらず『検証中』のみ（早期昇格の禁止）。"""
    if n_live_settled < N_JUDGE:
        return (f"🔍 検証中 — 前向き精算 n={n_live_settled}/{N_JUDGE}。"
                f"n>={N_JUDGE} までROIに関わらず昇格・棄却の判断をしない（実弾禁止）")
    if roi_wide_actual is not None and roi_wide_actual >= 100.0:
        return (f"n={n_live_settled}>={N_JUDGE} 到達・ワイドROI(確定払戻) "
                f"{roi_wide_actual:.1f}%>=100% → 昇格検討ライン。"
                f"WATCHLIST更新と人間の判断へ（自動昇格はしない）")
    return (f"n={n_live_settled}>={N_JUDGE} 到達・ワイドROI(確定払戻) "
            f"{roi_wide_actual:.1f}%<100% → 棄却基準該当。WATCHLISTを閉じる")


# ── 台帳 ─────────────────────────────────────────────
def load_log():
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]


def save_log(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ── オッズ（判定時点） ──────────────────────────────────
def get_odds(rid, arg, has_result, tminus, no_odds=False, fresh_combo=False):
    """(単勝辞書{馬番int:オッズ}, fetch_jraの生dict|None, 出所)。
       過去（結果あり）= hist確定単勝を代理値に使う（ネット不要。ワイド/三連複はnull）。
       ライブ = predict.fetch_jra（発走30分前以内は fresh=True でJRA公式単複。
       --fresh-combo でワイド/三連複も公式から取り直し=約15-20秒/R）。"""
    if no_odds:
        return {}, None, None
    if has_result:
        try:
            import v99w_rank as VR
            d = json.load(open(VR.find_race_path(arg), encoding="utf-8"))
            order = (d.get("result") or {}).get("order") or []
            tan = {int(o["num"]): float(o["odds"]) for o in order if o.get("odds")}
            if tan:
                return tan, None, "hist_final"
        except Exception:
            pass
    try:
        import predict as PR
        fresh = tminus is not None and 0 < tminus <= 30
        od = PR.fetch_jra(rid, fresh=fresh, fresh_combo=fresh_combo)
        tan = {int(k): float(v) for k, v in (od.get("tan") or {}).items() if v}
        if tan:
            return tan, od, od.get("tan_source")
    except Exception as e:
        print(f"  {rid} オッズ取得失敗: {e}", file=sys.stderr)
    return {}, None, None


# ── run ─────────────────────────────────────────────
def cmd_run(args):
    import v99w_rank as VR
    VR.load_model()                       # comps側の依存を先に確保（v99w_rank同順）
    wg16, ws16 = VR.load_model16()
    now = jst_now()
    today = now.strftime("%Y%m%d")
    logs = load_log()
    byrid = {r["rid"]: r for r in logs}
    n_new = n_upd = n_fire = 0
    for arg in args.races:
        try:
            race, rdate, has_result = VR.load_race(arg)
        except Exception as e:
            print(f"  {arg}: 読込失敗 {e}", file=sys.stderr)
            continue
        rid = str(race.get("race_id") or os.path.basename(arg).replace(".json", ""))
        date = rdate or today
        judged_tminus = None
        if args.post:
            try:
                ph, pm = (int(x) for x in args.post.split(":"))
                judged_tminus = (ph * 60 + pm) - (now.hour * 60 + now.minute)
            except Exception:
                pass
        surface, dist = race.get("surface"), race.get("distance")
        tan, od, osrc = get_odds(rid, arg, has_result, judged_tminus,
                                 no_odds=args.no_odds, fresh_combo=args.fresh_combo)
        fav_p, ent = EX.metrics(tan)
        head = (f"W12 {rid} {race.get('venue','')} {surface}{dist} "
                f"tier{race.get('today_tier','')}")
        if surface != SURFACE or not dist or dist > MAX_DIST:
            print(f"{head} → 対象外（ダ1400m以下でない）")
            continue
        if fav_p is None:
            print(f"{head} → 判定不能（オッズなし。--no-odds中か取得失敗）")
            continue
        if not fire(surface, dist, fav_p, ent):
            why = []
            if fav_p < EX.FAV_P_MIN:
                why.append(f"fav_p={fav_p:.3f}<{EX.FAV_P_MIN}")
            if ent > EX.ENT_MAX:
                why.append(f"ent={ent:.3f}>{EX.ENT_MAX}")
            print(f"{head} → 非発火（{' / '.join(why)}）[{osrc}]")
            continue
        n_fire += 1
        # B-sd16順位と買い目（v99w_rank と同一経路・同一タイブレーク）
        rows, Z = VR.scores_for(race)
        s16, grp16, nz0 = VR.score_bsd16(race, rows, Z, date, wg16, ws16)
        rank16 = VR.rank_nums(rows, s16)
        wide_pair, legs, trio = bets_for(rank16)
        sgap16 = EX.sgap_of(s16)
        wide_odds = (od or {}).get("wide", {}).get(wide_pair) if od else None
        trio_odds = {c: ((od or {}).get("sanrenpuku", {}).get(c) if od else None)
                     for c in trio}
        combo_src = (od or {}).get("combo_source") if od else None
        if od and not combo_src and (od.get("wide") or od.get("sanrenpuku")):
            combo_src = "netkeiba"
        print(f"{head} 🔥発火 fav_p={fav_p:.3f} ent={ent:.3f} sgap16={sgap16:+.3f} [{osrc}]")
        names = {h["num"]: h.get("name", "") for h in race.get("horses", [])}
        a, b = rank16[0], rank16[1]
        print(f"  B-sd16上位: 1位{a}{names.get(a,'')} 2位{b}{names.get(b,'')} "
              f"相手{legs}")
        print(f"  主 ワイド {wide_pair}: "
              + (f"{wide_odds}倍" if wide_odds else "オッズnull（未取得）"))
        for c in trio:
            o = trio_odds[c]
            print(f"  副 三連複 {c}: " + (f"{o}倍" if o else "オッズnull（未取得）"))
        if args.no_record:
            continue
        prev = byrid.get(rid)
        if prev and prev.get("settled"):
            print(f"  {rid}: 精算済みのため記帳せず（記録は不変）", file=sys.stderr)
            continue
        # 後知恵ブロック（v99w_rank踏襲）: 過去日付 or 結果同梱は既定で記帳しない
        past = (date < today) or has_result
        if past and not args.allow_past:
            print(f"  {rid}: 過去日付/結果ありのため記帳しない（後知恵防止）。"
                  f"検証目的の追記は --allow-past", file=sys.stderr)
            continue
        # 発走3分前で凍結。発走後の再記帳は入力が汚れるためブロック
        if judged_tminus is not None and judged_tminus <= 3 and not args.allow_past:
            print(f"  {rid}: 発走{judged_tminus:+d}分＝凍結時刻を過ぎたため記帳しない",
                  file=sys.stderr)
            continue
        entry = dict(rid=rid, date=date, venue=race.get("venue"),
                     surface=surface, dist=dist, dist_cat=VR.sd_key(race)[1],
                     tier=race.get("today_tier"), field=len(rows),
                     fav_p=round(fav_p, 5), ent=round(ent, 5),
                     sgap16=round(sgap16, 5) if sgap16 is not None else None,
                     bsd16_top6=rank16[:6],
                     bsd16_group="known" if grp16 else "fallback_wg16",
                     corner_zero=nz0,
                     wide=dict(pair=wide_pair, odds=wide_odds),
                     trio=dict(axis=sorted((a, b)), legs=legs, odds=trio_odds),
                     odds_src=osrc, combo_src=combo_src,
                     recorded=now.strftime("%m%d %H:%M"),
                     judged_tminus=judged_tminus,
                     past=bool(past), stake=0, settled=False)
        if prev:
            entry["recorded_first"] = prev.get("recorded_first", prev["recorded"])
            n_upd += 1
        else:
            entry["recorded_first"] = entry["recorded"]
            n_new += 1
        byrid[rid] = entry
        print(f"  📝 記帳 {rid}（掛け金ゼロ）", file=sys.stderr)
    if not args.no_record:
        keep = [r for r in logs if r["rid"] not in byrid]
        save_log(keep + list(byrid.values()))
        print(f"W12 発火{n_fire} / 記帳 新規{n_new} 更新{n_upd} / 総{len(byrid)}件 → {LOG}",
              file=sys.stderr)


# ── settle ───────────────────────────────────────────
def cmd_settle():
    """確定払戻のみ取り込む（v99w_rank.settle と同経路=fetch_result。捏造・手入力は不可）。"""
    import fetch_result as FRES
    logs = load_log()
    n = 0
    for r in logs:
        if r.get("settled"):
            continue
        try:
            res = FRES.get_result(r["rid"])
        except Exception as e:
            print(f"  {r['rid']} 取得失敗: {e}", file=sys.stderr)
            continue
        pay = res.get("payout") or {}
        fin = {o["num"]: int(o["rank"]) for o in (res.get("order") or [])
               if str(o.get("rank", "")).isdigit()}
        if not pay.get("単勝") or len(fin) < 3:
            print(f"  {r['rid']} 未確定（払戻なし）→ 保留", file=sys.stderr)
            continue
        top3 = res.get("top3") or \
            [num for num, rk in sorted(fin.items(), key=lambda kv: kv[1])[:3]]
        r["fin"] = {str(k): v for k, v in sorted(fin.items())}
        r["result_top3"] = top3
        pw = pay.get("ワイド") or {}
        r["ret_wide"] = int(pw.get(r["wide"]["pair"], 0))
        pt = pay.get("三連複") or {}
        r["ret_trio"] = sum(int(pt.get(c, 0)) for c in r["trio"]["odds"])
        r["settled"] = True
        r["settled_at"] = jst_now().strftime("%m%d %H:%M")
        n += 1
        mark = "🎯" if r["ret_wide"] else ("○" if r["ret_trio"] else "…")
        print(f"  {mark} {r['rid']} {r.get('venue','')} 結果{top3} "
              f"ワイド{r['wide']['pair']}={r['ret_wide']}円 三連複計={r['ret_trio']}円",
              file=sys.stderr)
    save_log(logs)
    print(f"W12精算 {n}件", file=sys.stderr)


# ── stats ────────────────────────────────────────────
def _hit_combo(r):
    """的中した三連複combo（無ければNone）。comboは昇順結合＝payout書式と同じ。"""
    t3 = r.get("result_top3") or []
    if len(t3) != 3:
        return None
    key = "-".join(str(x) for x in sorted(t3))
    return key if key in r["trio"]["odds"] else None


def _lane(rows):
    """(ワイド, 三連複) 各レーンの [点数, 的中数, 確定払戻計, 判定時オッズ点数, 同払戻計]。"""
    w = dict(pts=0, hit=0, ret=0, jpts=0, jret=0.0)
    t = dict(pts=0, hit=0, ret=0, jpts=0, jret=0.0)
    for r in rows:
        w["pts"] += 1
        w["hit"] += 1 if r.get("ret_wide") else 0
        w["ret"] += r.get("ret_wide", 0)
        wo = r["wide"].get("odds")
        if wo:
            w["jpts"] += 1
            if r.get("ret_wide"):
                w["jret"] += wo * 100.0
        hc = _hit_combo(r)
        for c, o in r["trio"]["odds"].items():
            t["pts"] += 1
            if o:
                t["jpts"] += 1
                if c == hc:
                    t["jret"] += o * 100.0
        t["hit"] += 1 if hc else 0
        t["ret"] += r.get("ret_trio", 0)
    return w, t


def _roi(ret, pts):
    return f"{ret / (pts * 100.0) * 100.0:.1f}%" if pts else "—"


def _block(rows, label):
    if not rows:
        print(f"  {label}: 0R")
        return
    w, t = _lane(rows)
    n = len(rows)
    print(f"  {label}: {n}R")
    print(f"    主 ワイド1点  : 的中 {w['hit']}/{n} ({100.0*w['hit']/n:.0f}%)  "
          f"ROI 確定払戻 {_roi(w['ret'], w['pts'])} / "
          f"判定時オッズ {_roi(w['jret'], w['jpts'])} [オッズ記録{w['jpts']}/{n}点]")
    print(f"    副 三連複4点  : 的中 {t['hit']}/{n}R ({100.0*t['hit']/n:.0f}%)  "
          f"ROI 確定払戻 {_roi(t['ret'], t['pts'])} / "
          f"判定時オッズ {_roi(t['jret'], t['jpts'])} [オッズ記録{t['jpts']}/{t['pts']}点]")


def cmd_stats():
    logs = load_log()
    st = [r for r in logs if r.get("settled")]
    live = [r for r in st if not r.get("past")]
    back = [r for r in st if r.get("past")]
    print(f"W12 紙上フォワード（ダ短×選別×B-sd16上位2頭・掛け金ゼロ/名目100円）: "
          f"発火{len(logs)}R 精算{len(st)}R")
    if not st:
        print("  精算済みレコードなし（settle を先に）")
    else:
        _block(live, "ライブ記帳（発走前判定）[実測・判定に使う]")
        _block(back, "--allow-past 追記（検証用バックフィル）[参考・判定に使わない]")
    lw, _ = _lane(live) if live else (dict(ret=0, pts=0), None)
    roi_live = (lw["ret"] / (lw["pts"] * 100.0) * 100.0) if lw["pts"] else None
    print(f"  進捗: 前向き精算 {len(live)}/{N_JUDGE}R（WATCHLIST W12判定ライン）")
    print(f"  判定: {verdict(len(live), roi_live)}")
    print("  ※台帳側の数字（ワイド MINE101.2/VAL131.8/CONF140.3・n=49/32）は"
          "[窓内=参考値]。多重比較696案の生き残りであり偶然の可能性が高い前提で検証する。")


# ── probe（selfcheck.py が呼ぶ・オフライン） ─────────────────────
# 指紋レース（hist の確定単勝オッズから算出した fav_p/ent。ファイルはgit管理で不変）:
#   202205010102 ダ1400 fav_p=0.45974 ent=1.78532 → 発火
#   202205010101 ダ1400 fav_p=0.18904 ent=2.26707 → 非発火（選別不通過）
#   202205010104 ダ1600 fav_p=0.37447 ent=1.87595 → 非発火（距離）
#   202205010110 芝1400 fav_p=0.37538 ent=1.70756 → 非発火（芝）
PROBE_CASES = [
    ("202205010102", True, 0.45974, 1.78532, "ダ1400×選別通過→発火"),
    ("202205010101", False, 0.18904, 2.26707, "ダ1400×選別不通過→非発火"),
    ("202205010104", False, 0.37447, 1.87595, "ダ1600×選別通過→距離で非発火"),
    ("202205010110", False, 0.37538, 1.70756, "芝1400×選別通過→芝で非発火"),
]


def _hist_tan(rid):
    d = json.load(open(os.path.join(_DIR, "hist", f"{rid}.json"), encoding="utf-8"))
    tan = {o["num"]: o["odds"] for o in d["result"]["order"] if o.get("odds")}
    return d["race"], tan


def probe():
    """発火ロジックとログの健全性を検査。異常は例外。戻り値は1行サマリ。"""
    # (a) 選別判定モジュールの自己検査（凍結値・式）
    EX.selftest()
    # (b) 既知レース4象限の発火指紋（該当/非該当×選別通過/不通過）
    for rid, want, wf, we, why in PROBE_CASES:
        race, tan = _hist_tan(rid)
        fav_p, ent = EX.metrics(tan)
        assert abs(fav_p - wf) < 1e-4 and abs(ent - we) < 1e-4, \
            f"{rid} fav_p/ent指紋不一致 got=({fav_p:.5f},{ent:.5f}) want=({wf},{we})"
        got = fire(race["surface"], race["distance"], fav_p, ent)
        assert got == want, f"{rid} {why} のはずが fire={got}"
    # (c) 純関数fireの境界: 1400ちょうど発火・1401非発火・指標欠落は非発火
    assert fire("ダ", 1400, 0.341, 1.904) and not fire("ダ", 1401, 0.5, 1.5)
    assert not fire("ダ", 1200, None, None) and not fire("芝", 1200, 0.5, 1.5)
    # (d) 買い目の組み立て（key書式=payout/オッズ辞書と同じ昇順結合）
    w, legs, t = bets_for([5, 3, 7, 2, 9, 1, 4])
    assert w == "3-5" and legs == [7, 2, 9, 1], f"買い目構成が壊れた: {w} {legs}"
    assert t == ["3-5-7", "2-3-5", "3-5-9", "1-3-5"], f"三連複comboが壊れた: {t}"
    assert bets_for([5, 3, 7])[2] == ["3-5-7"], "頭数不足時の縮退が壊れた"
    # (e) n<80 では ROI がいくつでも「検証中」（早期昇格の禁止）
    assert verdict(79, 250.0).startswith("🔍 検証中"), "n<80で昇格判定が出てしまう"
    assert "昇格検討" in verdict(80, 120.0) and "棄却" in verdict(80, 99.9)
    # (f) 台帳の健全性（1行1レース・必須キー・掛け金ゼロ・重複なし）
    rows = load_log()
    for r in rows:
        for k in ("rid", "date", "fav_p", "ent", "wide", "trio"):
            if k not in r:
                raise RuntimeError(f"w12_log.jsonl に壊れた行: {r.get('rid')} ({k}欠落)")
        if r.get("stake"):
            raise RuntimeError(f"W12記録に賭け金が入っている（ゼロのはず）: {r['rid']}")
    ids = [r["rid"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("w12_log.jsonl に rid 重複")
    st = sum(1 for r in rows if r.get("settled"))
    return (f"発火4象限指紋OK・境界/買い目/検証中規則OK / 台帳{len(rows)}R(精算{st})")


def main():
    ap = argparse.ArgumentParser(description="W12紙上フォワード（記録専用・掛け金ゼロ）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run", help="発火判定と記帳")
    p1.add_argument("races", nargs="+", help="race_jsonパス または race_id")
    p1.add_argument("--allow-past", action="store_true",
                    help="過去日付/結果ありでも記帳（後知恵記録になるため通常は使わない）")
    p1.add_argument("--no-record", action="store_true", help="表示のみ・記帳しない")
    p1.add_argument("--post", default=None, help="発走時刻 HH:MM（3分前で記帳凍結）")
    p1.add_argument("--fresh-combo", action="store_true",
                    help="ワイド/三連複オッズもJRA公式から取り直す（約15-20秒/R）")
    p1.add_argument("--no-odds", action="store_true", help="オッズ取得を省略（判定不能になる）")
    sub.add_parser("settle", help="確定払戻の取り込み")
    sub.add_parser("stats", help="n/的中率/ROI（判定時オッズ・確定払戻の両基準）")
    sub.add_parser("probe", help="自己診断（selfcheckが呼ぶ）")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "settle":
        cmd_settle()
    elif a.cmd == "stats":
        cmd_stats()
    else:
        print(probe())


if __name__ == "__main__":
    main()
