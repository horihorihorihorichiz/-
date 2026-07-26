# Slides-to-Web System

## 概要
パワーポイントの代わりに、HTML/CSS/JSでスライドを作成するシステム。
ブラウザの16:9表示でプレゼンテーションを行う。

## ワークフロー
```
1. Claude Code でスライドを生成（HTML/CSS/JS）
2. ブラウザで確認・レビュー（npx serve slides）
3. 修正があればClaude Codeに依頼
4. OKなら npm run export でPowerPointに変換
5. 最終パワポを納品・共有
```

## ファイル構成
```
slides/
├── index.html          # スライド本体（ここにスライドを追加）
├── engine.js           # ナビゲーションエンジン（←→/タッチ/クリック対応）
├── themes/
│   └── default.css     # デフォルトテーマ（CSS変数でカスタマイズ可）
├── assets/             # 画像等のアセット
└── exports/            # エクスポートされたPPTXファイル
scripts/
└── export-pptx.js      # PPTX変換スクリプト（Puppeteer + pptxgenjs）
```

## スライド作成ルール

### 基本構造
各スライドは `<div class="slide slide--{type}">` で囲む。
内側に `<div class="slide-inner">` を置き、そこにコンテンツを記述。

### スライドタイプ
- `slide--title` : タイトルスライド（中央揃え、大きな見出し）
- `slide--section` : セクション区切り（番号+見出し）
- `slide--content` : 通常コンテンツスライド

### レイアウトヘルパー
- `.columns.columns--2` : 2カラム
- `.columns.columns--3` : 3カラム
- `.columns.columns--2-1` : 2:1比率
- `.columns.columns--1-2` : 1:2比率

### コンポーネント
- `.card` / `.card--numbered` : カード（data-number属性で番号表示）
- `.slide-list` / `.slide-list--check` : リスト
- `.diagram` / `.diagram-flow` : フロー図
- `.highlight-box` : ハイライトボックス
- `.slide-quote` : 引用
- `.code-block` : コードブロック
- `.badge` : バッジ（--accent, --secondary, --outline）

### アニメーション
要素に以下のクラスを付与：
- `.animate-in` : 下からフェードイン
- `.animate-left` : 左からフェードイン
- `.animate-right` : 右からフェードイン
- `.animate-scale` : スケールイン
- `.delay-1` ～ `.delay-6` : 遅延（0.1s刻み）

### テーマカスタマイズ
`themes/default.css` の `:root` のCSS変数を変更：
- `--primary` : メイン背景色
- `--accent` : アクセントカラー
- `--accent-secondary` : セカンダリアクセント
- `--font-main` : メインフォント

## プロンプト集

### 1. 新規スライド作成
```
以下のテーマでプレゼンスライドを作成してください。
slides/index.html を編集し、既存のテーマ（themes/default.css）とエンジン（engine.js）を使ってください。

テーマ: [テーマを入力]
対象: [聴衆を入力]
枚数: 約[数字]枚
トーン: [フォーマル/カジュアル/テクニカル]

内容の構成:
1. タイトル
2. [セクション1の概要]
3. [セクション2の概要]
...

各スライドには図解やフロー図を積極的に入れてください。
テキストだけのスライドは避け、ビジュアル要素を必ず含めてください。
```

### 2. 自社ブランドテーマの作成
```
以下のブランドカラーで新しいテーマを作成してください。
slides/themes/ に新しいCSSファイルを追加してください。

ブランドカラー:
- プライマリ: [色コード]
- アクセント: [色コード]
- 背景: [色コード]
- テキスト: [色コード]

フォント: [フォント名]
雰囲気: [モダン/クリーン/エレガント/ポップ]
```

### 3. 既存スライドの改善
```
slides/index.html の既存スライドを以下の観点で改善してください：
- 情報が多すぎるスライドの分割
- テキストだけのスライドに図解を追加
- アニメーションの調整
- カラーバランスの最適化
```

## PowerPointエクスポート
```bash
# 依存インストール（初回のみ）
npm install

# スライドをPowerPointに変換
npm run export

# カスタム入出力
node scripts/export-pptx.js --input slides/index.html --output output.pptx
```
各スライドを1920x1080でスクリーンショットし、16:9のPPTXに画像として配置する。
Webで確認したままの見た目がそのままパワポになる。

## 操作方法
- `→` `↓` `Space` `PageDown` : 次のスライド
- `←` `↑` `PageUp` : 前のスライド
- `Home` / `End` : 最初/最後のスライド
- `F` : フルスクリーン切替
- 画面右半分クリック : 次 / 左半分クリック : 前
- スワイプ対応（タッチデバイス）
- `#slide-N` のURLハッシュで直接アクセス可能

---

# 競馬予想システム（keiba/）★毎セッション必読

競馬の予想依頼が来たら **必ず先に `keiba/RULES.md`（ルール・教訓）と `keiba/SOP.md`（作業手順・馬柱→json変換規則）を読む**。モデルが変わっても、この2つ＋スクリプト群だけで同じ品質で回せる。

## ★V4モデル作り替えの確定事項（2026-07-26。詳細=MODEL_V4_RESULT.md／要点=RULES.md冒頭）
- **JRAの tier は {3,4,5,6,10} だけ**。tier6=1勝クラス。patterns.pyの`6<=tier<=9`は「上級」ではなく1勝クラス。
- **オッズ抜きで市場を上回るのは現時点で不可能**（測定結果）。全2200R比較で三連複 モデル76.5% < 市場77.8%、
  モデル1位は市場implied比-2.2pt。→ 控除率を超える道は「市場の価格ズレを突く」=オッズ必須しかない。
