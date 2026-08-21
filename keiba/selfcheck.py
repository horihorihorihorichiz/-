# -*- coding: utf-8 -*-
"""起動検査（毎セッション最初に1回実行する）。「迷わない・ミスらないシステム」の入口。

   コンテナリセット・モデル交代・ファイル移動があっても、これ1本が通れば
   予想パイプラインは安全に動く。落ちた項目には対処コマンドを表示する。

   検査内容:
     1. git同期      : ローカルがorigin/claude/stoic-ride-p35k9nに追従しているか(リセット検出)
     2. 依存         : numpy / lightgbm
     3. 必須ファイル : モデル・パラメータ・台帳
     4. V3回帰指紋   : 既知レースの得点が既知値と一致するか(モデル/特徴の取り違え検出)
     5. パターン発火 : patterns.py の代表発火・抑止・V4ゲートが仕様通りか
     6. JST時刻      : 実行時刻の取得(時間軸ズレ事故の防止)
     7. JRA公式オッズ: jra_odds.py が sp.jra.jp に到達し単複を取れるか(非開催日はスキップ)
     8. watch台帳    : watch_log.py のW10/W11判定ロジックと台帳の健全性
     8a. W12発火     : w12_watch.py のダ短×選別発火ロジック(既知4レース指紋)と台帳
     9. 通知ギャップ : notify.py の欠落検出・実行基盤停止(ギャップ)検出が動くか

   usage: python3 selfcheck.py        # 全部
          python3 selfcheck.py -q     # 結果1行のみ
          KEIBA_SELFCHECK_NONET=1 python3 selfcheck.py   # 外部サイトを叩く検査を飛ばす
"""
import datetime, json, os, subprocess, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)

OK, NG, SKIP = [], [], []


class Skip(Exception):
    """検査の前提が今日は成立しない(非開催日など)。NGではない。"""


def check(name, fn, fix=""):
    try:
        detail = fn()
        OK.append((name, detail or ""))
    except Skip as s:
        SKIP.append((name, f"{s}"))
    except Exception as e:
        NG.append((name, f"{e}", fix))


# 1. git同期 ---------------------------------------------------------------
def git_sync():
    subprocess.run(["git", "fetch", "-q", "origin", "claude/stoic-ride-p35k9n"],
                   capture_output=True, timeout=60)
    behind = subprocess.run(
        ["git", "rev-list", "--count", "HEAD..origin/claude/stoic-ride-p35k9n"],
        capture_output=True, text=True).stdout.strip()
    if behind and int(behind) > 0:
        raise RuntimeError(f"リモートより{behind}コミット遅れ＝コンテナリセットの疑い")
    return "originに追従"


check("git同期", git_sync,
      fix="git merge --ff-only origin/claude/stoic-ride-p35k9n && pip install -q numpy lightgbm")

# 2. 依存 -----------------------------------------------------------------
check("依存(numpy/lightgbm)", lambda: __import__("numpy") and __import__("lightgbm") and "OK",
      fix="pip install -q numpy lightgbm")

# 3. 必須ファイル -----------------------------------------------------------
REQUIRED = ["model_v3.txt", "model_v5.txt", "params.json", "params_v2.json", "pattern_stats.json",
            "results.jsonl", "RULES.md", "SOP.md",
            "model_v4_s0.txt", "model_v4_s1.txt", "model_v4_s2.txt",
            "model_v4_s3.txt", "model_v4_s4.txt",
            "filtered_w16.json", "hori_v100_w.json"]
check("必須ファイル", lambda: (
    (lambda miss: (_ for _ in ()).throw(RuntimeError(f"欠落: {miss}")) if miss else f"{len(REQUIRED)}本OK")
    ([f for f in REQUIRED if not os.path.exists(f)])))

