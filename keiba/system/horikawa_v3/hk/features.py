# -*- coding: utf-8 -*-
"""成分づくり。発走前に分かることだけを使う。

 16成分は堀川システムの説明に沿った再実装。
 そこに実測で効いた7つを足してある（騎手・調教師・前走人気・馬体重・距離変化・齢・公式指数）。
 調教が揃えば 24番目以降として同じ形で足せる（add_training を参照）。
"""
import math
from collections import defaultdict

BASE_NAMES = ["TSI", "LTS", "FSI", "Bonus", "DSI", "NSI", "CSI", "WAS", "TAS", "HCS",
              "NRJA", "展開乗数", "spd_res", "mgn_abs", "wide4c", "pos_gain",
              "騎手", "調教師", "前走人気", "馬体重", "距離変化", "齢", "公式指数"]
# 追い切りが取れているときだけ足す3つ。
#   調教縦断 … 同じ馬の、同じコース種別での過去の追い切り時計との差（速いほど＋）
#   調教本数 … 前走からの本数
#   調教評価 … 「前走並み」等の短評を順序に直したもの
TRAIN_NAMES = ["調教縦断", "調教本数", "調教評価"]
# 木の学習器に渡す「条件」と「生の値」。レース内で標準化せず、そのまま渡す。
# 条件を成分として渡すと、学習器が場・距離・クラスごとの使い分けを自分で見つける。
CTX_NAMES = ["頭数", "距離", "芝ダ", "馬場", "クラス", "場", "回り", "内外", "R", "月"]
RAW_NAMES = ["馬番相対", "枠", "斤量", "齢生", "前走着順", "前走着差", "前走上り",
             "通算出走", "通算勝率", "同条件率", "連続3着内", "初出走", "前走頭数", "休養日数"]
MKT_NAMES = ["log単勝", "人気", "オッズ順位", "1番人気との比"]
PLACES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]

NAMES = BASE_NAMES
NF = len(NAMES)

# 追い切りコースの種別。坂路とウッドは時計の尺度が違うので必ず分けて比べる。
def course_kind(c):
    c = (c or "").replace("Ｗ", "W").replace("ダ", "D")
    if not c:
        return ""
    head, tail = c[0], c[1:]
    if "坂" in c:
        return head + "坂"
    if "W" in tail:
        return head + "W"
    if "D" in tail:
        return head + "D"
    if "芝" in tail:
        return head + "芝"
    return c

EVAL_SCORE = {"抜群": 3, "文句なし": 3, "上々": 2, "順調": 2, "好調": 2,
              "動き良化": 2, "上昇": 2, "気配良化": 2, "乗込入念": 1, "直前強め": 1,
              "前走並み": 0, "平行線": 0, "変わらず": 0, "反応平凡": -1, "動き平凡": -1,
              "いま一息": -2, "物足りず": -2, "案外": -2, "不安": -3, "太目": -2}


def eval_score(t):
    t = (t or "").strip()
    if t in EVAL_SCORE:
        return EVAL_SCORE[t]
    for k, v in EVAL_SCORE.items():
        if k and k in t:
            return v
    return None
RANK = {"t10": 0, "t6": 1, "t5": 2, "t4": 3, "t3": 4}
PACE_TAB = [[8, 4, -4, -8], [5, 3, -2, -5], [0, 1, 0, -1],
            [-5, -2, 3, 5], [-8, -4, 4, 8]]


def band(d):
    return "S" if d <= 1400 else ("M" if d <= 2000 else "L")


def cell_keys(r):
    sb = r["surf"] + band(r["dist"])
    return {"L1": sb, "A": r["place"] + sb, "B": sb + "/" + r["cls"],
            "C": r["place"] + sb + "/" + r["cls"] + (r["turn"] or "-")}


def _days(a, b):
    import datetime as dt
    f = lambda s: dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return (f(a) - f(b)).days


def _fin(s):
    try:
        return int(s)
    except Exception:
        return None


def _corners(s):
    out = []
    for x in (s or "").split("-"):
        try:
            v = int(x)
            if v > 0:
                out.append(v)
        except Exception:
            pass
    return out


