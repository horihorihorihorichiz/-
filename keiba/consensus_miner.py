# -*- coding: utf-8 -*-
"""consensus_miner.py — CONSENSUS_PROTOCOL.md（2026-08-18 事前登録）の実装。

「モデル1位 ∧ 前走タイム指数(tsi)1位が一致した合議レース」を、単勝だけでなく
複勝・馬連・ワイド・三連複まで広げて機械的に検証する。

事前登録（変更禁止・詳細は CONSENSUS_PROTOCOL.md）:
  合議定義 C1..C4 × {一致, 不一致}      = 8群
  券種 tan1/fuku1/uma12/wide12/trio123/trioM2/uma_mt/wide_mt = 8種（全て1点100円）
  条件 surface/dist/tier/field/o1/tb    = 6軸・結合は最大2条件 → 203セル
  MINE(202409-202602) n>=40 & ROI>=120% & 並べ替えp<0.05
   → VALIDATE(202603-202605) n>=15 & ROI>=105%
   → CONFIRM(202606-202608) n>=10 & ROI>=100%
  多重比較: VALIDATE通過数 < 3 ×（null通過数×0.05）なら全体不合格。

精算のランク空間エンコードと並べ替え検定は miner_v2.py と同一手続き
（settle_direct との全件一致を実行時に assert して担保）。

usage:
  python3 consensus_miner.py [--path wf_preds_v3ext2.jsonl] [--histdir hist] [--out .]
"""
import argparse
import itertools
import json
import os

import numpy as np

# ── 事前固定パラメータ ─────────────────────────────────────────────
MINE_START, MINE_END = "202409", "202602"
VAL_END, CONF_END = "202605", "202608"
MINE_N, MINE_ROI = 40, 120.0
VAL_N, VAL_ROI = 15, 105.0
CONF_N, CONF_ROI = 10, 100.0
NULL_B, NULL_P = 1000, 0.05
SEED = 20260817
MAX_COMBO = 2

STYLES = ["tan1", "fuku1", "uma12", "wide12", "trio123", "trioM2", "uma_mt", "wide_mt"]
STAKE = {s: 100.0 for s in STYLES}
TAKEOUT = {"tan1": 20.0, "fuku1": 20.0, "uma12": 22.5, "wide12": 22.5,
           "trio123": 25.0, "trioM2": 25.0, "uma_mt": 22.5, "wide_mt": 22.5}
SIGNALS = ["C1", "C2", "C3", "C4"]

# dead heat スロット（台帳実測の最大: 単勝2/複勝4/馬連2/ワイド5/三連複2）
NW, NF, NU, NWD, NT = 2, 4, 2, 6, 2


# ── 読み込み ───────────────────────────────────────────────────────
def tsi_of_race(histdir, rid):
    """前走tsi。{馬番: tsi}。有効(3頭以上)でなければ None"""
    fp = os.path.join(histdir, f"{rid}.json")
    try:
        d = json.load(open(fp, encoding="utf-8"))
    except Exception:
        return None
    out = {}
    for h in d["race"]["horses"]:
        rs = h.get("races") or []
        t = rs[0].get("tsi") if rs else None
        if t is None or t == "":
            continue
        try:
            out[int(h.get("num"))] = float(t)
        except Exception:
            continue
    return out if len(out) >= 3 else None


