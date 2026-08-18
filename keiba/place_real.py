# -*- coding: utf-8 -*-
"""3着内特化システムの「実オッズ版」本番検証 — PLACE_REAL_ODDS_REPORT.md の実装。

PLACE_SYSTEM_20260817.md では組合せ馬券の事前オッズが台帳に無く、市場側も券種EVも
すべて Harville近似に依存していた（実測で複勝含みオッズが実払戻の1.25倍＝2割過大）。
本スクリプトは hist_odds/ の **実オッズ**（複勝下限・ワイド下限・三連複・馬連）を使って
同じ検証をやり直す。

測るもの:
  (1) α_place（実オッズ版）… 市場側を「単勝→Harville」ではなく **実複勝オッズ** から作る。
  (2) 券種別EV … 複勝/ワイド/三連複/馬連。確率はモデル（Harville/PL近似は使う）、
                 オッズは実測値。EV閾値は事前登録（複勝 1.1/1.2/1.3、他 1.2）。
  (3) 控除率の壁 … 実オッズから券種ごとの控除率を実測し、必要エッジと実エッジを比較。
  (4) 点数設計 … EVプラス全買い vs 上位k点（k=1,3,5,10,20）。
  (5) 較正補正 … モデル確率の過大（勝者の呪いのモデル側）を isotonic（MINE期のみ学習）で補正。

既存経路は一切変更しない（読むだけ）。

usage:
  python3 place_real.py --variants v3place,v8place
  python3 place_real.py --selftest
"""
import argparse, json, math, os, sys, time
from collections import defaultdict

import numpy as np

import fit_place as FP
import place_eval as PE

SPLITS = PE.SPLITS                       # MINE / VALIDATE / CONFIRM（事前登録・変更禁止）
ODDS_DIR = "hist_odds"

# ── 事前登録の判定基準（本タスクで与えられたもの。事後変更禁止）────────────────
PASS_VAL = dict(n=40, roi=110.0)
PASS_CONF = dict(n=25, roi=105.0)
EV_TH_FUKU = (1.1, 1.2, 1.3)
EV_TH_COMBO = (1.2,)
TOPK = (1, 3, 5, 10, 20)


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def _logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def ckey(nums):
    return "-".join(str(int(x)) for x in sorted(int(v) for v in nums))


# ── 実オッズの読み込み ────────────────────────────────────────────────
def load_real_odds(rid):
    p = os.path.join(ODDS_DIR, "%s.json" % rid)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def market_place_from_fuku(fuku_odds, target=3.0, cap=0.999):
    """実複勝オッズ（**下限**）から市場の「複勝圏内」確率を作る。

    複勝プールは的中 target 頭に配当が割れるため、真の確率の総和は target。
    （JRA: 出走8頭以上=3着まで / 5〜7頭=2着まで）
    比例正規化 p_i = λ/odds_i（Σp=target・上限capでクリップ）で控除率を落とす。
    台帳(hist_odds)には下限しか無いため下限を使用する（上限は未収穫）。
    下限は実払戻より系統的に低い（実測で実払戻/下限 = 平均1.19倍）が、
    比例正規化でその共通スケールは吸収される。
    """
    o = np.asarray(fuku_odds, dtype=float)
    raw = 1.0 / np.clip(o, 1e-6, None)
    if len(raw) <= target:
        return np.ones(len(raw))
    lo, hi = 1e-9, 100.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if np.minimum(mid * raw, cap).sum() > target:
            hi = mid
        else:
            lo = mid
    return np.clip(np.minimum((lo + hi) / 2 * raw, cap), 1e-9, 1 - 1e-9)


def load_all(variant):
    """place_preds_*.jsonl + hist_odds/ を結合して評価用レース配列を返す。"""
    path = "place_preds_%s.jsonl" % variant
    races, dropped = PE.load_ledger(path)
    # place_eval.load_ledger は馬連を持たないので生台帳から補う
    umaren = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        umaren[d["rid"]] = {PE._key(k): int(v)
                            for k, v in ((d.get("payout") or {}).get("馬連") or {}).items()}
    out, no_odds = [], []
    for r in races:
        r["pay_umaren"] = umaren.get(r["rid"], {})
        ro = load_real_odds(r["rid"])
        if not ro:
            no_odds.append(r["rid"])
            continue
        fk = ro.get("fuku") or {}
        if any(str(h) not in fk or not fk[str(h)] for h in r["ns"]):
            no_odds.append(r["rid"])
            continue
        r["fuku_odds"] = np.array([float(fk[str(h)]) for h in r["ns"]], dtype=float)
        r["o_wide"] = {k: float(v) for k, v in (ro.get("wide") or {}).items() if v}
        r["o_trio"] = {k: float(v) for k, v in (ro.get("sanrenpuku") or {}).items() if v}
        r["o_umaren"] = {k: float(v) for k, v in (ro.get("umaren") or {}).items() if v}
        out.append(r)
    return out, dropped, no_odds