- **部分集合のROIで勝てると言わない**。①全レース比較で選択バイアスを外す ②`rule_audit.py --null-sweep`で
  実力ゼロの偽データから同じ採掘をやり直し偽陽性率を測る。この2つを通らない数字は実弾に載せない。
- **馬場は必須**（同一ルールで良148%/道悪51%）。**開催初日は買わない**。
- V4は `KEIBA_ENGINE=v4` で明示有効化（既定はV3。g12系パターン再採掘が未了のため）。V4時は外枠モデル2位を廃止。

## ★Ver.100体制（2026-07-12全面改修。詳細=RULES.md§0とAUDIT_20260712.md）
- **既定エンジン＝エッジ購入**: 較正確率(params.json)×市場ブレンドで、閾値超えの点だけ薄く買う。
  勝者予測はα=0（市場を使う）。**得点システムは3着内の並び（複勝/ワイド/三連複の確率）に効かせる**（α_place）。
  勝ち順系（馬連・馬単・三連単）は買わない。**大半のレースが見送り＝正常動作**。
- **実弾は停止中→紙上運用(paper.py)で検証**: 精算150Rで回収90%超→少額実弾を検討／70%未満→設計に戻る。
- 従来の買い方（floor保証・軸流し）は `--floor-mode`。ユーザーが実弾で買う時に明示希望があれば使う。

## 絶対に忘れない5項目（忘れて怒られた実績あり）
1. **全頭ランキングに「得点(WAvg)」列を必ず入れる**（馬番・馬名・脚質・得点・PWin・ランク・単勝）。
   **チャット返信でも全頭・全列（上位のみの抜粋禁止）**。predict.pyの表をそのまま貼る。
2. **floor 250%は「複合馬券」で担保**（※Ver.99=--floor-mode時のルール。Ver.100既定はエッジ購入で、
   エッジ無し=買わないが正）。短オッズ安全網を勝手に切らない。
3. **軸＝Sランク最上位**（※--floor-mode時）。EV妙味でSを軸から外さない。単勝3.5倍以下の人気馬は評価Cでも核に入れる。
4. **予算10,000円・100円単位**が既定。点数（券種ごと＋合計）を必ず明記。買い目は券種ごと・馬番の若い順。
   **買い目は毎回・聞かれなくても出す**（各行に現在オッズ→的中時払戻を付ける。見送りでも理由を添える）。
5. **馬場・馬体重・最終オッズを毎回確認**して反映。結果は results.jsonl に記録（stats.py で的中率・回収率）。
   紙上運用は paper_log.jsonl（paper.py settle/stats）。
6. **予想完了ごとに、まとめファイル(md)を SendUserFile でユーザーに送る**（全頭ランキング＋買い目・払戻付き）。

## 実行
```bash
cd keiba
# ★完全自動（race_idだけ・既定）: 出馬表+過去9走をnetkeiba公開ページから自動取得→予想まで一気通貫
python fetch_race.py <race_id> --run --budget 10000
#   タイム指数のみプレミアム限定→既定None（軸はほぼ不変）。貼れる時だけ --tsi tsi.txt。
# 手動（馬柱を貼られた／race_id不明時）
python predict.py race_xxx.json --race-id <id>   # ランキング→オッズ→買い目→i-PAT
python stats.py                                   # 通算成績
```
- 取得: fetch_race.py（出馬表→各馬の競走成績9走→race_json） / エンジン: calc.py (Ver.99.27)
- レース入力(手動): build_*.py が race_*.json を生成
- 安全: 購入ボタンは人間。認証情報は扱わない。netkeibaへのログインもしない。

## 週末まるごと自動（毎週土日）／毎日の期待値スキャン
```bash
python pick_races.py                       # 次の土日の全レースから約10レースを自動選定
python pick_races.py <YYYYMMDD> --run       # 選定→各レース予想(fetch_race→predict)まで一気通貫
python pick_races.py --ev                   # ★毎日: 今日の候補を評価しGO(期待値+)レースだけ報告
python pick_races.py --ev --all --tracks 川崎 # 平場も含め場を絞ってスキャン
python pick_races.py --prescreen             # ★オッズ前の事前絞り: 頭数+モデルで軸が立つレースを先に選ぶ
python pick_races.py --prescreen --max-field 12 # 頭数上限で更に絞る
python3 day_board.py                         # ★デイボード: 今日の大井+JRA全場を1枚のmdに集約(S/A/B/C判定)
```
- pick_races.py: netkeiba公開のレース一覧から 重賞>OP/特別>特別 の順で選定（帯広ばんえいは除外）。
- **恒久運用（毎週自動起動）は Routines**（`/schedule` or claude.ai/code/routines）。設定手順とコピペ用
  プロンプトは `keiba/ROUTINE.md`。ルーチンは買い目の確認連絡まで・購入とGOは人間。
- **モデル非依存**: 買いパターン判定は patterns.py(JRA)/oi_patterns.py(大井)/day_board.py にコード化済み。
  どのモデル(Opus等)で動いてもスクリプトの判定に従う。条件マップ=keiba/COND_MAP_20260723.md。
  日付は必ず実行時JSTを取得(day_board.pyのjst_now方式)。新環境では pip install -q numpy lightgbm を先に。
