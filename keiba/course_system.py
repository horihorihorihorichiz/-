# -*- coding: utf-8 -*-
"""course_system.py — COURSE_PROTOCOL.md の実装（事前登録どおり・実行後の基準変更禁止）。

問い:「コース単位（場×馬場×距離の具体値。例 東京芝2000m）の専用システムなら期待値プラスになるか」

比較する4本（3方式）:
  GEN   汎用（基準）             … m より前の全レース
  M1    方式1 素朴               … m より前の当該コースだけ
  M2    方式2 階層(残差/薄い追加) … 当該コース + 特徴に GEN の OOS スコア
  M3w3/M3w10 方式3 重み付け      … 全データ・当該コース行の sample_weight = 3 / 10

目的変数は PLACE(3着内=1) と WIN(1着=1) の両方。
既存経路は1行も変更していない（fit_place / place_eval / fit_v2 / wf_compare は読むだけ）。

usage:
  python3 course_cache.py               # 特徴行列キャッシュ（先に1回）
  python3 course_system.py gen          # GEN 30fold × 2目的      -> course_preds_gen.jsonl
  python3 course_system.py m12          # M1/M2 30fold × 28course -> course_preds_m1.jsonl / m2
  python3 course_system.py m3           # M3 6fold × 28course × w -> course_preds_m3.jsonl
  python3 course_system.py eval         # 判定 -> course_result.json（表は標準出力）
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

# ── 事前登録の凍結パラメータ ────────────────────────────────────────────
START_FOLD = "202403"
EVAL_FOLDS = ["202603", "202604", "202605", "202606", "202607", "202608"]
MIN_COURSE_RACES = 100      # 対象コース: 台帳100R以上
MIN_TRAIN_RACES = 30        # M1/M2: これ未満は学習せず GEN 流用
W_LIST = [3.0, 10.0]
N_ROUND = 800
ES = 60
THIN = dict(num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10.0)
THIN_ROUND, THIN_ES = 300, 30
OBJS = ["place", "win"]

VAL_MIN_N, CONF_MIN_N = 15, 10     # 判定対象の下限
ROI_VAL_TH, ROI_CONF_TH = 110.0, 100.0
MONTH_SUB_MIN = 10                 # 月次サブ判定に使う最低レース数
MC_ITERS = 2000


def course_of(m):
    return f"{m['venue']}{m['surface']}{m['dist']}"


# ── データ ─────────────────────────────────────────────────────────────
class Data:
    def __init__(self):
        X, yw, yp, ridx, meta = CC.load()
        self.X, self.ridx, self.meta = X, ridx, meta
        self.y = {"win": yw, "place": yp}
        self.month = np.array([m["month"] for m in meta])
        self.course = np.array([course_of(m) for m in meta])
        # レース i の行スライス（ridx は昇順に並んでいる）
        self.rowslice = []
        start = 0
        for i in range(len(meta)):
            end = start
            while end < len(ridx) and ridx[end] == i:
                end += 1
            self.rowslice.append((start, end))
            start = end
        cnt = defaultdict(int)
        for c in self.course:
            cnt[c] += 1
        self.course_cnt = dict(cnt)
        self.targets = sorted([c for c, v in cnt.items() if v >= MIN_COURSE_RACES],
                              key=lambda c: -cnt[c])

    def rows_of(self, race_idx):
        """レース番号の配列 -> 行インデックス配列"""
        out = []
        for i in race_idx:
            s, e = self.rowslice[i]
            out.append(np.arange(s, e))
        return np.concatenate(out) if out else np.zeros(0, dtype=int)


def train_generic(D, obj, race_idx, weight=None, extra_col=None, thin=False):
    """race_idx（学習に使うレース番号・時系列順）で1本学習。
       weight: 行ごとの重み / extra_col: 追加特徴（行数×1）"""
    # 検証分割（2026-08-18 実行前に修正・COURSE_PROTOCOL §2 追記）:
    # 「末尾10%・最低10レース」。当初案の「最低50レース」だと 100-300R しかない
    # コース内学習で学習データの半分を検証に取られ、方式1/2 が構造的に不利になる。
    n_val = max(10, len(race_idx) // 10)
    tr_r, va_r = race_idx[:-n_val], race_idx[-n_val:]
    if len(tr_r) < 1:
        return None
    itr, iva = D.rows_of(tr_r), D.rows_of(va_r)
    Xtr, Xva = D.X[itr], D.X[iva]
    if extra_col is not None:
        Xtr = np.hstack([Xtr, extra_col[itr][:, None]]).astype(np.float32)
        Xva = np.hstack([Xva, extra_col[iva][:, None]]).astype(np.float32)
    ytr, yva = D.y[obj][itr], D.y[obj][iva]
    p = dict(FP.BIN_PARAMS)
    nr, es = N_ROUND, ES
    if thin:
        p.update(THIN)
        nr, es = THIN_ROUND, THIN_ES
    wtr = weight[itr] if weight is not None else None
    wva = weight[iva] if weight is not None else None
    d1 = lgb.Dataset(Xtr, label=ytr, weight=wtr, params=p)
    d2 = lgb.Dataset(Xva, label=yva, weight=wva, reference=d1, params=p)
    return lgb.train(p, d1, num_boost_round=nr, valid_sets=[d2],
                     callbacks=[lgb.early_stopping(es, verbose=False)])


def predict_rows(model, D, race_idx, extra_col=None):
    rows = D.rows_of(race_idx)
    Xp = D.X[rows]
    if extra_col is not None:
        Xp = np.hstack([Xp, extra_col[rows][:, None]]).astype(np.float32)
    return rows, model.predict(Xp)


def dump(fh, D, obj, method, race_idx, rows, preds, meta_extra):
    """1fold分の予測を jsonl に書く（レース単位・馬番順は meta['ns'] のまま）"""
    pos = 0
    for i in race_idx:
        s, e = D.rowslice[i]
        k = e - s
        m = D.meta[i]
        rec = dict(rid=m["rid"], month=m["month"], obj=obj, method=method,
                   course=course_of(m), ns=m["ns"],
                   scores=[round(float(x), 6) for x in preds[pos:pos + k]])
        rec.update(meta_extra)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        pos += k


# ── GEN ────────────────────────────────────────────────────────────────
def run_gen():
    D = Data()
    folds = sorted({m for m in set(D.month) if m >= START_FOLD})
    print(f"GEN: {len(D.meta)}R / folds {folds[0]}..{folds[-1]} ({len(folds)})", flush=True)
    fh = open("course_preds_gen.jsonl", "w", encoding="utf-8")
    t0 = time.time()
    for m in folds:
        tr = np.where(D.month < m)[0]
        fo = np.where(D.month == m)[0]
        if len(tr) < 400 or not len(fo):
            print(f"[{m}] skip train={len(tr)}", flush=True)
            continue
        for obj in OBJS:
            model = train_generic(D, obj, tr)
            rows, pr = predict_rows(model, D, fo)
            dump(fh, D, obj, "GEN", fo, rows, pr, dict(train_races=int(len(tr)),
                                                       best_iter=int(model.best_iteration)))
        fh.flush()
        print(f"[{m}] {len(fo)}R train={len(tr)}R ({time.time()-t0:.0f}s)", flush=True)
    fh.close()
    print(f"GEN done ({(time.time()-t0)/60:.1f}min)")


def load_gen():
    """GEN の OOS スコアを {(obj, rid): {馬番: score}} で返す"""
    g = {}
    for line in open("course_preds_gen.jsonl", encoding="utf-8"):
        d = json.loads(line)
        g[(d["obj"], d["rid"])] = dict(zip(d["ns"], d["scores"]))
    return g


# ── M1 / M2 ────────────────────────────────────────────────────────────
def run_m12():
    D = Data()
    gen = load_gen()
    folds = sorted({m for m in set(D.month) if m >= START_FOLD})
    print(f"M1/M2: targets={len(D.targets)} folds={len(folds)}", flush=True)
    # GEN スコアを行ベクトル化（M2 の追加特徴。GEN 予測が無い行は NaN）
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

    f1 = open("course_preds_m1.jsonl", "w", encoding="utf-8")
    f2 = open("course_preds_m2.jsonl", "w", encoding="utf-8")
    t0 = time.time()
    fb = defaultdict(int)
    for m in folds:
        for c in D.targets:
            fo = np.where((D.month == m) & (D.course == c))[0]
            if not len(fo):
                continue
            tr1 = np.where((D.month < m) & (D.course == c))[0]
            tr2 = np.where((D.month < m) & (D.course == c) & has_gen)[0]
            for obj in OBJS:
                # ---- M1
                mod = (train_generic(D, obj, tr1)
                       if len(tr1) >= MIN_TRAIN_RACES else None)
                if mod is not None:
                    rows, pr = predict_rows(mod, D, fo)
                    used = True
                else:
                    pr = np.concatenate([[gen[(obj, D.meta[i]["rid"])][n]
                                          for n in D.meta[i]["ns"]] for i in fo])
                    used = False
                    fb[("M1", obj)] += len(fo)
                dump(f1, D, obj, "M1", fo, None, pr,
                     dict(train_races=int(len(tr1)), spec_used=used))
                # ---- M2
                mod = (train_generic(D, obj, tr2, extra_col=gcol[obj], thin=True)
                       if len(tr2) >= MIN_TRAIN_RACES else None)
                if mod is not None:
                    rows, pr = predict_rows(mod, D, fo, extra_col=gcol[obj])
                    used = True
                else:
                    pr = np.concatenate([[gen[(obj, D.meta[i]["rid"])][n]
                                          for n in D.meta[i]["ns"]] for i in fo])
                    used = False
                    fb[("M2", obj)] += len(fo)
                dump(f2, D, obj, "M2", fo, None, pr,
                     dict(train_races=int(len(tr2)), spec_used=used))
        f1.flush()
        f2.flush()
        print(f"[{m}] done ({time.time()-t0:.0f}s)", flush=True)
    f1.close()
    f2.close()
    print(f"M1/M2 done ({(time.time()-t0)/60:.1f}min) fallback rows={dict(fb)}")


# ── M3 ─────────────────────────────────────────────────────────────────
def run_m3():
    D = Data()
    print(f"M3: targets={len(D.targets)} folds={EVAL_FOLDS} weights={W_LIST}", flush=True)
    fh = open("course_preds_m3.jsonl", "w", encoding="utf-8")
    t0 = time.time()
    for m in EVAL_FOLDS:
        tr = np.where(D.month < m)[0]
        rows_tr = None
        for c in D.targets:
            fo = np.where((D.month == m) & (D.course == c))[0]
            if not len(fo):
                continue
            iscourse = np.zeros(len(D.X), dtype=bool)
            crace = np.where(D.course == c)[0]
            for i in crace:
                s, e = D.rowslice[i]
                iscourse[s:e] = True
            for w in W_LIST:
                weight = np.where(iscourse, w, 1.0).astype(np.float64)
                for obj in OBJS:
                    mod = train_generic(D, obj, tr, weight=weight)
                    rows, pr = predict_rows(mod, D, fo)
                    dump(fh, D, obj, f"M3w{int(w)}", fo, rows, pr,
                         dict(train_races=int(len(tr)), w=w,
                              best_iter=int(mod.best_iteration)))
            fh.flush()
            print(f"[{m}] {c} {len(fo)}R done ({time.time()-t0:.0f}s)", flush=True)
    fh.close()
    print(f"M3 done ({(time.time()-t0)/60:.1f}min)")


# ── 評価 ───────────────────────────────────────────────────────────────
def race_meta():
    _, _, _, _, meta = CC.load()
    return {m["rid"]: m for m in meta}


def split_of(m):
    return PE.split_of(m)


def prep_race(mrec, ns, scores, obj):
    """1レース分の (q_model, q_market, y, odds, ns) を作る"""
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
    """rs: prep_race の list -> (alpha, se, beta, n_races)"""
    if len(rs) < 3:
        return None
    X = np.concatenate([np.stack([PE._logit(r["q_model"]), PE._logit(r["q_market"]),
                                  np.ones(len(r["ns"]))], axis=1) for r in rs])
    y = np.concatenate([r["y"] for r in rs])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(rs)])
    th = PE.fit_logit(X, y)
    se = PE.cluster_se(X, y, g, th)
    return float(th[0]), float(se[0]), float(th[1]), len(rs)


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


def load_preds(path, RM):
    """{(obj, method, course): {rid: prepped}} と生レコードを返す"""
    out = defaultdict(dict)
    info = defaultdict(lambda: dict(spec_used=0, n=0, train_races=[]))
    if not os.path.exists(path):
        return out, info
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        mrec = RM[d["rid"]]
        pr = prep_race(mrec, d["ns"], d["scores"], d["obj"])
        if pr is None:
            continue
        key = (d["obj"], d["method"], d["course"])
        out[key][d["rid"]] = pr
        k = info[key]
        k["n"] += 1
        k["spec_used"] += int(d.get("spec_used", True))
        k["train_races"].append(int(d.get("train_races", 0)))
    return out, info


def mc_null(rs, metas_v, rs_c, metas_c, rng):
    """情報ゼロ(一様ランダム1頭)が VAL≥110% & CONF≥100% を同時達成する確率"""
    def draws(rs_, metas_):
        pays, ks = [], []
        for r, mrec in zip(rs_, metas_):
            p = np.array([(mrec["payout"].get("単勝") or {}).get(str(h), 0)
                          for h in r["ns"]], dtype=float)
            pays.append(p)
            ks.append(len(p))
        return pays, ks
    pv, kv = draws(rs, metas_v)
    pc, kc = draws(rs_c, metas_c)
    if not pv or not pc:
        return None
    ok = 0
    for _ in range(MC_ITERS):
        rv = sum(p[rng.integers(k)] for p, k in zip(pv, kv)) / (100 * len(pv)) * 100
        rc = sum(p[rng.integers(k)] for p, k in zip(pc, kc)) / (100 * len(pc)) * 100
        ok += int(rv >= ROI_VAL_TH and rc >= ROI_CONF_TH)
    return ok / MC_ITERS


def evaluate():
    t0 = time.time()
    RM = race_meta()
    D = Data()
    preds, info = defaultdict(dict), {}
    for p in ("course_preds_gen.jsonl", "course_preds_m1.jsonl",
              "course_preds_m2.jsonl", "course_preds_m3.jsonl"):
        o, i = load_preds(p, RM)
        preds.update(o)
        info.update(i)
    print(f"loaded {len(preds)} (obj,method,course) keys ({time.time()-t0:.0f}s)", flush=True)

    methods = ["M1", "M2", "M3w3", "M3w10"]
    rng = np.random.default_rng(20260818)
    res = {}
    mc_cache = {}

    for course in D.targets:
        for obj in OBJS:
            # GEN は全レース分あるので当該コースだけ取り出す
            gen_c = preds.get((obj, "GEN", course), {})
            for meth in methods:
                key = (obj, meth, course)
                if key not in preds:
                    continue
                rows = preds[key]
                rec = dict(course=course, obj=obj, method=meth,
                           n_ledger=D.course_cnt[course])
                windows = {}
                for spn in ("MINE", "VALIDATE", "CONFIRM"):
                    rids = [r for r in rows if split_of(RM[r]["month"]) == spn]
                    rids = [r for r in rids if r in gen_c]
                    if not rids:
                        windows[spn] = dict(n=0)
                        continue
                    rs = [rows[r] for r in rids]
                    gs = [gen_c[r] for r in rids]
                    ms = [RM[r] for r in rids]
                    a_m = alpha_of(rs)
                    a_g = alpha_of(gs)
                    n, roi, hit = roi_of(rs, ms, "単勝")
                    ng, roig, hitg = roi_of(gs, ms, "単勝")
                    _, froi, fhit = roi_of(rs, ms, "複勝")
                    _, froig, _ = roi_of(gs, ms, "複勝")
                    w = dict(n=n, roi=roi, hit=hit, roi_gen=roig, hit_gen=hitg,
                             froi=froi, froi_gen=froig, fhit=fhit)
                    if a_m and a_g:
                        w.update(alpha=round(a_m[0], 4), se=round(a_m[1], 4),
                                 alpha_gen=round(a_g[0], 4), se_gen=round(a_g[1], 4),
                                 d_alpha=round(a_m[0] - a_g[0], 4))
                    # 月次サブ判定（VALIDATE のみ・n>=10 の月）
                    if spn == "VALIDATE":
                        sub = {}
                        for mo in sorted({RM[r]["month"] for r in rids}):
                            rr = [r for r in rids if RM[r]["month"] == mo]
                            if len(rr) < MONTH_SUB_MIN:
                                sub[mo] = dict(n=len(rr), d_alpha=None)
                                continue
                            am = alpha_of([rows[r] for r in rr])
                            ag = alpha_of([gen_c[r] for r in rr])
                            sub[mo] = dict(n=len(rr),
                                           d_alpha=round(am[0] - ag[0], 4)
                                           if am and ag else None)
                        w["months"] = sub
                    windows[spn] = w
                rec["windows"] = windows
                V, C = windows.get("VALIDATE", {}), windows.get("CONFIRM", {})
                rec["judgeable"] = bool(V.get("n", 0) >= VAL_MIN_N
                                        and C.get("n", 0) >= CONF_MIN_N)
                subs = [v["d_alpha"] for v in (V.get("months") or {}).values()
                        if v.get("d_alpha") is not None]
                rec["n_sub"] = len(subs)
                rec["primary"] = bool(rec["judgeable"] and V.get("d_alpha") is not None
                                      and V["d_alpha"] > 0 and all(s > 0 for s in subs))
                rec["secondary"] = bool(rec["judgeable"] and V.get("roi") is not None
                                        and C.get("roi") is not None
                                        and V["roi"] >= ROI_VAL_TH
                                        and C["roi"] >= ROI_CONF_TH)
                rec["pass"] = bool(rec["primary"] and rec["secondary"])
                inf = info.get(key, {})
                rec["spec_used_races"] = inf.get("spec_used")
                rec["train_races_max"] = max(inf.get("train_races") or [0])
                res[f"{obj}|{meth}|{course}"] = rec

            # 偶然期待（二次）: コース単位で1回だけMC
            if (obj, course) not in mc_cache:
                gk = None
                for meth in methods:
                    if (obj, meth, course) in preds:
                        gk = preds[(obj, meth, course)]
                        break
                if gk is None:
                    mc_cache[(obj, course)] = None
                else:
                    vr = [r for r in gk if split_of(RM[r]["month"]) == "VALIDATE"]
                    cr = [r for r in gk if split_of(RM[r]["month"]) == "CONFIRM"]
                    if len(vr) >= VAL_MIN_N and len(cr) >= CONF_MIN_N:
                        mc_cache[(obj, course)] = mc_null(
                            [gk[r] for r in vr], [RM[r] for r in vr],
                            [gk[r] for r in cr], [RM[r] for r in cr], rng)
                    else:
                        mc_cache[(obj, course)] = None
        print(f"  {course} evaluated ({time.time()-t0:.0f}s)", flush=True)

    # ── 多重比較 ──
    trials = [k for k, v in res.items() if v["judgeable"]]
    exp_sec = 0.0
    exp_both = 0.0
    for k in trials:
        v = res[k]
        p_c = mc_cache.get((v["obj"], v["course"]))
        if p_c is None:
            continue
        exp_sec += p_c
        exp_both += p_c * 0.5 ** (1 + v["n_sub"])
    passed = [k for k in trials if res[k]["pass"]]
    prim = [k for k in trials if res[k]["primary"]]
    sec = [k for k in trials if res[k]["secondary"]]
    summary = dict(n_keys=len(res), n_judgeable=len(trials),
                   n_primary=len(prim), n_secondary=len(sec), n_pass=len(passed),
                   expect_secondary=round(exp_sec, 3), expect_both=round(exp_both, 4),
                   verdict=("PASS" if len(passed) >= 3 * max(exp_both, 1e-9) and passed
                            else "FAIL"),
                   primary=prim, secondary=sec, passed=passed,
                   mc={f"{o}|{c}": p for (o, c), p in mc_cache.items()})
    json.dump(dict(result=res, summary=summary),
              open("course_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:3000])
    print(f"saved course_result.json ({(time.time()-t0)/60:.1f}min)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    {"gen": run_gen, "m12": run_m12, "m3": run_m3, "eval": evaluate}[cmd]()
