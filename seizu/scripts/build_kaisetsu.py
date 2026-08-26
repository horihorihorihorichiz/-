# -*- coding: utf-8 -*-
"""kaisetsu.src.html の {{SVG:名前}} を埋めて解説書のHTMLを作る。"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    src = io.open(os.path.join(BASE, 'kaisetsu.src.html'),
                  encoding='utf-8').read()
    out = re.sub(r'\{\{SVG:(\w+)\}\}',
                 lambda m: inline_svg(m.group(1)), src)
    p = os.path.join(BASE, 'kaisetsu.html')
    io.open(p, 'w', encoding='utf-8').write(out)
    print('wrote %s  (%.1f KB)' % (p, len(out) / 1024.0))


if __name__ == '__main__':
    main()
