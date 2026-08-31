# -*- coding: utf-8 -*-
"""レース判定コール: 発走前の再判定結果をLINEへ送る（2026-08-22新設）。

指示「これ買うか通知してくれる？」「通知をラインでほしいのよね」。
使い方: python3 race_call.py <本文ファイル or 標準入力>
        echo "本文" | python3 race_call.py
LINE(broadcast)へ送る。未設定なら送らずに警告のみ（運用は止めない）。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import line_notify

def main():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        text = open(sys.argv[1], encoding="utf-8").read()
    else:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        print("本文が空", file=sys.stderr); return 1
    ok = line_notify.push(text)
    print("LINE送信OK" if ok else "LINE送信できず(トークン未設定/API失敗)")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
