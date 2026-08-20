# -*- coding: utf-8 -*-
"""V99W学習配点の紙上並走レーン（2026-08-19新設・掛け金ゼロの記録専用）。

   V99W_REPORT.md で合格した学習配点（腕A=全体1本 / B-sd=芝ダ×距離帯6群）と、
   V99W2_REPORT.md で最良となった B-sd16（B-sdの11成分+乗数に CORNER4特徴
   spd_res/mgn_abs/wide4c/pos_gain を足した16成分・同6群。2026-08-19追加）を、
   本番エンジン（calc.py/params.json/patterns.py/predict.py の既定動作）には
   一切触れずに、レースごとの「現行WAvg順位 vs 学習配点順位」の対比として
   記帳・精算・集計する。8/22からの凍結ルールブック実測と並走させる。

   usage:
     python3 v99w_rank.py run <race_json|race_id> [...] [--allow-past] [--no-record]
                              [--post HH:MM] [--no-odds]
         # 対比表を表示し v99w_live.jsonl に記帳（発走前のみ。過去日付/結果ありは既定ブロック）
         # 対比表の下に選別判定（exclusion.py: 予想可能(A∧B)/例外）を1行表示・記帳（--no-oddsで省略）
     python3 v99w_rank.py settle    # 結果確定済みレースの着順を取り込む（捏造禁止・確定後のみ）
     python3 v99w_rank.py stats     # 現行 vs 腕A vs B-sd vs B-sd16 の複勝的中率（1位が3着内）

   記録先: v99w_live.jsonl（1行=1レース。B-sd16は bsd16 系フィールドの追加のみ＝
           既存レコードはそのまま読める後方互換）
   モデル: v99w_result.pkl（無ければ build_comps_v99.py → v99w_fit.py --stage final で再生成）
           v99w2_result.pkl（B-sd16。無ければ corner_eval.py build → v99w2_fit.py で再生成）
   CORNER特徴のライブ生成: corner_live.py（corner_ds.npz と一致することを検算済み）
   ※購入機能なし。これは順位の記録だけ。判定・買い目はライブ既定（patterns/day_board）が正。"""
import argparse, ast, datetime, json, os, pickle, subprocess, sys

import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import calc

LOG = os.path.join(_DIR, "v99w_live.jsonl")
PKL = os.path.join(_DIR, "v99w_result.pkl")
PKL2 = os.path.join(_DIR, "v99w2_result.pkl")
SEL2 = os.path.join(_DIR, "v99w2_sel.json")
CORNER_DS = os.path.join(_DIR, "corner_ds.npz")
COMPS_PKL = os.path.join(_DIR, "comps_v99.pkl")

# v99w_fit.py の COMPS と同一順（末尾 kankai=(乗数-1)×100）
COMPS = ["tsi", "lts", "fsi", "bonus", "dsi", "nsi", "csi",
         "was", "tas", "hcs", "nrja", "kankai"]


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


# ───────── モデル ─────────
def load_model(auto_fit=True):
    """v99w_result.pkl から腕A重み(wg)と B-sd重み({(芝ダ,距離帯):w}) を読む。"""
    if not os.path.exists(PKL):
        if not auto_fit:
            raise RuntimeError("v99w_result.pkl が無い。"
                               "python3 build_comps_v99.py && python3 v99w_fit.py --stage final")
        print("v99w_result.pkl が無いため再生成する（約30秒）…", file=sys.stderr)
        if not os.path.exists(COMPS_PKL):
            subprocess.run([sys.executable, "build_comps_v99.py"], cwd=_DIR, check=True)
        subprocess.run([sys.executable, "v99w_fit.py", "--stage", "final"],
                       cwd=_DIR, check=True)
    d = pickle.load(open(PKL, "rb"))
    wg = np.array([d["wg"][c] for c in COMPS])
    wsd = {ast.literal_eval(k): np.asarray(v, dtype=float)
           for k, v in d["ws_axes"]["sd"].items()}
    return wg, wsd