def prep(races):
    for r in races:
        n = len(r["ns"])
        # JRA: 出走8頭以上=複勝は3着まで / 5〜7頭=2着まで（払戻の実データと一致を確認済み）
        r["fuku_k"] = 3 if n >= 8 else 2
        r["q_model"] = PE.norm_place(r["s"])
        pw, qm = PE.market_probs(r["odds"])
        r["p_market"] = pw
        r["q_hv"] = qm                                   # 旧: 単勝→Harville
        # 新: 実複勝オッズ（α推定は3着まで=8頭以上のレースのみを使う）
        r["q_real"] = market_place_from_fuku(r["fuku_odds"], 3.0)
        r["q_real_k"] = market_place_from_fuku(r["fuku_odds"], float(r["fuku_k"]))
        r["y"] = np.zeros(n)
        for i in r["top3_idx"]:
            r["y"][i] = 1.0


# ── (1) α_place の月次WF ────────────────────────────────────────────
def stack_cols(races, cols):
    X = np.concatenate([np.stack([c(r) for c in cols] + [np.ones(len(r["ns"]))], axis=1)
                        for r in races])
    y = np.concatenate([r["y"] for r in races])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(races)])
    return X, y, g


def cluster_se_fast(X, y, g, th):
    """place_eval.cluster_se と数学的に同一のクラスタ頑健SE。
       グループ和を np.add.at でベクトル化しただけ（fold数×モデル数が多いため）。"""
    p = _sig(X @ th)
    W = p * (1 - p)
    A = X.T @ (X * W[:, None])
    Ai = np.linalg.pinv(A)
    u = (y - p)[:, None] * X
    gi = np.unique(g, return_inverse=True)[1]
    S = np.zeros((gi.max() + 1, X.shape[1]))
    np.add.at(S, gi, u)
    B = S.T @ S
    V = Ai @ B @ Ai
    return np.sqrt(np.clip(np.diag(V), 0, None))


def logloss(X, y, th):
    p = _sig(X @ th)
    return float(-(y * np.log(np.clip(p, 1e-12, None))
                   + (1 - y) * np.log(np.clip(1 - p, 1e-12, None))).mean())


C_MODEL = lambda r: _logit(r["q_model"])
C_REAL = lambda r: _logit(r["q_real"])
C_HV = lambda r: _logit(r["q_hv"])


def alpha_wf(races, months, by_m, tag_cols, min_train=200, keep=None):
    """tag_cols = {name: [列関数,...]} を同じfoldで同時に推定する。
       keep: 推定に使うレースのフィルタ（既定=全部）。q_blend は全レースに付ける。
       戻り: folds[m][name] = dict(alpha, se, z, coef)、各月の q_blend。"""
    keep = keep or (lambda r: True)
    folds = {}
    for mi, m in enumerate(months):
        tr = [r for mm in months[:mi] for r in by_m[mm] if keep(r)]
        if len(tr) < min_train:
            folds[m] = dict(skipped=True, train=len(tr))
            continue
        rec = dict(train=len(tr), split=PE.split_of(m))
        cur = [r for r in by_m[m] if keep(r)]
        for name, cols in tag_cols.items():
            X, y, g = stack_cols(tr, cols)
            th = PE.fit_logit(X, y)
            se = cluster_se_fast(X, y, g, th)
            rec[name] = dict(coef=[round(float(v), 4) for v in th],
                             se=[round(float(v), 4) for v in se],
                             alpha=round(float(th[0]), 4),
                             se_alpha=round(float(se[0]), 4),
                             z_alpha=round(float(th[0] / max(se[0], 1e-9)), 2))
            if cur:
                Xm, ym, _ = stack_cols(cur, cols)
                rec[name]["oos_logloss"] = round(logloss(Xm, ym, th), 6)
                rec[name]["oos_n"] = int(len(ym))
            if name == "real":
                # 推定はfield>=8のみ、適用は当月の全レース
                Xa, _, _ = stack_cols(by_m[m], cols)
                off = 0
                for r in by_m[m]:
                    k = len(r["ns"])
                    # 和=3 に正規化（組合せ券のPL逆変換で必要）。
                    # 5〜7頭立ての複勝(2着まで)は P(top2)=harville(w,2) を別途使う。
                    r["q_blend"] = PE.norm_place(_sig(Xa[off:off + k] @ th))
                    off += k
        folds[m] = rec
    return folds


