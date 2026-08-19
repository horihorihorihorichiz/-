# V99W並走レーン — 学習配点（腕A/B-sd）のゼロ掛け金ライブ記録

土曜（8/22〜）の運用への組み込み方。**本番（PATTERNS_FROZEN/day_board/predict）の判定・買い目には一切影響しない**。順位の記録だけ。

```bash
python3 selfcheck.py                                   # V99W並走レーンの項目がALL GREENであること
python3 v99w_rank.py run race_<race_id>.json --post HH:MM   # 各レースのfetch_race後・発走前に1回
                                                       #（発走3分前で凍結。--post省略可だが推奨）
python3 v99w_rank.py settle                            # 当日夜または翌朝。確定結果のみ取り込み
python3 v99w_rank.py stats                             # 現行 vs 腕A vs B-sd の複勝的中率を対比
```

- 表示の「▲腕A入替/▲B-sd入替」＝学習配点なら上位3頭の顔ぶれが変わるレース（観察対象）。
- 記録先は v99w_live.jsonl。過去日付・結果同梱のrace_jsonは既定ブロック（検証時のみ --allow-past）。
- v99w_result.pkl が消えていたら run が自動再生成（約30秒）。検証・合否の根拠は V99W_REPORT.md。