# 4. V3回帰指紋 -------------------------------------------------------------
#    hist/202610020612.json のV3得点top3は (15,106.8)(8,103.8)(5,103.5) で固定のはず。
#    ズレたら「特徴の変更がV3経路に漏れた」か「モデルファイル取り違え」。
def v3_regression():
    import calc, v2_live
    d = json.load(open("hist/202610020612.json", encoding="utf-8"))
    res = calc.run(d["race"])
    info = v2_live.rescore(d["race"], res["rows"])
    if not info or info["engine"] != "Ver.3(LambdaRank)":
        raise RuntimeError(f"エンジンがV3でない: {info}")
    got = [(r["num"], r["wavg"]) for r in res["rows"][:3]]
    # 7/27情報統一(speedidx 2年化・tsi被覆66%)でhistの入力が変わり指紋も正当に更新。
    # 旧: [(15,106.8),(8,103.8),(5,103.5)] (tsi被覆21.9%時代)
    # 旧: [(15,106.8),(5,104.5),(8,103.5)] (7/27統一データ・〜7/12学習)
    # 8/2: 7/18-8/2の216R追加+speedidx再較正(74.2+6.65×raw)+V3/V5再学習後の指紋
    want = [(15, 104.3), (5, 103.2), (4, 102.1)]
    if got != want:
        raise RuntimeError(f"得点指紋不一致 got={got} want={want}")
    return "得点指紋一致"


check("V3回帰指紋", v3_regression, fix="git status で fit_v2/v2_live/model_v3.txt の変更を確認")


# 4b. V4エンジン(KEIBA_ENGINE=v4のときだけ使う経路) ---------------------------
def v4_engine():
    import calc, v2_live
    os.environ["KEIBA_ENGINE"] = "v4"
    try:
        d = json.load(open("hist/202610020612.json", encoding="utf-8"))
        res = calc.run(d["race"])
        info = v2_live.rescore(d["race"], res["rows"])
        if not info or not info["engine"].startswith("Ver.4"):
            raise RuntimeError(f"V4が起動しない: {info}")
        return info["engine"]
    finally:
        os.environ.pop("KEIBA_ENGINE", None)


check("V4エンジン起動", v4_engine, fix="model_v4_s*.txt の存在とfit_v2のRAW/CTX特徴を確認")


def v5_engine():
    import calc, v2_live
    os.environ["KEIBA_ENGINE"] = "v5"
    try:
        d = json.load(open("hist/202610020612.json", encoding="utf-8"))
        res = calc.run(d["race"])
        info = v2_live.rescore(d["race"], res["rows"])
        if not info or not info["engine"].startswith("Ver.5"):
            raise RuntimeError(f"V5が起動しない: {info}")
        return info["engine"]
    finally:
        os.environ.pop("KEIBA_ENGINE", None)


check("V5エンジン起動", v5_engine, fix="model_v5.txt の存在とEXTRA_FEATSを確認")


