# -*- coding: utf-8 -*-
"""設定ひな型。config.py という名前でコピーして書き換えてください。
   config.py は絶対に他人に渡さないでください（ログイン情報が入ります）。"""

# netkeiba のログイン用の記録（クッキー）
#
#   取り方: Chrome で netkeiba にログインした状態で F12 → Application →
#           Cookies → https://db.netkeiba.com を開き、名前が「netkeiba」の
#           行の Value をそのまま貼る。
#
#   ここに貼った値は自分のパソコンの中だけに置いてください。
#   誰かに送る必要は一切ありません。
NETKEIBA_COOKIE = ""

# 取得の速さ（1秒あたりの件数）。上げすぎると netkeiba 側に止められます。
# 実測: 着順表は毎秒3件で1時間持ちましたが、追い切りは毎秒2件を1時間半で止められました。
RATE_RESULT = 2.0     # db.netkeiba.com 着順表
RATE_OIKIRI = 0.7     # race.netkeiba.com 追い切り（こちらは必ず遅く）

# 保管先
DB_PATH = "data/hori.sqlite"

# 期間の区切り
CUT_HIST    = "20240824"   # ここより前は過去走の材料としてのみ使う
CUT_EMBARGO = "20260221"   # 学習はここまで
CUT_VAL     = "20260301"   # 未知期間はここから（間の1週間は隔離）

# ── LINE 通知（notify.py が使う）
#
# LINE Notify は 2025年3月31日で終了しているので使えない。
# いまは Messaging API で自分の公式アカウントから自分へ push する形になる。
#
#   1 LINE Developers で Messaging API チャネルを作る
#   2 「チャネルアクセストークン（長期）」を発行して LINE_TOKEN に貼る
#   3 自分のユーザーID（U で始まる33文字）を LINE_TO に貼る
#     ボットを友だち追加して Webhook で受け取るか、
#     LINE Developers の「あなたのユーザーID」欄で確認できる
#
# ここに貼った値は自分のパソコンの中だけに置くこと。config.py は .gitignore 済み。
LINE_TOKEN = ""
LINE_TO = ""
