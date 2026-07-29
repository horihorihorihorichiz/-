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

   usage: python3 selfcheck.py        # 全部
          python3 selfcheck.py -q     # 結果1行のみ
"""
import datetime, json, os, subprocess, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)

OK, NG = [], []


def check(name, fn, fix=""):
    try:
        detail = fn()
        OK.append((name, detail or ""))
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
            "model_v4_s3.txt", "model_v4_s4.txt"]
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
    want = [(15, 106.8), (5, 104.5), (8, 103.5)]
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
    # (g) 階級規則(7/27 sim改4): SS=乖離300+×h5+ / h4はA退避 / S=200-300×h4+ / 非乖離はヒート無視
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス")[0] == "SS"
    assert patterns.tier_of(383, 4, "◎◎乖離単勝×中距離×1勝クラス")[0] == "A"
    assert patterns.tier_of(247, 4, "◎◎乖離単勝×システム強化")[0] == "S"
    assert patterns.tier_of(165.9, 5, "◎◎芝 馬連モデル1-2位×1600-1800×自信")[0] == "A"
    # (h) 中山の乖離はB降格(7/29 sim場別: 中山18.9%/23R vs 他場287%)。未勝利2位と他場は対象外
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス", "中山")[0] == "B"
    assert patterns.tier_of(383, 5, "◎◎乖離単勝×中距離×1勝クラス", "京都")[0] == "SS"
    assert patterns.tier_of(138.8, 3, "◎未勝利・新馬 モデル2位中穴単勝", "中山")[0] == "B"
    return "発火8仕様OK(最強帯/未勝利抑止/初日抑止/外枠V4廃止/三連複良限定/未勝利2位道悪降格/階級改4/中山乖離B降格)"


check("パターン発火仕様", pattern_spec, fix="patterns.py の直近変更を確認")

# 6. JST -----------------------------------------------------------------
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
check("JST時刻", lambda: now.strftime("%Y-%m-%d %H:%M JST"))


def main():
    quiet = "-q" in sys.argv
    if not quiet:
        print("━━ selfcheck（迷わない・ミスらないための起動検査）━━")
        for name, detail in OK:
            print(f"  ✅ {name}: {detail}")
        for name, err, fix in NG:
            print(f"  ❌ {name}: {err}")
            if fix:
                print(f"     対処→ {fix}")
    status = "ALL GREEN" if not NG else f"NG {len(NG)}件"
    print(f"selfcheck: {status} ({now.strftime('%m/%d %H:%M JST')})")
    if not NG and not quiet:
        print("\n次にやること:")
        print("  当日運用   : python3 day_board.py")
        print("  単レース   : python3 fetch_race.py <race_id> --run --budget 10000")
        print("  結果記録   : python3 log_result.py … → python3 stats.py")
    sys.exit(1 if NG else 0)


if __name__ == "__main__":
    main()
