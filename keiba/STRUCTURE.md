# keiba/ ファイル構成マップ（2026-07-26整理）

**入口は3つだけ。迷ったらこの順で:**
```bash
python3 selfcheck.py                              # ①毎セッション最初に必ず(環境+回帰検査)
python3 day_board.py                              # ②当日の全レース判定(S/SS発火・買い目)
python3 day_board.py --baba                       # ②' 全開催場の現在馬場だけ即confirm(発走前チェック毎)
python3 fetch_race.py <race_id> --run --budget 10000   # ③単レース予想
```

## トップ階層 = 現役のみ（過去物は archive/、実行ログは logs/）

### 台帳(md) — 読む順
| ファイル | 役割 |
|---|---|
| RULES.md | ★運用ルールと教訓。**冒頭のV4確定事項から読む** |
| SOP.md | 作業手順・馬柱→json変換規則 |
| STRUCTURE.md | 本書（地図） |
| MODEL_V4_RESULT.md | V4作り替えの結果と理論(7/26)。tier用語訂正・オッズ必須の証明 |
| COND_MAP_20260723.md | 条件マップ(用語訂正の注記あり) |
| MODEL_V4_PLAN.md / MODEL_DIAGNOSIS_20260725.md | V4の計画と診断(経緯) |
| ROUTINE.md / AUTO_PLAYBOOK.md / INPUT_GUIDE.md / template-v99.27.md | 自動化・入力の手引き |
| JRA_PATTERNS_AUDIT.md / MAIDEN_N1000_20260725.md | パターン監査・未勝利/千直の採掘記録 |

### 当日運用パイプライン(py)
```
selfcheck.py     起動検査(git同期/依存/回帰指紋/発火仕様/JST)
day_board.py     デイボード: 大井+JRA全場をS/SS/A/B/C判定・全発火パターン列挙
fetch_race.py    race_id→出馬表+過去9走取得→予想まで一気通貫
predict.py       race_json→ランキング→オッズ→買い目→i-PAT文字列
pick_races.py    週末レース選定 / --ev 期待値スキャン / --prescreen 事前絞り
patterns.py      ★JRA買いパターンカタログ(発火・抑止・SS/S/A/B階級)
oi_patterns.py   大井版パターン
n1000_system.py  新潟芝1000直専用(--live <rid>)
log_result.py / stats.py / paper.py   結果記録・通算成績・紙上運用
```

### モデル層(py)
```
calc.py          Ver.99.27得点エンジン(TAS/展開/LTS。babaを使う→毎回ライブ取得必須)
v2_live.py       得点差し替え: 既定V3(model_v3.txt) / KEIBA_ENGINE=v4でV4(5種平均)
fit_v2.py        特徴定義(FEATS 27 + V4のRAW_FEATS/CTX_FEATS) ※特徴を触ったらselfcheckの回帰指紋を必ず回す
features2.py     U2追加12特徴(exp_course_apt等4本をimport→この4本は移動禁止)
fit_v4.py        V4学習(二値×5シード) / fit_v3.py V3学習 / fit.py,fit_score.py 較正
wf_compare.py    V3/V4を同一foldで4ゲート比較 / score_wfpreds.py 既存予測の採点
verify_all.py    実装済み全パターンをwf_preds.jsonlから再計算する監査
mine_cond.py / oddsfree_mine.py / rule_audit.py   条件採掘と偽陽性検定(--null-sweep)
baba_impact.py   実装済み全パターンの馬場(良/稍/重不)別ROI実測
course.py        コース特性VG・JRA枠割当(jra_waku)
harvest.py       学習データ収穫(hist/) / harvest_year.py, harvest_nar_year.py 年次収穫
```

### データ
```
model_v3.txt / model_v4_s0..4.txt      本番モデル(V4は5本平均で使う)
params.json / params_v2.json           較正パラメータ
pattern_stats.json                     patterns.pyが実行時に読む(移動禁止)
jockey_stats.json / speedidx.json / sire_map.json   補助DB
results.jsonl / paper_log.jsonl        ★実弾/紙上の戦績台帳(追記のみ)
wf_preds.jsonl / wf_preds_v4bin*.jsonl WF予測(V3/V4)＝全採掘の原典
hist/ hist_feat/ hist_odds/            JRA学習データ(6701R) ※hist2023/=拡張収穫中(202R)
hist_nar*/                             NAR学習データ
n1000_*.jsonl,json                     新潟千直5年分
```

### 退避
```
archive/races/     過去レースの入力json・tsiテキスト・ブックマークレット
archive/reports/   日付付きボード/ランキング/計画書(AUDIT_20260712.md等もここ)
archive/builders/  一回きりの build_*.py (手動レース構築の見本として参照可)
logs/              実験・学習の実行ログ(.out/.log)
```

## ミスらないための約束(コード化済みのもの)
- **selfcheckが落ちたら作業を始めない**(コンテナリセット・特徴の漏れ・発火仕様の破壊を検出する)
- day_boardは発火した**全パターンを併記**する(単勝の陰に三連複が隠れた7/26事故の再発防止)
- `--fast`でも馬場(baba)は必ずライブ更新される(7/26修正済)
- 外枠モデル2位はV4では自動で発火しない(V3の枠バグ由来のため)
- 新パターンは mine_cond基準 + rule_audit --null-sweep を通るまで実弾に載せない

※購入・投票・GOは人間。認証情報は扱わない。netkeibaにログインしない。
