# -*- coding: utf-8 -*-
"""buzai.src.html から、1ファイルで完結する部材ずかんを作る。

{{CSS}}         → style.css の中身をそのまま埋める
{{SVG:名前}}    → figures/名前.svg を <img> ではなく本文に埋める
（1枚のHTMLだけで見られるようにするため。kaisetsu と同じやり方。）
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    src = io.open(os.path.join(BASE, 'buzai.src.html'),
                  encoding='utf-8').read()
    css = io.open(os.path.join(BASE, 'style.css'), encoding='utf-8').read()
    out = src.replace('{{CSS}}', css)
    out = re.sub(r'\{\{SVG:(\w+)\}\}', lambda m: inline_svg(m.group(1)), out)
    p = os.path.join(BASE, 'buzai.html')
    io.open(p, 'w', encoding='utf-8').write(out)
    print('wrote %s  (%.1f KB)' % (p, len(out) / 1024.0))


if __name__ == '__main__':
    main()
