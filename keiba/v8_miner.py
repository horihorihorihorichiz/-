# -*- coding: utf-8 -*-
"""v8_miner.py — V8MINE_PROTOCOL_20260817.md の機械探索実装（第2次採掘）。

第1次(miner_v2.py)は旧特徴のみの13軸。今回は **V8の新特徴を「条件として切る」** ために
V8軸7本 + 前走tsi合議軸1本 を足した21軸グリッドを走らせる。

精算・null検定・3段関門は miner_v2.py の関数をそのまま import して使う
（＝第1次と1バイトも同じ精算ロジック。実装差による数字のズレを構造的に排除）。

段構成（事前登録・変更禁止）:
  1. MINE(202409-202602):     n>=40, ROI>=130%, null(レース間シャッフル×1000) p<0.05
  2. VALIDATE(202603-202605): n>=15, ROI>=110%   (MINE通過セルのみ・1回だけ)
  3. CONFIRM(202606-202608):  n>=10, ROI>=100%   (VALIDATE通過セルのみ・1回だけ)

結合は 1〜3条件のみ（4条件以上は事前登録で禁止）。seed=20260817固定。

実行（v8run/ から走らせる。cb_cache.pkl がV8評価時のスナップショットと一致するため）:
  cd keiba/v8run && python3 v8_miner.py --path wf_preds_v8all.jsonl --out <dir>
"""
import argparse
import itertools
import json
import os
import sys
import time

import numpy as np

import miner_v2 as M
import course_bias as CB

# ── 事前固定パラメータ（V8MINE_PROTOCOL_20260817.md）────────────────────
MINE_START = "202409"       # 第1次と窓を揃える。202403-202408 は全段で除外
MINE_END = "202602"
VAL_END = "202605"
CONF_END = "202608"
MINE_N, MINE_ROI = 40, 130.0
VAL_N, VAL_ROI = 15, 110.0
CONF_N, CONF_ROI = 10, 100.0
NULL_B, NULL_P = 1000, 0.05
SEED = 20260817
MAX_COMBO = 3
PREV_TRIALS = 58690         # 第1次の総試行数
PREV_VAL_PASS = 12          # 第1次のVALIDATE通過数
PREV_NULL_PASS = 175        # 第1次のnull検定通過数（偶然期待の分母）

V8_AXES = ["tb_waku_surf", "tb_front_surf", "tb_upset",
           "cp_waku", "cp_front", "cp_fav", "f2_wide_max"]
STYLES = M.STYLES
STAKE = M.STAKE


# ── V8特徴・tsiの抽出 ──────────────────────────────────────────────────
def attach_v8(R, histdir, cache_path):
    """各レースに V8軸7本 + tsi合議 を付ける。全て as-of 済み（V8_IMPL_NOTES §3）。"""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            cache = {}
    idx = CB.index(histdir, verbose=True)
    miss_ctx = miss_tsi = 0
    for r in R:
        rid = r["rid"]
        c = cache.get(rid)
        if c is None:
            ctx = idx.ctx.get(rid)
            f2 = idx.f2_of(rid)
            top = r["order"][0]
            c = {}
            if ctx:
                for k in ("tb_waku_surf", "tb_front_surf", "tb_upset",
                          "cp_waku", "cp_front", "cp_fav"):
                    c[k] = ctx.get(k)
            c["f2_wide_max"] = (f2.get(top) or {}).get("f2_wide_max")
            # tsi合議: 前走tsi最大の馬 vs モデル1位
            c["tsi_agree"] = None
            fp = os.path.join(histdir, f"{rid}.json")
            try:
                d = json.load(open(fp, encoding="utf-8"))
                best, bn, cnt = None, None, 0
                for h in d["race"]["horses"]:
                    rs = h.get("races") or []
                    t = rs[0].get("tsi") if rs else None
                    if t is None or t == "":
                        continue
                    t = float(t)
                    cnt += 1
                    if best is None or t > best:
                        best, bn = t, h.get("num")
                if cnt >= 3 and bn is not None:
                    c["tsi_agree"] = bool(int(bn) == int(top))
            except Exception:
                pass
            cache[rid] = c
        if c.get("tb_upset") is None and c.get("cp_waku") is None:
            miss_ctx += 1
        if c.get("tsi_agree") is None:
            miss_tsi += 1
        r.update(c)
    if cache_path:
        try:
            json.dump(cache, open(cache_path, "w", encoding="utf-8"))
        except Exception:
            pass
    print(f"V8特徴付与: {len(R)}R  ctx欠損={miss_ctx}  tsi不可(3頭未満/欠損)={miss_tsi}")


