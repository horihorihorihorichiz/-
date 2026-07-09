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

競馬の予想依頼が来たら **必ず先に `keiba/RULES.md` を読む**。全ルール・過去の失敗教訓がそこにある。

## 絶対に忘れない5項目（忘れて怒られた実績あり）
1. **全頭ランキングに「得点(WAvg)」列を必ず入れる**（馬番・馬名・脚質・得点・PWin・ランク・単勝）。
2. **floor 250%は「複合馬券」で担保**：同じ買い目の馬連＋ワイド等は一緒に当たる→合算で250%。短オッズ安全網を勝手に切らない。
3. **軸＝Sランク最上位**。EV妙味でSを軸から外さない。単勝3.5倍以下の人気馬は評価Cでも核に入れる。
4. **予算10,000円・100円単位**が既定。点数（券種ごと＋合計）を必ず明記。買い目は券種ごと・馬番の若い順。
5. **馬場・馬体重・最終オッズを毎回確認**して反映。結果は results.jsonl に記録（stats.py で的中率・回収率）。

## 実行
```bash
cd keiba
python predict.py race_xxx.json --race-id <id>   # ランキング→オッズ→買い目→i-PAT
python stats.py                                   # 通算成績
```
- エンジン: calc.py (Ver.99.27) / レース入力: build_*.py が race_*.json を生成
- 安全: 購入ボタンは人間。認証情報は扱わない。
