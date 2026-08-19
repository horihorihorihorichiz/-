# V99W並走レーン — 学習配点（腕A/B-sd/B-sd16）のゼロ掛け金ライブ記録

土曜（8/22〜）の運用への組み込み方。**本番（PATTERNS_FROZEN/day_board/predict）の判定・買い目には一切影響しない**。順位の記録だけ。

対比する4レーン:
| レーン | 中身 | 根拠 |
|---|---|---|
| 現行 | Ver.99.27 WAvg（等重み） | 本番と同じ並び |
| 腕A | 学習配点・全体1本（12成分） | V99W_REPORT.md |
| B-sd | 学習配点・芝ダ×距離帯6群（12成分） | V99W_REPORT.md |
| B-sd16 | **最良配点**。B-sdの11成分+乗数に CORNER4特徴（spd_res/mgn_abs/wide4c/pos_gain）を足した16成分×同6群 | V99W2_REPORT.md（CONFIRM 複勝1点 54.7%＝現行+5.0pt） |

```bash
python3 selfcheck.py                                   # V99W並走レーンの項目がALL GREENであること
python3 v99w_rank.py run race_<race_id>.json --post HH:MM   # 各レースのfetch_race後・発走前に1回
                                                       #（発走3分前で凍結。--post省略可だが推奨）
python3 v99w_rank.py settle                            # 当日夜または翌朝。確定結果のみ取り込み
python3 v99w_rank.py stats                             # 現行 vs 腕A vs B-sd vs B-sd16 の複勝的中率
```

- 表示の「▲腕A入替/▲B-sd入替/▲B-sd16入替」＝学習配点なら上位3頭の顔ぶれが変わるレース（観察対象）。
- 記録先は v99w_live.jsonl。B-sd16は `bsd16`/`swap.bsd16`/`bsd16_group`/`corner_zero` フィールドの**追加のみ**（旧3レーンのレコードもそのまま読める。statsでは [nR] 表記で区別）。
- 過去日付・結果同梱のrace_jsonは既定ブロック（検証時のみ --allow-past）。
- **B-sd16のCORNER特徴はライブ経路で生成**（corner_live.py）: fetch_raceのrace_jsonが持つ過去9走の corner_all/pace_first/pace_last/run_time/margin から計算。時計ベンチ（SpeedBench）はレース日付より前のhistのみ参照（as-of・後知恵なし。corner_bench_cache.json に日別キャッシュ、hist増加で自動再構築）。`python3 corner_live.py verify` で corner_ds.npz と一致することを検算できる（実測: 2022〜2026の8Rで最大差1.1e-11）。
- v99w_result.pkl が消えていたら run が自動再生成（約30秒）。v99w2_result.pkl（B-sd16）も同様に corner_eval.py build → v99w2_fit.py --stage mine/final の順で自動再生成。
- 欠測（corner特徴が作れない馬）は z=0 埋め＝v99w2_fit.py と同じ規約。runが「corner特徴が全欠測の馬 n頭」を表示する。
- 検証・合否の根拠は V99W_REPORT.md（腕A/B-sd）と V99W2_REPORT.md（B-sd16）。