def load(path, histdir):
    R = []
    n_raw = n_month = n_tsi = 0
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        n_raw += 1
        m = d["month"]
        if m < MINE_START or m > CONF_END:
            continue
        n_month += 1
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        order = [int(x) for x in d["order"]]
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        if len(order) < 3:
            continue
        t1, t2, t3 = order[0], order[1], order[2]
        if t1 not in odds or t2 not in odds or t3 not in odds:
            continue
        by_odds = sorted(odds, key=lambda h: (odds[h], h))
        rank = {h: i + 1 for i, h in enumerate(by_odds)}
        partners = [h for h in by_odds if h != t1][:2]

        tsi = tsi_of_race(histdir, d["rid"])
        if tsi is None:
            continue
        n_tsi += 1
        tsi_order = sorted(tsi, key=lambda h: (-tsi[h], h))
        ts1 = tsi_order[0]
        top3_model = set(order[:3])
        top3_tsi = set(tsi_order[:3])
        sig = {
            "C1": (t1 == ts1),
            "C2": (len(top3_model & top3_tsi) >= 2),
            "C3": (t1 in top3_tsi),
            "C4": (t1 != ts1 and t2 == ts1),
        }
        sc_raw = d["scores"]
        sc = {n: float(v) for n, v in zip(order, sc_raw)} if isinstance(sc_raw, list) \
            else {int(k): float(v) for k, v in sc_raw.items()}

        w = [(rank[int(h)], float(v)) for h, v in pay["単勝"].items() if int(h) in rank]
        fuku = [(rank[int(h)], float(v)) for h, v in (pay.get("複勝") or {}).items()
                if int(h) in rank]
        uma = [(tuple(sorted(rank[int(x)] for x in k.split("-"))), float(v))
               for k, v in (pay.get("馬連") or {}).items()
               if all(int(x) in rank for x in k.split("-"))]
        wide = [(tuple(sorted(rank[int(x)] for x in k.split("-"))), float(v))
                for k, v in (pay.get("ワイド") or {}).items()
                if all(int(x) in rank for x in k.split("-"))]
        tri = [(tuple(sorted(rank[int(x)] for x in k.split("-"))), float(v))
               for k, v in (pay.get("三連複") or {}).items()
               if all(int(x) in rank for x in k.split("-"))]

        R.append(dict(
            rid=d["rid"], month=m,
            surface=d.get("surface"), dist=int(d.get("dist") or 0),
            field=int(d.get("field") or len(order)), tier=d.get("tier"),
            venue=d.get("venue"),
            o1=odds.get(t1),
            t1r=rank[t1], t2r=rank[t2], t3r=rank[t3],
            tsr=(rank[ts1] if ts1 in rank else -9),
            partners=[rank[h] for h in partners] if len(partners) == 2 else None,
            sig=sig, w=w, fuku=fuku, uma=uma, wide=wide, tri=tri,
            order=order, odds=odds, pay=pay, ts1=ts1, g12=(sc[t1] - sc[t2])))
    print(f"台帳{n_raw}行 → 窓内{n_month} → tsi有効{n_tsi} → 精算可 {len(R)}R")
    return R


def to_arrays(R):
    n = len(R)
    A = dict(
        t1r=np.full(n, -9, np.int32), t2r=np.full(n, -9, np.int32),
        t3r=np.full(n, -9, np.int32), tsr=np.full(n, -9, np.int32),
        P=np.full((n, 2), -9, np.int32),
        W=np.full((n, NW), -1, np.int32), WP=np.zeros((n, NW)),
        FR=np.full((n, NF), -1, np.int32), FP=np.zeros((n, NF)),
        UR=np.full((n, NU, 2), -1, np.int32), UP=np.zeros((n, NU)),
        DR=np.full((n, NWD, 2), -1, np.int32), DP=np.zeros((n, NWD)),
        TR=np.full((n, NT, 3), -1, np.int32), TP=np.zeros((n, NT)))
    for i, r in enumerate(R):
        A["t1r"][i], A["t2r"][i], A["t3r"][i] = r["t1r"], r["t2r"], r["t3r"]
        A["tsr"][i] = r["tsr"]
        if r["partners"]:
            A["P"][i] = r["partners"]
        for s, (rk, v) in enumerate(r["w"][:NW]):
            A["W"][i, s], A["WP"][i, s] = rk, v
        for s, (rk, v) in enumerate(r["fuku"][:NF]):
            A["FR"][i, s], A["FP"][i, s] = rk, v
        for s, (pr, v) in enumerate(r["uma"][:NU]):
            A["UR"][i, s], A["UP"][i, s] = pr, v
        for s, (pr, v) in enumerate(r["wide"][:NWD]):
            A["DR"][i, s], A["DP"][i, s] = pr, v
        for s, (tr, v) in enumerate(r["tri"][:NT]):
            A["TR"][i, s], A["TP"][i, s] = tr, v
    # 券種ごとの成立マスク（買えるレースだけを分母にする）
    ok = {}
    ok["tan1"] = np.ones(n, bool)
    ok["fuku1"] = np.ones(n, bool)
    ok["uma12"] = np.ones(n, bool)
    ok["wide12"] = np.ones(n, bool)
    ok["trio123"] = np.ones(n, bool)
    ok["trioM2"] = (A["P"][:, 0] > 0) & (A["P"][:, 1] > 0)
    diff = (A["tsr"] > 0) & (A["tsr"] != A["t1r"])
    ok["uma_mt"] = diff
    ok["wide_mt"] = diff
    A["ok"] = ok
    return A


