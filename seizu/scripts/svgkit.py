# -*- coding: utf-8 -*-
"""SVGを組み立てるための小さな道具箱。"""

FONT = ("'Hiragino Sans','Hiragino Kaku Gothic ProN','Noto Sans JP',"
        "'Yu Gothic',Meiryo,'IPAGothic',sans-serif")


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def attrs(d):
    out = []
    for k, v in d.items():
        if v is None:
            continue
        out.append('%s="%s"' % (k.replace('_', '-'), esc(v)))
    return ' '.join(out)


def f(v):
    """数値を短い文字列にする。"""
    return ('%.2f' % v).rstrip('0').rstrip('.')


class Svg(object):
    def __init__(self, w, h, bg='#ffffff'):
        self.w, self.h, self.bg = w, h, bg
        self.parts = []

    def add(self, s):
        self.parts.append(s)
        return self

    def rect(self, x, y, w, h, **kw):
        kw.setdefault('fill', 'none')
        return self.add('<rect x="%s" y="%s" width="%s" height="%s" %s/>'
                        % (f(x), f(y), f(w), f(h), attrs(kw)))

    def line(self, x1, y1, x2, y2, **kw):
        kw.setdefault('stroke', '#111')
        return self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" %s/>'
                        % (f(x1), f(y1), f(x2), f(y2), attrs(kw)))

    def poly(self, pts, **kw):
        kw.setdefault('fill', 'none')
        d = ' '.join('%s,%s' % (f(p[0]), f(p[1])) for p in pts)
        return self.add('<polyline points="%s" %s/>' % (d, attrs(kw)))

    def polygon(self, pts, **kw):
        kw.setdefault('fill', 'none')
        d = ' '.join('%s,%s' % (f(p[0]), f(p[1])) for p in pts)
        return self.add('<polygon points="%s" %s/>' % (d, attrs(kw)))

    def circle(self, cx, cy, r, **kw):
        kw.setdefault('fill', 'none')
        return self.add('<circle cx="%s" cy="%s" r="%s" %s/>'
                        % (f(cx), f(cy), f(r), attrs(kw)))

    def path(self, d, **kw):
        kw.setdefault('fill', 'none')
        return self.add('<path d="%s" %s/>' % (d, attrs(kw)))

    def text(self, x, y, s, size=12, anchor='middle', fill='#111',
             weight='400', **kw):
        kw.update(dict(x=f(x), y=f(y), font_size=size, text_anchor=anchor,
                       fill=fill, font_weight=weight, font_family=FONT))
        return self.add('<text %s>%s</text>' % (attrs(kw), esc(s)))

    def lines_text(self, x, y, rows, size=12, lh=None, anchor='middle',
                   fill='#111', weight='400'):
        """複数行のテキスト。rowsは (文字列, サイズ, 太さ, 色) でも可。"""
        lh = lh or size * 1.35
        for i, row in enumerate(rows):
            if isinstance(row, tuple):
                s = row[0]
                sz = row[1] if len(row) > 1 else size
                w = row[2] if len(row) > 2 else weight
                c = row[3] if len(row) > 3 else fill
            else:
                s, sz, w, c = row, size, weight, fill
            self.text(x, y + i * lh, s, size=sz, anchor=anchor, fill=c,
                      weight=w)
        return self

    # 寸法線（両端に矢羽根）
    def dim_h(self, x1, x2, y, label, size=11, color='#444', tick=4):
        self.line(x1, y, x2, y, stroke=color, stroke_width=0.8)
        for x in (x1, x2):
            self.line(x, y - tick, x, y + tick, stroke=color, stroke_width=0.8)
        self.text((x1 + x2) / 2.0, y - 5, label, size=size, fill=color)
        return self

    def dim_v(self, y1, y2, x, label, size=11, color='#444', tick=4,
              anchor='end', dx=-6):
        self.line(x, y1, x, y2, stroke=color, stroke_width=0.8)
        for y in (y1, y2):
            self.line(x - tick, y, x + tick, y, stroke=color, stroke_width=0.8)
        self.text(x + dx, (y1 + y2) / 2.0 + 4, label, size=size, fill=color,
                  anchor=anchor)
        return self

    def dump(self):
        head = ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 %s %s" width="%s" height="%s" '
                'font-family=%s>' % (f(self.w), f(self.h), f(self.w),
                                     f(self.h), '"' + FONT.replace('"', '') + '"'))
        bg = ('<rect width="%s" height="%s" fill="%s"/>'
              % (f(self.w), f(self.h), self.bg)) if self.bg else ''
        return head + bg + ''.join(self.parts) + '</svg>'

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(self.dump())
        return path


def _text_rot(self, x, y, s, angle=-90, size=12, anchor='middle',
              fill='#111', weight='400'):
    """回転させた文字。"""
    self.add('<g transform="translate(%s,%s) rotate(%s)">' % (f(x), f(y), f(angle)))
    self.text(0, 0, s, size=size, anchor=anchor, fill=fill, weight=weight)
    self.add('</g>')
    return self


Svg.text_rot = _text_rot
