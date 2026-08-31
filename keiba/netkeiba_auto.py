# netkeiba 買い目入力の自動化（帝王賞 12点ポートフォリオ版）
#
# 仕組み:
#   ・自動化専用プロファイル(USER_DATA_DIR)に「初回だけ手動ログイン」
#   ・一度ログインすればログイン状態が保存され、次回からは自動でログイン済み
#   ・ログイン後、オッズ画面で「12点の買い目を選択 → 金額入力」までを代行
#   ・★購入(投票)確定ボタンだけは“あなたが”押す（安全のため自動では押さない）
#
# 準備（Windowsのターミナルで一度だけ）:
#   pip install playwright
#   ※ channel="chrome" なので、普段使っているChromeをそのまま使います
#   ※ playwright install は不要（普段のChrome本体を使うため）
#
# 実行:
#   python netkeiba_auto.py
#
# セレクタについて:
#   ・買い目の「選択」は netkeiba の実HTMLから確認済みの cart-item 属性で行うので確実。
#   ・「金額入力欄」と「投票ボタン」はログイン後の投票画面に出るため、
#     初回は AMOUNT_INPUT_SELECTOR / VOTE_BUTTON_HINT を画面に合わせて微調整してください
#     （対象を右クリック →「検証」で id/class を確認。分からなければ Claude Code に貼れば埋めます）。

import re
from pathlib import Path
from playwright.sync_api import sync_playwright

# ── 設定 ──────────────────────────────────────────────
USER_DATA_DIR = str(Path.home() / "netkeiba_bot_profile")
RACE_ID = "202644070111"          # 帝王賞 大井11R(2026/7/1)
ODDS_URL = f"https://nar.netkeiba.com/odds/index.html?race_id={RACE_ID}"

# 券種コード: 単勝=b1 / 馬連=b4 / ワイド=b5 / 三連複=b6
# 買い目ポートフォリオ（20,000円・全点500%超・期待回収275%）
#   ("券種", [馬番...], 金額円)
PORTFOLIO = [
    ("ワイド", [1, 10], 2300),   # ①-⑩ ナチュラル-ディクテ（本線）47.9倍
    ("単勝",  [1],      4600),   # ① ナチュラルライズ 26.1倍
    ("ワイド", [1, 2],  2000),   # ①-② ナチュラル-カゼノ 54.0倍
    ("単勝",  [11],     1900),   # ⑪ カズタンジャー 58.9倍
    ("ワイド", [1, 6],  1700),   # ①-⑥ ナチュラル-サントノ 65.1倍
    ("ワイド", [10, 11], 1600),  # ⑩-⑪ ディクテ-カズタン 68.4倍
    ("ワイド", [11, 13], 1500),  # ⑪-⑬ カズタン-ラム 72.1倍
    ("ワイド", [1, 11], 1200),   # ①-⑪ ナチュラル-カズタン 94.2倍
    ("馬連",  [1, 5],  1000),   # ①-⑤ ナチュラル-クロンヌ 105.5倍
    ("馬連",  [10, 13], 1000),  # ⑩-⑬ ディクテ-ラム 109.6倍
    ("馬連",  [1, 2],   600),   # ①-② ナチュラル-カゼノ 169.8倍
    ("馬連",  [5, 11],  600),   # ⑤-⑪ クロンヌ-カズタン 182.1倍
]

BET_TYPE_CODE = {"単勝": "b1", "馬連": "b4", "ワイド": "b5", "三連複": "b6"}

# ↓ ログイン後の投票画面に合わせて必要なら微調整（初回のみ）
AMOUNT_INPUT_SELECTOR = "input.Kingaku, input[name*='amount'], input.JS_Bet_Kingaku"
VOTE_BUTTON_HINT = "投票"   # 「投票する」「選択した買い目を登録」等のボタン文言


