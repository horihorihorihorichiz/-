#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_eval.py -- 調教レビュー原文(netkeibaプレミアム)の増分予測力を検証する。

設計:
  * 目的変数 = 3着内(複勝) / 1着(単勝)
  * 必ず市場オッズを条件に入れる (A: 市場のみ / B: +タイム指数z / C: +レビューz)
  * レース内相対化(zスコア・条件付きロジット)を徹底
  * null検定: レビュースコアをレース内でシャッフルして1000回再推定
辞書は review_score.py に凍結。ここでは一切いじらない。
"""
import json, glob, math, sys, random
import numpy as np
from scipy import optimize, stats
from review_score import load_review_file, score_race, lexicon_summary, VERSION

REVIEW_FILES = ["premium_review_20260815.txt",
                "premium_review_20260816.txt",
                "premium_review_20260815b.txt"]
TSI_FILE = "premium_tsi_20260817.csv"
RNG_SEED = 20260817


# ------------------------------------------------------------------ data
def load_tsi():
    tsi = {}
    with open(TSI_FILE, encoding="utf-8") as f:
        head = f.readline()
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < 8:
                continue
            rid, num = p[0].strip(), p[3].strip()
            if not num.isdigit():
                continue
            def num_of(s):
                s = s.replace("*", "").strip()
                try:
                    return float(s)
                except Exception:
                    return None
            tsi[(rid, int(num))] = {"best": num_of(p[5]), "avg5": num_of(p[6]),
                                    "eval": p[7].strip()}
    return tsi


def build():
    races = {}
    for p in REVIEW_FILES:
        for rid, rows in load_review_file(p).items():
            races.setdefault(rid, []).extend(rows)
    tsi = load_tsi()
    data = []
    for rid in sorted(races):
        rows = races[rid]
        d = json.load(open(f"hist/{rid}.json"))
        order = d["result"]["order"]
        pay = d["result"].get("payout", {})
        byn = {o["num"]: o for o in order}
        scored = score_race(rows)
        # 市場: 単勝オッズ -> implied, レース内で正規化
        raw = {}
        for r in scored:
            o = byn.get(r["num"])
            raw[r["num"]] = 1.0 / o["odds"] if (o and o.get("odds")) else None
        tot = sum(v for v in raw.values() if v)
        recs = []
        for r in scored:
            o = byn.get(r["num"])
            if o is None or not o.get("odds"):
                continue
            try:
                rank = int(str(o["rank"]))
            except Exception:
                rank = 99                      # 中止・失格は着外扱い
            t = tsi.get((rid, r["num"]), {})
            recs.append(dict(
                rid=rid, num=r["num"], name=r["name"], text=r["text"],
                score=r["score"], pos_n=r["pos_n"], neg_n=r["neg_n"],
                pos=r["pos"], neg=r["neg"], cond=r["cond"], grp=r["grp"],
                odds=o["odds"], ninki=o.get("ninki"), rank=rank,
                p_mkt=raw[r["num"]] / tot,
                tsi_best=t.get("best"), tsi_avg5=t.get("avg5"),
                win=1 if rank == 1 else 0, top3=1 if rank <= 3 else 0,
                field=len(rows), date=d["date"], rname=d["race"]["name"],
                pay_win=pay.get("単勝", {}).get(str(r["num"])),
                pay_pla=pay.get("複勝", {}).get(str(r["num"])),
            ))
        # レース内z
        def zfill(key, dst):
            vals = [x[key] for x in recs if x[key] is not None]
            if len(vals) < 3:
                for x in recs:
                    x[dst] = None
                return
            mu, sd = np.mean(vals), np.std(vals)
            for x in recs:
                x[dst] = (x[key] - mu) / sd if (x[key] is not None and sd > 0) else (
                    0.0 if x[key] is not None else None)
        zfill("score", "rev_z")
        zfill("tsi_best", "tsib_z")
        zfill("tsi_avg5", "tsia_z")
        data.extend(recs)
    return data


# ------------------------------------------------- models: logistic (top3)
def loglik_logit(b, X, y, off):
    eta = X @ b + off
    return -np.sum(y * eta - np.logaddexp(0.0, eta))


def fit_logit(X, y, off):
    b0 = np.zeros(X.shape[1])
    res = optimize.minimize(loglik_logit, b0, args=(X, y, off), method="BFGS",
                            options={"maxiter": 500, "gtol": 1e-8})
    b = res.x
    p = 1 / (1 + np.exp(-(X @ b + off)))
    W = p * (1 - p)
    H = X.T @ (X * W[:, None])
    Hinv = np.linalg.pinv(H)
    return b, -res.fun, Hinv, p


def robust_se(X, y, p, Hinv, groups):
    s = X * (y - p)[:, None]
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in set(groups):
        idx = [i for i, gg in enumerate(groups) if gg == g]
        sg = s[idx].sum(axis=0)
        meat += np.outer(sg, sg)
    V = Hinv @ meat @ Hinv
    return np.sqrt(np.diag(V))


# --------------------------------------- models: conditional logit (win)
def loglik_clogit(b, groups_X, groups_y):
    ll = 0.0
    for X, y in zip(groups_X, groups_y):
        eta = X @ b
        ll += eta[y] - np.logaddexp.reduce(eta)
    return -ll


def fit_clogit(groups_X, groups_y, k):
    res = optimize.minimize(loglik_clogit, np.zeros(k),
                            args=(groups_X, groups_y), method="BFGS",
                            options={"maxiter": 800, "gtol": 1e-8})
    b = res.x
    # 数値ヘッセ行列からSE
    H = np.zeros((k, k)); h = 1e-4
    f0 = loglik_clogit(b, groups_X, groups_y)
    for i in range(k):
        for j in range(k):
            bpp = b.copy(); bpp[i] += h; bpp[j] += h
            bpm = b.copy(); bpm[i] += h; bpm[j] -= h
            bmp = b.copy(); bmp[i] -= h; bmp[j] += h
            bmm = b.copy(); bmm[i] -= h; bmm[j] -= h
            H[i, j] = (loglik_clogit(bpp, groups_X, groups_y)
                       - loglik_clogit(bpm, groups_X, groups_y)
                       - loglik_clogit(bmp, groups_X, groups_y)
                       + loglik_clogit(bmm, groups_X, groups_y)) / (4 * h * h)
    se = np.sqrt(np.diag(np.linalg.pinv(H)))
    return b, -res.fun, se


def lr_test(ll_small, ll_big, df=1):
    stat = 2 * (ll_big - ll_small)
    return stat, 1 - stats.chi2.cdf(max(stat, 0.0), df)


# ------------------------------------------------------------------ main
def main():
    data = build()
    rids = sorted(set(d["rid"] for d in data))
    print(f"review_score.py {VERSION}")
    print("辞書サイズ:", json.dumps(lexicon_summary(), ensure_ascii=False))
    print(f"\nn_races={len(rids)}  n_horses={len(data)}  "
          f"top3={sum(d['top3'] for d in data)}  win={sum(d['win'] for d in data)}")
    sub_tsi = [d for d in data if d["tsia_z"] is not None]
    print(f"TSIあり: n_horses={len(sub_tsi)} "
          f"races={len(set(d['rid'] for d in sub_tsi))}")

    print("\nレビュースコア分布:")
    sc = [d["score"] for d in data]
    for v in range(min(sc), max(sc) + 1):
        c = sc.count(v)
        if c:
            print(f"  score={v:+d}: n={c:3d}  top3={sum(d['top3'] for d in data if d['score']==v):2d} "
                  f"win={sum(d['win'] for d in data if d['score']==v):2d}")
    print(f"  mean={np.mean(sc):.2f} sd={np.std(sc):.2f}")
    print(f"  ネガ語1つ以上: n={sum(1 for d in data if d['neg_n']>0)}")
    print(f"  相関 rev_z vs log(p_mkt): r="
          f"{np.corrcoef([d['rev_z'] for d in data],[math.log(d['p_mkt']) for d in data])[0,1]:+.3f}")
    print(f"  相関 rev_z vs tsi_avg5z (TSIあり): r="
          f"{np.corrcoef([d['rev_z'] for d in sub_tsi],[d['tsia_z'] for d in sub_tsi])[0,1]:+.3f}")

    # ---------------- Top3 logistic ----------------
    def run_top3(ds, feats, label):
        X = np.column_stack([np.ones(len(ds))] + [[d[f] for d in ds] for f in feats])
        y = np.array([d["top3"] for d in ds], float)
        off = np.array([math.log((3.0 / d["field"]) / (1 - 3.0 / d["field"])) for d in ds])
        b, ll, Hinv, p = fit_logit(X, y, off)
        se = robust_se(X, y, p, Hinv, [d["rid"] for d in ds])
        return b, ll, se, ["const"] + feats

    def run_win(ds, feats, label):
        gX, gy = [], []
        for rid in sorted(set(d["rid"] for d in ds)):
            rr = [d for d in ds if d["rid"] == rid]
            if not any(d["win"] for d in rr):
                continue
            gX.append(np.column_stack([[d[f] for d in rr] for f in feats]))
            gy.append([d["win"] for d in rr].index(1))
        b, ll, se = fit_clogit(gX, gy, len(feats))
        return b, ll, se, feats

    for d in data:
        d["lmkt"] = math.log(d["p_mkt"])
        d["logit_mkt"] = math.log(d["p_mkt"] / (1 - d["p_mkt"]))
        d["has_neg"] = 1.0 if d["neg_n"] >= 1 else 0.0
        d["pos_z"] = d["neg_z"] = d["sc_c"] = 0.0
    for rid in set(d["rid"] for d in data):
        rr = [d for d in data if d["rid"] == rid]
        for src, dst in (("pos_n", "pos_z"), ("neg_n", "neg_z")):
            v = np.array([d[src] for d in rr], float)
            sd = v.std()
            for d, x in zip(rr, v):
                d[dst] = (x - v.mean()) / sd if sd > 0 else 0.0
        m = np.mean([d["score"] for d in rr])
        for d in rr:
            d["sc_c"] = d["score"] - m

    print("\n" + "=" * 72)
    print("【0】市場を入れない(無条件)場合のレビュースコアの素の予測力")
    print("=" * 72)
    y0 = np.array([d["top3"] for d in data], float)
    off0 = np.array([math.log((3.0 / d["field"]) / (1 - 3.0 / d["field"])) for d in data])
    _, ll_null, _, _ = fit_logit(np.ones((len(data), 1)), y0, off0)
    for nm, feats in [("rev_zのみ", ["rev_z"]), ("has_negのみ", ["has_neg"]),
                      ("市場のみ", ["logit_mkt"])]:
        b, ll, se, cols = run_top3(data, feats, "")
        st, p = lr_test(ll_null, ll)
        print(f"  3着内 {nm:12s} logL={ll:9.4f} 2ΔlogL(vs定数のみ {ll_null:.3f})={st:6.3f} p={p:.4f}"
              f"  b={b[1]:+.4f} se={se[1]:.4f}")
    ll_w0 = -sum(math.log(len([d for d in data if d["rid"] == r]))
                 for r in rids if any(d["win"] for d in data if d["rid"] == r))
    for nm, feats in [("rev_zのみ", ["rev_z"]), ("has_negのみ", ["has_neg"]),
                      ("市場のみ", ["lmkt"])]:
        b, ll, se, cols = run_win(data, feats, "")
        st, p = lr_test(ll_w0, ll)
        print(f"  1着   {nm:12s} logL={ll:9.4f} 2ΔlogL(vs等確率 {ll_w0:.3f})={st:6.3f} p={p:.4f}"
              f"  b={b[0]:+.4f} se={se[0]:.4f}")
    print("  レビュースコアと市場人気:")
    for lo, hi, lab in [(-9, 0, "score<=0"), (1, 2, "score1-2"), (3, 9, "score>=3")]:
        s = [d for d in data if lo <= d["score"] <= hi]
        print(f"    {lab:9s} n={len(s):3d} 平均人気={np.mean([d['ninki'] for d in s]):5.2f} "
              f"単勝オッズ中央値={np.median([d['odds'] for d in s]):6.1f}")
    print(f"    相関 score vs 人気順 r="
          f"{np.corrcoef([d['score'] for d in data],[d['ninki'] for d in data])[0,1]:+.3f} "
          f"(負=高スコアほど人気)")

    print("\n" + "=" * 72)
    print("【1】3着内(複勝) ロジスティック回帰  offset=logit(3/N), SE=レースクラスタ頑健")
    print("=" * 72)
    results = {}
    for tag, ds, specs in [
        ("全頭 n=%d" % len(data), data,
         [("A 市場のみ", ["logit_mkt"]), ("C 市場+レビュー", ["logit_mkt", "rev_z"])]),
        ("TSIあり n=%d" % len(sub_tsi), sub_tsi,
         [("A 市場のみ", ["logit_mkt"]), ("B 市場+TSI", ["logit_mkt", "tsia_z"]),
          ("C 市場+TSI+レビュー", ["logit_mkt", "tsia_z", "rev_z"])]),
    ]:
        print(f"\n--- {tag} ---")
        prev = None
        for name, feats in specs:
            b, ll, se, cols = run_top3(ds, feats, name)
            z = b / se
            pv = 2 * (1 - stats.norm.cdf(np.abs(z)))
            print(f"{name:22s} logL={ll:9.4f}")
            for c, bb, ss, zz, pp in zip(cols, b, se, z, pv):
                print(f"     {c:12s} b={bb:+.4f} se={ss:.4f} z={zz:+.2f} p={pp:.4f}")
            if prev is not None:
                st, p = lr_test(prev, ll)
                print(f"     LR vs 前モデル: 2ΔlogL={st:.4f} p={p:.4f}")
            prev = ll
            results[(tag, name)] = (b, ll, se, cols)

    print("\n" + "=" * 72)
    print("【2】1着(単勝) 条件付きロジット(レース内)")
    print("=" * 72)
    for tag, ds, specs in [
        ("全頭 n=%d" % len(data), data,
         [("A 市場のみ", ["lmkt"]), ("C 市場+レビュー", ["lmkt", "rev_z"])]),
        ("TSIあり n=%d" % len(sub_tsi), sub_tsi,
         [("A 市場のみ", ["lmkt"]), ("B 市場+TSI", ["lmkt", "tsia_z"]),
          ("C 市場+TSI+レビュー", ["lmkt", "tsia_z", "rev_z"])]),
    ]:
        print(f"\n--- {tag} ---")
        prev = None
        for name, feats in specs:
            b, ll, se, cols = run_win(ds, feats, name)
            z = b / se
            pv = 2 * (1 - stats.norm.cdf(np.abs(z)))
            print(f"{name:22s} logL={ll:9.4f}")
            for c, bb, ss, zz, pp in zip(cols, b, se, z, pv):
                print(f"     {c:12s} b={bb:+.4f} se={ss:.4f} z={zz:+.2f} p={pp:.4f}")
            if prev is not None:
                st, p = lr_test(prev, ll)
                print(f"     LR vs 前モデル: 2ΔlogL={st:.4f} p={p:.4f}")
            prev = ll

    # ---------------- null (permutation) ----------------
    print("\n" + "=" * 72)
    print("【3】null検定: レビュースコアをレース内でシャッフル (1000回)")
    print("=" * 72)
    rng = random.Random(RNG_SEED)
    NPERM = 1000

    # レビュー由来の列を「まとめて」レース内で別の馬に付け替える
    #  = 「レース内で調教レビューをランダムな馬に割り当てたら何が起きるか」の帰無分布
    REV_COLS = ["rev_z", "sc_c", "has_neg", "pos_z", "neg_z", "score", "neg_n", "pos_n"]

    def perm_data(ds):
        out = [dict(d) for d in ds]
        for rid in set(d["rid"] for d in out):
            idx = [i for i, d in enumerate(out) if d["rid"] == rid]
            sh = idx[:]; rng.shuffle(sh)
            snap = [{c: out[i].get(c) for c in REV_COLS} for i in idx]
            for i, s in zip(sh, snap):
                out[i].update(s)
        return out

    def perm_test(kind, tag, ds, base_feats, addf):
        fitf = run_top3 if kind == "top3" else run_win
        r0 = fitf(ds, base_feats, "")
        ll0 = r0[1]
        b1, ll1, se1, _ = fitf(ds, base_feats + [addf], "")
        obs_lr = 2 * (ll1 - ll0); obs_b = b1[-1]
        cnt_lr = cnt_b = 0
        for _ in range(NPERM):
            pd_ = perm_data(ds)
            bp, llp, _, _ = fitf(pd_, base_feats + [addf], "")
            if 2 * (llp - ll0) >= obs_lr - 1e-9:
                cnt_lr += 1
            if abs(bp[-1]) >= abs(obs_b) - 1e-9:
                cnt_b += 1
        print(f"{tag:26s} {addf:8s} 観測b={obs_b:+.4f} 2ΔlogL={obs_lr:6.3f} | "
              f"p_perm(LR)={(cnt_lr+1)/(NPERM+1):.4f}  p_perm(|b|)={(cnt_b+1)/(NPERM+1):.4f}")

    perm_test("top3", "全頭 3着内", data, ["logit_mkt"], "rev_z")
    perm_test("top3", "全頭 3着内", data, ["logit_mkt"], "has_neg")
    perm_test("top3", "TSIあり 3着内", sub_tsi, ["logit_mkt", "tsia_z"], "rev_z")
    perm_test("win", "全頭 1着", data, ["lmkt"], "rev_z")
    perm_test("win", "全頭 1着", data, ["lmkt"], "has_neg")
    perm_test("win", "TSIあり 1着", sub_tsi, ["lmkt", "tsia_z"], "rev_z")

    # leave-one-race-out: has_neg(1着)の安定性
    print("\n[頑健性] has_neg(1着,全頭)の係数 -- 1レースずつ除いた場合:")
    base_b = run_win(data, ["lmkt", "has_neg"], "")[0][-1]
    print(f"  全13R: b={base_b:+.3f}")
    worst = []
    for rid in rids:
        sub = [d for d in data if d["rid"] != rid]
        bb = run_win(sub, ["lmkt", "has_neg"], "")[0][-1]
        worst.append((abs(bb - base_b), rid, bb))
    worst.sort(reverse=True)
    for delta, rid, bb in worst[:4]:
        print(f"  -{rid} を除く: b={bb:+.3f} (変化 {bb-base_b:+.3f})")

    # -------- 追加: カテゴリ別特徴 / ネガダミー を市場条件下で直接検定 --------
    print("\n" + "=" * 72)
    print("【1b】仕様違い(頑健性): 市場を条件にした上での各レビュー特徴")
    print("=" * 72)
    b0, ll0, _, _ = run_top3(data, ["logit_mkt"], "")
    print(f"基準A(3着内, 全頭) logL={ll0:.4f}")
    for name, feats in [("+ rev_z (z化スコア)", ["logit_mkt", "rev_z"]),
                        ("+ sc_c (生スコア・中心化)", ["logit_mkt", "sc_c"]),
                        ("+ has_neg (ネガ語ダミー)", ["logit_mkt", "has_neg"]),
                        ("+ pos_z / neg_z 分離", ["logit_mkt", "pos_z", "neg_z"])]:
        b, ll, se, cols = run_top3(data, feats, "")
        z = b / se; pv = 2 * (1 - stats.norm.cdf(np.abs(z)))
        st, p = lr_test(ll0, ll, len(feats) - 1)
        extra = "  ".join(f"{c}: b={bb:+.3f} se={ss:.3f} p={pp:.3f}"
                          for c, bb, ss, pp in list(zip(cols, b, se, pv))[2:])
        print(f"{name:26s} logL={ll:9.4f}  2ΔlogL={st:5.3f} p={p:.4f} | {extra}")

    bw0, llw0, _ = run_win(data, ["lmkt"], "")[:3]
    print(f"\n基準A(1着, 全頭) logL={llw0:.4f}")
    for name, feats in [("+ rev_z", ["lmkt", "rev_z"]),
                        ("+ sc_c", ["lmkt", "sc_c"]),
                        ("+ has_neg", ["lmkt", "has_neg"]),
                        ("+ pos_z / neg_z 分離", ["lmkt", "pos_z", "neg_z"])]:
        b, ll, se, cols = run_win(data, feats, "")
        z = b / se; pv = 2 * (1 - stats.norm.cdf(np.abs(z)))
        st, p = lr_test(llw0, ll, len(feats) - 1)
        extra = "  ".join(f"{c}: b={bb:+.3f} se={ss:.3f} p={pp:.3f}"
                          for c, bb, ss, pp in list(zip(cols, b, se, pv))[1:])
        print(f"{name:26s} logL={ll:9.4f}  2ΔlogL={st:5.3f} p={p:.4f} | {extra}")

    # -------- 残差(市場モデルAで説明できない分)をレビュー水準で層別 --------
    print("\n" + "=" * 72)
    print("【1c】市場モデルA(3着内)の予測に対する実績の差 = レビューの増分の可視化")
    print("=" * 72)
    Xa = np.column_stack([np.ones(len(data)), [d["logit_mkt"] for d in data]])
    offa = np.array([math.log((3.0 / d["field"]) / (1 - 3.0 / d["field"])) for d in data])
    pa = 1 / (1 + np.exp(-(Xa @ b0 + offa)))
    for d, p_ in zip(data, pa):
        d["p_hat_A"] = p_
    print(f"{'層':22s} {'n':>4s} {'実績3着内':>7s} {'モデルA期待':>9s} {'差':>7s}")
    for label, sel in [("score <= 0", lambda d: d["score"] <= 0),
                       ("score 1-2", lambda d: 1 <= d["score"] <= 2),
                       ("score >= 3", lambda d: d["score"] >= 3),
                       ("ネガ語あり", lambda d: d["neg_n"] >= 1),
                       ("ネガ語なし", lambda d: d["neg_n"] == 0),
                       ("rev_z <= -1", lambda d: d["rev_z"] <= -1),
                       ("rev_z >= +1", lambda d: d["rev_z"] >= 1)]:
        s = [d for d in data if sel(d)]
        if not s: continue
        act = sum(d["top3"] for d in s); exp = sum(d["p_hat_A"] for d in s)
        print(f"{label:22s} {len(s):4d} {act:7d} {exp:9.2f} {act-exp:+7.2f}"
              + ("  ※n<30 参考" if len(s) < 30 else ""))

    print("\nネガ語ありで実際に馬券圏内だった馬:")
    for d in data:
        if d["neg_n"] >= 1 and d["top3"]:
            print(f"  {d['rid']} {d['num']:>2} {d['name']:<12} {d['rank']}着 "
                  f"{d['ninki']}人気 odds={d['odds']} score={d['score']:+d} neg={d['neg']}")

    # ---------------- practical rules ----------------
    print("\n" + "=" * 72)
    print("【4】実務ルールの効果")
    print("=" * 72)

    def block(name, sel):
        s = [d for d in data if sel(d)]
        if not s:
            print(f"{name}: 該当なし"); return
        n = len(s)
        t3 = sum(d["top3"] for d in s); w = sum(d["win"] for d in s)
        exp_w = sum(d["p_mkt"] for d in s)
        pay_w = sum(d["pay_win"] or 0 for d in s)
        pay_p = sum(d["pay_pla"] or 0 for d in s)
        print(f"{name:34s} n={n:3d} 1着={w:2d}({w/n*100:5.1f}%) 市場期待1着={exp_w:5.2f} "
              f"3着内={t3:2d}({t3/n*100:5.1f}%) 単ROI={pay_w/(100*n)*100:6.1f}% 複ROI={pay_p/(100*n)*100:6.1f}%"
              + ("  ※n<30 参考値" if n < 30 else ""))

    block("全頭", lambda d: True)
    block("ネガ語あり(neg_n>=1)", lambda d: d["neg_n"] >= 1)
    block("ネガ語なし(neg_n==0)", lambda d: d["neg_n"] == 0)
    block("score <= -1", lambda d: d["score"] <= -1)
    block("score == 0", lambda d: d["score"] == 0)
    block("score 1-2", lambda d: 1 <= d["score"] <= 2)
    block("score >= 3", lambda d: d["score"] >= 3)
    block("rev_z >= +1", lambda d: d["rev_z"] >= 1.0)
    block("rev_z <= -1", lambda d: d["rev_z"] <= -1.0)
    print()
    block("人気1-3番 かつ ネガ語あり", lambda d: (d["ninki"] or 99) <= 3 and d["neg_n"] >= 1)
    block("人気1-3番 かつ ネガ語なし", lambda d: (d["ninki"] or 99) <= 3 and d["neg_n"] == 0)
    block("人気4番以下 かつ rev_z>=+1", lambda d: (d["ninki"] or 99) >= 4 and d["rev_z"] >= 1.0)
    print()
    print("『ネガ語が付いた馬を消す』= 上位人気からの除外効果:")
    for k in (1, 2, 3, 5):
        s = [d for d in data if (d["ninki"] or 99) <= k]
        sn = [d for d in s if d["neg_n"] >= 1]
        if not sn:
            print(f"  人気{k}番以内: 除外該当 0頭"); continue
        print(f"  人気{k}番以内 n={len(s)}: 除外該当={len(sn)}頭 "
              f"うち3着内={sum(d['top3'] for d in sn)} 1着={sum(d['win'] for d in sn)} "
              f"(残す側 n={len(s)-len(sn)} 3着内率={sum(d['top3'] for d in s if d['neg_n']==0)/max(1,len(s)-len(sn))*100:.1f}%) "
              f"※n<30 参考値")

    # ---------------- exploratory per-term ----------------
    print("\n" + "=" * 72)
    print("【5】語彙別(探索的・多重比較未補正。参考値として読むこと)")
    print("=" * 72)
    from collections import defaultdict
    terms = defaultdict(list)
    for d in data:
        for t in d["pos"]:
            terms["POS:" + t].append(d)
        for t in d["neg"]:
            terms["NEG:" + t].append(d)
        for t in d["cond"]:
            terms["CND:" + t].append(d)
    base_t3 = sum(d["top3"] for d in data) / len(data)
    rows = []
    for t, ds in terms.items():
        if len(ds) < 8:
            continue
        n = len(ds)
        t3 = sum(d["top3"] for d in ds)
        exp3 = sum(d["p_mkt"] for d in ds) * 1.0    # 参考: 単勝implied合計
        pay_p = sum(d["pay_pla"] or 0 for d in ds)
        # 二項検定(全体基準率に対して)
        p = stats.binomtest(t3, n, base_t3).pvalue
        rows.append((t, n, t3, t3 / n, pay_p / (100 * n) * 100, p))
    rows.sort(key=lambda r: -r[3])
    print(f"(全体の3着内率={base_t3*100:.1f}%, 出現8頭以上の語のみ)")
    print(f"{'語':28s} {'n':>4s} {'3着内':>5s} {'率':>7s} {'複ROI':>8s} {'二項p':>7s}")
    for t, n, t3, r, roi, p in rows:
        print(f"{t:28s} {n:4d} {t3:5d} {r*100:6.1f}% {roi:7.1f}% {p:7.3f}")

    # 保存
    with open("review_eval_rows.json", "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in d.items() if k != "grp"} for d in data],
                  f, ensure_ascii=False, indent=1)
    print("\nrows -> review_eval_rows.json")


if __name__ == "__main__":
    main()
