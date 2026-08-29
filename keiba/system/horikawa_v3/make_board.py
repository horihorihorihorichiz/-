# -*- coding: utf-8 -*-
"""viz JSON からボードのHTMLを作る。

board/style.html（配色と組版）と board/body.html（中身と描画）を読み、
__DATA__ を viz JSON に差し替えて1枚のHTMLにする。

  python make_board.py ../../data/viz_20260830.json ../../data/board_20260830.html

アーティファクトとして公開できるのは Claude Code が動いているときだけなので、
ここで作るのはローカルのファイル。ブラウザで直接開ける。
"""
import io
import os
import sys

HEAD = ('<title>堀川ボード</title>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+JP:wght@400;500;600'
        '&family=Shippori+Mincho+B1:wght@700;800&display=swap">\n')


def build(viz_path, out_path, title=None):
    here = os.path.dirname(os.path.abspath(__file__))
    css = io.open(os.path.join(here, "board", "style.html"), encoding="utf-8").read()
    body = io.open(os.path.join(here, "board", "body.html"), encoding="utf-8").read()
    data = io.open(viz_path, encoding="utf-8").read().strip()
    head = HEAD if not title else HEAD.replace("堀川ボード", title)
    html = head + css + "\n" + body.replace("__DATA__", data)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(html)
    return len(html)


if __name__ == "__main__":
    v, o = sys.argv[1], sys.argv[2]
    t = sys.argv[3] if len(sys.argv) > 3 else None
    print(f"{build(v, o, t):,} バイト → {o}")