def load_model16(auto_fit=True):
    """v99w2_result.pkl から B-sd16（16成分×芝ダ×距離帯6群）と全体1本wg16を読む。
       欠落時は load_model と同じ流儀で依存の欠けたものだけ順に再生成する。"""
    if not os.path.exists(PKL2):
        cmd = ("python3 corner_eval.py build && python3 v99w2_fit.py --stage mine "
               "&& python3 v99w2_fit.py --stage final")
        if not auto_fit:
            raise RuntimeError(f"v99w2_result.pkl が無い。{cmd}")
        print("v99w2_result.pkl が無いため再生成する…", file=sys.stderr)
        load_model(auto_fit=True)             # comps_v99.pkl / v99w_result.pkl を先に確保
        if not os.path.exists(CORNER_DS):
            subprocess.run([sys.executable, "corner_eval.py", "build"],
                           cwd=_DIR, check=True)
        if not os.path.exists(SEL2):
            subprocess.run([sys.executable, "v99w2_fit.py", "--stage", "mine"],
                           cwd=_DIR, check=True)
        subprocess.run([sys.executable, "v99w2_fit.py", "--stage", "final"],
                       cwd=_DIR, check=True)
    d = pickle.load(open(PKL2, "rb"))
    w = d["arm2_w"]
    wg16 = np.asarray(w["wg16"], dtype=float)
    ws16 = {ast.literal_eval(k): np.asarray(v, dtype=float)
            for k, v in w["ws16"].items()}
    return wg16, ws16


# ───────── スコア計算 ─────────
def scores_for(race):
    """calc.run（本番paramsのまま。成分値はparams非依存）→ rows と レース内標準化Z。
       Z の作り方は v99w_fit.load_races と同一（成分11+（乗数-1)×100、レース内z化）。"""
    res = calc.run(race)
    rows = res["rows"]                       # 現行WAvg降順＝現行順位
    X = np.array([[r[c] for c in COMPS[:-1]] + [(r["mult"] - 1.0) * 100.0]
                  for r in rows])
    mu = X.mean(0)
    sd = X.std(0)
    Z = np.where(sd > 1e-9, (X - mu) / np.where(sd > 1e-9, sd, 1.0), 0.0)
    return rows, Z


def z16_for(race, rows, Z, date):
    """Z16 = [Z(12成分) | CORNER4のレース内z]（v99w2_fit.attach_corner と同じ並び）。
       corner z はライブ経路（corner_live.py）で生成。欠測はz=0（同じ規約）。
       返り値: (Z16, corner無情報の頭数)。"""
    import corner_live
    cz = corner_live.corner_z(race, date)
    C = np.array([cz.get(r["num"], [0.0] * 4) for r in rows], dtype=float)
    nz0 = int(sum(1 for row in C if not row.any()))
    return np.hstack([Z, C]), nz0


def score_bsd16(race, rows, Z, date, wg16, ws16):
    """B-sd16スコア（群が既知なら群別重み、無ければ全体1本wg16）。"""
    Z16, nz0 = z16_for(race, rows, Z, date)
    wb = ws16.get(sd_key(race))
    return Z16 @ (wb if wb is not None else wg16), (wb is not None), nz0


def rank_nums(rows, score):
    """v99w_fit.rank_horses と同じタイブレーク（スコア↓→WAvg↓→馬番↑）。"""
    o = sorted(range(len(rows)),
               key=lambda i: (-score[i], -rows[i]["wavg"], rows[i]["num"]))
    return [rows[i]["num"] for i in o]


def sd_key(race):
    return (race.get("surface"), race.get("dist_cat")
            or ("S" if race["distance"] <= 1400 else
                "M" if race["distance"] <= 1700 else "L"))


# ───────── 入出力 ─────────
def find_race_path(arg):
    """race_jsonパス か race_id → 実ファイルパス（race_{id}.json → hist/{id}.json の順）。"""
    if os.path.exists(arg):
        return arg
    for cand in (os.path.join(_DIR, f"race_{arg}.json"),
                 os.path.join(_DIR, "hist", f"{arg}.json")):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(f"race_json が見つからない: {arg}")