# 5. パターン発火(仕様の生きた検査) ------------------------------------------
def pattern_spec():
    import patterns
    # (a) 1勝クラス×10倍+ の最強帯が発火する
    r = patterns.classify(order=[3, 9, 1], tan={3: 12.0, 9: 4.0, 1: 2.5}, field=14,
                          surface="ダ", dist=1600, tier=6, gap12=0.5, p1=0.18,
                          day=3, venue="東京", baba="良")
    names = [x[0] for x in r]
    assert any("10倍+×1勝クラス" in n for n in names), f"最強帯が発火しない: {names}"
    # (b) 未勝利の乖離単勝は抑止される
    r = patterns.classify(order=[3, 9, 1], tan={3: 12.0, 9: 4.0, 1: 2.5}, field=14,
                          surface="ダ", dist=1600, tier=10, gap12=0.2, p1=0.18,
                          day=3, venue="東京", baba="良")
    assert any("新馬・未勝利" in x[0] and x[3].startswith("✕") for x in r), "未勝利抑止が消えた"
    # (c) 開催初日は抑止される
    r = patterns.classify(order=[3, 9, 1], tan={3: 12.0, 9: 4.0, 1: 2.5}, field=14,
                          surface="ダ", dist=1600, tier=6, gap12=0.5, p1=0.18,
                          day=1, venue="東京", baba="良")
    assert any("開催初日" in x[0] for x in r), "初日抑止が消えた"
    # (d) 外枠モデル2位はV3で発火・V4で発火しない
    kw = dict(order=[3, 9, 1, 5, 7, 2], tan={3: 12.0, 9: 8.0, 1: 2.5, 5: 4.0, 7: 20.0, 2: 30.0},
              field=14, surface="芝", dist=1600, tier=6, gap12=0.5, p1=0.2,
              day=3, venue="東京", spread15=2.0, waku2=8, baba="良")
    os.environ.pop("KEIBA_ENGINE", None)
    v3f = [x[0] for x in patterns.classify(**kw)]
    os.environ["KEIBA_ENGINE"] = "v4"
    try:
        v4f = [x[0] for x in patterns.classify(**kw)]
    finally:
        os.environ.pop("KEIBA_ENGINE", None)
    assert any("外枠モデル2位" in n for n in v3f), "V3で外枠2位が発火しない"
    assert not any("外枠モデル2位" in n for n in v4f), "V4で外枠2位が発火してしまう(廃止済のはず)"
    # (e) 芝三連複は良馬場限定
    kw2 = dict(order=[1, 2, 3, 4, 5], tan={1: 3.0, 2: 4.0, 3: 6.0, 4: 8.0, 5: 10.0},
               field=12, surface="芝", dist=1600, tier=5, gap12=0.3, p1=0.3,
               day=3, venue="東京", baba="不")
    r = patterns.classify(**kw2)
    assert not any("三連複モデル1-2-3位" in x[0] for x in r), "道悪で芝三連複が発火(良限定のはず)"
    # (f) 未勝利モデル2位は道悪で「△縁」へ自動降格(7/26 baba_impact: 良158.9% vs 道悪83.0%)
    kw3 = dict(order=[4, 8, 2], tan={4: 3.0, 8: 6.5, 2: 9.0}, field=12, surface="ダ",
               dist=1400, tier=10, gap12=0.8, p1=0.3, day=3, venue="東京")
    good = [x for x in patterns.classify(**kw3, baba="良") if "モデル2位" in x[0]]
    wet = [x for x in patterns.classify(**kw3, baba="重") if "モデル2位" in x[0]]
    assert good and good[0][3].startswith("◎"), f"良で未勝利2位が発火しない: {good}"
    assert wet and wet[0][3].startswith("△"), f"道悪で未勝利2位が降格しない: {wet}"
    # (g) 階級規則(8/15 SS再定義): SS=乖離230+×h4+ (ss_mine.py 237.6%/42R null p=0) / S=200-230×h4+
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス")[0] == "SS"
    assert patterns.tier_of(247, 4, "◎◎乖離単勝×システム強化")[0] == "SS"
    assert patterns.tier_of(210, 4, "◎◎乖離単勝×システム強化")[0] == "S"
    assert patterns.tier_of(247, 3, "◎◎乖離単勝×システム強化")[0] == "A"
    assert patterns.tier_of(165.9, 5, "◎◎芝 馬連モデル1-2位×1600-1800×自信")[0] == "A"
    # (h) 中山の乖離はB降格(7/29 sim場別: 中山18.9%/23R vs 他場287%)。未勝利2位と他場は対象外
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス", "中山")[0] == "B"
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス", "京都")[0] == "SS"
    assert patterns.tier_of(138.8, 3, "◎未勝利・新馬 モデル2位中穴単勝", "中山")[0] == "B"
    return "発火8仕様OK(最強帯/未勝利抑止/初日抑止/外枠V4廃止/三連複良限定/未勝利2位道悪降格/階級改4/中山乖離B降格)"


check("パターン発火仕様", pattern_spec, fix="patterns.py の直近変更を確認")


# 5.5 ルールブック凍結(2026-08-16 後知恵禁止ルール) ----------------------
def frozen_check():
    import hashlib
    import json as _json
    rec = _json.load(open(os.path.join(_DIR, "PATTERNS_FROZEN.json"), encoding="utf-8"))
    for f, want in rec["sha256"].items():
        got = hashlib.sha256(open(os.path.join(_DIR, f), "rb").read()).hexdigest()
        assert got == want, (f"{f} が凍結記録と不一致。ルール改定なら PATTERNS_FROZEN.json を"
                             f"新しい窓端とともに更新し、成績カウントは窓端より後の月からやり直すこと")
    return f"凍結{rec['frozen_at']}版と一致(窓端{rec['data_window_end']})"


