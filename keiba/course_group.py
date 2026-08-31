# -*- coding: utf-8 -*-
"""course_group.py — COURSE_GROUP_PROTOCOL.md の実装（事前登録どおり・実行後の基準変更禁止）。

問い:「個別コース(120種)は少なすぎ、汎用(全部込み)は粗すぎる。
      物理特性でコースを類型化した中間の粒度なら市場を超えられるか」

前回(course_system.py / COURSE_REPORT.md)の失敗2点を潰す:
  ① コース単位 → **物理特性グループ**(G1 8 / G2 24 / G3 72 まで)
  ② 月次3ヶ月窓  → **レース数ベース 70/15/15 の時系列分割**(開催日境界にスナップ)

比較する3本:
  GEN  汎用（基準・course_preds_gen.jsonl を再利用。再学習しない）
  GP   グループ専用      … m より前の当該グループだけで学習
  GH   汎用+グループ補正 … 当該グループ + 特徴に GEN の OOS スコア(薄いモデル)

目的変数は PLACE(3着内=1) と WIN(1着=1) の両方。
既存経路は1行も変更していない（course_cache / fit_place / place_eval / fit_v2 は読むだけ）。

usage:
  python3 course_group.py groups          # 類型化の確認（グループ一覧と台帳レース数）
  python3 course_group.py run g1          # G1 の GP/GH を 30fold × 2目的 で学習
  python3 course_group.py run g2
  python3 course_group.py run g3
  python3 course_group.py eval            # 一次/二次/診断 -> course_group_result.json
  python3 course_group.py ev              # 三次(実オッズEV買い) -> course_group_ev.json
  python3 course_group.py datasize        # 学習レース数 vs Δα
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import course_cache as CC
import fit_place as FP
import place_eval as PE

# ══════════════════════════════════════════════════════════════════════
# 1. コース類型（物理的事実・COURSE_GROUP_PROTOCOL §1-1 と1バイトも同じ）
#    出典 = JRA公式コース紹介の各競馬場コース図・公表直線距離
# ══════════════════════════════════════════════════════════════════════

# 軸C: 最後の直線の長さ(m)。キー = (場, 馬場, 内外)。内外は芝のみ意味を持つ。
STRAIGHT_M = {
    ("東京", "芝", "内"): 525.9, ("東京", "芝", "外"): 525.9, ("東京", "ダ", "内"): 501.6,
    ("中山", "芝", "内"): 310.0, ("中山", "芝", "外"): 310.0, ("中山", "ダ", "内"): 308.0,
    ("阪神", "芝", "内"): 356.5, ("阪神", "芝", "外"): 473.6, ("阪神", "ダ", "内"): 352.7,
    ("京都", "芝", "内"): 328.4, ("京都", "芝", "外"): 403.7, ("京都", "ダ", "内"): 329.1,
    ("中京", "芝", "内"): 412.5, ("中京", "芝", "外"): 412.5, ("中京", "ダ", "内"): 410.7,
    ("新潟", "芝", "内"): 358.7, ("新潟", "芝", "外"): 658.7, ("新潟", "ダ", "内"): 353.9,
    ("福島", "芝", "内"): 292.0, ("福島", "芝", "外"): 292.0, ("福島", "ダ", "内"): 295.7,
    ("小倉", "芝", "内"): 293.0, ("小倉", "芝", "外"): 293.0, ("小倉", "ダ", "内"): 291.3,
    ("札幌", "芝", "内"): 266.1, ("札幌", "芝", "外"): 266.1, ("札幌", "ダ", "内"): 264.3,
    ("函館", "芝", "内"): 262.1, ("函館", "芝", "外"): 262.1, ("函館", "ダ", "内"): 260.2,
}

# しきい値は実測値の自然な空隙に置く（310.0→328.4 の間 / 412.5→473.6 の間）
STRAIGHT_CUT = (320.0, 450.0)

# 軸D: ゴール前直線の勾配
SLOPE = {"中山": "急坂", "阪神": "急坂",
         "東京": "緩坂", "中京": "緩坂",
         "京都": "平坦", "新潟": "平坦", "小倉": "平坦",
         "札幌": "平坦", "函館": "平坦", "福島": "平坦"}

# 軸E: 回り（記録のみ・G1〜G3 では使わない）
TURN = {"中山": "右", "阪神": "右", "京都": "右", "福島": "右", "小倉": "右",
        "札幌": "右", "函館": "右", "東京": "左", "中京": "左", "新潟": "左"}

# 軸F: 1周距離(m)（記録のみ・G1〜G3 では使わない）。大回り = 1周 >= 1900m
LAP_M = {("東京", "芝"): 2083.1, ("東京", "ダ"): 1899.0,
         ("新潟", "芝外"): 2223.0, ("新潟", "芝内"): 1623.0, ("新潟", "ダ"): 1472.0,
         ("阪神", "芝外"): 2089.0, ("阪神", "芝内"): 1689.0, ("阪神", "ダ"): 1517.6,
         ("京都", "芝外"): 1894.3, ("京都", "芝内"): 1782.8, ("京都", "ダ"): 1607.6,
         ("中山", "芝外"): 1839.7, ("中山", "芝内"): 1667.1, ("中山", "ダ"): 1493.0,
         ("中京", "芝"): 1705.9, ("中京", "ダ"): 1530.0,
         ("福島", "芝"): 1600.0, ("福島", "ダ"): 1444.6,
         ("小倉", "芝"): 1615.1, ("小倉", "ダ"): 1445.4,
         ("札幌", "芝"): 1640.9, ("札幌", "ダ"): 1487.0,
         ("函館", "芝"): 1626.6, ("函館", "ダ"): 1475.8}

# 芝の外回り距離集合 = course.py::_JRA_SHIBA_OUTER をそのまま流用（既存情報の再利用）
import course as CRS


def io_of(venue, surface, dist):
    """芝の内外。台帳に内外表記が無いため _JRA_SHIBA_OUTER の集合判定で機械的に決める。"""
    if surface != "芝":
        return "内"
    return "外" if dist in CRS._JRA_SHIBA_OUTER.get(venue, set()) else "内"


def dist_band(d):
    if d < 1400:
        return "短"
    if d < 1800:
        return "マ"
    if d < 2200:
        return "中"
    return "長"


def straight_class(venue, surface, dist):
    # 特例: 新潟芝1000 は直線競走
    if venue == "新潟" and surface == "芝" and dist == 1000:
        return "LONG"
    m = STRAIGHT_M.get((venue, surface, io_of(venue, surface, dist)))
    if m is None:
        return None
    lo, hi = STRAIGHT_CUT
    return "SHORT" if m < lo else ("MID" if m < hi else "LONG")


def slope_class(venue, surface, dist):
    if venue == "新潟" and surface == "芝" and dist == 1000:
        return "平坦"
    return SLOPE.get(venue)


def group_of(venue, surface, dist, level):
    """level: 'g1' 馬場×距離帯 / 'g2' +直線長 / 'g3' +坂"""
    b = dist_band(dist)
    if level == "g1":
        return f"{surface}|{b}"
    st = straight_class(venue, surface, dist)
    if st is None:
        return None
    if level == "g2":
        return f"{surface}|{b}|{st}"
    sl = slope_class(venue, surface, dist)
    if sl is None:
        return None
    return f"{surface}|{b}|{st}|{sl}"


LEVELS = ["g1", "g2", "g3"]

# ══════════════════════════════════════════════════════════════════════
# 2. 事前登録の凍結パラメータ（COURSE_GROUP_PROTOCOL §1-3 / §2 / §4）
# ══════════════════════════════════════════════════════════════════════
START_FOLD = "202403"          # GEN の OOS 予測がある最初の fold月
MIN_GROUP_RACES = 100          # 台帳100R以上
MIN_TRAIN_RACES = 30           # これ未満なら学習せず GEN 流用
N_ROUND, ES = 800, 60
THIN = dict(num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10.0)
THIN_ROUND, THIN_ES = 300, 30
OBJS = ["place", "win"]
METHODS = ["GP", "GH"]

# 窓（レース数ベース 70/15/15・開催日境界スナップ・実行前に確定）
SPLIT_D1, SPLIT_D2 = "20251227", "20260426"
VAL_MIN_N, CONF_MIN_N = 15, 10
ROI_TH = 95.0                  # 二次: VAL/CONF とも単勝flat ROI >= 95%
MC_ITERS = 2000
EV_TH = 1.2                    # 三次: EV >= 1.2 の点だけ買う
EV_MIN_BETS = 50
EV_ROI_TH = 100.0
ODDS_DIR = "hist_odds"


def split_of_date(d):
    if d < SPLIT_D1:
        return "MINE"
    if d < SPLIT_D2:
        return "VALIDATE"
    return "CONFIRM"


def preds_path(level):
    return f"course_group_preds_{level}.jsonl"


# ══════════════════════════════════════════════════════════════════════
# 3. データ
# ══════════════════════════════════════════════════════════════════════
class Data:
    def __init__(self):
        X, yw, yp, ridx, meta = CC.load()
        self.X, self.ridx, self.meta = X, ridx, meta
        self.y = {"win": yw, "place": yp}
        self.month = np.array([m["month"] for m in meta])
        self.date = np.array([m["date"] for m in meta])
        self.grp = {}
        for lv in LEVELS:
            self.grp[lv] = np.array([group_of(m["venue"], m["surface"], m["dist"], lv) or ""
                                     for m in meta])
        self.rowslice = []
        start = 0
        for i in range(len(meta)):
            end = start
            while end < len(ridx) and ridx[end] == i:
                end += 1
            self.rowslice.append((start, end))
            start = end

    def counts(self, lv):
        c = defaultdict(int)
        for g in self.grp[lv]:
            if g:
                c[g] += 1
        return dict(c)

    def targets(self, lv):
        c = self.counts(lv)
        return sorted([g for g, v in c.items() if v >= MIN_GROUP_RACES], key=lambda g: -c[g])

    def rows_of(self, race_idx):
        out = []
        for i in race_idx:
            s, e = self.rowslice[i]
            out.append(np.arange(s, e))
        return np.concatenate(out) if len(out) else np.zeros(0, dtype=int)


def train_model(D, obj, race_idx, extra_col=None, thin=False):
    """race_idx（時系列順）で1本学習。検証分割は末尾10%・最低10レース（前回と同一規則）。"""
    n_val = max(10, len(race_idx) // 10)
    tr_r, va_r = race_idx[:-n_val], race_idx[-n_val:]
    if len(tr_r) < 1:
        return None
    itr, iva = D.rows_of(tr_r), D.rows_of(va_r)
    Xtr, Xva = D.X[itr], D.X[iva]
    if extra_col is not None:
        Xtr = np.hstack([Xtr, extra_col[itr][:, None]]).astype(np.float32)
        Xva = np.hstack([Xva, extra_col[iva][:, None]]).astype(np.float32)
    p = dict(FP.BIN_PARAMS)
    nr, es = N_ROUND, ES
    if thin:
        p.update(THIN)
        nr, es = THIN_ROUND, THIN_ES
    d1 = lgb.Dataset(Xtr, label=D.y[obj][itr], params=p)
    d2 = lgb.Dataset(Xva, label=D.y[obj][iva], reference=d1, params=p)
    return lgb.train(p, d1, num_boost_round=nr, valid_sets=[d2],
                     callbacks=[lgb.early_stopping(es, verbose=False)])


def predict_rows(model, D, race_idx, extra_col=None):
    rows = D.rows_of(race_idx)
    Xp = D.X[rows]
    if extra_col is not None:
        Xp = np.hstack([Xp, extra_col[rows][:, None]]).astype(np.float32)
    return model.predict(Xp)


def load_gen():
    """GEN の OOS スコア {(obj, rid): {馬番: score}}（前回生成をそのまま再利用）"""
    g = {}
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        g[(d["obj"], d["rid"])] = dict(zip(d["ns"], d["scores"]))
    return g


# ══════════════════════════════════════════════════════════════════════
# 4. 学習・予測
# ══════════════════════════════════════════════════════════════════════
def run_level(level):
    D = Data()
    gen = load_gen()
    tg = D.targets(level)
    folds = sorted({m for m in set(D.month) if m >= START_FOLD})
    print(f"[{level}] groups={len(tg)} folds={len(folds)} ({folds[0]}..{folds[-1]})", flush=True)
    for g in tg:
        print(f"   {g}: {D.counts(level)[g]}R", flush=True)

    gcol = {}
    for obj in OBJS:
        col = np.full(len(D.X), np.nan, dtype=np.float32)
        for i, m in enumerate(D.meta):
            gs = gen.get((obj, m["rid"]))
            if gs is None:
                continue
            s, e = D.rowslice[i]
            for j, n in enumerate(m["ns"]):
                col[s + j] = gs[n]
        gcol[obj] = col
    has_gen = np.array([(("place", m["rid"]) in gen) for m in D.meta])

    fh = open(preds_path(level), "w", encoding="utf-8")
    t0 = time.time()
    fb = defaultdict(int)
    ntrain = 0
    G = D.grp[level]
    for m in folds:
        for g in tg:
            fo = np.where((D.month == m) & (G == g))[0]
            if not len(fo):
                continue
            tr_gp = np.where((D.month < m) & (G == g))[0]
            tr_gh = np.where((D.month < m) & (G == g) & has_gen)[0]
            for obj in OBJS:
                for meth, tr, ex, thin in (("GP", tr_gp, None, False),
                                           ("GH", tr_gh, gcol[obj], True)):
                    mod = train_model(D, obj, tr, extra_col=ex, thin=thin) \
                        if len(tr) >= MIN_TRAIN_RACES else None
                    if mod is not None:
                        pr = predict_rows(mod, D, fo, extra_col=ex)
                        used = True
                        ntrain += 1
                    else:
                        pr = np.concatenate([[gen[(obj, D.meta[i]["rid"])][n]
                                              for n in D.meta[i]["ns"]] for i in fo])
                        used = False
                        fb[(meth, obj)] += len(fo)
                    pos = 0
                    for i in fo:
                        s, e = D.rowslice[i]
                        k = e - s
                        mr = D.meta[i]
                        fh.write(json.dumps(dict(
                            rid=mr["rid"], date=mr["date"], month=mr["month"], obj=obj,
                            method=meth, level=level, group=g, ns=mr["ns"],
                            train_races=int(len(tr)), spec_used=used,
                            scores=[round(float(x), 6) for x in pr[pos:pos + k]]),
                            ensure_ascii=False) + "\n")
                        pos += k
        fh.flush()
        print(f"  [{m}] done trainings={ntrain} ({time.time()-t0:.0f}s)", flush=True)
    fh.close()
    print(f"[{level}] done trainings={ntrain} fallback_races={dict(fb)} "
          f"({(time.time()-t0)/60:.1f}min)")


# ══════════════════════════════════════════════════════════════════════
# 5. 評価（一次・二次・診断）
# ══════════════════════════════════════════════════════════════════════
def race_meta():
    _, _, _, _, meta = CC.load()
    return {m["rid"]: m for m in meta}


def prep_race(mrec, ns, scores, obj):
    odds = np.array([mrec["odds"].get(n, 0.0) for n in ns], dtype=float)
    if np.any(odds <= 0):
        return None
    s = np.array(scores, dtype=float)
    if obj == "place":
        q_model = PE.norm_place(s)
        _, q_market = PE.market_probs(odds)
        y = np.array([1.0 if n in mrec["top3"] else 0.0 for n in ns])
    else:
        p = np.clip(s, 1e-9, None)
        q_model = p / p.sum()
        pw = 1.0 / odds
        q_market = pw / pw.sum()
        y = np.array([1.0 if n == mrec["top3"][0] else 0.0 for n in ns])
    return dict(q_model=q_model, q_market=q_market, y=y, odds=odds, ns=ns)


def alpha_of(rs):
    if len(rs) < 3:
        return None
    X = np.concatenate([np.stack([PE._logit(r["q_model"]), PE._logit(r["q_market"]),
                                  np.ones(len(r["ns"]))], axis=1) for r in rs])
    y = np.concatenate([r["y"] for r in rs])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(rs)])
    th = PE.fit_logit(X, y)
    se = PE.cluster_se(X, y, g, th)
    return float(th[0]), float(se[0])


def roi_of(rs, metas, kind="単勝"):
    n = pay = hit = 0
    for r, mrec in zip(rs, metas):
        h = r["ns"][int(np.argmax(r["q_model"]))]
        n += 1
        p = (mrec["payout"].get(kind) or {}).get(str(h), 0)
        pay += p
        hit += 1 if p else 0
    return (n, round(pay / (100 * n) * 100, 1) if n else None,
            round(hit / n * 100, 1) if n else None)


def binom_sf(k, n, p=0.5):
    """P(X >= k) （両側でなく片側上側）。"""
    from math import comb
    return float(sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def mc_null(rs_v, mv, rs_c, mc, rng):
    """情報ゼロ(一様ランダム1頭)が VAL>=95% かつ CONF>=95% を同時達成する確率"""
    def draws(rs_, ms_):
        pays, ks = [], []
        for r, mrec in zip(rs_, ms_):
            p = np.array([(mrec["payout"].get("単勝") or {}).get(str(h), 0)
                          for h in r["ns"]], dtype=float)
            pays.append(p)
            ks.append(len(p))
        return pays, ks
    pv, kv = draws(rs_v, mv)
    pc, kc = draws(rs_c, mc)
    if not pv or not pc:
        return None
    ok = 0
    for _ in range(MC_ITERS):
        rv = sum(p[rng.integers(k)] for p, k in zip(pv, kv)) / (100 * len(pv)) * 100
        rc = sum(p[rng.integers(k)] for p, k in zip(pc, kc)) / (100 * len(pc)) * 100
        ok += int(rv >= ROI_TH and rc >= ROI_TH)
    return ok / MC_ITERS


def evaluate():
    t0 = time.time()
    RM = race_meta()
    # GEN を rid 単位で
    gen = {}
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        pr = prep_race(RM[d["rid"]], d["ns"], d["scores"], d["obj"])
        if pr is not None:
            gen[(d["obj"], d["rid"])] = pr
    print(f"GEN loaded {len(gen)} (obj,rid) ({time.time()-t0:.0f}s)", flush=True)

    res, agree, dbg = {}, defaultdict(lambda: [0, 0]), {}
    rng = np.random.default_rng(20260818)
    mc_cache = {}

    for level in LEVELS:
        path = preds_path(level)
        if not os.path.exists(path):
            print(f"!! {path} が無い（未実行）")
            continue
        # (obj, meth, group) -> {rid: prep}
        store = defaultdict(dict)
        info = defaultdict(lambda: dict(spec=0, n=0))
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            pr = prep_race(RM[d["rid"]], d["ns"], d["scores"], d["obj"])
            if pr is None:
                continue
            key = (d["obj"], d["method"], d["group"])
            store[key][d["rid"]] = pr
            info[key]["n"] += 1
            info[key]["spec"] += int(d["spec_used"])
            if d["spec_used"]:
                g0 = gen.get((d["obj"], d["rid"]))
                if g0 is not None:
                    a = agree[(level, d["method"], d["obj"])]
                    a[1] += 1
                    a[0] += int(d["ns"][int(np.argmax(pr["q_model"]))]
                                == d["ns"][int(np.argmax(g0["q_model"]))])
        groups = sorted({k[2] for k in store})
        print(f"[{level}] {len(groups)} groups loaded ({time.time()-t0:.0f}s)", flush=True)

        for g in groups:
            for obj in OBJS:
                for meth in METHODS:
                    key = (obj, meth, g)
                    if key not in store:
                        continue
                    rows = store[key]
                    rec = dict(level=level, group=g, obj=obj, method=meth,
                               spec_used_races=info[key]["spec"], n_pred=info[key]["n"])
                    W = {}
                    for spn in ("MINE", "VALIDATE", "CONFIRM"):
                        rids = [r for r in rows
                                if split_of_date(RM[r]["date"]) == spn and (obj, r) in gen]
                        if not rids:
                            W[spn] = dict(n=0)
                            continue
                        rs = [rows[r] for r in rids]
                        gs = [gen[(obj, r)] for r in rids]
                        ms = [RM[r] for r in rids]
                        am, ag = alpha_of(rs), alpha_of(gs)
                        n, roi, hit = roi_of(rs, ms, "単勝")
                        _, roig, hitg = roi_of(gs, ms, "単勝")
                        _, froi, _ = roi_of(rs, ms, "複勝")
                        _, froig, _ = roi_of(gs, ms, "複勝")
                        w = dict(n=n, roi=roi, hit=hit, roi_gen=roig, hit_gen=hitg,
                                 froi=froi, froi_gen=froig)
                        if am and ag:
                            w.update(alpha=round(am[0], 4), se=round(am[1], 4),
                                     alpha_gen=round(ag[0], 4), se_gen=round(ag[1], 4),
                                     d_alpha=round(am[0] - ag[0], 4))
                        W[spn] = w
                    rec["windows"] = W
                    V, C = W.get("VALIDATE", {}), W.get("CONFIRM", {})
                    rec["judgeable"] = bool(V.get("n", 0) >= VAL_MIN_N
                                            and C.get("n", 0) >= CONF_MIN_N)
                    rec["primary"] = bool(rec["judgeable"] and V.get("d_alpha") is not None
                                          and V["d_alpha"] > 0)
                    rec["secondary"] = bool(rec["judgeable"] and V.get("roi") is not None
                                            and C.get("roi") is not None
                                            and V["roi"] >= ROI_TH and C["roi"] >= ROI_TH)
                    rec["pass"] = bool(rec["primary"] and rec["secondary"])
                    res[f"{level}|{obj}|{meth}|{g}"] = rec

                # 偶然期待（二次）: グループ×目的で1回だけ MC
                ck = (level, obj, g)
                if ck not in mc_cache:
                    src = None
                    for meth in METHODS:
                        if (obj, meth, g) in store:
                            src = store[(obj, meth, g)]
                            break
                    p_g = None
                    if src:
                        vr = [r for r in src if split_of_date(RM[r]["date"]) == "VALIDATE"]
                        cr = [r for r in src if split_of_date(RM[r]["date"]) == "CONFIRM"]
                        if len(vr) >= VAL_MIN_N and len(cr) >= CONF_MIN_N:
                            p_g = mc_null([src[r] for r in vr], [RM[r] for r in vr],
                                          [src[r] for r in cr], [RM[r] for r in cr], rng)
                    mc_cache[ck] = p_g

    # ── 集計 ────────────────────────────────────────────────────
    summary = {}
    for level in LEVELS:
        for meth in METHODS:
            for obj in OBJS:
                ks = [k for k, v in res.items()
                      if v["level"] == level and v["method"] == meth and v["obj"] == obj
                      and v["judgeable"]]
                G = len(ks)
                if not G:
                    continue
                kprim = sum(1 for k in ks if res[k]["primary"])
                kconf = sum(1 for k in ks
                            if (res[k]["windows"].get("CONFIRM", {}).get("d_alpha") or 0) > 0)
                ksec = sum(1 for k in ks if res[k]["secondary"])
                kpass = sum(1 for k in ks if res[k]["pass"])
                exp_sec = sum(mc_cache.get((level, obj, res[k]["group"])) or 0.0 for k in ks)
                summary[f"{level}|{meth}|{obj}"] = dict(
                    n_groups=G, k_primary=kprim, exp_primary=G * 0.5,
                    p_binom=round(binom_sf(kprim, G), 5),
                    primary_sig=bool(binom_sf(kprim, G) < 0.05),
                    k_confirm_dalpha=kconf,
                    k_secondary=ksec, exp_secondary=round(exp_sec, 3),
                    k_pass=kpass, exp_pass=round(exp_sec * 0.5, 3),
                    agree_top1=(round(agree[(level, meth, obj)][0]
                                      / max(agree[(level, meth, obj)][1], 1) * 100, 1),
                                agree[(level, meth, obj)][1]))
    tot_trials = sum(v["n_groups"] for v in summary.values())
    tot_pass = sum(v["k_pass"] for v in summary.values())
    tot_exp = sum(v["exp_pass"] for v in summary.values())
    overall = dict(trials=tot_trials, passed=tot_pass, expect=round(tot_exp, 3),
                   verdict="PASS" if tot_pass >= 3 * max(tot_exp, 1e-9) and tot_pass else "FAIL")
    json.dump(dict(result=res, summary=summary, overall=overall,
                   mc={f"{a}|{b}|{c}": v for (a, b, c), v in mc_cache.items()}),
              open("course_group_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)

    print("\n=== 水準×方式×目的 サマリー ===")
    hd = ("key", "G", "一次k", "期待", "p", "有意", "CONF Δα>0", "二次k", "二次期待",
          "総合", "1位一致%")
    print("%-20s%4s%6s%6s%8s%6s%10s%7s%9s%6s%9s" % hd)
    for k, v in summary.items():
        print("%-20s%4d%6d%6.1f%8.4f%6s%10d%7d%9.2f%6d%9.1f"
              % (k, v["n_groups"], v["k_primary"], v["exp_primary"], v["p_binom"],
                 "○" if v["primary_sig"] else "×", v["k_confirm_dalpha"],
                 v["k_secondary"], v["exp_secondary"], v["k_pass"], v["agree_top1"][0]))
    print("\n総合: 試行 %d / 通過 %d / 偶然期待 %.3f -> %s"
          % (tot_trials, tot_pass, tot_exp, overall["verdict"]))
    print(f"saved course_group_result.json ({(time.time()-t0)/60:.1f}min)")


# ══════════════════════════════════════════════════════════════════════
# 6. 三次: 実オッズ EV 買い（複勝・ワイド・三連複）
# ══════════════════════════════════════════════════════════════════════
def _key(k):
    return tuple(sorted(int(x) for x in k.replace("→", "-").split("-")))


def ev_bets(mrec, ns, scores):
    """1レース分: モデル3着内確率 → PL → 複勝/ワイド/三連複の (EV, 払戻) を返す"""
    ns = list(ns)
    n = len(ns)
    ro_p = os.path.join(ODDS_DIR, f"{mrec['rid']}.json")
    if not os.path.exists(ro_p):
        return None
    try:
        ro = json.load(open(ro_p, encoding="utf-8"))
    except Exception:
        return None
    fk = ro.get("fuku") or {}
    if any(str(h) not in fk or not fk[str(h)] for h in ns):
        return None
    q = PE.norm_place(np.array(scores, dtype=float))
    w = FP.pl_from_place(q)
    pay = mrec["payout"] or {}
    out = []
    # 複勝（8頭以上=3着まで / 5〜7頭=2着まで）
    k = 3 if n >= 8 else 2
    pq = q if k == 3 else FP.harville_place(w, 2)
    pf = pay.get("複勝") or {}
    for i, h in enumerate(ns):
        o = float(fk[str(h)])
        out.append(("fuku", pq[i] * o, float(pf.get(str(h), 0))))
    if n >= 4:
        tri, pt = FP.trio_probs(w)
        ow = ro.get("wide") or {}
        ot = ro.get("sanrenpuku") or {}
        pw_pay = {_key(a): float(b) for a, b in (pay.get("ワイド") or {}).items()}
        pt_pay = {_key(a): float(b) for a, b in (pay.get("三連複") or {}).items()}
        arr = np.array(ns)
        for t, p in zip(tri, pt):
            kk = "-".join(str(int(x)) for x in sorted(arr[t]))
            o = ot.get(kk)
            if o:
                out.append(("trio", p * float(o), pt_pay.get(_key(kk), 0.0)))
        W = FP.wide_probs(tri, pt, n)
        for i in range(n):
            for j in range(i + 1, n):
                kk = "-".join(str(x) for x in sorted((int(ns[i]), int(ns[j]))))
                o = ow.get(kk)
                if o:
                    out.append(("wide", (W[i, j] + W[j, i]) * float(o),
                                pw_pay.get(_key(kk), 0.0)))
    return out


def run_ev():
    t0 = time.time()
    RM = race_meta()
    # GEN 側も同じ集合で
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0]))   # key -> kind -> [n, pay, hit]
    gen_scores = {}
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if d["obj"] == "place":
            gen_scores[d["rid"]] = (d["ns"], d["scores"])

    def add(key, rid, ns, scores):
        b = ev_bets(RM[rid], ns, scores)
        if b is None:
            return
        spn = split_of_date(RM[rid]["date"])
        for kind, ev, p in b:
            if ev >= EV_TH:
                a = acc[(key, spn)][kind]
                a[0] += 1
                a[1] += p
                a[2] += int(p > 0)

    done_gen = set()
    for level in LEVELS:
        path = preds_path(level)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            if d["obj"] != "place":
                continue
            add((level, d["method"], d["group"]), d["rid"], d["ns"], d["scores"])
            gk = ("GEN", level, d["group"])
            if (gk, d["rid"]) not in done_gen:
                done_gen.add((gk, d["rid"]))
                gs = gen_scores.get(d["rid"])
                if gs:
                    add(gk, d["rid"], gs[0], gs[1])
        print(f"[{level}] ev done ({time.time()-t0:.0f}s)", flush=True)

    out = {}
    for (key, spn), kinds in acc.items():
        for kind, (n, pay, hit) in kinds.items():
            out.setdefault("|".join(str(x) for x in key) + "|" + kind, {})[spn] = dict(
                n=n, roi=round(pay / (100 * n) * 100, 1) if n else None,
                hit=round(hit / n * 100, 1) if n else None)
    # 通過判定
    passed = []
    for k, v in out.items():
        V, C = v.get("VALIDATE") or {}, v.get("CONFIRM") or {}
        if (V.get("n", 0) >= EV_MIN_BETS and C.get("n", 0) >= EV_MIN_BETS
                and (V.get("roi") or 0) >= EV_ROI_TH and (C.get("roi") or 0) >= EV_ROI_TH):
            passed.append(k)
    json.dump(dict(table=out, passed=passed), open("course_group_ev.json", "w",
                                                   encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(f"\n三次(EV>={EV_TH}) 通過 {len(passed)} 件 / 全 {len(out)} 系列")
    for k in passed:
        print("  ", k, out[k])
    print(f"saved course_group_ev.json ({(time.time()-t0)/60:.1f}min)")


# ══════════════════════════════════════════════════════════════════════
# 7. 診断: 学習レース数 と Δα
# ══════════════════════════════════════════════════════════════════════
def datasize():
    RM = race_meta()
    gen = {}
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        pr = prep_race(RM[d["rid"]], d["ns"], d["scores"], d["obj"])
        if pr is not None:
            gen[(d["obj"], d["rid"])] = pr
    BINS = [(30, 100), (100, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 10 ** 9)]
    out = {}
    for level in LEVELS:
        path = preds_path(level)
        if not os.path.exists(path):
            continue
        for meth in METHODS:
            for obj in OBJS:
                acc = defaultdict(lambda: dict(rs=[], gs=[], ms=[]))
                for line in open(path, encoding="utf-8"):
                    d = json.loads(line)
                    if d["obj"] != obj or d["method"] != meth or not d["spec_used"]:
                        continue
                    pr = prep_race(RM[d["rid"]], d["ns"], d["scores"], obj)
                    g0 = gen.get((obj, d["rid"]))
                    if pr is None or g0 is None:
                        continue
                    for lo, hi in BINS:
                        if lo <= d["train_races"] < hi:
                            b = acc[(lo, hi)]
                            b["rs"].append(pr); b["gs"].append(g0); b["ms"].append(RM[d["rid"]])
                            break
                row = {}
                for (lo, hi), b in sorted(acc.items()):
                    if len(b["rs"]) < 50:
                        row[f"{lo}-{hi}"] = dict(n=len(b["rs"]))
                        continue
                    am, ag = alpha_of(b["rs"]), alpha_of(b["gs"])
                    n, roi, hit = roi_of(b["rs"], b["ms"], "単勝")
                    _, roig, _ = roi_of(b["gs"], b["ms"], "単勝")
                    row[f"{lo}-{hi}"] = dict(n=n, alpha=round(am[0], 4),
                                             alpha_gen=round(ag[0], 4),
                                             d_alpha=round(am[0] - ag[0], 4),
                                             se=round(am[1], 4), roi=roi, roi_gen=roig)
                out[f"{level}|{meth}|{obj}"] = row
                print(f"\n=== {level} / {meth} / {obj} ===")
                print(f"{'train_races':<12}{'n':>7}{'Δα':>9}{'α専':>9}{'α汎':>9}{'SE':>8}"
                      f"{'単ROI専':>9}{'単ROI汎':>9}")
                for k, v in row.items():
                    if v.get("n", 0) < 50:
                        print(f"{k:<12}{v.get('n',0):>7}  (n<50 未推定)")
                        continue
                    print(f"{k:<12}{v['n']:>7}{v['d_alpha']:>9.4f}{v['alpha']:>9.4f}"
                          f"{v['alpha_gen']:>9.4f}{v['se']:>8.4f}{v['roi']:>9.1f}"
                          f"{v['roi_gen']:>9.1f}")
    json.dump(out, open("course_group_datasize.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print("\nsaved course_group_datasize.json")


def show_groups():
    D = Data()
    RM = D.meta
    for lv in LEVELS:
        c = D.counts(lv)
        tg = set(D.targets(lv))
        print(f"\n=== {lv} : 非空 {len(c)} グループ / 100R以上 {len(tg)} ===")
        # 窓別レース数（OOSプールのみ）
        wc = defaultdict(lambda: defaultdict(int))
        for i, m in enumerate(RM):
            if m["month"] < START_FOLD:
                continue
            g = D.grp[lv][i]
            if g:
                wc[g][split_of_date(m["date"])] += 1
        print(f"{'group':<22}{'台帳R':>7}{'MINE':>7}{'VAL':>6}{'CONF':>6}  判定")
        for g in sorted(c, key=lambda x: -c[x]):
            w = wc[g]
            jd = ("対象" if (c[g] >= MIN_GROUP_RACES and w["VALIDATE"] >= VAL_MIN_N
                             and w["CONFIRM"] >= CONF_MIN_N) else "対象外")
            print(f"{g:<22}{c[g]:>7}{w['MINE']:>7}{w['VALIDATE']:>6}{w['CONFIRM']:>6}  {jd}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if cmd == "run":
        run_level(sys.argv[2])
    else:
        {"groups": show_groups, "eval": evaluate, "ev": run_ev,
         "datasize": datasize}[cmd]()
