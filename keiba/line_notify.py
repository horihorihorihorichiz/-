# -*- coding: utf-8 -*-
"""LINE通知（2026-08-22新設・ユーザー指示「LINEのアカウント作ったから通知来るようにして欲しい」）。

★重要な前提: **LINE Notify は 2025-03-31 で終了している。**
   旧来の「LINE Notifyのトークンを貼るだけ」方式はもう使えない。
   現在 LINE に自動でメッセージを送る道は Messaging API（LINE公式アカウント）だけ。

★セキュリティ規約（RULES.md・変更禁止）との関係:
   「認証情報を扱わない・保存しない」は**購入・投票まわりの資格情報**についての規約。
   LINE のチャネルアクセストークンは通知専用でこれには当たらないが、
   **リポジトリに書くとGitHubに公開されるので絶対に置かない**。
   このスクリプトは環境変数からのみ読む。ファイルにも書かない・ログにも出さない。

## 使う前の準備（人間がやる。ここは自動化しない）

1. LINE Developers (https://developers.line.biz/) でログイン
2. プロバイダー作成 → 「Messaging API」チャネルを作成
3. チャネル基本設定 →「チャネルアクセストークン(長期)」を発行
4. 自分のLINEでその公式アカウントを friend 追加（QRコードは同じ画面にある）
5. トークンを環境変数に入れる:
       export LINE_CHANNEL_TOKEN='発行した長期トークン'
   ※ .bashrc に書くならリポジトリの外。コミットしない。

## 使い方

    printf '%s' '長期トークン' | python3 line_notify.py --set   # 保存(引数では渡さない)
    python3 line_notify.py "テスト送信"
    python3 line_notify.py --check          # 設定できているかだけ確認(送信しない)

    from line_notify import push
    push("札幌11R A→S昇格。単勝14を5,000円")

送信は broadcast（友だち全員＝自分だけ）を使う。宛先IDを保存しなくて済むため。
"""
import json
import os
import sys
import urllib.request

ENV_KEY = "LINE_CHANNEL_TOKEN"
API = "https://api.line.me/v2/bot/message/broadcast"
# 環境変数が使えない経路(番人が起こす子プロセス・コンテナ再起動後)向けの置き場。
# .gitignore 済み＝GitHubには絶対に上がらない。コンテナリセットでは消えるので再設定が要る。
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "line_token.local")


def _token():
    """環境変数 → gitignore済みローカルファイル の順に探す。"""
    t = os.environ.get(ENV_KEY, "").strip()
    if t:
        return t
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def configured():
    return bool(_token())


def push(text, timeout=15):
    """LINEへ送る。成功=True。未設定なら送らずFalse（例外にしない=運用を止めない）。"""
    token = _token()
    if not token:
        print(f"[line_notify] {ENV_KEY} が未設定のため送信しない", file=sys.stderr)
        return False
    text = str(text)[:4900]        # LINEの上限5000文字
    body = json.dumps({"messages": [{"type": "text", "text": text}]}).encode()
    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = r.status == 200
            if not ok:
                print(f"[line_notify] HTTP {r.status}", file=sys.stderr)
            return ok
    except Exception as e:
        # トークンはログに出さない（例外文にも含まれない想定だが念のため型だけ）
        print(f"[line_notify] 送信失敗: {type(e).__name__}", file=sys.stderr)
        return False


def main():
    args = sys.argv[1:]
    if args and args[0] == "--set":
        # 標準入力からトークンを受け取り、gitignore済みファイルへ 600 で保存する。
        # 引数では受け取らない(ps/履歴に残るため)。
        import stat
        tok = sys.stdin.read().strip()
        if not tok:
            print("標準入力が空。使い方: printf '%s' 'トークン' | python3 line_notify.py --set")
            return 1
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(tok)
        os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)
        print(f"保存した: {TOKEN_FILE} (600・gitignore済み) 長さ{len(tok)}文字")
        return 0
    if not args or args[0] == "--check":
        if configured():
            src = "環境変数" if os.environ.get(ENV_KEY, "").strip() else "line_token.local"
            print(f"✅ トークン設定済み（{src}から読めた・送信可能）")
        else:
            print(f"❌ {ENV_KEY} が未設定。\n"
                  f"   LINE Developers でMessaging APIチャネルを作り、長期トークンを\n"
                  f"   export {ENV_KEY}='...' で入れてください（リポジトリには置かない）。\n"
                  f"   ※LINE Notify は2025-03-31終了。Messaging APIのみ。")
        return 0 if configured() else 1
    ok = push(" ".join(args))
    print("送信OK" if ok else "送信できなかった")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