# ── 軸定義 ────────────────────────────────────────────────────────────
def build_axes(R, mine_m):
    """従来7軸 + V8軸7本(MINE窓3分位) + シグナル7軸。バンド境界は払戻を一切見ずに決める。"""
    axes = M.build_axes(R)          # 従来7 + シグナル6（第1次と完全同一のバンド）
    cuts = {}
    for name in V8_AXES:
        x = np.array([r.get(name) if r.get(name) is not None else np.nan
                      for r in R], dtype=float)
        ok = ~np.isnan(x)
        vals = x[ok & mine_m]
        if len(vals) < 100:
            cuts[name] = None
            continue
        q1, q2 = float(np.quantile(vals, 1 / 3)), float(np.quantile(vals, 2 / 3))
        cuts[name] = (q1, q2)
        axes[name] = [
            (f"{name}低", ok & (x < q1)),
            (f"{name}中", ok & (x >= q1) & (x < q2)),
            (f"{name}高", ok & (x >= q2)),
        ]
    tsi = np.array([1 if r.get("tsi_agree") is True else
                    (0 if r.get("tsi_agree") is False else -1) for r in R])
    axes["tsi"] = [("tsi一致", tsi == 1), ("tsi不一致", tsi == 0)]
    return axes, cuts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="wf_preds_v8all.jsonl")
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--out", default=".")
    ap.add_argument("--cache", default="v8mine_feats.json")
    a = ap.parse_args()
    t0 = time.time()

    R = M.load(a.path)
    print(f"loaded {len(R)}R from {a.path}")
    R = [r for r in R if MINE_START <= r["month"] <= CONF_END]
    print(f"窓フィルタ後({MINE_START}-{CONF_END}): {len(R)}R")

    attach_v8(R, a.histdir, a.cache)

    months = np.array([r["month"] for r in R])
    mine_m = months <= MINE_END
    val_m = (months > MINE_END) & (months <= VAL_END)
    conf_m = (months > VAL_END) & (months <= CONF_END)
    print(f"MINE={mine_m.sum()} VAL={val_m.sum()} CONF={conf_m.sum()}")

    A = M.to_arrays(R)
    ident = np.arange(len(R))
    obs = M.returns_for(A, ident, ident)

    # 精算エンコード検証（第1次と同じ・ランク空間 == 馬番直接）
    bad = 0
    for i, r in enumerate(R):
        d = M.settle_direct(r)
        for st in STYLES:
            if abs(d[st] - float(obs[st][i])) > 1e-6:
                bad += 1
    print(f"encoding verification: mismatches={bad} / {len(R)*len(STYLES)}")
    assert bad == 0, "rank-space encoding mismatch — abort"

    OBS = np.vstack([obs[st] for st in STYLES])            # (5, N)
    STK = np.array([STAKE[st] for st in STYLES])

    axes, cuts = build_axes(R, mine_m)
    names = list(axes)
    print(f"軸数={len(names)} バンド総数={sum(len(v) for v in axes.values())}")
    for k, v in cuts.items():
        if v:
            print(f"  3分位境界 {k}: {v[0]:+.6f} / {v[1]:+.6f}")
        else:
            print(f"  3分位境界 {k}: 標本不足で軸を採用せず")

    # ── Stage 1: MINE（1〜3条件の全結合を逐次生成。マスクは通過分のみ保持）──
    mine_pass = []
    n_cells = 0
    is_v8 = set(V8_AXES)

    def eval_cell(label, combo, mask):
        nonlocal n_cells
        n_cells += 1
        mm = mask & mine_m
        n = int(mm.sum())
        if n < MINE_N:
            return
        rets = OBS[:, mm].sum(1)
        rois = rets / (n * STK) * 100.0
        for si, st in enumerate(STYLES):
            if rois[si] >= MINE_ROI:
                hit = float((OBS[si][mm] > 0).mean())
                mine_pass.append(dict(
                    cell=label, axes=list(combo), style=st,
                    v8=bool(is_v8 & set(combo)),
                    mine_n=n, mine_roi=round(float(rois[si]), 1),
                    mine_hit=round(hit * 100, 1), _mask=mask))

    for ai in range(len(names)):
        for la, ma in axes[names[ai]]:
            eval_cell(la, (names[ai],), ma)
            for aj in range(ai + 1, len(names)):
                for lb, mb in axes[names[aj]]:
                    mab = ma & mb
                    eval_cell(f"{la} & {lb}", (names[ai], names[aj]), mab)
                    for ak in range(aj + 1, len(names)):
                        for lc, mc in axes[names[ak]]:
                            eval_cell(f"{la} & {lb} & {lc}",
                                      (names[ai], names[aj], names[ak]), mab & mc)
    n_trials = n_cells * len(STYLES)
    print(f"cells={n_cells} × styles={len(STYLES)} → trials={n_trials}  "
          f"({time.time()-t0:.0f}s)")
    print(f"MINE基準通過(null検定前): {len(mine_pass)}")

    # ── Stage 1b: null検定 ────────────────────────────────────────
    rng = np.random.default_rng(SEED)
    null_pass = []
    for i, c in enumerate(mine_pass):
        idx = np.where(c["_mask"] & mine_m)[0]
        obs_ret = float(obs[c["style"]][idx].sum())
        p = M.null_test(A, idx, c["style"], obs_ret, rng, B=NULL_B)
        c["null_p"] = round(p, 4)
        if p < NULL_P:
            null_pass.append(c)
        if (i + 1) % 200 == 0:
            print(f"  null {i+1}/{len(mine_pass)} ({time.time()-t0:.0f}s)",
                  flush=True)
    print(f"null検定(p<{NULL_P})通過: {len(null_pass)}")

    # ── Stage 2/3 ────────────────────────────────────────────────
    val_pass, conf_pass = [], []
    for c in null_pass:
        n, roi, hit = M.stats_for(c["_mask"], val_m, obs, c["style"])
        c["val_n"], c["val_roi"], c["val_hit"] = n, round(roi, 1), round(hit * 100, 1)
        if n >= VAL_N and roi >= VAL_ROI:
            val_pass.append(c)
    print(f"VALIDATE通過: {len(val_pass)}")
    for c in val_pass:
        n, roi, hit = M.stats_for(c["_mask"], conf_m, obs, c["style"])
        c["conf_n"], c["conf_roi"], c["conf_hit"] = n, round(roi, 1), round(hit * 100, 1)
        vc = c["_mask"] & (val_m | conf_m)
        nn = int(vc.sum())
        c["vc_n"] = nn
        c["vc_roi"] = round(float(obs[c["style"]][vc].sum()) /
                            (nn * STAKE[c["style"]]) * 100, 1) if nn else 0.0
        if n >= CONF_N and roi >= CONF_ROI:
            conf_pass.append(c)
    print(f"CONFIRM通過: {len(conf_pass)}")

    # ── 多重比較（事前登録 第4条 (a)合算 / (b)単独）────────────────
    exp_val_solo = len(null_pass) * 0.05
    exp_val_comb = (len(null_pass) + PREV_NULL_PASS) * 0.05
    solo_ok = len(val_pass) > 0 and len(val_pass) >= 3 * exp_val_solo
    comb_ok = (len(val_pass) + PREV_VAL_PASS) >= 3 * exp_val_comb
    summary = dict(
        data=a.path, n_races=len(R),
        window=f"{MINE_START}-{CONF_END}",
        splits=dict(MINE=int(mine_m.sum()), VALIDATE=int(val_m.sum()),
                    CONFIRM=int(conf_m.sum())),
        axes=len(names), n_cells=n_cells, n_styles=len(STYLES), n_trials=n_trials,
        v8_tertile_cuts={k: (None if v is None else [round(v[0], 6), round(v[1], 6)])
                         for k, v in cuts.items()},
        mine_pass_pre_null=len(mine_pass), null_pass=len(null_pass),
        val_pass=len(val_pass), conf_pass=len(conf_pass),
        mine_pass_v8=sum(1 for c in mine_pass if c["v8"]),
        null_pass_v8=sum(1 for c in null_pass if c["v8"]),
        val_pass_v8=sum(1 for c in val_pass if c["v8"]),
        conf_pass_v8=sum(1 for c in conf_pass if c["v8"]),
        expected_val_pass_solo=round(exp_val_solo, 2),
        expected_val_pass_combined=round(exp_val_comb, 2),
        prev_trials=PREV_TRIALS, prev_val_pass=PREV_VAL_PASS,
        combined_trials=PREV_TRIALS + n_trials,
        combined_val_pass=len(val_pass) + PREV_VAL_PASS,
        rule_3x_solo=("PASS" if solo_ok else "FAIL"),
        rule_3x_combined=("PASS" if comb_ok else "FAIL"),
        verdict=("PASS" if (solo_ok and comb_ok) else "FAIL"),
        seed=SEED, null_B=NULL_B, elapsed_s=round(time.time() - t0, 1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    def clean(c):
        return {k: v for k, v in c.items() if not k.startswith("_")}

    os.makedirs(a.out, exist_ok=True)
    op = os.path.join(a.out, "v8_miner_result.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(dict(summary=summary,
                       mine_pass=[clean(c) for c in mine_pass],
                       null_pass=[clean(c) for c in null_pass],
                       val_pass=[clean(c) for c in val_pass],
                       conf_pass=[clean(c) for c in conf_pass]),
                  f, ensure_ascii=False, indent=1)
    print("saved:", op)


if __name__ == "__main__":
    main()
