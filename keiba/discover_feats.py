# -*- coding: utf-8 -*-
"""DISCOVER: 過去走の生データから候補特徴を機械的に大量生成する（DISCOVER_PROTOCOL.md §2 の実装）。

既存ファイルは一切変更しない（本ファイルは新規・独立）。
- build_ds() : comps_v99.pkl のレース ∩ hist/*.json の過去9走 → 生テンソルを作り discover_ds.npz に保存
- iter_candidates() : 凍結した生成規則どおりに候補（レース内z化済み）を1本ずつ yield
"""
import glob, json, os, pickle, sys
import numpy as np

import v99w_fit as V

MAXH = V.MAXH
DS_PATH = "discover_ds.npz"

# ── 過去走1走の生の列（21本） ──
RAW = ["finish", "field", "umaban", "agari", "run_time", "margin", "dist",
       "days", "baba_idx", "vg", "tier", "pace_first", "pace_last",
       "cL", "cL1", "cL2", "cL3", "cfirst", "ncor", "dirt", "c_sd"]
RI = {k: i for i, k in enumerate(RAW)}

# ── 対象列30本（§2.1）: 名前 → 日本語の意味 ──
DCOLS = [
    ("fin",        "着順"),
    ("fin_rate",   "着順÷頭数(相対着順)"),
    ("uma_rate",   "馬番÷頭数(枠の内外)"),
    ("agari",      "上がり3F"),
    ("run_time",   "走破タイム"),
    ("spd",        "平均速度(距離÷走破タイム)"),
    ("margin",     "着差(秒・勝ち馬との差)"),
    ("mgn_abs",    "着差の絶対値"),
    ("pace_first", "前半3F"),
    ("pace_last",  "後半3F"),
    ("pace_diff",  "前半3F−後半3F(前傾ラップの度合い)"),
    ("agari_ratio", "上がり3F÷走破タイム(終いの比重)"),
    ("cL_rate",    "4角(最終角)通過順÷頭数"),
    ("cL1_rate",   "3角通過順÷頭数"),
    ("cL2_rate",   "2角通過順÷頭数"),
    ("cL3_rate",   "1角通過順÷頭数"),
    ("cfirst_rate", "最初の角の通過順÷頭数"),
    ("move_last",  "(3角−4角)÷頭数: 最後の角で上げた幅(正=上げた/負=外を回して下げた)"),
    ("move_all",   "(初角−4角)÷頭数: 道中トータルで押し上げた幅"),
    ("move_mid",   "(2角−3角)÷頭数: 中間で上げた幅"),
    ("c_sd_rate",  "通過順の標準偏差÷頭数(道中で動く度合い)"),
    ("unlucky",    "着順率−4角位置率(位置の割に負けた度合い)"),
    ("days",       "レース間隔(日)"),
    ("dist",       "距離"),
    ("tier",       "クラス(数字が小さいほど上級)"),
    ("baba_idx",   "馬場(0良1稍2重3不)"),
    ("field",      "頭数"),
    ("vg",         "コース格"),
    ("win",        "1着フラグ"),
    ("top3",       "3着内フラグ"),
]
DNAME = [c[0] for c in DCOLS]
DJA = dict(DCOLS)
NC = len(DCOLS)
NR = 9  # 過去走の最大数


# ══════════════════════════════ データ構築 ══════════════════════════════
def _raw_from_hist(rs):
    """過去走リスト → (NR, len(RAW)) の生行列（欠測 nan・新しい順）"""
    A = np.full((NR, len(RAW)), np.nan, dtype=np.float64)
    for i, r in enumerate(rs[:NR]):
        ca = r.get("corner_all") or []
        ca = [c for c in ca if c is not None]
        g = lambda k: (float(r[k]) if r.get(k) is not None else np.nan)
        A[i, RI["finish"]] = g("finish")
        A[i, RI["field"]] = g("field")
        A[i, RI["umaban"]] = g("umaban")
        A[i, RI["agari"]] = g("agari")
        A[i, RI["run_time"]] = g("run_time")
        A[i, RI["margin"]] = g("margin")
        A[i, RI["dist"]] = g("dist")
        A[i, RI["days"]] = g("days")
        A[i, RI["baba_idx"]] = g("baba_idx")
        A[i, RI["vg"]] = g("vg")
        A[i, RI["tier"]] = g("tier")
        A[i, RI["pace_first"]] = g("pace_first")
        A[i, RI["pace_last"]] = g("pace_last")
        A[i, RI["dirt"]] = 1.0 if r.get("surface") == "ダ" else 0.0
        A[i, RI["ncor"]] = len(ca)
        if len(ca) >= 1:
            A[i, RI["cL"]] = ca[-1]
            A[i, RI["cfirst"]] = ca[0]
        if len(ca) >= 2:
            A[i, RI["cL1"]] = ca[-2]
            A[i, RI["c_sd"]] = float(np.std(ca))
        if len(ca) >= 3:
            A[i, RI["cL2"]] = ca[-3]
        if len(ca) >= 4:
            A[i, RI["cL3"]] = ca[-4]
    return A