def _pair_hit(a, b, PR, PP):
    """(..,) rank pair vs (..,n,slots,2)"""
    return (((a[..., None] == PR[..., 0]) & (b[..., None] == PR[..., 1])) * PP).sum(-1)


def returns_for(A, recip, donor, styles=STYLES):
    t1r, t2r, t3r, tsr = (A["t1r"][recip], A["t2r"][recip],
                          A["t3r"][recip], A["tsr"][recip])
    P = A["P"][recip]
    W, WP = A["W"][donor], A["WP"][donor]
    FR, FP = A["FR"][donor], A["FP"][donor]
    UR, UP = A["UR"][donor], A["UP"][donor]
    DR, DP = A["DR"][donor], A["DP"][donor]
    TR, TP = A["TR"][donor], A["TP"][donor]
    out = {}
    if "tan1" in styles:
        out["tan1"] = ((t1r[..., None] == W) * WP).sum(-1)
    if "fuku1" in styles:
        out["fuku1"] = ((t1r[..., None] == FR) * FP).sum(-1)
    a12, b12 = np.minimum(t1r, t2r), np.maximum(t1r, t2r)
    if "uma12" in styles:
        out["uma12"] = _pair_hit(a12, b12, UR, UP)
    if "wide12" in styles:
        out["wide12"] = _pair_hit(a12, b12, DR, DP)
    amt, bmt = np.minimum(t1r, tsr), np.maximum(t1r, tsr)
    if "uma_mt" in styles:
        out["uma_mt"] = _pair_hit(amt, bmt, UR, UP)
    if "wide_mt" in styles:
        out["wide_mt"] = _pair_hit(amt, bmt, DR, DP)
    if "trio123" in styles:
        trio = np.stack([t1r, t2r, t3r], -1)
        trio = np.sort(trio, axis=-1)
        hit = ((trio[..., None, :] == TR).all(-1)) * TP
        out["trio123"] = hit.sum(-1)
    if "trioM2" in styles:
        trio = np.sort(np.stack([t1r, P[..., 0], P[..., 1]], -1), axis=-1)
        hit = ((trio[..., None, :] == TR).all(-1)) * TP
        out["trioM2"] = hit.sum(-1)
    return out


def settle_direct(r):
    """馬番恒等での直接精算（ランク空間エンコードの検証用）"""
    o, pay = r["order"], r["pay"]
    g = lambda k, key: float((pay.get(k) or {}).get(key, 0))
    ret = {}
    ret["tan1"] = g("単勝", str(o[0]))
    ret["fuku1"] = g("複勝", str(o[0]))
    k12 = "-".join(str(x) for x in sorted(o[:2]))
    ret["uma12"] = g("馬連", k12)
    ret["wide12"] = g("ワイド", k12)
    ret["trio123"] = g("三連複", "-".join(str(x) for x in sorted(o[:3])))
    by_odds = sorted(r["odds"], key=lambda h: (r["odds"][h], h))
    mp = [h for h in by_odds if h != o[0]][:2]
    ret["trioM2"] = (g("三連複", "-".join(str(x) for x in sorted([o[0], *mp])))
                     if len(mp) == 2 else 0.0)
    ts1 = r["ts1"]
    if ts1 != o[0] and ts1 in r["odds"]:
        kmt = "-".join(str(x) for x in sorted([o[0], ts1]))
        ret["uma_mt"], ret["wide_mt"] = g("馬連", kmt), g("ワイド", kmt)
    else:
        ret["uma_mt"] = ret["wide_mt"] = 0.0
    return ret