def runs(vals):
    best = run = 0
    for v in vals:
        run = run + 1 if v > 0 else 0
        best = max(best, run)
    return best


# ── isotonic（PAVA・自前実装。sklearn非依存）──────────────────────────
def _pava(y, w):
    ys, ws, ns = [], [], []
    for yi, wi in zip(y, w):
        ys.append(float(yi)); ws.append(float(wi)); ns.append(1)
        while len(ys) > 1 and ys[-2] > ys[-1] + 1e-15:
            y2, w2, n2 = ys.pop(), ws.pop(), ns.pop()
            y1, w1, n1 = ys.pop(), ws.pop(), ns.pop()
            ys.append((y1 * w1 + y2 * w2) / (w1 + w2)); ws.append(w1 + w2); ns.append(n1 + n2)
    out = []
    for v, n in zip(ys, ns):
        out.extend([v] * n)
    return np.array(out)


class Iso:
    """分位ビン + PAVA の単調較正器。x（確率）→ 較正済み確率。"""

    def __init__(self, x, y, nbins=120, min_per_bin=50):
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        o = np.argsort(x, kind="mergesort")
        xs, ys = x[o], y[o]
        n = len(xs)
        nb = max(2, min(nbins, n // max(min_per_bin, 1)))
        edges = np.linspace(0, n, nb + 1).astype(int)
        bx, by, bw = [], [], []
        for a, b in zip(edges[:-1], edges[1:]):
            if b <= a:
                continue
            bx.append(xs[a:b].mean()); by.append(ys[a:b].mean()); bw.append(b - a)
        self.bx = np.array(bx)
        self.by = _pava(by, bw)
        self.n = n

    def __call__(self, x):
        if len(self.bx) < 2:
            return np.full_like(np.asarray(x, dtype=float), float(self.by[0]))
        return np.clip(np.interp(np.asarray(x, dtype=float), self.bx, self.by), 1e-12, 1.0)


# ── 券種テーブル（実オッズ付き）────────────────────────────────────
def bet_tables(r, w_by_src):
    """レース r について 複勝/ワイド/三連複/馬連 の
       (キー, 各確率源の確率, 実オッズ, 実払戻, 的中フラグ) を作る。

    **的中フラグは「実払戻が存在するか」で定義する。**
    着順から作ると (a) 5〜7頭立ての複勝が2着までであること
    (b) 3着同着（20R）で三連複が2組・ワイドが6組当たること を取りこぼす。
    """
    ns = np.array(r["ns"])
    n = len(ns)
    T = {}

    # --- 複勝（5〜7頭立ては2着まで。確率も P(top2) に切り替える）---
    pays = np.array([float(r["pay_fuku"].get(int(h), 0)) / 100.0 for h in ns])
    hits = (pays > 0).astype(float)
    pf = {}
    for src, d in w_by_src.items():
        pf[src] = d["q"] if r["fuku_k"] == 3 else FP.harville_place(d["w"], 2)
    T["fuku"] = dict(keys=[str(int(h)) for h in ns], odds=r["fuku_odds"].copy(),
                     pay=pays, hit=hits, p=pf)

    if n < 4:
        return T

    tri_idx = FP.triples(n)
    k3 = ["-".join(str(int(x)) for x in sorted(ns[t])) for t in tri_idx]
    iu = np.triu_indices(n, 1)
    k2 = ["-".join(str(int(x)) for x in sorted((int(ns[i]), int(ns[j]))))
          for i, j in zip(*iu)]

    p3 = {}; p2 = {}; pu = {}
    for src, d in w_by_src.items():
        w = d["w"]
        _, pt = FP.trio_probs(w)
        p3[src] = pt
        W = FP.wide_probs(tri_idx, pt, n)
        p2[src] = W[iu] + W.T[iu]
        d1 = np.clip(1.0 - w, 1e-9, None)
        M = (w[:, None] * w[None, :]) / d1[:, None] + (w[:, None] * w[None, :]) / d1[None, :]
        pu[src] = M[iu]

    def _mk(keys, probs, odds_map, pay_map):
        od = np.array([odds_map.get(k, np.nan) for k in keys])
        pay = np.array([float(pay_map.get(PE._key(k), 0)) / 100.0 for k in keys])
        ok = np.isfinite(od) & (od > 0)
        return dict(keys=[k for k, m in zip(keys, ok) if m], odds=od[ok],
                    pay=pay[ok], hit=(pay[ok] > 0).astype(float),
                    p={s: probs[s][ok] for s in probs})

    T["trio"] = _mk(k3, p3, r["o_trio"], r["pay_trio"])
    T["wide"] = _mk(k2, p2, r["o_wide"], r["pay_wide"])
    T["umaren"] = _mk(k2, pu, r["o_umaren"], r["pay_umaren"])
    return T


BET_KINDS = ("fuku", "wide", "trio", "umaren")
BET_JP = dict(fuku="複勝", wide="ワイド", trio="三連複", umaren="馬連")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--out", default="place_real_result.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    OUT = {}
    for variant in a.variants.split(","):
        t0 = time.time()
        print("\n" + "=" * 78 + "\n%s\n" % variant + "=" * 78, flush=True)
        races, dropped, no_odds = load_all(variant)
        prep(races)
        months = sorted({r["month"] for r in races})
        by_m = {m: [r for r in races if r["month"] == m] for m in months}
        print("races=%d dropped(ledger)=%d no_real_odds=%d months=%s..%s"
              % (len(races), len(dropped), len(no_odds), months[0], months[-1]), flush=True)
        res = dict(n_races=len(races), dropped=len(dropped), no_real_odds=len(no_odds))

        # ── (1) α_place ──────────────────────────────────────────────
        print("\n[1] α_place の月次WF（市場側=実複勝オッズ / 旧=単勝Harville）", flush=True)
        folds = alpha_wf(races, months, by_m, {
            "real": [C_MODEL, C_REAL],
            "hv": [C_MODEL, C_HV],
            "both": [C_MODEL, C_REAL, C_HV],
            "mkt_real_only": [C_REAL],
            "mkt_hv_only": [C_HV],
        }, keep=lambda r: r["fuku_k"] == 3)
        res["folds"] = folds
        res["n_alpha_races"] = sum(1 for r in races if r["fuku_k"] == 3)
        res["n_small_field"] = sum(1 for r in races if r["fuku_k"] == 2)
        print("  α推定に使うレース（8頭以上・複勝3着まで）= %d R / 5〜7頭立て %d R は除外"
              % (res["n_alpha_races"], res["n_small_field"]))
        # 参考: 全レース（旧報告と同じ集合）での Harville α
        folds_all = alpha_wf(races, months, by_m, {"hv": [C_MODEL, C_HV]})
        act_all = [m for m in months if not folds_all[m].get("skipped")]
        res["alpha_hv_allraces_last"] = folds_all[act_all[-1]]["hv"]["alpha"]
        print("  参考: 全レースでの Harville α（旧報告と同一集合）最終fold = %+.4f"
              % res["alpha_hv_allraces_last"])
        act = [m for m in months if not folds[m].get("skipped")]
        for nm in ("real", "hv", "both"):
            av = [folds[m][nm]["alpha"] for m in act]
            res["alpha_%s" % nm] = dict(pos=sum(1 for v in av if v > 0), n=len(av),
                                        max_run=runs(av),
                                        last=av[-1] if av else None)
        print("  %-8s %-24s %-24s %-24s" % ("fold", "real α(se,z)", "harville α(se,z)", "both α(se,z)"))
        for m in act:
            f = folds[m]
            print("  %-8s[%-8s] tr=%5dR  " % (m, f["split"], f["train"]), end="")
            for nm in ("real", "hv", "both"):
                d = f[nm]
                print("%+.4f(%.4f,%+.2f) " % (d["alpha"], d["se_alpha"], d["z_alpha"]), end="")
            print(flush=True)
        for nm, jp in (("real", "実複勝オッズ"), ("hv", "単勝Harville"), ("both", "両方入り")):
            d = res["alpha_%s" % nm]
            print("  → α>0: %d/%dfold 最長連続=%d 最終fold α=%+.4f  [%s]"
                  % (d["pos"], d["n"], d["max_run"], d["last"], jp))
        # 3分割ごとの α と3fold連続判定
        res["alpha_by_split"] = {}
        for sp, _, _ in SPLITS:
            ms = [m for m in act if folds[m]["split"] == sp]
            for nm in ("real", "hv", "both"):
                av = [folds[m][nm]["alpha"] for m in ms]
                res["alpha_by_split"].setdefault(sp, {})[nm] = dict(
                    months=ms, alphas=av, all_pos=bool(av) and all(v > 0 for v in av),
                    n_fold=len(av))
        # OOS対数損失（市場のみ vs 市場+モデル）
        ll = defaultdict(lambda: [0.0, 0])
        for m in act:
            f = folds[m]
            sp = f["split"]
            for nm, base in (("real", "mkt_real_only"), ("hv", "mkt_hv_only")):
                nn = f[nm]["oos_n"]
                ll["%s/%s/full" % (sp, nm)][0] += f[nm]["oos_logloss"] * nn
                ll["%s/%s/full" % (sp, nm)][1] += nn
                ll["%s/%s/mkt" % (sp, nm)][0] += f[base]["oos_logloss"] * nn
                ll["%s/%s/mkt" % (sp, nm)][1] += nn
        res["oos_logloss"] = {}
        print("\n  [OOS対数損失/頭]  split   市場のみ   +モデル    改善")
        for sp, _, _ in SPLITS:
            for nm in ("real", "hv"):
                a1, n1 = ll["%s/%s/mkt" % (sp, nm)]
                a2, n2 = ll["%s/%s/full" % (sp, nm)]
                if not n1:
                    continue
                v = dict(n=n1, market=round(a1 / n1, 6), full=round(a2 / n2, 6),
                         gain=round((a1 / n1) - (a2 / n2), 6))
                res["oos_logloss"]["%s/%s" % (sp, nm)] = v
                print("   %-9s %-9s %.6f  %.6f  %+.6f  (n=%d頭)"
                      % (sp, nm, v["market"], v["full"], v["gain"], n1))

        # ── ヌル検査（最終fold・レース内シャッフル8シード）──────────
        print("\n  [ヌル検査] 最終foldでモデル確率をレース内シャッフル", flush=True)
        mlast = act[-1]
        tr = [r for mm in months[:months.index(mlast)] for r in by_m[mm] if r["fuku_k"] == 3]
        nulls = []
        for seed in range(8):
            rng = np.random.default_rng(1000 + seed)
            saved = []
            for r in tr:
                saved.append(r["q_model"])
                r["q_model"] = rng.permutation(r["q_model"])
            X, y, g = stack_cols(tr, [C_MODEL, C_REAL])
            th = PE.fit_logit(X, y)
            nulls.append(round(float(th[0]), 4))
            for r, s in zip(tr, saved):
                r["q_model"] = s
        real_alpha = folds[mlast]["real"]["alpha"]
        res["null"] = dict(fold=mlast, real_alpha=real_alpha, nulls=nulls,
                           mean=round(float(np.mean(nulls)), 4),
                           max=round(float(np.max(nulls)), 4),
                           n_ge_real=int(sum(1 for v in nulls if v >= real_alpha)))
        print("   実データ α=%+.4f / ヌル8本 平均%+.4f 最大%+.4f 実データ以上 %d/8"
              % (real_alpha, res["null"]["mean"], res["null"]["max"], res["null"]["n_ge_real"]))

        # ── (2)-(5) 券種検証 ────────────────────────────────────────
        print("\n[2] 券種テーブル構築（実オッズ）", flush=True)
        ev_races = [r for r in races if "q_blend" in r]
        cache = []
        for i, r in enumerate(ev_races):
            wsrc = {}
            for src, q in (("model", r["q_model"]), ("blend", r["q_blend"])):
                wsrc[src] = dict(q=q, w=FP.pl_from_place(q))
            T = bet_tables(r, wsrc)
            cache.append(dict(rid=r["rid"], split=r["split"], month=r["month"],
                              field=len(r["ns"]), T=T))
            if (i + 1) % 1000 == 0:
                print("   %d/%d (%.0fs)" % (i + 1, len(ev_races), time.time() - t0), flush=True)

        # 控除率の実測
        tk = {}
        for kind in BET_KINDS:
            ss = []
            for c in cache:
                t = c["T"].get(kind)
                if t is None or len(t["odds"]) == 0:
                    continue
                ss.append(float((1.0 / t["odds"]).sum()))
            m = float(np.mean(ss))
            tgt = 3.0 if kind in ("fuku", "wide") else 1.0
            tk[kind] = dict(n=len(ss), mean_sum_inv_odds=round(m, 4),
                            implied_takeout=round(1 - tgt / m, 4),
                            required_edge=round(m / tgt - 1, 4))
        res["takeout"] = tk
        print("\n[3] 控除率の実測（実オッズ）")
        print("   券種      Σ(1/odds)  的中組数  実測控除率  EV1に必要なエッジ(p_model/p_market)")
        for kind in BET_KINDS:
            d = tk[kind]
            print("   %-8s %8.4f  %6s   %7.1f%%   ×%.3f"
                  % (BET_JP[kind], d["mean_sum_inv_odds"],
                     "3" if kind in ("fuku", "wide") else "1",
                     d["implied_takeout"] * 100, 1 + d["required_edge"]))
        print("   ※複勝・ワイドは台帳が**下限**オッズのため控除率が過大に出る"
              "（実払戻/下限=複勝1.19倍・ワイド1.05倍を掛け戻すと実効20〜23%）")

        # 下限オッズ → 期待払戻の写像（MINE期のみで学習・複勝/ワイドのみ）
        # 台帳の複勝・ワイドは**下限**なので、下限のままEVを測ると系統的に過小になる
        # （実測 実払戻/下限 = 複勝1.19倍・ワイド1.05倍）。発走前に見えるのは下限だけなので、
        # 「下限 → 期待払戻」の写像を MINE期だけで推定して EV に使う（買い判断に未来情報は入らない）。
        print("\n[3b] 下限→期待払戻の写像（MINE期のみ）", flush=True)
        oratio = {}
        for kind in ("fuku", "wide"):
            xs, ys = [], []
            for c in cache:
                if c["split"] != "MINE":
                    continue
                t = c["T"].get(kind)
                if t is None or len(t["hit"]) == 0:
                    continue
                m = t["hit"] > 0
                xs.append(np.log(t["odds"][m])); ys.append(t["pay"][m] / t["odds"][m])
            x = np.concatenate(xs); y = np.concatenate(ys)
            oratio[kind] = Iso(x, y, nbins=40, min_per_bin=200)
            res.setdefault("odds_ratio", {})[kind] = dict(
                n=int(len(x)), mean=round(float(y.mean()), 4))
            probe = np.array([1.2, 1.5, 2.0, 3.0, 5.0, 10.0, 30.0])
            print("   %-6s n=%7d 平均比%.3f  写像: %s"
                  % (BET_JP[kind], len(x), y.mean(),
                     " ".join("%.1f→×%.2f" % (o, oratio[kind](np.log([o]))[0]) for o in probe)),
                  flush=True)

        # 較正器（MINE期のみで学習）
        print("\n[4] 較正器の学習（MINE期のみ・isotonic）", flush=True)
        iso = {}
        for kind in BET_KINDS:
            for src in ("model", "blend"):
                xs, ys = [], []
                for c in cache:
                    if c["split"] != "MINE":
                        continue
                    t = c["T"].get(kind)
                    if t is None or len(t["hit"]) == 0:
                        continue
                    xs.append(t["p"][src]); ys.append(t["hit"])
                if not xs:
                    continue
                x = np.concatenate(xs); y = np.concatenate(ys)
                iso[(kind, src)] = Iso(x, y)
                print("   %-6s/%-5s n=%9d  平均予測%.5f → 実測%.5f (倍率 %.2f×)"
                      % (BET_JP[kind], src, len(x), x.mean(), y.mean(),
                         x.mean() / max(y.mean(), 1e-12)), flush=True)
        res["calib_mine"] = {("%s/%s" % (k[0], k[1])):
                             dict(n=int(iso[k].n),
                                  knots=[[round(float(bx), 6), round(float(by), 6)]
                                         for bx, by in zip(iso[k].bx[-12:], iso[k].by[-12:])])
                             for k in iso}

        # 評価本体
        print("\n[5] 券種別EV検証（実オッズ）", flush=True)
        acc = defaultdict(float)
        kelly = defaultdict(list)
        for c in cache:
            sp = c["split"]
            for kind in BET_KINDS:
                t = c["T"].get(kind)
                if t is None or len(t["hit"]) == 0:
                    continue
                omodes = {"floor": t["odds"]}
                if kind in oratio:
                    omodes["exp"] = t["odds"] * oratio[kind](np.log(np.clip(t["odds"], 1e-9, None)))
                for src in ("model", "blend"):
                    for cal in ("raw", "iso"):
                        p = t["p"][src]
                        if cal == "iso":
                            f = iso.get((kind, src))
                            if f is None:
                                continue
                            p = f(p)
                        for om, oo in omodes.items():
                            ev = p * oo
                            ths = EV_TH_FUKU if kind == "fuku" else EV_TH_COMBO
                            for th in ths:
                                sel = ev >= th
                                tag = "%s/%s/%s/%s/%s/ev%.1f" % (sp, kind, src, cal, om, th)
                                acc[tag + "/n"] += int(sel.sum())
                                acc[tag + "/pay"] += float(t["pay"][sel].sum())
                                acc[tag + "/floor"] += float((t["odds"][sel] * t["hit"][sel]).sum())
                                acc[tag + "/hit"] += float(t["hit"][sel].sum())
                                acc[tag + "/ev"] += float(ev[sel].sum())
                                acc[tag + "/pm"] += float(p[sel].sum())
                                acc[tag + "/imp"] += float((1.0 / t["odds"][sel]).sum())
                            # top-k（EV降順・EV>=1.0 のものだけ）
                            order = np.argsort(-ev)
                            for k in TOPK:
                                idx = [i for i in order[:k] if ev[i] >= 1.0]
                                if not idx:
                                    continue
                                tag = "%s/%s/%s/%s/%s/top%d" % (sp, kind, src, cal, om, k)
                                acc[tag + "/n"] += len(idx)
                                acc[tag + "/pay"] += float(t["pay"][idx].sum())
                                acc[tag + "/floor"] += float((t["odds"][idx] * t["hit"][idx]).sum())
                                acc[tag + "/hit"] += float(t["hit"][idx].sum())
                                acc[tag + "/ev"] += float(ev[idx].sum())
                                acc[tag + "/pm"] += float(p[idx].sum())
                                acc[tag + "/imp"] += float((1.0 / t["odds"][idx]).sum())
                                acc[tag + "/races"] += 1
                            if src == "blend" and cal == "iso" and sp != "MINE" and om == list(omodes)[-1]:
                                sel = ev >= 1.0
                                if sel.any():
                                    b = oo[sel] - 1.0
                                    pp = p[sel]
                                    fk = np.clip((pp * (b + 1) - 1) / np.clip(b, 1e-9, None), 0, 1)
                                    kelly["%s/%s" % (sp, kind)].append(float(fk.sum()))

        def _row(tag):
            n = acc[tag + "/n"]
            if not n:
                return None
            return dict(n=int(n), hits=int(acc[tag + "/hit"]),
                        roi=round(acc[tag + "/pay"] / n * 100, 1),
                        roi_floor=round(acc[tag + "/floor"] / n * 100, 1),
                        hit_rate=round(acc[tag + "/hit"] / n * 100, 3),
                        mean_ev=round(acc[tag + "/ev"] / n, 3),
                        mean_p=round(acc[tag + "/pm"] / n, 6) if acc[tag + "/pm"] else None,
                        mean_imp=round(acc[tag + "/imp"] / n, 6) if acc[tag + "/imp"] else None,
                        races=int(acc[tag + "/races"]) or None)

        OMODES = ("floor", "exp")
        RULES = {}
        for kind in BET_KINDS:
            RULES[kind] = (["ev%.1f" % th for th in
                            (EV_TH_FUKU if kind == "fuku" else EV_TH_COMBO)]
                           + ["top%d" % k for k in TOPK])
        res["bets"] = {}
        for sp, _, _ in SPLITS:
            for kind in BET_KINDS:
                for src in ("model", "blend"):
                    for cal in ("raw", "iso"):
                        for om in OMODES:
                            for rule in RULES[kind]:
                                tag = "%s/%s/%s/%s/%s/%s" % (sp, kind, src, cal, om, rule)
                                v = _row(tag)
                                if v:
                                    res["bets"][tag] = v
        res["kelly"] = {k: dict(n=len(v), mean_total_f=round(float(np.mean(v)), 3),
                                p90=round(float(np.percentile(v, 90)), 3))
                        for k, v in kelly.items() if v}

        # 表示
        for kind in BET_KINDS:
            print("\n  ── %s ──  (odds: floor=台帳下限 / exp=下限×期待払戻倍率)" % BET_JP[kind])
            print("   %-9s %-6s %-4s %-5s %-7s %8s %6s %8s %9s %7s"
                  % ("split", "src", "cal", "odds", "rule", "n", "hits", "ROI%",
                     "ROI_floor", "meanEV"))
            for sp, _, _ in SPLITS:
                for src in ("model", "blend"):
                    for cal in ("raw", "iso"):
                        for om in OMODES:
                            for rule in RULES[kind]:
                                v = res["bets"].get("%s/%s/%s/%s/%s/%s"
                                                    % (sp, kind, src, cal, om, rule))
                                if not v:
                                    continue
                                if rule.startswith("top") and not (src == "blend" and cal == "iso"):
                                    continue
                                print("   %-9s %-6s %-4s %-5s %-7s %8d %6d %8.1f %9.1f %7.2f%s"
                                      % (sp, src, cal, om, rule, v["n"], v["hits"], v["roi"],
                                         v["roi_floor"], v["mean_ev"],
                                         "" if not v["races"] else " (%dR)" % v["races"]))

        # 合否判定
        print("\n[6] 合否判定（事前登録: VAL n>=40 & ROI>=110 / CONF n>=25 & ROI>=105）")
        verdict = {}
        for kind in BET_KINDS:
            for src in ("model", "blend"):
                for cal in ("raw", "iso"):
                    for om in OMODES:
                        for rule in RULES[kind]:
                            v = res["bets"].get("VALIDATE/%s/%s/%s/%s/%s"
                                                % (kind, src, cal, om, rule))
                            c = res["bets"].get("CONFIRM/%s/%s/%s/%s/%s"
                                                % (kind, src, cal, om, rule))
                            if not v or not c:
                                continue
                            ok = (v["n"] >= PASS_VAL["n"] and v["roi"] >= PASS_VAL["roi"]
                                  and c["n"] >= PASS_CONF["n"] and c["roi"] >= PASS_CONF["roi"])
                            verdict["%s/%s/%s/%s/%s" % (kind, src, cal, om, rule)] = dict(
                                val=(v["n"], v["roi"]), conf=(c["n"], c["roi"]), pass_=bool(ok))
        res["verdict"] = verdict
        npass = sum(1 for v in verdict.values() if v["pass_"])
        print("   合格 %d / %d 組合せ" % (npass, len(verdict)))
        for k, v in verdict.items():
            if v["pass_"]:
                print("   ✅ %s  VAL n=%d ROI=%.1f%% / CONF n=%d ROI=%.1f%%"
                      % (k, v["val"][0], v["val"][1], v["conf"][0], v["conf"][1]))
        if npass == 0:
            print("   ❌ 合格なし = 不合格")

        res["elapsed_sec"] = round(time.time() - t0, 1)
        OUT[variant] = res
        print("\n(%s 完了 %.0fs)" % (variant, time.time() - t0), flush=True)

    json.dump(OUT, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nwrote %s" % a.out)


# ── selftest ────────────────────────────────────────────────────────
def selftest():
    # market_place_from_fuku: 和=3 / 単調
    o = np.array([1.1, 2.0, 3.0, 5.0, 10.0, 30.0, 80.0, 200.0])
    q = market_place_from_fuku(o)
    assert abs(q.sum() - 3.0) < 1e-6, q.sum()
    assert np.all(np.diff(q) < 0), q
    # 3頭以下はそのまま / target=2 も和が合う
    assert market_place_from_fuku(np.array([1.1, 2.0, 3.0])).sum() == 3.0
    q2 = market_place_from_fuku(np.array([1.1, 1.6, 2.2, 4.0, 9.0, 20.0]), 2.0)
    assert abs(q2.sum() - 2.0) < 1e-6, q2.sum()

    # bet_tables: 的中は「実払戻の有無」で決まる（5〜7頭の複勝2着まで / 3着同着）
    ns = [1, 2, 3, 4, 5, 6]
    r = dict(ns=ns, top3=[1, 2, 3], fuku_k=2,
             fuku_odds=np.array([1.1, 1.5, 2.0, 4.0, 8.0, 20.0]),
             pay_fuku={1: 110, 2: 150},               # 2着までしか払戻が無い
             pay_wide={"1-2": 300, "1-3": 400, "2-3": 900},
             pay_trio={(1, 2, 3): 2500}, pay_umaren={(1, 2): 800},
             o_wide={"1-2": 2.5, "1-3": 3.5, "2-3": 8.0},
             o_trio={"1-2-3": 25.0}, o_umaren={"1-2": 8.0})
    r["pay_wide"] = {PE._key(k): v for k, v in r["pay_wide"].items()}
    q = np.array([0.72, 0.60, 0.42, 0.15, 0.08, 0.03])
    q = q * 2.0 / q.sum()
    w = FP.pl_from_place(q * 3.0 / q.sum())
    T = bet_tables(r, {"model": dict(q=q * 3.0 / q.sum(), w=w)})
    assert T["fuku"]["hit"].sum() == 2, T["fuku"]["hit"]           # 2着まで
    assert abs(T["fuku"]["p"]["model"].sum() - 2.0) < 1e-6         # P(top2) を使う
    assert T["trio"]["hit"].sum() == 1 and T["trio"]["pay"][0] == 25.0
    assert T["wide"]["hit"].sum() == 3
    assert T["umaren"]["hit"].sum() == 1 and T["umaren"]["pay"].sum() == 8.0
    # PAVA
    y = _pava([0.3, 0.1, 0.2, 0.9], [1, 1, 1, 1])
    assert np.all(np.diff(y) >= -1e-12), y
    assert abs(y[:3].mean() - 0.2) < 1e-9, y
    # Iso: 単調・端でクリップ
    rng = np.random.default_rng(0)
    x = rng.random(20000)
    yv = (rng.random(20000) < x * 0.5).astype(float)
    f = Iso(x, yv, nbins=50)
    g = f(np.linspace(0.01, 0.99, 50))
    assert np.all(np.diff(g) >= -1e-9)
    assert abs(g[-1] - 0.5) < 0.08, g[-1]
    # ckey
    assert ckey([10, 2, 7]) == "2-7-10"
    # 馬連確率の総和=1（PL）
    w = np.array([0.4, 0.3, 0.2, 0.1])
    d1 = 1 - w
    M = (w[:, None] * w[None, :]) / d1[:, None] + (w[:, None] * w[None, :]) / d1[None, :]
    iu = np.triu_indices(4, 1)
    assert abs(M[iu].sum() - 1.0) < 1e-9, M[iu].sum()
    print("place_real selftest OK")


if __name__ == "__main__":
    main()