def build_ds(force=False):
    """discover_ds.npz を作る。既に有れば読むだけ。"""
    if os.path.exists(DS_PATH) and not force:
        return
    races = V.load_races()
    rid2 = {r["rid"]: r for r in races}
    rows_raw, rows_race, rows_num = [], [], []
    ctx = []          # (surface_dirt, dist, tier, baba_off) 当該レース
    keep = []
    stats = dict(days_le0=0, runs=0, files_missing=0)
    for ri, r in enumerate(races):
        f = f"hist/{r['rid']}.json"
        if not os.path.exists(f):
            stats["files_missing"] += 1
            continue
        d = json.load(open(f, encoding="utf-8"))
        rc = d["race"]
        hs = {h["num"]: h for h in rc["horses"]}
        baba_off = 0.0 if rc.get("baba") == "良" else 1.0
        ki = len(keep)
        keep.append(ri)
        ctx.append((1.0 if rc.get("surface") == "ダ" else 0.0,
                    float(rc.get("distance") or 0),
                    float(rc.get("today_tier") or 0), baba_off))
        for num in r["nums"]:
            h = hs.get(num)
            rs = (h.get("races") or []) if h else []
            for x in rs[:NR]:
                stats["runs"] += 1
                if x.get("days") is not None and x["days"] <= 0:
                    stats["days_le0"] += 1
            rows_raw.append(_raw_from_hist(rs))
            rows_race.append(ki)
            rows_num.append(num)
    A = np.array(rows_raw, dtype=np.float32)
    np.savez_compressed(
        DS_PATH,
        A=A, race_idx=np.array(rows_race, dtype=np.int32),
        num=np.array(rows_num, dtype=np.int32),
        keep=np.array(keep, dtype=np.int32),
        ctx=np.array(ctx, dtype=np.float32),
        stats=np.array([stats["days_le0"], stats["runs"],
                        stats["files_missing"]], dtype=np.int64))
    print(f"[build_ds] races={len(keep)} horses={len(rows_raw)} "
          f"runs={stats['runs']} days<=0={stats['days_le0']} "
          f"hist欠={stats['files_missing']}")


# ══════════════════════════════ 派生列 ══════════════════════════════
def derive(A):
    """(N, NR, len(RAW)) 生 → (N, NR, NC) 対象列30本"""
    N = A.shape[0]
    D = np.full((N, NR, NC), np.nan, dtype=np.float32)
    g = lambda k: A[:, :, RI[k]]
    fld = np.where(g("field") > 0, g("field"), np.nan)
    put = lambda name, v: D.__setitem__((slice(None), slice(None),
                                         DNAME.index(name)), v)
    fin = g("finish")
    put("fin", fin)
    put("fin_rate", fin / fld)
    put("uma_rate", g("umaban") / fld)
    put("agari", g("agari"))
    rt = np.where(g("run_time") > 0, g("run_time"), np.nan)
    put("run_time", rt)
    put("spd", g("dist") / rt)
    put("margin", g("margin"))
    put("mgn_abs", np.abs(g("margin")))
    put("pace_first", g("pace_first"))
    put("pace_last", g("pace_last"))
    put("pace_diff", g("pace_first") - g("pace_last"))
    put("agari_ratio", g("agari") / rt)
    put("cL_rate", g("cL") / fld)
    put("cL1_rate", g("cL1") / fld)
    put("cL2_rate", g("cL2") / fld)
    put("cL3_rate", g("cL3") / fld)
    put("cfirst_rate", g("cfirst") / fld)
    put("move_last", (g("cL1") - g("cL")) / fld)
    put("move_all", (g("cfirst") - g("cL")) / fld)
    put("move_mid", (g("cL2") - g("cL1")) / fld)
    put("c_sd_rate", g("c_sd") / fld)
    put("unlucky", fin / fld - g("cL") / fld)
    put("days", g("days"))
    put("dist", g("dist"))
    put("tier", g("tier"))
    put("baba_idx", g("baba_idx"))
    put("field", g("field"))
    put("vg", g("vg"))
    put("win", (fin == 1).astype(np.float32) + 0 * fin)
    put("top3", (fin <= 3).astype(np.float32) + 0 * fin)
    return D


