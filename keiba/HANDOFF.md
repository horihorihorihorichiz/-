# ローカルの Claude Code に貼るプロンプト集

PC の PowerShell で `claude` を起動し、以下をそのまま貼り付ける。
1つずつ順番に。全部まとめて貼らないこと。

---

## プロンプト1　評価ロジックを吸い出す

```
Chrome で動いている競馬予想システム（堀川システム）を調べてください。

1. chrome-devtools MCP で Chrome に接続
2. chrome://extensions を開き、競馬関連の拡張機能を特定
3. その拡張機能のソースコード（manifest.json, content script, background）を読む
4. 評価ロジックを説明してください:
   - どの項目をスコア化しているか
   - 各項目の重み（調教評価が 75.2 とされているが、
     それが何に対する重みで、他の成分の重みがいくつなのか）
   - スコアの合成方法（線形和か、正規化しているか）
   - 最終的に何を出力するか（順位付けか、期待値か）

コードそのものも省略せずに見せてください。
```

---

## プロンプト2　リポジトリに移植する

プロンプト1 の結果が出てから実行する。

```
いま読み取った評価ロジックを、再現可能なコードとして保存してください。

1. https://github.com/horihorihorihorichiz/- をクローン
2. ブランチ claude/chrome-戸津長輝-nvv3rs をチェックアウト
3. keiba/system/ に以下を作成:
   - logic.md      評価ロジックの仕様書（人間が読む用）
   - score.js      スコア計算の実装（Node.js で動くもの）
   - weights.json  重み付けの定義を外に出したもの
4. keiba/README.md の「未確認の点」を、判明した内容で更新
5. コミットして push
```

---

## プロンプト3　IndexedDB の中身を確認する

`meta` ストアの構造が未確認なので、必要なら実行する。

```
db.netkeiba.com を開いて、IndexedDB の "hk" データベースを調べてください。
races と meta それぞれのオブジェクトストアについて、
1件目のレコードの構造（キーと値の型）を示してください。
値が長い場合は先頭だけで構いません。
```

---

## プロンプト4　当日の予想を実行する

システムの移植が済んだあと、実戦で使う。

```
netkeiba (race.netkeiba.com) を開いて、本日のまだ発走していないレースを
リストアップしてください。

そのあと各レースについて:
1. 有料の出馬表を開き、指数・調教評価・厩舎コメントを読み取る
2. keiba/system/logic.md の評価ロジックに従ってスコアを計算
3. オッズと自己評価の乖離が大きい馬を抽出

出力:
- 本命 / 対抗 / 単穴 / 連下
- 各馬の根拠を1行ずつ
- 推奨買い目と、期待値が高いと考える理由
- スコアの内訳（どの成分が効いたか）
```

---

## つまずいたときの確認

| 症状 | 確認すること |
|---|---|
| Chrome につながらない | `chrome://inspect/#remote-debugging` が ON か。Chrome 144 以上か |
| ツールが見つからない | `claude mcp list` で `chrome-devtools ✔ Connected` が出るか |
| 拡張機能が見つからない | ブックマークレット方式かもしれない。ブックマーク一覧を確認 |

## PowerShell での注意

`--` はそのまま書くと PowerShell に食われる。必ずクォートする。

```powershell
claude mcp add -s user chrome-devtools "--" npx chrome-devtools-mcp@latest --autoConnect
```