check("ルールブック凍結", frozen_check,
      fix="意図した改定なら PATTERNS_FROZEN.json のsha256と窓端を更新(RULES.md §後知恵禁止)")

# 5.6 V99W並走レーン(2026-08-19新設・学習配点のゼロ掛け金記録。本番エンジン非依存) ----
#     v99w_result.pkl は.gitignore(コンテナリセットで消える)。土曜ライブで並走させる前に
#     モデルの存在と腕A/B-sdランキングの指紋をオフラインで確認する。
def v99w_lane():
    if not os.path.exists("v99w_result.pkl"):
        raise RuntimeError("v99w_result.pkl が無い(コンテナリセットで消えた可能性)")
    import v99w_rank
    wg, wsd = v99w_rank.load_model(auto_fit=False)
    assert len(wg) == 12, f"腕A重みの次元異常: {len(wg)}"
    assert len(wsd) == 6, f"B-sd群数異常: {len(wsd)} (芝ダ×S/M/L=6のはず)"
    d = json.load(open("hist/202610020612.json", encoding="utf-8"))
    rows, Z = v99w_rank.scores_for(d["race"])
    armA = v99w_rank.rank_nums(rows, Z @ wg)
    bsd = v99w_rank.rank_nums(rows, Z @ wsd[("芝", "S")])
    assert sorted(armA) == sorted(r["num"] for r in rows), "腕A順位が全頭順列でない"
    wantA, wantB = [5, 15, 8], [5, 8, 16]
    if armA[:3] != wantA or bsd[:3] != wantB:
        raise RuntimeError(f"V99W指紋不一致 腕A={armA[:3]}(want{wantA}) "
                           f"B-sd={bsd[:3]}(want{wantB})。v99w_fit再学習が意図的なら"
                           f"selfcheckの指紋を更新すること")
    # B-sd16レーン(2026-08-19追加。V99W2_REPORT.mdの最良配点+corner_liveのライブ特徴生成)
    if not os.path.exists("v99w2_result.pkl"):
        raise RuntimeError("v99w2_result.pkl が無い(コンテナリセットで消えた可能性)")
    wg16, ws16 = v99w_rank.load_model16(auto_fit=False)
    assert len(wg16) == 16, f"B-sd16重みの次元異常: {len(wg16)}"
    assert len(ws16) == 6, f"B-sd16群数異常: {len(ws16)} (芝ダ×S/M/L=6のはず)"
    z16 = v99w_rank.z16_for(d["race"], rows, Z, str(d["date"]))
    s16, grp16, _nz = v99w_rank.score_bsd16(d["race"], rows, Z, str(d["date"]),
                                            wg16, ws16, z16=z16)
    bsd16 = v99w_rank.rank_nums(rows, s16)
    assert grp16, "B-sd16の群(芝,S)が引けない"
    want16 = [5, 8, 15]
    if bsd16[:3] != want16:
        raise RuntimeError(f"V99W指紋不一致 B-sd16={bsd16[:3]}(want{want16})。"
                           f"v99w2_fit再学習/corner_live変更が意図的なら"
                           f"selfcheckの指紋を更新すること")
    # fltレーン(2026-08-20追加。filtered_w16.json=絞り専用配点wF。凍結・再学習しない)
    wF, flt_sha = v99w_rank.load_flt()
    assert len(wF) == 16, f"flt(wF)の次元異常: {len(wF)}"
    want_sha = "9380dd58004a"
    if flt_sha != want_sha:
        raise RuntimeError(f"filtered_w16.json のwF指紋不一致 {flt_sha}(want {want_sha})。"
                           f"wFは凍結配点＝書き換え禁止(EXCLUSION_REPORT_20260818追記)。"
                           f"正当な再学習ならレポートとselfcheck指紋を同時更新すること")
    flt = v99w_rank.rank_nums(rows, z16[0] @ wF)
    wantF = [5, 15, 8]
    if flt[:3] != wantF:
        raise RuntimeError(f"V99W指紋不一致 flt={flt[:3]}(want{wantF})。"
                           f"corner_live/z16経路の変更が意図的なら指紋を更新すること")
    # V100レーン(2026-08-21追加。hori_v100_w.json=堀川システムVer.100配点。凍結)
    w6, wg100, v100_sha = v99w_rank.load_v100()
    assert len(w6) == 6, f"V100群数異常: {len(w6)} (芝ダ×S/M/L=6のはず)"
    assert len(wg100) == 16, f"V100全体1本の次元異常: {len(wg100)}"
    want_v100_sha = "67ae1a5b91a5"
    if v100_sha != want_v100_sha:
        raise RuntimeError(f"hori_v100_w.json の指紋不一致 {v100_sha}(want {want_v100_sha})。"
                           f"Ver.100の配点は凍結＝書き換え禁止(HORIKAWA_V100.md)。"
                           f"標本追加などで正当に引き直したなら、レポートと"
                           f"selfcheckの指紋を同時に更新すること")
    v100 = v99w_rank.rank_nums(rows, z16[0] @ w6[("芝", "S")])
    wantV = [5, 15, 8]
    if v100[:3] != wantV:
        raise RuntimeError(f"V99W指紋不一致 V100={v100[:3]}(want{wantV})。"
                           f"corner_live/z16経路の変更が意図的なら指紋を更新すること")
    if os.path.exists("v99w_live.jsonl"):
        for ln in open("v99w_live.jsonl", encoding="utf-8"):
            if ln.strip():
                rec = json.loads(ln)
                assert {"rid", "date", "cur", "armA", "bsd"} <= set(rec), \
                    f"v99w_live.jsonl スキーマ異常: {sorted(rec)}"
    return ("モデルOK(腕A12次元/B-sd6群/B-sd16 16次元6群/flt16次元1本/"
            "V100 16次元6群)・指紋一致")


