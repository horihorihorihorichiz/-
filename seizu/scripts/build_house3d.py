# -*- coding: utf-8 -*-
"""型の家を3Dで組み立てるページ（house3d.html）を作る。

平面図・伏図・柱の位置は plans.py から取り出して JSON にし、
scripts/house3d.template.html の /*DATA*/ に埋めこむ。
"""
import io
import json
import os

import plans

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def export():
    nx, ny = plans.NX, plans.NY
    fits = plans.fit_all(plans.FLOORS, nx, ny, plans.XLINES, plans.YLINES)
    floors = {}
    for n, d in plans.FLOORS.items():
        walls = []
        for (ori, ln), segs in plans._wall_segments({n: d}).items():
            for a, b in segs:
                walls.append([ori, float(ln), float(a), float(b)])
        tooshi, kuda = plans.columns_of(n)
        floors[n] = dict(
            title=d['title'],
            rooms=[[nm, ar, a, b, c, e] for nm, ar, a, b, c, e, _ in d['rooms']],
            walls=walls,
            openings=[[f, float(p), float(l), k, lab] for f, p, l, k, lab in fits[n]],
            doors=[[o, float(w), float(p), float(l)]
                   for o, w, p, l in plans.fit_doors(d, plans.FLOORS)],
            tooshi=[list(p) for p in tooshi],
            kuda=[list(p) for p in kuda],
        )
    fr = {}
    for key, (lo, up) in (('f2', (1, 2)), ('f3', (2, 3)), ('roof', (3, None))):
        fr[key] = [[o, l, a, b, s, k] for o, l, a, b, s, k in plans.framing(lo, up)]
    return dict(
        module=910, nx=nx, ny=ny,
        xlines=[[g, nm] for g, nm in plans.XLINES],
        ylines=[[g, nm] for g, nm in plans.YLINES],
        floors=floors, framing=fr,
        heights=dict(gl=0, kiso_bottom=-300, slab=-150, kiso_top=371,
                     dodai=511, fl={'1': 550, '2': 3650, '3': 6550},
                     beam_top={'2': 3611, '3': 6511}, noki=9350, top=10806,
                     ceil={'1': 3250, '2': 6150, '3': 9050}),
        roof=dict(slope=0.4, eave=600, kerava=455, ridge_x=nx / 2.0),
    )


if __name__ == '__main__':
    data = export()
    tpl = io.open(os.path.join(BASE, 'scripts', 'house3d.template.html'),
                  encoding='utf-8').read()
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    out = tpl.replace('/*DATA*/', 'const DATA = %s;' % js, 1)
    p = os.path.join(BASE, 'house3d.html')
    io.open(p, 'w', encoding='utf-8').write(out)
    print('wrote house3d.html  (%.1f KB)' % (len(out.encode('utf-8')) / 1024.0))
