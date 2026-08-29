# 競馬予想システム 移植プロジェクト

## これは何か

堀川システム（競馬予想）の実体をリポジトリに集めて、
**どの環境からでも同じ予想を再現できる状態**にするための作業場所。

- **データ**: Chrome の IndexedDB（DB名 `hk`、ストア `races` / `meta`）
- **ロジック**: ~~Chrome 拡張機能またはブックマークレット~~
  → **誤り**。STEP 1 の調査で否定された。実体は Python
  （`Downloads\horikawa_v3.zip` → `system/horikawa_v3/` に取り込み済み）。
  設計図は Artifact「堀川システム設計図」（Ver.99.27 / hori52）。
  詳細は [`system/logic.md`](system/logic.md)

ブラウザだけに置いていたときの問題:

1. タブを閉じると索引が消える（実際に一度作業が止まった）
2. クラウド側の Claude からは一切見えないため、予想を手伝えない

## フォルダ構成

```
keiba/
├── README.md          このファイル
├── HANDOFF.md         ローカルの Claude Code に貼るプロンプト集
├── system/            評価ロジック
│   ├── logic.md       評価ロジックの仕様書（人間が読む用）
│   ├── weights.json   16成分の層別配点 + 26成分の全体配点
│   ├── score.js       16成分の採点実装（Node.js・依存なし）
│   └── horikawa_v3/   Python 本体（26成分・50成分）
│       ├── hk/        features.py / cli.py / fit.py / gbdt.py / predict.py …
│       ├── weights/   reference_browser_fit.json（26成分の参考配点）
│       └── config.example.py
└── data/              書き出しデータの置き場所（gitignore 対象）
```

## 秘密情報の扱い

`system/horikawa_v3/` は **`config.py` に netkeiba のログインクッキーを置く設計**。
リポジトリ直下の `.gitignore` で以下を除外してある。

```
config.py / **/config.py     *cookie* *cookies*     .env / *.env
*secret* / *secrets*         *credential*           *token*
*.pem *.key *.p12 *.pfx      id_rsa* .netrc _netrc  secrets/
```

`config.example.py` と `.env.example` は除外対象外（ひな型なのでコミットしてよい）。
`git check-ignore` で確認済み。**`config.py` は絶対にコミットしないこと。**

## 進め方

### ~~STEP 1　ロジックを吸い出す~~　完了

Chrome を調査した結果、競馬関連の拡張機能もブックマークレットも存在しなかった。
ロジックの出所は Artifact「堀川システム設計図」と `horikawa_v3.zip` だった。

### ~~STEP 2　リポジトリに書き出す~~　完了

`system/logic.md`・`system/weights.json`・`system/score.js`・`system/horikawa_v3/` を配置済み。
`node system/score.js --selftest` で検算できる（22項目）。

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

Python 側を回すなら:

```
pip install numpy requests          # 木の学習器を使うなら lightgbm も
cp config.example.py config.py      # NETKEIBA_COOKIE を書き換える
python -m hk.cli harvest 20230805 20260823
python -m hk.cli gbdt               # 本命（50成分・木）
python -m hk.cli predict 202605020811
```

取得速度は上げないこと。実測で追い切り（race.netkeiba.com）は毎秒2件を1時間半で
アクセスを止められた（HTTP 400）。復旧に数時間かかる。既定は毎秒0.7件。

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

### 「調教評価の重み 75.2」→ 実在した。26成分版の主力成分

**`調教評価` は実在する成分で、`75.2` はその重み。**
出典は `system/horikawa_v3/weights/reference_browser_fit.json`（26成分・線形モデルの
「全体1本(global)」配点）。

- **何に対する重みか**: レース内Z正規化した**後**の値に掛かる係数（Z化 → 内積、の順）
- **正規化前か後か**: 後
- **どのスケールか**: 「平均絶対値=30に正規化」した実効配点。生の重みではない
- **どのモデルか**: 設計図 Artifact の16成分版ではなく **26成分版**。16成分版に調教は無い
- **成分の中身**: 追い切り時計ではなく、**厩舎短評を順序尺度に直したもの**。
  当該レースより前の実績のみで逐次に学習しており、リークはしていない
- **他の成分の重み**: 齢 −88.8 / 公式指数 86.7 / **調教評価 75.2** / LTS 56.5 / 騎手 55.1 /
  mgn_abs −54.5 / 前走人気 42.0 / DSI 39.4 / 調教師 37.5 / NSI 36.7 …
  全26個は `system/weights.json` の `linear26.global`、解説は `system/logic.md`