check("V99W並走レーン", v99w_lane,
      fix="python3 build_comps_v99.py && python3 v99w_fit.py --stage final && "
          "python3 corner_eval.py build && python3 v99w2_fit.py --stage mine && "
          "python3 v99w2_fit.py --stage final "
          "(再学習で指紋が正当に変わった場合は selfcheck.py の "
          "wantA/wantB/want16/wantF/wantV を更新)")

# 6. JST -----------------------------------------------------------------
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
check("JST時刻", lambda: now.strftime("%Y-%m-%d %H:%M JST"))


# 7. JRA公式オッズ(2026-08-17追加) -------------------------------------------
#    直前判定・凍結は fetch_jra(fresh=True)=sp.jra.jp が生命線(netkeibaは40-50分遅れ)。
#    週末朝に「実は取れなくなっていた」を当日発見しないための到達確認。
#    非開催日(JRA公式のオッズ一覧に開催が載らない日)はスキップ扱い。
def jra_odds_reach():
    if os.environ.get("KEIBA_SELFCHECK_NONET"):
        raise Skip("KEIBA_SELFCHECK_NONET=1 のため外部到達確認を省略")
    import re
    import jra_odds as JO
    try:
        idx = JO._http(JO.ACCESS_O, "cname=" + JO.ODDS_INDEX_CNAME)
    except Exception as e:
        raise RuntimeError(f"sp.jra.jp に到達できない: {e}")
    keys = sorted(set(re.findall(r"sw15orl\d{2}(\d{10})\d{8}/", idx)))
    if not keys:
        if "sw15orl" in idx:
            raise RuntimeError("オッズ一覧の開催リンク書式が変わった疑い(正規表現の見直しが必要)")
        raise Skip("JRA公式オッズ一覧に開催なし(=当日/前日がJRA非開催。週末は掲載される)")
    k = keys[-1]                                   # VV+YYYY+KK+DD
    rid = k[2:6] + k[:2] + k[6:8] + k[8:10] + "11"  # → netkeiba形式 YYYY+VV+KK+DD+RR
    d = JO.fetch_official(rid)
    if d.get("tan"):
        return (f"{len(keys)}開催掲載 / {rid} 単勝{len(d['tan'])}頭・複勝{len(d.get('fuku') or {})}頭 "
                f"取得OK({d.get('kai_nichi')} {d.get('asof')})")
    reason = d.get("reason") or "不明"
    if "パース" in reason or "構造" in reason:
        raise RuntimeError(f"公式ページのパース失敗=サイト構造変更の疑い: {reason}")
    raise Skip(f"到達OK・オッズ未取得({reason})")


