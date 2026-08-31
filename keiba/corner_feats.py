# -*- coding: utf-8 -*-
"""再収穫した4項目（corner_all / pace_first / pace_last / run_time / margin）から作る
   10特徴 — CORNER_PROTOCOL.md §2 の実装。

すべて as-of（過去走レコードのみ。当該レースの結果は使わない）。
既存ファイルは一切変更していない（本ファイルは新規・独立）。
"""
CLIP = 2.5
WIN = 5          # 既定の窓＝直近5走（プロトコル §2）

FEATS = [
    "pos_gain",   # 1 道中で位置を上げる馬
    "pos_var",    # 2 道中で動く馬
    "wide4c",     # 3 最後の角で位置を下げる（外を回す）
    "pace_lv",    # 4 経験した前半3Fの水準
    "pace_gap",   # 5 前傾/後傾ラップの経験
    "fwd_fin",    # 6 前傾ラップでの着順
    "mgn_abs",    # 7 着差の絶対値
    "spd_res",    # 8 条件補正した時計の水準
    "grind",      # 9 先行して粘った割合
    "unlucky",    # 10 位置が良いのに着順が悪い
]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def _ff(r):
    f, n = r.get("finish"), r.get("field")
    if not f or not n:
        return None
    return f / max(n, 1)


class SpeedBench:
    """(馬場, 距離200括り, baba_idx) の平均速度 m/s。標本30未満は (馬場,距離)→(馬場) に落ちる。
       AgariBench と同じ規約: 日付が進んだ時にだけ反映（同日レースも参照しない）。"""

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
        if self.day is not None and date != self.day:
            self._flush()
        self.day = date
        for r in races:
            t, d, sf = r.get("run_time"), r.get("dist"), r.get("surface")
            if not t or not d or not sf or t <= 0:
                continue
            self.pend.append(((sf, int(d) // 200, r.get("baba_idx") or 0), d / t))

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
        """標準より速い＝正。±2.5でクリップ（m/s単位）"""
        t, d = r.get("run_time"), r.get("dist")
        if not t or not d or t <= 0:
            return None
        b = self.bench(r.get("surface"), r.get("dist"), r.get("baba_idx"))
        if b is None:
            return None
        return max(-CLIP, min(CLIP, d / t - b))


def feats(h, race, sbench):
    """1頭分・10本の生値（Noneあり）を返す。"""
    rs = h.get("races") or []
    w = rs[:WIN]
    f = {k: None for k in FEATS}

    # 1-3: 通過順の全区間
    gains, varis, wides = [], [], []
    for r in w:
        ca = r.get("corner_all") or []
        F = r.get("field") or 0
        if len(ca) >= 2 and F:
            gains.append((ca[0] - ca[-1]) / F)
            sd = _std(ca)
            if sd is not None:
                varis.append(sd / F)
            wides.append((ca[-1] - ca[-2]) / F)
    f["pos_gain"] = _mean(gains)
    f["pos_var"] = _mean(varis)
    f["wide4c"] = _mean(wides)

    # 4-5: ペース
    f["pace_lv"] = _mean([r.get("pace_first") for r in w])
    f["pace_gap"] = _mean([(r["pace_first"] - r["pace_last"])
                           for r in w
                           if r.get("pace_first") is not None
                           and r.get("pace_last") is not None])

    # 6: 前傾ラップ（前半3F < 後半3F）での着順（最大9走＝レコード全体）
    fw = []
    for r in rs:
        a, b = r.get("pace_first"), r.get("pace_last")
        v = _ff(r)
        if a is not None and b is not None and v is not None and a < b:
            fw.append(-v)
    f["fwd_fin"] = _mean(fw)

    # 7: 着差の絶対値
    f["mgn_abs"] = _mean([abs(r["margin"]) for r in w if r.get("margin") is not None])

    # 8: 条件補正した時計
    f["spd_res"] = _mean([sbench.resid(r) for r in w])

    # 9: 先行して粘った割合
    flags = []
    for r in w:
        ca = r.get("corner_all") or []
        F = r.get("field") or 0
        mg = r.get("margin")
        if not ca or not F or mg is None:
            continue
        pos = (sum(ca) / len(ca)) / F
        flags.append(1.0 if (pos <= 0.4 and abs(mg) <= 0.5) else 0.0)
    f["grind"] = _mean(flags)

    # 10: 位置が良いのに着順が悪い
    unl = []
    for r in w:
        ca = r.get("corner_all") or []
        F = r.get("field") or 0
        v = _ff(r)
        if ca and F and v is not None:
            unl.append(v - (sum(ca) / len(ca)) / F)
    f["unlucky"] = _mean(unl)
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
    """定義の自己検査（固定入力で作り方が意図どおりかを確認）"""
    sb = SpeedBench()
    for _ in range(40):
        sb.feed("20200101", [dict(run_time=100.0, dist=1600, surface="芝", baba_idx=0)])
    sb.feed("20200102", [])
    race = dict(distance=1600, surface="芝", field=10, baba="良", today_tier=6, horses=[])
    h = dict(name="テスト", races=[
        dict(surface="芝", dist=1600, finish=1, field=10, corner_all=[8, 8, 6, 2],
             pace_first=34.0, pace_last=36.0, run_time=95.0, margin=-0.2),
        dict(surface="芝", dist=1600, finish=9, field=10, corner_all=[2, 3],
             pace_first=36.0, pace_last=34.5, run_time=105.0, margin=3.0),
    ])
    f = feats(h, race, sb)
    # 1走目: (8-2)/10=0.6  2走目: (2-3)/10=-0.1 → 平均 0.25
    assert abs(f["pos_gain"] - 0.25) < 1e-9, f["pos_gain"]
    # wide4c: (2-6)/10=-0.4, (3-2)/10=0.1 → -0.15
    assert abs(f["wide4c"] + 0.15) < 1e-9, f["wide4c"]
    assert abs(f["pace_lv"] - 35.0) < 1e-9
    # pace_gap: (34-36)=-2, (36-34.5)=1.5 → -0.25
    assert abs(f["pace_gap"] + 0.25) < 1e-9, f["pace_gap"]
    # fwd_fin: 前傾=1走目のみ → -(1/10) = -0.1
    assert abs(f["fwd_fin"] + 0.1) < 1e-9, f["fwd_fin"]
    assert abs(f["mgn_abs"] - 1.6) < 1e-9, f["mgn_abs"]
    # spd_res: bench=16.0, 1走目 1600/95=16.842 → +0.842、2走目 1600/105=15.238 → -0.762
    assert abs(f["spd_res"] - (16.0 / 2 * 0 + (1600 / 95 - 16.0 + 1600 / 105 - 16.0) / 2)) < 1e-9
    # grind: 1走目 pos=(8+8+6+2)/4/10=0.6>0.4 → 0 / 2走目 pos=0.25<=0.4 だが |3.0|>0.5 → 0
    assert f["grind"] == 0.0, f["grind"]
    # unlucky: 1走目 0.1-0.6=-0.5 / 2走目 0.9-0.25=0.65 → 平均 0.075
    assert abs(f["unlucky"] - 0.075) < 1e-9, f["unlucky"]
    print("corner_feats selftest OK", {k: (round(v, 4) if v is not None else None)
                                       for k, v in f.items()})


if __name__ == "__main__":
    selftest()
