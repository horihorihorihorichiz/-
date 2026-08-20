# -*- coding: utf-8 -*-
"""onepage.src.html の {{SVG:名前}} と {{CARDS}} を埋めて 1枚のHTMLを作る。"""
import io, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'onepage.src.html')
OUT = os.path.join(BASE, 'onepage.html')
FIG = os.path.join(BASE, 'figures')


def inline_svg(name):
    with io.open(os.path.join(FIG, name + '.svg'), encoding='utf-8') as f:
        s = f.read()
    # 画面幅に合わせて伸縮させるため width/height を外す
    m = re.match(r'<svg\b([^>]*)>', s)
    head = m.group(1)
    vb = re.search(r'viewBox="([^"]+)"', head).group(1)
    w = float(vb.split()[2])
    head = re.sub(r'\s(width|height)="[^"]*"', '', head)
    head += ' style="max-width:%dpx;margin:0 auto"' % int(w)
    head += ' role="img"'
    return '<svg' + head + '>' + s[m.end():]


def inline_part(name):
    with io.open(os.path.join(BASE, 'parts', name + '.html'),
                 encoding='utf-8') as f:
        return f.read()


def cards_literal():
    with io.open(os.path.join(BASE, '03-cards.html'), encoding='utf-8') as f:
        s = f.read()
    i = s.index('const CARDS = [')
    j = s.index('\n];', i)
    return s[i + len('const CARDS = '):j + 2]


def main():
    with io.open(SRC, encoding='utf-8') as f:
        html = f.read()
    html = re.sub(r'\{\{PART:(\w+)\}\}',
                  lambda m: inline_part(m.group(1)), html)
    html = re.sub(r'\{\{SVG:(\w+)\}\}',
                  lambda m: inline_svg(m.group(1)), html)
    html = html.replace('{{CARDS}}', cards_literal())
    assert '{{' not in html, '未置換のプレースホルダが残っています'
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('wrote %s  (%.1f KB)' % (OUT, os.path.getsize(OUT) / 1024.0))


if __name__ == '__main__':
    main()
