# -*- coding: utf-8 -*-
# ============================================================
# Path B: あなたのログイン済みChrome(SuperPremium)からレースデータを取得
# ============================================================
# これは「あなたのWindows PCのローカルのClaude Code / ターミナル」で動かす前提。
# クラウド側からはあなたのブラウザに触れないので、ここだけは手元で実行する。
#
# 何を取るか（1レースぶん一括）:
#   ・10走ぶんの馬柱（shutuba_past_9.html … プレミアム）
#   ・タイム指数（speed.html … プレミアム）
#   ・全オッズ（単勝/複勝 b1・馬連 b4・ワイド b5・馬単 b6・三連複 b7）
#   → keiba/data/race_{RACE_ID}.json に保存。これを僕(クラウド)が読んで予想を組む。
#
# 仕組み: あなたが普段使うChromeを「デバッグ用の別プロファイル」で起動して
#         netkeibaに一度ログイン。このスクリプトはそのChromeにCDPで“つなぐ”だけ。
#         → あなたのSuperPremiumセッションのまま取得できる。認証情報はどこにも渡らない。
#
# ── 準備（Windows・初回だけ）─────────────────────────────
#   1) pip install playwright
#   2) 普段のChromeを一度ぜんぶ閉じてから、コマンドプロンプトで:
#        "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
#          --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
#      （↑この別プロファイルのChromeが1枚開く）
#   3) その開いたChromeで netkeiba にログイン（プレミアム会員のアカウントで）。
#
# ── 実行 ────────────────────────────────────────────────
#   python keiba/fetch_local.py 202644070206
#   （引数はrace_id。省略時は下のDEFAULT_RACE_IDを使う）
# ============================================================

import sys, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

DEFAULT_RACE_ID = "202644070206"   # 大井6R C2六七 ダ1600 (2026/7/2)
CDP_URL = "http://localhost:9222"

# オッズは公式の odds_get_form.html（JSON風テキスト）をブラウザ内fetchで取得。
# housiki=c0。b7(三連複)だけは軸ごと(jiku)にブロックが分かれる。
ODDS_TYPES = ["b1", "b4", "b5", "b6", "b7"]


def js_fetch(page, url):
    """ログイン済みセッションのままページ内で fetch してテキストを返す。"""
    return page.evaluate(
        """async (u) => {
            const r = await fetch(u, {credentials:'include'});
            return await r.text();
        }""",
        url,
    )


def get_odds(page, race_id):
    base = "https://nar.netkeiba.com/odds/odds_get_form.html"
    out = {}
    for t in ODDS_TYPES:
        if t == "b7":
            # 三連複は jiku=各1着ブロック で全馬ぶん回す（頭数ぶん）
            blocks = {}
            for jiku in range(1, 19):  # 最大18頭ぶん試行（無い軸は空で返る）
                url = f"{base}?type=b7&race_id={race_id}&housiki=c0&jiku={jiku}"
                txt = js_fetch(page, url)
                if txt and txt.strip() and txt.strip() not in ("[]", "{}", ""):
                    blocks[str(jiku)] = txt
            out[t] = blocks
        else:
            url = f"{base}?type={t}&race_id={race_id}&housiki=c0"
            out[t] = js_fetch(page, url)
    return out


def dump_rendered(page, url, waits=("networkidle",)):
    """プレミアム表(JSで後入れ)が描画されるまで待って innerText / HTML を返す。"""
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2500)  # AJAXの後入れ待ち
    # 馬柱・タイム指数の本体テーブルを広めに拾う
    text = page.evaluate("() => document.body.innerText")
    html = page.content()
    return {"innerText": text, "html": html}


def main():
    race_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RACE_ID
    outdir = Path(__file__).parent / "data"
    outdir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print("！ Chromeにつなげませんでした。")
            print("  別プロファイルのChromeを起動していますか？:")
            print('  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\chrome-debug"')
            print(f"  詳細: {e}")
            return
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ログイン確認
        page.goto("https://regist.netkeiba.com/account/", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        if "ログイン" in page.title() or "login" in page.url:
            input("▶ まだログインしていないようです。開いてるChromeでnetkeibaにログインし、Enter…")

        print(f"■ race_id={race_id} のデータを取得します…")

        data = {"race_id": race_id}

        # 1) タイム指数
        print("  - タイム指数 (speed.html)…")
        data["speed"] = dump_rendered(
            page, f"https://nar.netkeiba.com/race/speed.html?race_id={race_id}"
        )

        # 2) 10走馬柱
        print("  - 10走馬柱 (shutuba_past_9.html)…")
        data["past9"] = dump_rendered(
            page, f"https://nar.netkeiba.com/race/shutuba_past_9.html?race_id={race_id}"
        )

        # 3) 出馬表(基本情報・枠・斤量・馬体重)
        print("  - 出馬表 (shutuba.html)…")
        data["shutuba"] = dump_rendered(
            page, f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id}"
        )

        # 4) オッズ一式
        print("  - オッズ (b1/b4/b5/b6/b7)…")
        data["odds"] = get_odds(page, race_id)

        outfile = outdir / f"race_{race_id}.json"
        outfile.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        size_kb = outfile.stat().st_size / 1024
        print(f"\n✔ 保存しました: {outfile}  ({size_kb:.0f} KB)")
        print("  次にやること:")
        print(f"    git add {outfile}")
        print('    git commit -m "add race data" && git push')
        print("  → プッシュしたらクラウド側の僕が読んで予想を組みます。")
        # CDPで“つないだ”だけなので、あなたのChromeは閉じない（browser.closeしない）。


if __name__ == "__main__":
    main()