check("JRA公式オッズ(sp.jra.jp)", jra_odds_reach,
      fix="python3 jra_odds.py <race_id> --debug で確認。取れない間は直前判定のオッズが40-50分遅れになる")


# 8. watch台帳(W10/W11ライブ記録) --------------------------------------------
def watch_log_health():
    import watch_log
    return watch_log.probe()


check("watch台帳(W10/W11)", watch_log_health,
      fix="python3 watch_log.py probe で詳細。台帳が壊れていたら watch_log.jsonl の該当行を確認")


# 8a. W12発火(2026-08-20新設・w12_watch.py: ダ短×選別×B-sd16上位2頭の紙上フォワード) ----
#     既知4レースの発火/非発火指紋(該当/非該当×選別通過/不通過)と凍結値・台帳健全性を
#     完全オフラインで検査。発火条件の出所=WATCHLIST.md W12 / EXCLUSION_REPORT_20260818.md。
def w12_health():
    import w12_watch
    return w12_watch.probe()


check("W12発火(w12_watch)", w12_health,
      fix="python3 w12_watch.py probe で詳細。台帳が壊れていたら w12_log.jsonl の該当行を確認")


# 8b. オッズ時系列の収集器(2026-08-18新設・odds_timeline.py) -------------------
#     開催日にポーリングしなければその日のオッズ変化は永久に失われる＝作り直しが効かない。
#     週末に「実は壊れていた」を当日発見しないためのロジック回帰(完全オフライン)。
def odds_timeline_health():
    import odds_timeline
    return odds_timeline.health()


check("オッズ時系列(odds_timeline)", odds_timeline_health,
      fix="python3 odds_timeline.py selftest で詳細。実地確認は python3 odds_timeline.py probe")


# 9. 通知の欠落・停止ギャップ検出(2026-08-16の28分停止事故の再発防止) -------------
def notify_health():
    import notify
    detail = notify.selftest()          # 一時ファイルで検査。実台帳には触れない
    od = notify.check()                 # 実台帳の現況(未送信の遅延通知)
    if od:
        raise RuntimeError(f"未送信の期限超過通知が{len(od)}件ある: "
                           + ", ".join(f"{r['race_id']}/{r['kind']}({r['late_min']}分遅延)" for r in od[:3]))
    return detail


check("通知台帳・停止ギャップ検出", notify_health,
      fix="python3 notify.py で欠落一覧。送信済みなら notify.mark()、送る意味が無いなら notify.close()")


def main():
    quiet = "-q" in sys.argv
    if not quiet:
        print("━━ selfcheck（迷わない・ミスらないための起動検査）━━")
        for name, detail in OK:
            print(f"  ✅ {name}: {detail}")
        for name, why in SKIP:
            print(f"  ⏭ {name}: スキップ({why})")
        for name, err, fix in NG:
            print(f"  ❌ {name}: {err}")
            if fix:
                print(f"     対処→ {fix}")
    status = ("ALL GREEN" + (f"(スキップ{len(SKIP)})" if SKIP else "")) if not NG else f"NG {len(NG)}件"
    print(f"selfcheck: {status} ({now.strftime('%m/%d %H:%M JST')})")
    if not NG and not quiet:
        print("\n次にやること:")
        print("  当日運用   : python3 day_board.py")
        print("  単レース   : python3 fetch_race.py <race_id> --run --budget 10000")
        print("  結果記録   : python3 log_result.py … → python3 stats.py")
    sys.exit(1 if NG else 0)


if __name__ == "__main__":
    main()