# ── 条件軸（払戻を一切見ずに定義）───────────────────────────────────
def build_axes(R, mine_m, tb):
    n = len(R)
    arr = lambda f: np.array([f(r) for r in R])
    surface = arr(lambda r: r["surface"])
    dist = arr(lambda r: float(r["dist"]))
    field = arr(lambda r: float(r["field"]))
    tier = arr(lambda r: float(r["tier"] if r["tier"] is not None else -1))
    o1 = arr(lambda r: float(r["o1"]) if r["o1"] else np.nan)

    def bands(x, edges, labels):
        return [(lb, ~np.isnan(x) & (x >= lo) & (x < hi))
                for (lo, hi), lb in zip(edges, labels)]

    axes = {
        "surface": [("芝", surface == "芝"), ("ダ", surface == "ダ")],
        "dist": bands(dist, [(0, 1400), (1400, 1800), (1800, 2200), (2200, 9e9)],
                      ["短<1400", "ﾏｲﾙ1400-1799", "中1800-2199", "長2200+"]),
        "tier": bands(tier, [(0, 6), (6, 10), (10, 99)],
                      ["上級tier<=5", "1勝tier6-9", "未勝利tier>=10"]),
        "field": bands(field, [(0, 9), (9, 13), (13, 17), (17, 19)],
                       ["頭数<=8", "頭数9-12", "頭数13-16", "頭数17-18"]),
        "o1": bands(o1, [(0, 3), (3, 5), (5, 10), (10, 20), (20, 9e9)],
                    ["o1<3", "o1 3-5", "o1 5-10", "o1 10-20", "o1 20+"]),
    }
    # tb: 当日トラックバイアス(tb_front_surf) の MINE窓3分位
    x = np.array([v if v is not None else np.nan for v in tb], dtype=float)
    okx = ~np.isnan(x)
    vals = x[okx & mine_m]
    if len(vals) >= 100:
        q1, q2 = float(np.quantile(vals, 1 / 3)), float(np.quantile(vals, 2 / 3))
        axes["tb"] = [("tb先行不利", okx & (x < q1)),
                      ("tb中立", okx & (x >= q1) & (x < q2)),
                      ("tb先行有利", okx & (x >= q2))]
        print(f"tb_front_surf 3分位境界(MINE窓): {q1:.4f} / {q2:.4f}  有効={int(okx.sum())}R")
    else:
        print("tb: 有効データ不足 → 軸を使わない")
    return axes


def enumerate_cells(axes):
    names = list(axes)
    cells = [("(無条件)", (), np.ones(len(axes[names[0]][0][1]), bool))]
    for k in range(1, MAX_COMBO + 1):
        for combo in itertools.combinations(names, k):
            for picks in itertools.product(*[axes[a] for a in combo]):
                label = " & ".join(lb for lb, _ in picks)
                mask = picks[0][1].copy()
                for _, m in picks[1:]:
                    mask &= m
                cells.append((label, combo, mask))
    return cells