def cart_suffix(code, nums):
    """netkeibaの買い目選択要素 cart-item の末尾パターン。
    例) 単勝① -> _b1_c0_1 / 馬連①-⑤ -> _b4_c0_1_5 / ワイド①-⑩ -> _b5_c0_1_10"""
    return f"_{code}_c0_" + "_".join(str(n) for n in sorted(nums))


def select_tickets(page):
    """券種ごとにタブを切り替えながら、各買い目をクリックで選択する。"""
    # 券種ごとにまとめると切替が最小で済む
    by_type = {}
    for kind, nums, _amt in PORTFOLIO:
        by_type.setdefault(kind, []).append(nums)

    for kind, combos in by_type.items():
        code = BET_TYPE_CODE[kind]
        url = f"https://nar.netkeiba.com/odds/index.html?type={code}&race_id={RACE_ID}"
        print(f"\n── {kind}（{code}）の買い目を選択 ──")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        for nums in combos:
            suf = cart_suffix(code, nums)
            # cart-item 属性が suf で終わる要素をクリック（オッズセル or チェックボックス）
            loc = page.locator(f"[cart-item$='{suf}']").first
            try:
                loc.scroll_into_view_if_needed(timeout=4000)
                loc.click(timeout=4000)
                print(f"  選択OK: {kind} {'-'.join(map(str, nums))}  (cart{suf})")
            except Exception as e:
                print(f"  ★手動で選択してください: {kind} {'-'.join(map(str, nums))}  ({e.__class__.__name__})")
            page.wait_for_timeout(400)


def fill_amounts(page):
    """投票画面に進み、各買い目の金額欄に設定金額を入力する（ベストエフォート）。
    金額欄の対応付けが画面構造により異なるため、入力できない場合は
    下に印刷する一覧を見ながら手入力してください。"""
    print("\n── 金額入力 ──")
    print("  ※自動入力できない場合は、以下の対応表を見て手入力してください:")
    for kind, nums, amt in PORTFOLIO:
        print(f"    {kind:<4} {'-'.join(map(str, nums)):<7} … {amt:,}円")

    inputs = page.locator(AMOUNT_INPUT_SELECTOR)
    n = inputs.count()
    if n == 0:
        print("  （金額欄が見つかりませんでした。投票画面で手入力してください）")
        return
    # 投票リストの並び順 = PORTFOLIO の選択順とは限らないため、
    # まずは見つかった欄数とのズレを表示。安全側で“自動入力はしない”運用も可。
    print(f"  金額欄を {n} 個検出（買い目 {len(PORTFOLIO)} 点）。")
    if n == len(PORTFOLIO):
        for i, (_, _, amt) in enumerate(PORTFOLIO):
            try:
                inputs.nth(i).fill(str(amt))
            except Exception:
                print(f"  ★{i+1}番目の金額欄に手入力: {amt}円")
        print("  金額入力を試行しました。画面で必ず金額・買い目を確認してください。")
    else:
        print("  欄数が一致しないため自動入力は中止。上の対応表で手入力してください。")


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel="chrome",
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(ODDS_URL)

        # ── 初回だけ：手動ログイン（2段階認証・画像認証もこの場で人がこなす）──
        input("▶ netkeibaにログインが済んだら Enter を押してください ...")

        # ── 1) 12点の買い目を選択 ──
        select_tickets(page)

        # ── 2) 投票画面へ（「投票する」等のボタンを押す） ──
        print("\n▶ オッズ画面の『投票する／選択した買い目を登録』ボタンを押して投票画面に進めてください。")
        input("▶ 投票画面（金額入力欄が見える状態）になったら Enter ...")

        # ── 3) 金額入力（ベストエフォート） ──
        fill_amounts(page)

        # ── 4) ★購入確定は手動 ──
        print("\n★ 最終確認: 買い目・金額・合計(20,000円)を画面で必ずチェックしてください。")
        print("★ 購入(投票)ボタンは“あなた”が押してください。スクリプトは押しません。")
        input("▶ 確認が済んだら Enter でブラウザを閉じます（購入後でも前でもOK） ...")
        context.close()


if __name__ == "__main__":
    main()
