# -*- coding: utf-8 -*-
"""過去走レコードの「使い残し」特徴（27本）— PASTRUN_PROTOCOL.md §2 の実装。

すべて as-of（そのレースの発走時点で知り得る情報のみ）。
- 過去走 h["races"] は定義上すべて事前情報。
- 斤量・馬体重の履歴だけは台帳の横断結合が要るので AsOfHorse（日付昇順・読む→書く）で作る。
- 上がりの標準テーブル AgariBench も同じく前日以前のレコードのみで作る。

既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
import math

CLIP = 2.5
IV_BANDS = ((0, 7), (8, 27), (28, 70), (71, 10 ** 9))

FEATS = [
    "pace_h_fin", "pace_s_fin", "pace_pref",
    "baba_slope", "baba_match_fin", "baba_x_today",
    "dist_chg_signed", "ext_fin", "sht_fin", "dist_chg_apt",
    "switch_apt",
    "field_apt",
    "pos_sd", "pos_range",
    "agari_sd", "agari_trend",
    "fin_slope5", "fin_sd",
    "kin_chg",
    "wt_dev", "wt_sd",
    "iv_match_fin", "iv_best_match",
    "cls_exp_up", "cls_up_top3",
    "rebound_flag", "rebound_hist",
]
BABA_IDX = {"良": 0, "稍": 1, "稍重": 1, "重": 2, "不": 3, "不良": 3}


# ── 小道具 ────────────────────────────────────────────────────────────
def _ff(r):
    """finish/field（0=勝ち、1=最下位）。取れなければ None"""
    f, n = r.get("finish"), r.get("field")
    if not f or not n:
        return None
    return f / max(n, 1)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def _slope(xs, ys):
    """最小二乗傾き。点が2つ未満、またはxが全部同じなら None"""
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pts) < 2:
        return None
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    if den <= 1e-12:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in pts) / den


def _band(days):
    if days is None:
        return None
    for i, (lo, hi) in enumerate(IV_BANDS):
        if lo <= days <= hi:
            return i
    return None


# ── as-of 台帳 ────────────────────────────────────────────────────────
class AgariBench:
    """(馬場, 距離200括り, baba_idx) の平均上がり。標本30未満は (馬場,距離)→(馬場) に落ちる。
       日付が変わるまで pend に溜め、日付が進んだ時にだけ反映する（同日レースも参照しない）。"""

    def __init__(self):
        self.t3, self.t2, self.t1 = {}, {}, {}
        self.pend = []
        self.day = None

    def _flush(self):
        for k, v in self.pend:
            for tbl, key in ((self.t3, k), (self.t2, k[:2]), (self.t1, k[:1])):
                s = tbl.setdefault(key, [0.0, 0])
                s[0] += v
                s[1] += 1
        self.pend = []

    def feed(self, date, races):
        """races = 過去走レコードのリスト（当該レースの出走馬の馬柱）。"""
        if self.day is not None and date != self.day:
            self._flush()
        self.day = date
        for r in races:
            a, sf, d = r.get("agari"), r.get("surface"), r.get("dist")
            if not a or not sf or not d:
                continue
            self.pend.append(((sf, int(d) // 200, r.get("baba_idx") or 0), a))

    def bench(self, surface, dist, baba_idx):
        if not surface or not dist:
            return None
        k = (surface, int(dist) // 200, baba_idx or 0)
        for tbl, key in ((self.t3, k), (self.t2, k[:2]), (self.t1, k[:1])):
            s = tbl.get(key)
            if s and s[1] >= 30:
                return s[0] / s[1]
        return None

    def resid(self, r):
        """標準より速い＝正。±2.5でクリップ"""
        a = r.get("agari")
        if not a:
            return None
        b = self.bench(r.get("surface"), r.get("dist"), r.get("baba_idx"))
        if b is None:
            return None
        return max(-CLIP, min(CLIP, b - a))


class AsOfHorse:
    """馬名 -> [(date, kinryo, weight)]。当該レースより前の日付のみを返す。"""

    def __init__(self):
        self.db = {}
        self.pend = []
        self.day = None

    def _flush(self):
        for name, k, w in self.pend:
            self.db.setdefault(name, []).append((k, w))
        self.pend = []

    def feed(self, date, horses):
        if self.day is not None and date != self.day:
            self._flush()
        self.day = date
        for h in horses:
            nm = h.get("name")
            if nm:
                self.pend.append((nm, h.get("kinryo"), h.get("weight")))

    def get(self, name):
        return self.db.get(name, [])


# ── 特徴本体 ──────────────────────────────────────────────────────────
def feats(h, race, bench, hdb):
    """1頭分・27本の生値（Noneあり）を返す。"""
    rs = h.get("races") or []
    f = {k: None for k in FEATS}
    ffs = [_ff(r) for r in rs]
    tdist = race.get("distance")
    tsurf = race.get("surface")
    tfield = race.get("field") or len(race.get("horses") or [])
    ttier = race.get("today_tier")
    tbaba = BABA_IDX.get((race.get("baba") or "").strip(), 0)

    # ペース適性
    hf = _mean([-v for r, v in zip(rs, ffs) if v is not None and r.get("pace") == "H"])
    sf = _mean([-v for r, v in zip(rs, ffs) if v is not None and r.get("pace") == "S"])
    f["pace_h_fin"] = hf
    f["pace_s_fin"] = sf
    f["pace_pref"] = (hf - sf) if (hf is not None and sf is not None) else None

    # 馬場指数適性
    bx = [r.get("baba_idx") for r in rs]
    by = [-v if v is not None else None for v in ffs]
    pts = [(x, y) for x, y in zip(bx, by) if x is not None and y is not None]
    f["baba_slope"] = _slope([p[0] for p in pts], [p[1] for p in pts]) if pts else None
    f["baba_match_fin"] = _mean([-v for r, v in zip(rs, ffs)
                                 if v is not None and (r.get("baba_idx") or 0) == tbaba])
    f["baba_x_today"] = (f["baba_slope"] * tbaba) if f["baba_slope"] is not None else None

    # 距離変化
    if rs and rs[0].get("dist") and tdist:
        f["dist_chg_signed"] = (tdist - rs[0]["dist"]) / rs[0]["dist"]
    ext, sht = [], []
    for i in range(len(rs) - 1):
        a, b, v = rs[i].get("dist"), rs[i + 1].get("dist"), ffs[i]
        if a and b and v is not None:
            (ext if a > b else sht if a < b else []).append(-v)
    f["ext_fin"] = _mean(ext)
    f["sht_fin"] = _mean(sht)
    if rs and rs[0].get("dist") and tdist:
        if tdist > rs[0]["dist"]:
            f["dist_chg_apt"] = f["ext_fin"]
        elif tdist < rs[0]["dist"]:
            f["dist_chg_apt"] = f["sht_fin"]
        else:
            f["dist_chg_apt"] = _mean([-v for r, v in zip(rs, ffs)
                                       if v is not None and r.get("dist") == tdist])

    # 芝ダ替わりの実績（今日が替わりのときだけ有効）
    sw = [-ffs[i] for i in range(len(rs) - 1)
          if ffs[i] is not None and rs[i].get("surface") and rs[i + 1].get("surface")
          and rs[i]["surface"] != rs[i + 1]["surface"]]
    if rs and tsurf and rs[0].get("surface"):
        f["switch_apt"] = (_mean(sw) or 0.0) if rs[0]["surface"] != tsurf else 0.0

    # 頭数適性
    if tfield:
        f["field_apt"] = _mean([-v for r, v in zip(rs, ffs)
                                if v is not None and r.get("field")
                                and abs(r["field"] - tfield) <= 3])

    # 位置取りの安定性
    pos = [r["corner4"] / max(r.get("field") or 1, 1) for r in rs[:5]
           if r.get("corner4") and r.get("field")]
    if len(pos) >= 3:
        f["pos_sd"] = _std(pos)
        f["pos_range"] = max(pos) - min(pos)

    # 上がりの安定性・傾き
    res5 = [bench.resid(r) for r in rs[:5]]
    got = [(i, v) for i, v in enumerate(res5) if v is not None]
    if len(got) >= 3:
        f["agari_sd"] = _std([v for _, v in got])
        f["agari_trend"] = _slope([-i for i, _ in got], [v for _, v in got])

    # 着順の傾き・ばらつき
    got = [(i, v) for i, v in enumerate(ffs[:5]) if v is not None]
    if len(got) >= 3:
        f["fin_slope5"] = _slope([-i for i, _ in got], [-v for _, v in got])
        f["fin_sd"] = _std([v for _, v in got])

    # 斤量・馬体重（as-of 台帳）
    hist = hdb.get(h.get("name"))
    if hist:
        lastk = next((k for k, _ in reversed(hist) if k), None)
        if lastk and h.get("kinryo"):
            f["kin_chg"] = h["kinryo"] - lastk
        ws = [w for _, w in hist if w]
        if ws and h.get("weight"):
            f["wt_dev"] = h["weight"] - sum(ws) / len(ws)
        if len(ws) >= 2:
            f["wt_sd"] = _std(ws)

    # 間隔パターン
    tb = _band(h.get("last_race_days"))
    if tb is not None:
        f["iv_match_fin"] = _mean([-v for r, v in zip(rs, ffs)
                                   if v is not None and _band(r.get("days")) == tb])
        acc = {}
        for r, v in zip(rs, ffs):
            b = _band(r.get("days"))
            if b is not None and v is not None:
                acc.setdefault(b, []).append(-v)
        cand = {b: sum(v) / len(v) for b, v in acc.items() if len(v) >= 2}
        if cand:
            f["iv_best_match"] = 1.0 if max(cand, key=cand.get) == tb else 0.0

    # クラス経験
    tiers = [r.get("tier") for r in rs if r.get("tier") is not None]
    if tiers and ttier is not None:
        f["cls_exp_up"] = ttier - min(tiers)
        f["cls_up_top3"] = float(sum(1 for r in rs if r.get("tier") is not None
                                     and r["tier"] < ttier and (r.get("finish") or 99) <= 3))

    # 復調シグナル
    if ffs and ffs[0] is not None and any(v is not None for v in ffs[1:3]):
        f["rebound_flag"] = 1.0 if (ffs[0] >= 0.7 and any(
            v is not None and v <= 0.3 for v in ffs[1:3])) else 0.0
    bad = [i for i in range(1, len(rs)) if ffs[i] is not None and ffs[i] >= 0.7]
    if bad:
        f["rebound_hist"] = sum(1 for i in bad
                                if (rs[i - 1].get("finish") or 99) <= 3) / len(bad)
    return f


def z_in_race(vals):
    """レース内z標準化。Noneは0(平均)扱い（fit_v2.z_in_race と同じ規約）"""
    xs = [v for v in vals.values() if v is not None]
    if len(xs) < 2:
        return {k: 0.0 for k in vals}
    m = sum(xs) / len(xs)
    sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5 or 1.0
    return {k: ((v - m) / sd if v is not None else 0.0) for k, v in vals.items()}


def selftest():
    """定義の自己検査（数値の作り方が意図どおりかを固定入力で確認）"""
    race = dict(distance=1600, surface="芝", field=10, baba="良", today_tier=6,
                horses=[])
    h = dict(name="テスト", kinryo=56.0, weight=480, last_race_days=14, races=[
        dict(surface="ダ", dist=1400, finish=8, field=10, corner4=8, agari=36.0,
             tier=6, days=14, pace="H", baba_idx=0),
        dict(surface="芝", dist=1800, finish=2, field=12, corner4=4, agari=34.5,
             tier=10, days=21, pace="S", baba_idx=1),
        dict(surface="芝", dist=1600, finish=1, field=14, corner4=5, agari=34.0,
             tier=10, days=30, pace="M", baba_idx=0),
    ])
    b, db = AgariBench(), AsOfHorse()
    f = feats(h, race, b, db)
    assert abs(f["pace_h_fin"] - (-0.8)) < 1e-9, f["pace_h_fin"]
    assert abs(f["dist_chg_signed"] - (1600 - 1400) / 1400) < 1e-9
    assert f["switch_apt"] is not None and f["switch_apt"] != 0.0   # 今日は芝・前走ダ
    assert f["cls_exp_up"] == 0                                     # 過去最小tier=6=今日
    assert f["rebound_flag"] == 1.0                                 # 前走0.8→2走前0.167
    assert f["kin_chg"] is None and f["wt_dev"] is None              # 台帳が空
    db.feed("20260101", [dict(name="テスト", kinryo=54.0, weight=470)])
    db.feed("20260201", [])                                          # 日付が進んで反映
    f2 = feats(h, race, b, db)
    assert abs(f2["kin_chg"] - 2.0) < 1e-9 and abs(f2["wt_dev"] - 10.0) < 1e-9
    missing = [k for k in FEATS if k not in f]
    assert not missing, missing
    print(f"selftest OK  特徴数={len(FEATS)}")


if __name__ == "__main__":
    selftest()