# ══════════════════════════════ 集計 ══════════════════════════════
def _agg(Y, kind):
    """Y=(N,W) nan込み → (N,) 集計値（有効数不足は nan）"""
    m = ~np.isnan(Y)
    n = m.sum(1)
    out = np.full(Y.shape[0], np.nan, dtype=np.float64)
    if kind in ("mean", "median", "max", "min"):
        ok = n >= 1
    elif kind == "std":
        ok = n >= 2
    else:  # slope
        ok = n >= 2
    if not ok.any():
        return out
    with np.errstate(invalid="ignore"):
        if kind == "mean":
            s = np.nansum(np.where(m, Y, 0.0), 1)
            out[ok] = s[ok] / n[ok]
        elif kind == "median":
            Z = Y[ok]
            out[ok] = np.nanmedian(Z, 1)
        elif kind == "max":
            out[ok] = np.nanmax(np.where(m, Y, -np.inf), 1)[ok]
        elif kind == "min":
            out[ok] = np.nanmin(np.where(m, Y, np.inf), 1)[ok]
        elif kind == "std":
            Yf = np.where(m, Y, 0.0)
            s1 = Yf.sum(1)
            s2 = (Yf * Yf).sum(1)
            mu = np.where(n > 0, s1 / np.maximum(n, 1), 0.0)
            var = np.maximum(s2 / np.maximum(n, 1) - mu * mu, 0.0)
            out[ok] = np.sqrt(var)[ok]
        elif kind == "slope":
            W = Y.shape[1]
            X = -np.arange(W, dtype=np.float64)[None, :]  # 新しいほど大
            Xf = np.where(m, X, 0.0)
            Yf = np.where(m, Y, 0.0)
            nn = np.maximum(n, 1)
            sx = Xf.sum(1) / nn
            sy = Yf.sum(1) / nn
            cov = (Xf * Yf).sum(1) / nn - sx * sy
            var = (Xf * Xf).sum(1) / nn - sx * sx
            good = ok & (var > 1e-9)
            out[good] = cov[good] / var[good]
    return out


def _cond_mean(Y, CM):
    """条件マスク CM=(N,NR) の走のみで平均"""
    m = (~np.isnan(Y)) & CM
    n = m.sum(1)
    out = np.full(Y.shape[0], np.nan)
    ok = n >= 1
    s = np.where(m, np.nan_to_num(Y), 0.0).sum(1)
    out[ok] = s[ok] / n[ok]
    return out


# ══════════════════════════════ レース内標準化 ══════════════════════════════
class Grid:
    """行(馬)↔(R,MAXH) パディングの相互変換と、レース内z化。"""

    def __init__(self, race_idx, nR):
        self.race_idx = race_idx
        self.nR = nR
        order = np.argsort(race_idx, kind="stable")
        cnt = np.bincount(race_idx, minlength=nR)
        pos = np.concatenate([[0], np.cumsum(cnt)[:-1]])
        slot = np.arange(len(race_idx)) - pos[race_idx][np.argsort(order)] * 0
        # slot: レース内の並び順（元の順序を保つ）
        slot = np.zeros(len(race_idx), dtype=np.int64)
        c = np.zeros(nR, dtype=np.int64)
        for i, ri in enumerate(race_idx):
            slot[i] = c[ri]
            c[ri] += 1
        self.slot = slot
        self.cnt = cnt
        self.MASK = np.zeros((nR, MAXH), dtype=bool)
        self.MASK[race_idx, slot] = True
        self.LIN = np.full((nR, MAXH), -1, dtype=np.int64)
        self.LIN[race_idx, slot] = np.arange(len(race_idx))

    def pad(self, v):
        P = np.full((self.nR, MAXH), np.nan)
        P[self.race_idx, self.slot] = v
        return P

    def z(self, v, clip=3.0):
        """レース内z化 → (R,MAXH)。欠測=0。"""
        P = self.pad(v)
        m = ~np.isnan(P)
        n = m.sum(1)
        s = np.where(m, np.nan_to_num(P), 0.0).sum(1)
        mu = np.where(n > 0, s / np.maximum(n, 1), 0.0)
        d = np.where(m, P - mu[:, None], 0.0)
        sd = np.sqrt((d * d).sum(1) / np.maximum(n, 1))
        Z = np.where((sd > 1e-9)[:, None] & m, d / np.maximum(sd, 1e-9)[:, None], 0.0)
        return np.clip(Z, -clip, clip)

    def rankpct(self, v):
        """レース内順位パーセンタイル(0..1, 小さい値=0)。欠測は nan。"""
        P = self.pad(v)
        m = ~np.isnan(P)
        n = m.sum(1)
        big = np.where(m, P, np.inf)
        idx = np.argsort(big, axis=1, kind="stable")
        rank = np.empty_like(idx)
        np.put_along_axis(rank, idx, np.arange(MAXH)[None, :]
                          .repeat(self.nR, 0), axis=1)
        denom = np.maximum(n - 1, 1)[:, None]
        out = np.where(m, rank / denom, np.nan)
        out[n[:, None].repeat(MAXH, 1) <= 1] = np.nan
        return out[self.race_idx, self.slot]