def null_test(A, idx, style, obs_ret, rng, B=NULL_B):
    n = len(idx)
    perms = rng.permuted(np.tile(np.arange(n), (B, 1)), axis=1)
    donor = idx[perms]
    chunk = max(1, int(2e6 // max(n, 1)))
    ge = 0
    for s in range(0, B, chunk):
        d = donor[s:s + chunk]
        ret = returns_for(A, idx, d, styles=[style])[style].sum(axis=1)
        ge += int((ret >= obs_ret - 1e-9).sum())
    return (1 + ge) / (B + 1)


def cell_stats(mask, split_m, obs, style):
    m = mask & split_m
    n = int(m.sum())
    if n == 0:
        return 0, 0.0, 0.0
    ret = float(obs[style][m].sum())
    return n, ret / (n * STAKE[style]) * 100.0, float((obs[style][m] > 0).mean()) * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="wf_preds_v3ext2.jsonl")
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    R = load(a.path, a.histdir)
    months = np.array([r["month"] for r in R])
    mine_m = (months >= MINE_START) & (months <= MINE_END)
    val_m = (months > MINE_END) & (months <= VAL_END)
    conf_m = (months > VAL_END) & (months <= CONF_END)
    print(f"races={len(R)} MINE={mine_m.sum()} VAL={val_m.sum()} CONF={conf_m.sum()}")

    A = to_arrays(R)
    ident = np.arange(len(R))
    obs = returns_for(A, ident, ident)
    for st in STYLES:                      # 成立しないレースは払戻0（分母からも外す）
        obs[st] = obs[st] * A["ok"][st]

    bad = 0
    for i, r in enumerate(R):
        d = settle_direct(r)
        for st in STYLES:
            if abs(d[st] * (1.0 if A["ok"][st][i] else 0.0) - float(obs[st][i])) > 1e-6:
                bad += 1
                if bad <= 5:
                    print("MISMATCH", r["rid"], st, d[st], float(obs[st][i]))
    print(f"encoding verification: mismatches={bad} / {len(R)*len(STYLES)}")
    assert bad == 0, "rank-space encoding mismatch — abort"

    # 当日トラックバイアス
    tb = [None] * len(R)
    try:
        import course_bias as CB
        idx = CB.index(a.histdir, verbose=False)
        for i, r in enumerate(R):
            ctx = idx.ctx.get(r["rid"])
            if ctx:
                tb[i] = ctx.get("tb_front_surf")
    except Exception as e:
        print("course_bias 読み込み失敗 → tb軸なし:", e)

    axes = build_axes(R, mine_m, tb)
    cells = enumerate_cells(axes)

    # 合議群マスク
    groups = {}
    for c in SIGNALS:
        v = np.array([bool(r["sig"][c]) for r in R])
        groups[f"{c}一致"] = v
        groups[f"{c}不一致"] = ~v
    print("セル数=%d  合議群=%d  券種=%d  → 総試行 %d"
          % (len(cells), len(groups), len(STYLES), len(cells) * len(groups) * len(STYLES)))
    for g, m in groups.items():
        print(f"  {g}: {int(m.sum())}R (MINE {int((m&mine_m).sum())})")

    rng = np.random.default_rng(SEED)
    n_trials = len(cells) * len(groups) * len(STYLES)
    evaluated = 0
    mine_pass = []
    # ── Stage1 ────────────────────────────────────────────────
    for gname, gmask in groups.items():
        for label, combo, cmask in cells:
            base = gmask & cmask
            for st in STYLES:
                m = base & A["ok"][st] & mine_m
                n = int(m.sum())
                if n == 0:
                    continue
                evaluated += 1
                if n < MINE_N:
                    continue
                roi = float(obs[st][m].sum()) / (n * STAKE[st]) * 100.0
                if roi >= MINE_ROI:
                    mine_pass.append(dict(
                        sig=gname, cell=label, axes=list(combo), style=st,
                        mine_n=n, mine_roi=round(roi, 1),
                        mine_hit=round(float((obs[st][m] > 0).mean()) * 100, 1),
                        _mask=base & A["ok"][st]))
    print(f"評価できた試行(n>=1)={evaluated} / 総試行{n_trials}")
    print(f"MINE基準通過(null検定前)={len(mine_pass)}")

    # ── Stage1b null ──────────────────────────────────────────
    null_pass = []
    for c in mine_pass:
        idxs = np.where(c["_mask"] & mine_m)[0]
        obs_ret = float(obs[c["style"]][idxs].sum())
        p = null_test(A, idxs, c["style"], obs_ret, rng)
        c["null_p"] = round(p, 4)
        if p < NULL_P:
            null_pass.append(c)
    print(f"null検定(p<{NULL_P})通過={len(null_pass)}")

    # ── Stage2/3 ──────────────────────────────────────────────
    val_pass = []
    for c in null_pass:
        n, roi, hit = cell_stats(c["_mask"], val_m, obs, c["style"])
        c["val_n"], c["val_roi"], c["val_hit"] = n, round(roi, 1), round(hit, 1)
        if n >= VAL_N and roi >= VAL_ROI:
            val_pass.append(c)
    print(f"VALIDATE通過={len(val_pass)}")

    conf_pass = []
    for c in val_pass:
        n, roi, hit = cell_stats(c["_mask"], conf_m, obs, c["style"])
        c["conf_n"], c["conf_roi"], c["conf_hit"] = n, round(roi, 1), round(hit, 1)
        vc = c["_mask"] & (val_m | conf_m)
        nn = int(vc.sum())
        c["vc_n"] = nn
        c["vc_roi"] = (round(float(obs[c["style"]][vc].sum()) / (nn * STAKE[c["style"]]) * 100, 1)
                       if nn else 0.0)
        if n >= CONF_N and roi >= CONF_ROI:
            conf_pass.append(c)
    print(f"CONFIRM通過={len(conf_pass)}")

    exp_null = len(mine_pass) * NULL_P
    exp_val = len(null_pass) * 0.05
    verdict = (len(val_pass) >= 3 * exp_val) and len(val_pass) > 0

    # ── 記述統計: 合議群 × 券種（無条件セル）────────────────────
    table = []
    for gname, gmask in groups.items():
        for st in STYLES:
            row = dict(sig=gname, style=st)
            for tag, sm in (("all", mine_m | val_m | conf_m), ("mine", mine_m),
                            ("val", val_m), ("conf", conf_m)):
                n, roi, hit = cell_stats(gmask & A["ok"][st], sm, obs, st)
                row[f"{tag}_n"], row[f"{tag}_roi"], row[f"{tag}_hit"] = n, round(roi, 1), round(hit, 1)
            table.append(row)

    # ── 記述統計: 条件別（C1一致/不一致 × 主要券種 × 単一条件セル）──
    cond_table = []
    single = [(lb, cb, mk) for lb, cb, mk in cells if len(cb) == 1]
    for gname in ("C1一致", "C1不一致", "C4一致"):
        gmask = groups[gname]
        for st in STYLES:
            for lb, cb, mk in single:
                m_all = gmask & mk & A["ok"][st]
                n, roi, hit = cell_stats(m_all, mine_m | val_m | conf_m, obs, st)
                if n == 0:
                    continue
                nm, rm, _ = cell_stats(m_all, mine_m, obs, st)
                nv, rv, _ = cell_stats(m_all, val_m, obs, st)
                nc, rc, _ = cell_stats(m_all, conf_m, obs, st)
                cond_table.append(dict(sig=gname, style=st, cond=lb, axis=cb[0],
                                       n=n, roi=round(roi, 1), hit=round(hit, 1),
                                       mine_n=nm, mine_roi=round(rm, 1),
                                       val_n=nv, val_roi=round(rv, 1),
                                       conf_n=nc, conf_roi=round(rc, 1)))

    summary = dict(
        data=a.path, n_races=len(R),
        splits=dict(MINE=int(mine_m.sum()), VALIDATE=int(val_m.sum()), CONFIRM=int(conf_m.sum())),
        n_cells=len(cells), n_groups=len(groups), n_styles=len(STYLES),
        n_trials=n_trials, n_evaluated=evaluated,
        mine_pass_pre_null=len(mine_pass), null_pass=len(null_pass),
        val_pass=len(val_pass), conf_pass=len(conf_pass),
        expected_null_pass_by_chance=round(exp_null, 1),
        expected_val_pass_by_chance=round(exp_val, 2),
        verdict_3x=("PASS" if verdict else "FAIL"),
        seed=SEED, null_B=NULL_B, takeout=TAKEOUT)
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    clean = lambda c: {k: v for k, v in c.items() if not k.startswith("_")}
    os.makedirs(a.out, exist_ok=True)
    fp = os.path.join(a.out, "consensus_result.json")
    json.dump(dict(summary=summary, base_table=table, cond_table=cond_table,
                   mine_pass=[clean(c) for c in mine_pass],
                   null_pass=[clean(c) for c in null_pass],
                   val_pass=[clean(c) for c in val_pass],
                   conf_pass=[clean(c) for c in conf_pass]),
              open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
