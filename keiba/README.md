# 競馬予想システム 移植プロジェクト

## これは何か

堀川システム（競馬予想）は現在ブラウザの中だけに存在している。
- **データ**: Chrome の IndexedDB（DB名 `hk`、ストア `races` / `meta`）
- **ロジック**: ~~Chrome 拡張機能またはブックマークレット~~
  → **誤り**。STEP 1 の調査で否定された。実体は Python 側（`calc.py` + `hori52_w.json`）で、
  設計図は Artifact「堀川システム設計図」（Ver.99.27 / hori52）にある。
  詳細は [`system/logic.md`](system/logic.md)

この状態には2つの問題がある。

1. タブを閉じると索引が消える（実際に一度作業が止まった）
2. クラウド側の Claude からは一切見えないため、予想を手伝えない

このフォルダは、システムをリポジトリに移植して
**どの環境からでも同じ予想を再現できる状態**にするための作業場所。

## フォルダ構成

```
keiba/
├── README.md          このファイル
├── HANDOFF.md         ローカルの Claude Code に貼るプロンプト集
├── system/            評価ロジックの移植先
│   ├── logic.md       評価ロジックの仕様書（人間が読む用）
│   ├── weights.json   w6 / w52 / w30 の全重み（85ベクトル × 16成分）
│   └── score.js       スコア計算の実装（Node.js・依存なし）
└── data/              書き出しデータの置き場所（gitignore 対象）
```

## 進め方

### ~~STEP 1　ロジックを吸い出す~~　完了

Chrome を調査した結果、競馬関連の拡張機能もブックマークレットも存在しなかった。
ロジックの出所は Artifact「堀川システム設計図」（`hori52_w.json` から生成）だった。

### ~~STEP 2　リポジトリに書き出す~~　完了

`system/logic.md`・`system/weights.json`・`system/score.js` を作成済み。
`node system/score.js --selftest` で検算できる（22項目）。

残るのは手順1（16成分そのものの算出、`calc.py` 相当）の移植。

### STEP 3　データを置く

HORIKAWA / EXPORT の手順でファイルを書き出し、`keiba/data/` に置く。

```
hori_races_YYYYMMDD.jsonl.gz    レース結果 約10,551レース / 145,244頭
hori_train_YYYYMMDD.jsonl.gz    調教まわり 約10,553件
```

`.gz` は巨大なので Git にはコミットしない（`.gitignore` 済み）。
クラウド側の Claude に渡すときは会話に直接添付する。

### STEP 4　どちらの環境でも回せる状態にする

`system/` にロジックが入り、`data/` にデータがあれば、
ローカルでもクラウドでも同じ予想が再現できる。

## データ形式のメモ

書き出される JSONL の1行目はヘッダ。

```json
{"_":"horikawa-export","v":1,"rcols":[...],"hcols":[...],"races":10551}
```

2行目以降が各レース。

```json
{"r":[レース情報],"h":[[出走馬1],[出走馬2],...],"t":[調教インデックス]}
```

カラム定義（書き出しスクリプトより）

| 種別 | カラム |
|---|---|
| `rcols`（レース） | id, date, place, kai, nday, r, surf, turn, io, dist, weather, ground, cls, n |
| `hcols`（出走馬） | fin, waku, umaban, horse, sex, age, kin, jockey, sec, margin, corner, agari, odds, pop, bw, bwd, trainer |

## 判明した点

### 「調教評価の重み 75.2」→ 調教とは無関係だった

**調教に相当する成分は16成分のどれにも存在しない。**
`75.2` は重みテーブル全体（85ベクトル × 16成分 = 1,360個）の中で1箇所にしか出現せず、
その正体は **「中山・芝・中距離」セルにおける `mgn_abs`（着差）の重み `−75.2`**。
符号は**負**で、加点ではなく「大差で負けた馬を強く減点する」係数。

- **何に対する重みか**: レース内Z正規化した**後**の16次元ベクトルに掛かる係数
- **正規化前か後か**: 後。手順は Z化 → 配点ベクトルとの内積、の順
- **どのスケールか**: 「平均絶対値を30に揃えた」実効配点。生の重みそのものではない
- **他の成分の重みは**: `system/logic.md` の配点表、全数値は `system/weights.json`
  （二本柱は `DSI` 距離適性と `NSI` 格で60〜100、`mgn_abs` が唯一の大きな負で−40〜−70、
  第3の柱が `spd_res` 脚の残りで44〜60）

なお調教データ自体は `hori_train_*.jsonl.gz` と各レース行の `"t"` として存在するが、
スコア計算には使われていない。データはあるが評価には入っていない状態。

### ロジックの所在

Chrome 拡張機能でもブックマークレットでもなかった（インストール済み拡張6個に競馬関連ゼロ、
ブックマーク48件に `javascript:` ゼロ）。上流は `calc.py` / `hori52_w.json` / `HORIKAWA_FULL.md`。

## 未確認の点

- `meta` ストアの中身の構造が未確認（`HANDOFF.md` の【プロンプト3】）
- 手順1（16成分そのものの算出＝`calc.py` 相当）が未移植
- 設計図に数値が無く実装で暫定値を置いた7項目（距離帯の境界、softmax温度、
  形の判定しきい値ほか）。`system/score.js` の `PROVISIONAL` と
  `system/logic.md` 末尾の表を参照
