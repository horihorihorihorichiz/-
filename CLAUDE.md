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

## 編集可能PPTXの作成（export-pptx-text.js）

### ワークフロー
```
HTML/CSSで見た目を完成・承認 → scripts/export-pptx-text.js でテキスト版PPTXに変換
```
画像PPTXと異なり、PowerPoint上でテキスト編集が可能になる。

### pptxgenjs 注意ポイント

#### 1. 游明朝のフォントウェイト
- デフォルト（bold なし）= Light体（極細、用紙背景では読めない）
- `bold: true` = Demibold（通常の読みやすさ）
- **見出しだけでなく本文・注釈・数字すべてに `bold: true` を付ける**

#### 2. 縦中央揃え（テーブル状レイアウト）
- テキストボックスの高さを行高まるごと取る（`y=ry`, `h=TRH`）
- `valign: 'middle'` を指定する
- ❌ 小さなボックスに offset を足すのはNG（PowerPoint内部パディングとズレる）

#### 3. タイトル＋本文は1つのボックスにまとめる
```javascript
T(s, [
  { text: title, options: { bold: true, fontSize: 15, breakLine: true } },
  { text: body,  options: { bold: true, fontSize: 13 } },
], x, ry, w, TRH, { valign: 'middle', lineSpacingMultiple: 1.5 });
```
- 別ボックスに分けると overflow しやすく位置合わせも難しい
- `breakLine: true` で改行、`lineSpacingMultiple` で行間調整

#### 4. 寸法はインチ直接指定、ピクセル変換は使わない
- `px * W / 1920` の変換は日本語フォントの実測幅と合わない
- PowerPoint向けは `W=13.33`, `H=7.50`（LAYOUT_WIDE）を基準に実寸インチ値を直接決める

#### 5. テキストボックス幅は余裕を持たせる
- 日本語文字は欧文より幅広。内部パディング分も加味して広めに取る
- 特に数字2桁（「01」等）: 見た目0.4"でも `w=1.1"` 必要

#### 6. default.css の汚染に注意
カスタムスライドHTMLで必ず打ち消すべきスタイル:
```css
/* default.css の h2 border-bottom を無効化 */
.slide--content h2 { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
/* engine.js が作る .slide-progress のアクセントカラーを上書き */
.slide-progress { background: var(--ink); opacity: 0.15; height: 2px; }
```

#### 7. エクスポートはHTTPサーバー経由
- `file://` だとGoogle Fontsが読み込めず文字化け
- `export-pptx.js` は `http.createServer` で一時サーバーを立てて `page.goto('http://127.0.0.1:PORT/...')` を使う（実装済み）

#### 8. PPTXのGit共有
`.gitignore` に `*.pptx` が含まれる場合は強制追加:
```bash
git add -f slides/exports/presentation.pptx
git commit -m "Add PPTX export"
git push
```