def load_race(arg):
    """race_jsonパス か race_id を受け、(race, date_str|None, has_result) を返す。
       hist形式 {"race":…,"result":…,"date":…} と fetch_race形式（素のrace）の両対応。"""
    d = json.load(open(find_race_path(arg), encoding="utf-8"))
    if "race" in d and "horses" not in d:     # hist ラッパ
        return d["race"], (str(d["date"]) if d.get("date") else None), bool(d.get("result"))
    return d, None, False


def get_tan(rid, arg, has_result, tminus):
    """判定時点の単勝オッズ辞書 {馬番int: オッズ} と出所。
       過去（結果あり）= hist の確定単勝（最終オッズ・ネット不要。検証用の代理値）。
       ライブ = predict.fetch_jra（発走30分前以内は fresh=True で JRA公式。
       watch_log.cmd_run と同じ流儀。netkeiba無料オッズは40-50分遅れ＝RULES §7）。"""
    if has_result:
        try:
            d = json.load(open(find_race_path(arg), encoding="utf-8"))
            order = (d.get("result") or {}).get("order") or []
            tan = {int(o["num"]): float(o["odds"]) for o in order if o.get("odds")}
            if tan:
                return tan, "hist_final"
        except Exception:
            pass
    try:
        import predict as PR
        fresh = tminus is not None and 0 < tminus <= 30
        od = PR.fetch_jra(rid, fresh=fresh)
        tan = {int(k): float(v) for k, v in (od.get("tan") or {}).items() if v}
        if tan:
            return tan, od.get("tan_source")
    except Exception:
        pass
    return {}, None


def load_log():
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]