# ══════════════════════════════ 候補生成 ══════════════════════════════
AGGS = ["mean", "median", "max", "min", "std", "slope"]
WINS = [3, 5, 9]
AGG_JA = dict(mean="平均", median="中央値", max="最大", min="最小",
              std="標準偏差", slope="傾き(新しい走ほど大)")


def cond_masks(D, ctx, race_idx):
    """§2.3 の4条件マスク (N, NR)"""
    dist_p = D[:, :, DNAME.index("dist")]
    tier_p = D[:, :, DNAME.index("tier")]
    baba_p = D[:, :, DNAME.index("baba_idx")]
    surf_p = np.full_like(dist_p, np.nan)
    return None  # 未使用（build側で raw を渡す）


def make_cond(A, ctx, race_idx):
    dist_p = A[:, :, RI["dist"]]
    tier_p = A[:, :, RI["tier"]]
    baba_p = A[:, :, RI["baba_idx"]]
    dirt_p = A[:, :, RI["dirt"]]
    c = ctx[race_idx]           # (N,4) = dirt, dist, tier, baba_off
    return {
        "sameSurf": dirt_p == c[:, 0:1],
        "sameDist": np.abs(dist_p - c[:, 1:2]) <= 200,
        "sameBaba": (baba_p > 0).astype(np.float32) == c[:, 3:4],
        "classGE": tier_p <= c[:, 2:3],
    }
COND_JA = dict(sameSurf="同じ芝ダのみ", sameDist="同じ距離帯(±200m)のみ",
               sameBaba="同じ馬場区分(良/道悪)のみ", classGE="今回以上のクラスのみ")


def iter_candidates(D, A, ctx, race_idx, grid):
    """(name, 日本語説明, coverage, Z(R,MAXH)) を1本ずつ返す。"""
    CM = make_cond(A, ctx, race_idx)
    for ci, cname in enumerate(DNAME):
        Y = D[:, :, ci].astype(np.float64)
        ja = DJA[cname]
        # last
        v = Y[:, 0]
        yield (f"{cname}|last", f"{ja} の直近1走の値", v, grid.z(v))
        for w in WINS:
            Yw = Y[:, :w]
            for ag in AGGS:
                v = _agg(Yw, ag)
                yield (f"{cname}|{ag}{w}",
                       f"{ja} の直近{w}走の{AGG_JA[ag]}", v, grid.z(v))
        # 条件付き平均（窓9）
        for k, M in CM.items():
            v = _cond_mean(Y, M)
            yield (f"{cname}|{k}Mean9",
                   f"{ja} の直近9走平均（{COND_JA[k]}）", v, grid.z(v))
        # 順位パーセンタイル型
        for tag, v in (("last", Y[:, 0]), ("mean3", _agg(Y[:, :3], "mean")),
                       ("mean5", _agg(Y[:, :5], "mean")),
                       ("mean9", _agg(Y[:, :9], "mean"))):
            rp = grid.rankpct(v)
            yield (f"{cname}|rank_{tag}",
                   f"{ja}({tag}) のレース内順位パーセンタイル", rp, grid.z(rp))
        # 差分
        m3, m9, m5 = _agg(Y[:, :3], "mean"), _agg(Y[:, :9], "mean"), _agg(Y[:, :5], "mean")
        v = m3 - m9
        yield (f"{cname}|trend3_9", f"{ja} の直近3走平均−直近9走平均(トレンド)", v, grid.z(v))
        v = Y[:, 0] - m5
        yield (f"{cname}|dev_last5", f"{ja} の直近1走−直近5走平均(直近の突出度)", v, grid.z(v))


def load_ds():
    build_ds()
    z = np.load(DS_PATH)
    return (z["A"], z["race_idx"], z["num"], z["keep"], z["ctx"], z["stats"])


if __name__ == "__main__":
    build_ds(force="--force" in sys.argv)
    A, race_idx, num, keep, ctx, st = load_ds()
    print("A", A.shape, "keep", keep.shape, "stats(days<=0, runs, missing)", st)
    D = derive(A)
    grid = Grid(race_idx, len(keep))
    n = 0
    for name, ja, v, Z in iter_candidates(D, A, ctx, race_idx, grid):
        n += 1
    print("候補総数(生成規則どおり):", n)
