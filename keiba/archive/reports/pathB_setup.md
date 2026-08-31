# Path B: 完全自動化（あなたのPCで動かす）

クラウドの僕はあなたのブラウザに触れない＝プレミアム(タイム指数・10走・全オッズ)が取れない。
そこで **取得だけあなたのPCで** やって、予想と買い目づくりは今まで通りクラウドの僕がやる。役割分担はこれだけ。

```
[あなたのPC(ローカル)]  ログイン済みChromeからデータ取得  → git push
        │
        ▼
[クラウドの僕]  データを読む → 予想(calc.py) → 買い目/ブックマークレット
        │
        ▼
[あなた]  ブックマークレットで入力 → 最後の購入ボタンだけ自分で押す
```

## 初回セットアップ（1回だけ）

1. Python と Playwright
   ```
   pip install playwright
   ```
2. 普段のChromeを**全部閉じて**から、コマンドプロンプトで別プロファイル起動:
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
   ```
   （Chrome 136+ は通常プロファイルだとデバッグ接続を弾くので、この専用プロファイルが必須）
3. その開いたChromeで **netkeibaにログイン**（SuperPremiumのアカウントで）。以降このプロファイルはログイン状態を覚える。

## 毎回の流れ

1. 上の別プロファイルChromeが起動＆ログイン済みなのを確認。
2. ローカルでこのリポジトリを開いて:
   ```
   python keiba/fetch_local.py 202644070206
   ```
   （引数は race_id。`keiba/data/race_<id>.json` に保存される）
3. コミットしてプッシュ:
   ```
   git add keiba/data/ && git commit -m "add race data" && git push
   ```
4. クラウドの僕に「取ったよ」と言えば、予想→買い目まで組む。

## 安全ルール（不変）
- パスワードは使わない/受け取らない。
- CDPは既存Chromeに“つなぐ”だけ。認証情報はどこにも渡らない・保存しない。
- **最後の投票確定ボタンは必ずあなたが押す**。スクリプトもブックマークレットも押さない。