重みが大きい理由は評価語ごとの3着内率の開き。全体平均 22.0% に対し、
好調持続 44.4%(2,770件) 〜 いま一息 5.3%(1,225件) と **8倍**の幅がある。

### 中山芝Mの −75.2 は偶然の一致だった

16成分側の `w52` にも `75.2` が1箇所だけ現れる（中山芝M の `mgn_abs`＝着差 の `−75.2`）。
符号も成分も別物で、調教評価の 75.2 とは無関係。
**移植の初回調査ではこちらを 75.2 の正体と誤認した。**その報告は誤りだったので訂正する。

### モデルは3世代ある（16 → 26 → 50成分）

| 世代 | 成分 | 形 | 状態 |
|---|--:|---|---|
| 16成分・線形 | 16 | レース内Z化 → 層別配点との内積 | 設計図 Artifact / `system/score.js` |
| 26成分・線形 | 26 | 同上（配点は全体1本）。調教込み | `hk.cli fit` |
| **50成分・木** | 50 | LightGBM。条件そのものを成分に渡す | **本命**。`hk.cli gbdt` |

実測（中央競馬10,551レース・2023年8月〜2026年8月、未知期間1,707レースで1回だけ測定）:

| | 1位が1着 | 1位が3着内 | 上位6頭で3着独占 | 対数尤度 |
|---|--:|--:|--:|--:|
| 元の16成分・線形 | 23.43% | 54.66% | 37.96% | −2.2446 |
| 26成分・線形（調教込み） | 26.54% | 58.41% | 43.06% | −2.1338 |
| **50成分・木（本命）** | **27.77%** | **59.64%** | **43.94%** | **−2.0906** |
| （参考）市場＝単勝オッズ | 34.27% | 66.14% | 50.67% | −1.9169 |

### 市場には勝てていない

3通りで確認済み。26成分・線形の条件付きロジットで +0.0019 nats、
50成分・木を市場の上に積んで +0.0007 nats、54成分・木（市場も成分）は
**−0.0010 nats で悪化**。単勝の控除率20%を越えるには1レース **0.223 nats** が要る。
桁が3つ足りない。50成分・木でも3着内率は市場に **6.5pt 届いていない**。

> **このシステムは「当てる」ためのもので、「儲ける」ためのものではない。**
> — `system/horikawa_v3/README.md`

### 成分名と距離帯の食い違い（実装側を正とする）

| 記号 | 設計図 Artifact | 実装・HORIKAWA_FULL.md（正） |
|---|---|---|
| `LTS` | 近走着順 | **上がり** |
| `CSI` | コーナー | **コース適性** |
| `HCS` | 条件調整 | **馬体重** |

距離帯の境界も食い違う。`hk/features.py:66` は **S≤1400m / M≤2000m / L>2000m**、
`HORIKAWA_FULL.md` は「M=1500-1700m / L=1800m以上」で 1701–1799m が抜けている。
`system/score.js` は実装側に合わせてある。

### ロジックの所在

Chrome 拡張機能でもブックマークレットでもなかった（インストール済み拡張6個に競馬関連ゼロ、
ブックマーク48件に `javascript:` ゼロ）。

設計図が生成元として挙げるファイル名のうち、その名前で実在するのは `HORIKAWA_FULL.md` だけ
（`C:\Users` 全体と `D:` を検索）。

| 設計図の呼び名 | 実在するもの |
|---|---|
| `calc.py` | `system/horikawa_v3/hk/features.py` |
| `hori52_w.json` | `system/horikawa_v3/weights/reference_browser_fit.json`（参考値） |
| `HORIKAWA_FULL.md` | `C:\Users\horik\Downloads\HORIKAWA_FULL.md`（1,088行・2026-08-22） |
| `plus_fires.json` | **存在しない。未作成。** |

## 未確認の点

- `meta` ストアの中身の構造が未確認（`HANDOFF.md` の【プロンプト3】）
- **`plus_fires.json`（発火表）が未作成**。設計図は「買う根拠は発火表の証明済みエッジだけ」と
  するが、その表が無い。現状、買い目の根拠になるものは何も無い
- 本番の配点表 `weights/hori_w.json` が未生成（`python -m hk.cli fit` で作る）。
  いま入っているのはブラウザ学習の参考値で、Python版とは細部の丸めが違う
- 設計図に数値が無く実装で暫定値を置いた6項目（得点表示の平行移動、softmax温度、
  形の判定しきい値ほか）。`system/score.js` の `PROVISIONAL` と
  `system/logic.md` 末尾の表を参照。距離帯の境界は `features.py` で解決済み
