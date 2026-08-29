# -*- coding: utf-8 -*-
"""取得の手順。着順表と追い切りを、続きから何度でも再開できる形で貯める。"""
import datetime as dt
import concurrent.futures as cf
from . import parse


def kaisai_dates(f, start, end):
    """開催日の一覧。JRAは土日月しか開催しないので、その3曜日だけ当たる。"""
    d = dt.date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    e = dt.date(int(end[:4]), int(end[4:6]), int(end[6:8]))
    out = []
    while d <= e:
        if d.weekday() in (5, 6, 0):
            out.append(d.strftime("%Y%m%d"))
        d += dt.timedelta(days=1)
    return out


def scan_ids(f, start, end, log=print):
    """開催日ごとの一覧からレースIDを集める。空で返った日は1度だけ取り直す。"""
    ids, empty = [], []
    days = kaisai_dates(f, start, end)
    for i, day in enumerate(days):
        t = f.get(f"https://db.netkeiba.com/race/list/{day}/")
        got = parse.race_ids(t) if t else []
        if got:
            ids += [(x, day) for x in got]
        else:
            empty.append(day)
        if (i + 1) % 50 == 0:
            log(f"  日付 {i+1}/{len(days)} → {len(ids)}レース")
    for day in empty:                     # 取りこぼしの拾い直し
        t = f.get(f"https://db.netkeiba.com/race/list/{day}/")
        got = parse.race_ids(t) if t else []
        ids += [(x, day) for x in got]
    seen, uniq = set(), []
    for x, day in sorted(ids, key=lambda z: (z[1], z[0])):
        if x not in seen:
            seen.add(x); uniq.append(x)
    log(f"  合計 {len(uniq)}レース / 開催日 {len(days)-len(empty)+sum(1 for _ in [])}")
    return uniq


def results(f, store, ids, workers=3, log=print):
    """着順表。タイム指数もここで一緒に入る。"""
    todo = [i for i in ids if i not in store.have_races()]
    log(f"  着順表 残り {len(todo)}件")
    done = [0]

    def one(rid):
        t = f.get(f"https://db.netkeiba.com/race/{rid}/")
        r = parse.race(rid, t) if t else None
        return rid, r

    with cf.ThreadPoolExecutor(workers) as ex:
        for rid, r in ex.map(one, todo):
            done[0] += 1
            if r:
                store.put_race(r)
            else:
                store.mark_failed(rid, "race")
            if done[0] % 200 == 0:
                store.commit(); log(f"    {done[0]}/{len(todo)}")
    store.commit()
    return done[0]


def training(f, store, ids, workers=1, log=print):
    """追い切り。ここは必ず遅く。速いと netkeiba 側に止められる（実測）。"""
    todo = [i for i in ids if i not in store.have_oikiri()]
    log(f"  追い切り 残り {len(todo)}件（毎秒 {1/f.min_gap:.1f}件）")
    done = [0]; miss = [0]

    def one(rid):
        t = f.get(f"https://race.netkeiba.com/race/oikiri.html?race_id={rid}&type=2",
                  encoding="utf-8")
        return rid, (parse.oikiri(t) if t else None)

    with cf.ThreadPoolExecutor(workers) as ex:
        for rid, rows in ex.map(one, todo):
            done[0] += 1
            if rows:
                store.put_oikiri(rid, rows)
            else:
                miss[0] += 1
                store.mark_failed(rid, "oikiri")
                if miss[0] % 20 == 0:      # 続けて失敗するなら減速
                    f.slow_down(1.5)
                    log(f"    取りこぼしが {miss[0]}件。速さを落とします")
            if done[0] % 100 == 0:
                store.commit(); log(f"    {done[0]}/{len(todo)}（取りこぼし{miss[0]}）")
    store.commit()
    return done[0], miss[0]
