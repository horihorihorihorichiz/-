# -*- coding: utf-8 -*-
"""着順表と追い切りページの読み取り。ブラウザで実測した並びに合わせてある。"""
import re

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def _txt(html):
    return WS.sub(" ", TAG.sub(" ", html)).replace("&nbsp;", " ").strip()


# ── 着順表（db.netkeiba.com/race/<id>/）─────────────────────────────
# td の並び（実測）:
#  0着順 1枠 2馬番 3馬名 4性齢 5斤量 6騎手 7タイム 8着差 9タイム指数
#  10指数M 11スタート指数 12追走指数 13上がり指数 14通過 15上り 16単勝
#  17人気 18馬体重 19調教タイム 20厩舎コメント 21備考 22調教師 23馬主 24賞金
RE_TABLE = re.compile(r'<table[^>]*class="race_table_01[\s\S]*?</table>')
RE_TD = re.compile(r"<td[^>]*>([\s\S]*?)</td>")
RE_HORSE = re.compile(r"/horse/(\w{8,10})/")
RE_JOCKEY = re.compile(r"/jockey/(?:result/recent/)?(\w{5})/")
RE_TRAINER = re.compile(r"/trainer/(?:result/recent/)?(\w{5})/")
RE_TIME = re.compile(r"(\d+):(\d+)\.(\d+)")
RE_BW = re.compile(r"(\d+)\(([-+]?\d+)\)")
RE_SEXAGE = re.compile(r"([牡牝セ騸])(\d+)")
RE_COURSE = re.compile(r"(芝|ダ|障)\s*(右|左|直線)?\s*(外|内)?\s*(\d+)m")

CLASSES = ((r"新馬|未勝利", "t10"), (r"1勝クラス|500万", "t6"),
           (r"2勝クラス|1000万", "t5"), (r"3勝クラス|1600万", "t4"),
           (r"オープン", "t3"))


def race(rid, html):
    """1レースぶんを辞書で返す。読めなければ None。"""
    mi = re.search(r'<div class="data_intro">([\s\S]*?)</div>', html)
    mt = RE_TABLE.search(html)
    if not mi or not mt:
        return None
    intro = _txt(mi.group(1))
    md = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", intro)
    mk = re.search(r"(\d+)回(\S+?)(\d+)日目", intro)
    mc = RE_COURSE.search(intro)
    mw = re.search(r"天候\s*:\s*(\S+)", intro)
    mg = re.search(r"(?:芝|ダート)\s*:\s*(\S+)", intro)
    tail = intro[intro.index(md.group(0)):] if md else ""
    cls = ""
    for pat, name in CLASSES:
        if re.search(pat, tail):
            cls = name
            break

    rows, idx = [], []
    for tr in mt.group(0).split("<tr")[2:]:
        tds = [_txt(x) for x in RE_TD.findall(tr)]
        if len(tds) < 18:
            continue
        mh = RE_HORSE.search(tr)
        if not mh:
            continue
        mj, mtr = RE_JOCKEY.search(tr), RE_TRAINER.search(tr)
        mtime = RE_TIME.search(tds[7])
        mbw = RE_BW.search(tds[18])
        msa = RE_SEXAGE.search(tds[4])

        def f(x, d=0.0):
            try:
                return float(x)
            except Exception:
                return d

        rows.append({
            "fin": tds[0], "waku": int(f(tds[1])), "umaban": int(f(tds[2])),
            "horse": mh.group(1), "sex": msa.group(1) if msa else "",
            "age": int(msa.group(2)) if msa else 0, "kin": f(tds[5]),
            "jockey": mj.group(1) if mj else "",
            "sec": (int(mtime.group(1)) * 60 + int(mtime.group(2))
                    + int(mtime.group(3)) / 10) if mtime else 0.0,
            "margin": tds[8], "corner": tds[14], "agari": f(tds[15]),
            "odds": f(tds[16]), "pop": int(f(tds[17])),
            "bw": int(mbw.group(1)) if mbw else 0,
            "bwd": int(mbw.group(2)) if mbw else 0,
            "trainer": mtr.group(1) if mtr else "",
        })
        v = f(tds[9], 0.0)
        idx.append(v if v > 0 else 0.0)

    if not rows:
        return None
    return {"id": rid, "date": (md.group(1) + md.group(2).zfill(2) + md.group(3).zfill(2)) if md else "",
            "place": rid[4:6], "kai": int(mk.group(1)) if mk else 0,
            "nday": int(mk.group(3)) if mk else 0, "r": int(rid[10:12]),
            "surf": mc.group(1) if mc else "", "turn": mc.group(2) if mc and mc.group(2) else "",
            "io": mc.group(3) if mc and mc.group(3) else "",
            "dist": int(mc.group(4)) if mc else 0,
            "weather": mw.group(1) if mw else "", "ground": mg.group(1) if mg else "",
            "cls": cls, "n": len(rows), "rows": rows, "tidx": idx}


# ── 追い切り（race.netkeiba.com/race/oikiri.html?race_id=<id>&type=2）──
# 行の作りが2種類ある。日付の入った升を目印に相対で読む。
RE_OIK = re.compile(r'<table[^>]*OikiriTable[\s\S]*?</table>')
RE_TR = re.compile(r"<tr[\s\S]*?</tr>")
RE_LAP = re.compile(r"(\d{2,3}\.\d)\((\d{2}\.\d)\)")
RE_DATE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})")


def oikiri(html):
    mt = RE_OIK.search(html)
    if not mt:
        return None
    out, pend = [], None
    for tr in RE_TR.findall(mt.group(0)):
        tds = [_txt(x) for x in RE_TD.findall(tr)]
        if not tds:
            continue
        mh = RE_HORSE.search(tr)
        off = -1
        for i, c in enumerate(tds):
            if RE_DATE.match(c):
                off = i
                break
        if off < 0:
            if mh:
                try:
                    pend = (mh.group(1), int(float(tds[1])))
                except Exception:
                    pend = (mh.group(1), 0)
            continue
        g = lambda i: tds[i] if 0 <= i < len(tds) else ""
        md = RE_DATE.match(g(off))
        laps = [(float(a), float(b)) for a, b in RE_LAP.findall(g(off + 4))]
        horse = mh.group(1) if mh else (pend[0] if pend else "")
        if off >= 4:
            try:
                umaban = int(float(g(1)))
            except Exception:
                umaban = 0
        else:
            umaban = pend[1] if pend else 0
        try:
            hon = int(float(g(off + 5)))
        except Exception:
            hon = 0
        out.append({"horse": horse, "umaban": umaban,
                    "date": md.group(1) + md.group(2) + md.group(3),
                    "course": g(off + 1), "ground": g(off + 2),
                    "rider": g(off + 3), "laps": laps, "hon": hon,
                    "way": g(off + 6), "eval": g(off + 7), "leg": g(off + 8)})
        pend = None
    return out or None


def race_ids(html):
    """一覧ページから中央競馬のレースIDを拾う。"""
    ids = set(re.findall(r"/race/(\d{12})/", html))
    ids |= set(re.findall(r"race_id=(\d{12})", html))
    return sorted(i for i in ids if 1 <= int(i[4:6]) <= 10)