class Book:
    """レース一覧から、馬ごとの出走履歴と基準タイムを作る。"""

    def __init__(self, races, base_cutoff):
        self.races = [r for r in races
                      if r["surf"] in ("芝", "ダ") and r["n"] >= 5
                      and r["dist"] > 0 and r["cls"]]
        self.hist = defaultdict(list)
        for ri, r in enumerate(self.races):
            for hi, h in enumerate(r["rows"]):
                self.hist[h["horse"]].append((ri, hi))
        self._base(base_cutoff)

    def _base(self, cutoff):
        """馬場状態ごとの基準タイム。漏洩を避けるため学習窓より前だけで作る。"""
        acc = defaultdict(lambda: [[], [], [], []])
        for r in self.races:
            if r["date"] >= cutoff:
                break
            g = {"良": 0, "稍重": 1, "重": 2}.get(r["ground"], 3)
            k = r["place"] + r["surf"] + str(r["dist"])
            for h in r["rows"]:
                if h["sec"]:
                    acc[k][g].append(h["sec"])
        med = lambda a: sorted(a)[len(a) // 2] if a else None
        self.base = {}
        for k, g4 in acc.items():
            b = med(g4[0]) or med([x for a in g4 for x in a])
            if b is None:
                continue
            self.base[k] = (b, [((med(a) - b) if med(a) is not None else 0.0)
                                for a in g4])

    def spd(self, r, h):
        b = self.base.get(r["place"] + r["surf"] + str(r["dist"]))
        if not b or not h["sec"]:
            return None
        g = {"良": 0, "稍重": 1, "重": 2}.get(r["ground"], 3)
        return (b[0] + b[1][g] - h["sec"]) / r["dist"] * 1000 * 10

    def past(self, ri, hi, maxn=9):
        r = self.races[ri]
        arr = self.hist[r["rows"][hi]["horse"]]
        out = []
        for pri, phi in reversed(arr):
            if pri >= ri:
                continue
            pr = self.races[pri]
            ph = pr["rows"][phi]
            ti = pr["tidx"][phi] if phi < len(pr["tidx"]) else 0.0
            out.append({"r": pr, "h": ph, "pos": _fin(ph["fin"]),
                        "ago": _days(r["date"], pr["date"]),
                        "spd": self.spd(pr, ph),
                        "tidx": ti if ti > 0 else None,
                        "cor": _corners(ph["corner"])})
            if len(out) >= maxn:
                break
        return out

    @staticmethod
    def style(P):
        s = c = 0
        for p in P[:5]:
            if p["cor"]:
                s += p["cor"][0] / p["r"]["n"]
                c += 1
        if not c:
            return 1.5          # 過去の通過順が無い馬。展開乗数は欠測として扱う
        rr = s / c
        return 0 if rr < .16 else (1 if rr < .40 else (2 if rr < .68 else 3))


def _znorm(Z, n):
    """レース内で標準化する。点数は同一レース内でしか比べられない。"""
    for j in range(len(Z[0])):
        ok = [v[j] for v in Z if v[j] == v[j]]
        m = sum(ok) / len(ok) if ok else 0.0
        for v in Z:
            if v[j] != v[j]:
                v[j] = m
        mm = sum(v[j] for v in Z) / n
        sd = math.sqrt(sum((v[j] - mm) ** 2 for v in Z) / n) or 1.0
        for v in Z:
            v[j] = (v[j] - mm) / sd
    return Z


NAN = float("nan")


class Builder:
    """1レースぶんの Z ベクトルを作る。騎手・調教師は時系列で逐次更新する。"""

    def __init__(self, book, shrink_k=200, oikiri=None):
        self.b = book
        self.K = shrink_k
        self.jw = defaultdict(lambda: [0, 0])
        self.tw = defaultdict(lambda: [0, 0])
        self.gw = self.gn = 0
        # 調教: race_id -> {horse: 記録}。無ければ調教3成分は作らない。
        self.tr = {}
        if oikiri:
            for rid, rows in oikiri.items():
                self.tr[rid] = {x["horse"]: x for x in rows if x.get("horse")}
        self.use_train = bool(self.tr)
        self.names = BASE_NAMES + (TRAIN_NAMES if self.use_train else [])
        self.nf = len(self.names)

    # ── 逐次更新（そのレースを採点した後に呼ぶ）
    def advance(self, r):
        for h in r["rows"]:
            w = 1 if _fin(h["fin"]) == 1 else 0
            j = self.jw[h["jockey"]]; j[0] += w; j[1] += 1
            t = self.tw[h["trainer"]]; t[0] += w; t[1] += 1
            self.gw += w; self.gn += 1

    def build(self, ri):
        b = self.b
        r = b.races[ri]
        n, bd, rk = r["n"], band(r["dist"]), RANK[r["cls"]]
        P = [b.past(ri, hi) for hi in range(n)]
        ST = [Book.style(p) for p in P]
        front = sum(1 for s in ST if s <= 1) / n
        pace = 1 if front < .20 else (2 if front < .30 else
               (3 if front < .40 else (4 if front < .50 else 5)))
        kins = [h["kin"] for h in r["rows"] if h["kin"] > 0]
        km = sum(kins) / len(kins) if kins else 55.0
        ks = math.sqrt(sum((x - km) ** 2 for x in kins) / len(kins)) if kins else 1.0
        ks = ks or 1.0
        kmin = min(kins) if kins else 0
        bws = [h["bw"] for h in r["rows"] if h["bw"] > 0]
        bm = sum(bws) / len(bws) if bws else 480.0
        bs = math.sqrt(sum((x - bm) ** 2 for x in bws) / len(bws)) if bws else 30.0
        bs = bs or 30.0
        p0 = (self.gw / self.gn) if self.gn else 1 / 12

        Z = []
        for hi in range(n):
            h, p, st = r["rows"][hi], P[hi], ST[hi]
            v = [0.0] * self.nf
            dr = h["umaban"] / n

            # 1 TSI（自前の速度指数）
            b1 = b2 = any_ = None
            for q in p:
                if q["spd"] is None or q["r"]["surf"] != r["surf"]:
                    continue
                dd = abs(q["r"]["dist"] - r["dist"])
                if dd <= 200:
                    b1 = q["spd"] if b1 is None else max(b1, q["spd"])
                elif dd <= 400:
                    b2 = q["spd"] if b2 is None else max(b2, q["spd"])
            allspd = [q["spd"] for q in p if q["spd"] is not None]
            v[0] = (b1 if b1 is not None else
                    (b2 * .85 if b2 is not None else
                     (max(allspd) * .7 if allspd else NAN)))

            # 2 LTS（近走着順）
            best = None
            for i, q in enumerate(p):
                if q["pos"] is None:
                    continue
                sc = max(0.0, (q["r"]["n"] + 1 - q["pos"]) / q["r"]["n"]) * 10
                if q["r"]["surf"] == r["surf"] and band(q["r"]["dist"]) == bd:
                    sc *= 1.15
                if RANK[q["r"]["cls"]] >= rk:
                    sc *= 1.10
                sc *= 1.0 if i < 3 else (.85 if i < 6 else .7)
                best = sc if best is None else max(best, sc)
            v[1] = best if best is not None else NAN

            # 3 FSI（脚質×枠）
            v[2] = ((1 - dr) * 10 * (1.0 if st <= 1 else .6) if r["surf"] == "芝"
                    else (dr * 10 if st >= 2 else (1 - dr) * 10))

            # 4 Bonus（今回以上の格での勝ち鞍）
            w = sum(1 for q in p if q["pos"] == 1 and RANK[q["r"]["cls"]] >= rk)
            v[3] = 0.0 if w == 0 else (8.0 if w == 1 else 10.0)

            # 5 DSI（距離適性）
            near = lambda q: abs(q["r"]["dist"] - r["dist"])
            if any(near(q) <= 200 and q["pos"] and q["pos"] <= 5 for q in p[:3]):
                v[4] = 10.0
            elif any(q["ago"] <= 365 and near(q) <= 200 and q["pos"] and q["pos"] <= 5 for q in p):
                v[4] = 8.0
            elif any(near(q) <= 400 and q["pos"] and q["pos"] <= 5 for q in p):
                v[4] = 6.0

            # 6 NSI（格）
            a = bmax = -1
            for q in p:
                g = RANK[q["r"]["cls"]]
                bmax = max(bmax, g)
                if q["pos"] and q["pos"] <= 3:
                    a = max(a, g)
            v[5] = (a + 1) * 2.5 if a >= 0 else ((bmax + 1) * 1.2 if bmax >= 0 else NAN)

            # 7 CSI（位置取りの安定度）
            rs = [sum(q["cor"]) / len(q["cor"]) / q["r"]["n"] for q in p if q["cor"]]
            if rs:
                m = sum(rs) / len(rs)
                sd = math.sqrt(sum((x - m) ** 2 for x in rs) / len(rs))
                v[6] = (1 - m) * 6 + (1 - min(sd * 3, 1)) * 4
            else:
                v[6] = NAN

            # 8 WAS（斤量）
            v[7] = ((km - h["kin"]) / ks * 4 + (2 if h["kin"] == kmin else 0)
                    if h["kin"] > 0 else NAN)

            # 9 TAS（道悪適性）
            bad = [q for q in p if q["ago"] <= 365 and q["r"]["ground"] != "良" and q["pos"]]
            if bad:
                m = sum(q["pos"] / q["r"]["n"] for q in bad) / len(bad)
                v[8] = 10.0 if m < .30 else (5.0 if m < .55 else 0.0)
            else:
                v[8] = NAN

            last = p[0] if p else None
            # 10 HCS（斤量変化・格の変化）
            v[9] = (-(h["kin"] - last["h"]["kin"]) * 2
                    + (2 if RANK[last["r"]["cls"]] >= rk else -2)) if last else NAN
            # 11 NRJA（間隔）
            if last:
                d = last["ago"]
                v[10] = 6.0 if d < 14 else (10.0 if d < 28 else
                        (8.0 if d < 57 else (5.0 if d < 113 else 2.0)))
            else:
                v[10] = NAN
            # 12 展開乗数
            v[11] = float(PACE_TAB[pace - 1][st]) if isinstance(st, int) else NAN
            # 13 spd_res（4角からの詰め＋上がり）
            aa = [(q["cor"][-1] - (q["pos"] or q["r"]["n"])) / q["r"]["n"] * 10
                  for q in p if q["cor"]]
            ag = [q["h"]["agari"] for q in p if q["h"]["agari"] > 0]
            v[12] = ((sum(aa) / len(aa) if aa else 0.0)
                     + ((36.0 - sum(ag) / len(ag)) * 3 if ag else 0.0)) if (aa or ag) else NAN
            # 14 mgn_abs（勝ち馬とのタイム差）
            mg = []
            for q in p:
                win = next((x for x in q["r"]["rows"] if _fin(x["fin"]) == 1), None)
                if win and win["sec"] and q["h"]["sec"]:
                    mg.append(min(q["h"]["sec"] - win["sec"], 6.0))
            v[13] = sum(mg) / len(mg) if mg else NAN
            # 15 wide4c（3角→4角で外へ）
            aa = [(q["cor"][-1] - q["cor"][-2]) / q["r"]["n"] * 10 for q in p if len(q["cor"]) >= 3]
            v[14] = sum(aa) / len(aa) if aa else NAN
            # 16 pos_gain（1角→4角の押し上げ）
            aa = [(q["cor"][0] - q["cor"][-1]) / q["r"]["n"] * 10 for q in p if len(q["cor"]) >= 2]
            v[15] = sum(aa) / len(aa) if aa else NAN

            # 17 騎手 / 18 調教師（そのレースより前だけ・k=200で縮小）
            j, t = self.jw[h["jockey"]], self.tw[h["trainer"]]
            v[16] = ((j[0] + self.K * p0) / (j[1] + self.K) - p0) * 300
            v[17] = ((t[0] + self.K * p0) / (t[1] + self.K) - p0) * 300
            # 19 前走人気
            v[18] = 10 / math.sqrt(last["h"]["pop"]) if last and last["h"]["pop"] > 0 else NAN
            # 20 馬体重
            v[19] = (h["bw"] - bm) / bs * 3 if h["bw"] > 0 else NAN
            # 21 距離変化
            v[20] = -abs(r["dist"] - last["r"]["dist"]) / 200 if last else NAN
            # 22 齢
            v[21] = float(h["age"])
            # 23 公式指数（netkeiba のタイム指数）
            n1 = n2 = na = None
            for q in p:
                if q["tidx"] is None:
                    continue
                na = q["tidx"] if na is None else max(na, q["tidx"])
                if q["r"]["surf"] != r["surf"]:
                    continue
                dd = abs(q["r"]["dist"] - r["dist"])
                if dd <= 200:
                    n1 = q["tidx"] if n1 is None else max(n1, q["tidx"])
                elif dd <= 400:
                    n2 = q["tidx"] if n2 is None else max(n2, q["tidx"])
            v[22] = (n1 if n1 is not None else
                     (n2 - 2 if n2 is not None else
                      (na - 5 if na is not None else NAN)))
            if self.use_train:
                v[23], v[24], v[25] = self._train(ri, hi, h["horse"])
            Z.append(v)

        Z = _znorm(Z, n)
        order = [_fin(h["fin"]) for h in r["rows"]]
        return {"id": r["id"], "date": r["date"], "Z": Z, "ord": order,
                "pop": [h["pop"] for h in r["rows"]],
                "odds": [h["odds"] for h in r["rows"]],
                "umaban": [h["umaban"] for h in r["rows"]],
                "k": cell_keys(r), "n": n, "pace": pace}


def _best_lap(laps):
    """5本のラップのうち、いちばん長い区間の時計を代表値にする。"""
    return laps[0][0] if laps else None


def _add_train_methods():
    def _train(self, ri, hi, horse):
        """調教の3成分。過去の追い切りは、その馬が過去に走ったレースの分から拾う。"""
        r = self.b.races[ri]
        now = (self.tr.get(r["id"]) or {}).get(horse)
        if not now:
            return NAN, NAN, NAN
        kind = course_kind(now.get("course"))
        cur = _best_lap(now.get("laps") or [])
        hist = []
        for pri, phi in self.b.hist.get(horse, []):
            if pri >= ri:
                break
            prev = (self.tr.get(self.b.races[pri]["id"]) or {}).get(horse)
            if not prev:
                continue
            if course_kind(prev.get("course")) != kind:
                continue          # 坂路とウッドを混ぜない
            t = _best_lap(prev.get("laps") or [])
            if t:
                hist.append(t)
        # 縦断比較: 過去の自分より何秒速いか（速いほど＋）
        vert = (sum(hist) / len(hist) - cur) if (cur and hist) else NAN
        hon = float(now.get("hon") or 0) if now.get("hon") is not None else NAN
        ev = eval_score(now.get("eval"))
        return vert, hon, (float(ev) if ev is not None else NAN)
    Builder._train = _train


_add_train_methods()


def _ctx(r):
    """レース共通の条件。木の学習器がここで場合分けを覚える。"""
    return [float(r["n"]), float(r["dist"]),
            0.0 if r["surf"] == "芝" else 1.0,
            float({"良": 0, "稍重": 1, "重": 2}.get(r["ground"], 3)),
            float(RANK[r["cls"]]),
            float(PLACES.index(r["place"]) if r["place"] in PLACES else -1),
            0.0 if r["turn"] == "右" else (1.0 if r["turn"] == "左" else 2.0),
            1.0 if r["io"] == "外" else (2.0 if r["io"] == "内" else 0.0),
            float(int(r["id"][10:12])), float(int(r["date"][4:6]))]


class WideBuilder(Builder):
    """26成分に、条件10個と生の値14個（市場を使うならさらに4個）を足したもの。"""

    def __init__(self, book, shrink_k=200, oikiri=None, market=False):
        super().__init__(book, shrink_k, oikiri)
        self.market = market
        self.rec = defaultdict(lambda: {"n": 0, "w": 0, "c": defaultdict(lambda: [0, 0]), "s3": 0})
        self.wide_names = (self.names + CTX_NAMES + RAW_NAMES
                           + (MKT_NAMES if market else []))

    def advance(self, r):
        super().advance(r)
        cond = r["place"] + r["surf"] + band(r["dist"])
        for h in r["rows"]:
            st = self.rec[h["horse"]]
            pos = _fin(h["fin"])
            st["n"] += 1
            if pos == 1:
                st["w"] += 1
            c = st["c"][cond]
            c[1] += 1
            if pos is not None and pos <= 3:
                c[0] += 1
            st["s3"] = st["s3"] + 1 if (pos is not None and pos <= 3) else 0

    def build_wide(self, ri):
        d = self.build(ri)
        r = self.b.races[ri]
        n = r["n"]
        ctx = _ctx(r)
        cond = r["place"] + r["surf"] + band(r["dist"])
        odds = [h["odds"] if h["odds"] > 0 else 999.0 for h in r["rows"]]
        srt = sorted(range(n), key=lambda i: odds[i])
        orank = [0] * n
        for k, i in enumerate(srt):
            orank[i] = k + 1
        mn = min(odds)
        for i in range(n):
            h = r["rows"][i]
            P = self.b.past(ri, i, 9)
            last = P[0] if P else None
            st = self.rec.get(h["horse"]) or {"n": 0, "w": 0, "c": {}, "s3": 0}
            cr = (st["c"].get(cond) if isinstance(st["c"], dict) else None) or [0, 0]
            mg = NAN
            if last:
                win = next((x for x in last["r"]["rows"] if _fin(x["fin"]) == 1), None)
                if win and win["sec"] and last["h"]["sec"]:
                    mg = min(last["h"]["sec"] - win["sec"], 6.0)
            raw = [h["umaban"] / n, float(h["waku"]), h["kin"], float(h["age"]),
                   float(last["pos"]) if (last and last["pos"]) else NAN,
                   mg,
                   last["h"]["agari"] if (last and last["h"]["agari"] > 0) else NAN,
                   float(st["n"]), (st["w"] / st["n"]) if st["n"] else NAN,
                   (cr[0] / cr[1]) if cr[1] else NAN,
                   float(st["s3"]), 1.0 if st["n"] == 0 else 0.0,
                   float(last["r"]["n"]) if last else NAN,
                   float(last["ago"]) if last else NAN]
            d["Z"][i] = list(d["Z"][i]) + ctx + raw
            if self.market:
                d["Z"][i] += [math.log(1.0 / odds[i]), float(h["pop"] or 99),
                              float(orank[i]), odds[i] / mn]
        return d
