# -*- coding: utf-8 -*-
"""sotomawari.src.html から、1ファイルで完結する外まわりずかんを作る。"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_onepage import inline_svg          # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    src = io.open(os.path.join(BASE, 'sotomawari.src.html'),
                  encoding='utf-8').read()
    css = io.open(os.path.join(BASE, 'style.css'), encoding='utf-8').read()
    out = re.sub(r'\{\{SVG:(\w+)\}\}', lambda m: inline_svg(m.group(1)),
                 src.replace('{{CSS}}', css))
    p = os.path.join(BASE, 'sotomawari.html')
    io.open(p, 'w', encoding='utf-8').write(out)
    print('wrote %s  (%.1f KB)' % (p, len(out) / 1024.0))


if __name__ == '__main__':
    main()