def save_log(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ───────── run ─────────
def show_table(race, rid, rows, cur, armA, bsd, bsd16, sA, sB, s16):
    rk = {arm: {n: i + 1 for i, n in enumerate(o)}
          for arm, o in (("cur", cur), ("A", armA), ("B", bsd), ("B16", bsd16))}
    print(f"── V99W並走 {rid} {race.get('venue','')} "
          f"{race.get('surface','')}{race.get('distance','')} "
          f"帯{sd_key(race)[1]} {race.get('baba','')} tier{race.get('today_tier','')} "
          f"{len(rows)}頭 ──")
    print("馬番  馬名              現行  腕A  B-sd  B-16   (腕A/B-sd/B-sd16スコア)")
    for i, r in enumerate(rows):
        n = r["num"]
        print(f" {n:>3}  {r['name']:<8s}\t {rk['cur'][n]:>3} {rk['A'][n]:>4} "
              f"{rk['B'][n]:>4} {rk['B16'][n]:>5}    "
              f"({sA[i]:+.3f}/{sB[i]:+.3f}/{s16[i]:+.3f})")
    marks = []
    for label, o in (("腕A", armA), ("B-sd", bsd), ("B-sd16", bsd16)):
        if set(o[:3]) != set(cur[:3]):
            marks.append(f"▲{label}入替")
    top = (f"上位3頭: 現行{cur[:3]} 腕A{armA[:3]} B-sd{bsd[:3]} B-sd16{bsd16[:3]}"
           + ("  " + " ".join(marks) if marks else "  （現行と同メンバー）"))
    print(top)
    return marks


def cmd_run(args):
    wg, wsd = load_model()
    wg16, ws16 = load_model16()
    now = jst_now()
    today = now.strftime("%Y%m%d")
    logs = load_log()
    byrid = {r["rid"]: r for r in logs}
    n_new = n_upd = 0
    for arg in args.races:
        try:
            race, rdate, has_result = load_race(arg)
        except Exception as e:
            print(f"  {arg}: 読込失敗 {e}", file=sys.stderr)
            continue
        rid = str(race.get("race_id") or os.path.basename(arg).replace(".json", ""))
        date = rdate or today            # B-sd16のベンチはこの日付より前のhistのみ参照(as-of)
        rows, Z = scores_for(race)
        sA = Z @ wg
        wb = wsd.get(sd_key(race))
        sB = Z @ (wb if wb is not None else wg)
        s16, grp16, nz0 = score_bsd16(race, rows, Z, date, wg16, ws16)
        cur = [r["num"] for r in rows]
        armA = rank_nums(rows, sA)
        bsd = rank_nums(rows, sB)
        bsd16 = rank_nums(rows, s16)
        marks = show_table(race, rid, rows, cur, armA, bsd, bsd16, sA, sB, s16)
        if nz0:
            print(f"  （corner特徴が全欠測の馬 {nz0}/{len(rows)}頭 → z=0扱い）",
                  file=sys.stderr)
        judged_tminus = None
        if args.post:
            try:
                ph, pm = (int(x) for x in args.post.split(":"))
                judged_tminus = (ph * 60 + pm) - (now.hour * 60 + now.minute)
            except Exception:
                pass
        # 選別ライブ判定（exclusion.py・EXCLUSION_REPORT_20260818の凍結値。A∧B=予想可能）
        excl = None
        if not args.no_odds:
            import exclusion
            tan, osrc = get_tan(rid, arg, has_result, judged_tminus)
            excl = exclusion.judge(tan, s16)
            excl["odds_src"] = osrc
            print("  " + exclusion.line(excl))
        if args.no_record:
            continue
        prev = byrid.get(rid)
        if prev and prev.get("settled"):
            print(f"  {rid}: 精算済みのため記帳せず（記録は不変）", file=sys.stderr)
            continue
        # 後知恵ブロック（paper_rank踏襲）: 過去日付 or 結果同梱のrace_jsonは既定で記帳しない
        past = (date < today) or has_result
        if past and not args.allow_past:
            print(f"  {rid}: 過去日付/結果ありのため記帳しない（後知恵防止）。"
                  f"検証目的の追記は --allow-past", file=sys.stderr)
            continue
        # 発走3分前で凍結（paper_rank踏襲）。発走後の再記帳は入力が汚れるためブロック
        if judged_tminus is not None and judged_tminus <= 3 and not args.allow_past:
            print(f"  {rid}: 発走{judged_tminus:+d}分＝凍結時刻を過ぎたため記帳しない", file=sys.stderr)
            continue
        entry = dict(rid=rid, date=date, venue=race.get("venue"),
                     surface=race.get("surface"), dist_cat=sd_key(race)[1],
                     field=len(rows), cur=cur, armA=armA, bsd=bsd, bsd16=bsd16,
                     swap=dict(armA=set(armA[:3]) != set(cur[:3]),
                               bsd=set(bsd[:3]) != set(cur[:3]),
                               bsd16=set(bsd16[:3]) != set(cur[:3])),
                     bsd_group="known" if wb is not None else "fallback_wg",
                     bsd16_group="known" if grp16 else "fallback_wg16",
                     corner_zero=nz0, excl=excl,
                     recorded=now.strftime("%m%d %H:%M"),
                     judged_tminus=judged_tminus,
                     past=bool(past), settled=False)
        if prev:
            entry["recorded_first"] = prev.get("recorded_first", prev["recorded"])
            n_upd += 1
        else:
            entry["recorded_first"] = entry["recorded"]
            n_new += 1
        byrid[rid] = entry
        print(f"  📝 記帳 {rid} " + (" ".join(marks) if marks else "(上位3頭一致)"),
              file=sys.stderr)
    if not args.no_record:
        keep = [r for r in logs if r["rid"] not in byrid]
        save_log(keep + list(byrid.values()))
        print(f"記帳 新規{n_new} 更新{n_upd} / 総{len(byrid)}件 → {LOG}", file=sys.stderr)


# ───────── settle ─────────
def cmd_settle():
    """結果が確定したレースだけ着順を取り込む（fetch_result=histと同じ取得経路）。
       払戻(単勝)が出るまで＝確定前は書かない。結果の手入力・捏造は不可。"""
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
        r["fin"] = {str(k): v for k, v in sorted(fin.items())}
        r["result_top3"] = res.get("top3") or \
            [n_ for n_, rk in sorted(fin.items(), key=lambda kv: kv[1])[:3]]
        r["settled"] = True
        r["settled_at"] = jst_now().strftime("%m%d %H:%M")
        n += 1
        hits = []
        for arm in ("cur", "armA", "bsd", "bsd16"):
            if not r.get(arm):           # 旧レコード（B-sd16追加前）は3レーンのまま
                continue
            f1 = fin.get(r[arm][0])
            hits.append(f"{arm}1位={r[arm][0]}" + (f"({f1}着)" if f1 else "(着外)")
                        + ("🎯" if f1 and f1 <= 3 else ""))
        print(f"  ✅ {r['rid']} {r.get('venue','')} " + "  ".join(hits), file=sys.stderr)
    save_log(logs)
    print(f"精算 {n}件", file=sys.stderr)


# ───────── stats ─────────
def _block(rows, label):
    if not rows:
        print(f"  ({label}: 0R)")
        return
    print(f"  {label}: {len(rows)}R")
    for arm, name in (("cur", "現行WAvg"), ("armA", "腕A(全体1本)"),
                      ("bsd", "B-sd(芝ダ×距離帯)"), ("bsd16", "B-sd16(+corner4)")):
        sub = [r for r in rows if r.get(arm)]   # 旧レコードにbsd16は無い（後方互換）
        if not sub:
            continue
        fuku = win = 0
        for r in sub:
            f1 = r["fin"].get(str(r[arm][0]))
            if f1:
                fuku += f1 <= 3
                win += f1 == 1
        note = f" [{len(sub)}R]" if len(sub) != len(rows) else ""
        print(f"    {name:<16s}: 複勝(1位が3着内) {fuku}/{len(sub)} "
              f"({100.0*fuku/len(sub):.1f}%)   1着 {win} ({100.0*win/len(sub):.1f}%){note}")
    sw = [r for r in rows if any(r["swap"].get(a) for a in ("armA", "bsd", "bsd16"))]
    print(f"    参考: 上位3頭が現行と入替のレース {len(sw)}/{len(rows)}")


def cmd_stats():
    logs = [r for r in load_log() if r.get("settled")]
    if not logs:
        print("精算済みレコードなし（settle を先に）")
        return
    print(f"V99W並走レーン（掛け金ゼロ・順位記録のみ・4レーン対比）: {len(logs)}R精算済み")
    live = [r for r in logs if not r.get("past")]
    back = [r for r in logs if r.get("past")]
    _block(live, "ライブ記帳（発走前判定）[実測]")
    _block(back, "--allow-past 追記（検証用バックフィル）[参考]")
    print("  ※これは並び替え精度の並走記録。買い判定・実弾検討はライブ既定"
          "（PATTERNS_FROZEN/paper_rank）の側で行う。")


# ───────── main ─────────
def main():
    ap = argparse.ArgumentParser(description="V99W学習配点の紙上並走（記録専用）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run", help="対比表の表示と記帳")
    p1.add_argument("races", nargs="+", help="race_jsonパス または race_id")
    p1.add_argument("--allow-past", action="store_true",
                    help="過去日付/結果ありでも記帳（後知恵記録になるため通常は使わない）")
    p1.add_argument("--no-record", action="store_true", help="表示のみ・記帳しない")
    p1.add_argument("--post", default=None, help="発走時刻 HH:MM（3分前で記帳凍結）")
    p1.add_argument("--no-odds", action="store_true",
                    help="オッズ取得と選別判定(exclusion.py)を省略する")
    sub.add_parser("settle", help="確定結果の取り込み")
    sub.add_parser("stats", help="現行 vs 腕A vs B-sd vs B-sd16 の複勝的中率")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "settle":
        cmd_settle()
    else:
        cmd_stats()


if __name__ == "__main__":
    main()
