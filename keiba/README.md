# 競馬予想システム 移植プロジェクト

## これは何か

堀川システム（競馬予想）は現在ブラウザの中だけに存在している。
- **データ**: Chrome の IndexedDB（DB名 `hk`、ストア `races` / `meta`）
- **ロジック**: Chrome 拡張機能またはブックマークレット

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
├── system/            評価ロジックの移植先（これから作る）
└── data/              書き出しデータの置き場所（gitignore 対象）
```

## 進め方

### STEP 1　ロジックを吸い出す

ローカルの Claude Code で `HANDOFF.md` の【プロンプト1】を実行する。
拡張機能のコードから評価ロジックと重み付けを説明させる。

### STEP 2　リポジトリに書き出す

【プロンプト2】で、吸い出したロジックを `keiba/system/` に
実行可能なコードとして保存し、コミット＆プッシュする。

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

## 未確認の点

- **調教評価の重み 75.2** が何に対する重みなのか（正規化前か後か、
  他の成分の重みがいくつか）は手順書に書かれていない。STEP 1 で確認すること
- `meta` ストアの中身の構造が未確認
