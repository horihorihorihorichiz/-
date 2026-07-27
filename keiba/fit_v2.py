# -*- coding: utf-8 -*-
"""Ver.2モデル（Ver.101 B1）: 生特徴量の条件付きPlackett-Luceモデル。
   現行モデル(手作り点数の順位圧縮)が捨てている情報——自前指数の「実差」・騎手率・
   着差・通過位置など——をレース内z標準化してそのまま学習する。
   現行WAvgも1特徴量として含む(現行の知識を包含した上で上積みを測る)。

   ゲート: ホールドアウト(test)の3着内PL-NLLで現行スコアに勝った時だけ params_v2.json を書く。

   usage: python3 fit_v2.py [--test 20260704,20260705,20260711,20260712] [--l2 0.05] [--write]
"""
import argparse, glob, json, math, os, sys
import calc
import course

FEATS = ["idx_mean3", "idx_last", "idx_best", "wavg", "j_top3", "t_top3",
         "fin_frac", "agari_best", "days_log", "kinryo", "wchg",
         "corner_frac", "dist_chg", "csi", "n_runs",
         # U2統合(7/14 エージェント実験の勝ち特徴12: features2.py経由)
         "cond_perf", "db_best", "exact_dist_place", "surf_switch", "wet_apt",
         "agari_dist_match", "agari_mean3_rel", "agari_close_q",
         "fin_best2", "layoff_lastfin", "classup_lastgood", "field_chg"]

# ── V4追加(2026-07-26) ────────────────────────────────────────────────
# レース内z標準化を「しない」生特徴。z化すると枠番は単なる馬番の順序に潰れ、
# 「外枠かどうか」という絶対的な意味が消えるため生値のまま渡す。
RAW_FEATS = ["waku", "waku_rel", "umaban_rel", "wet_x_baba", "waku_x_dirt"]
# レース単位で全頭共通の文脈。z化すると全頭0になるので生値のまま渡す。
CTX_FEATS = ["field", "baba_today", "today_vg", "is_dirt"]

BABA_IDX = {"良": 0, "稍": 1, "稍重": 1, "重": 2, "不": 3, "不良": 3}

# ── V5追加(2026-07-27 強い馬当て強化) ────────────────────────────────
# 全て「保存済みの過去走フィールドだけ」から計算する＝学習とライブで完全同一(統一原則)。
# None耐性: 該当走が無ければNone→レース内zで0(平均扱い)に落ちる。
EXTRA_FEATS = ["idx_trend", "fin_w", "class_fin", "bigfield_fin", "corner_gain", "wet_fin"]


def extra_strength(h, race):
    """強い馬当てのための追加特徴。
       idx_trend   : 直近指数 − 2-5走前平均(上昇ムード)
       fin_w       : 着順割合のrecency加重平均(直近ほど重い)
       class_fin   : 今日と同等以上のクラスでの着順割合(格上での実績だけを見る)
       bigfield_fin: 多頭数(14頭+)での着順割合(混戦での強さ)
       corner_gain : 4角→ゴールの追い上げ幅(展開に頼らない末脚)
       wet_fin     : 道悪(baba_idx>=1)での着順割合 ※7/27のbaba_idx遡及補完で学習側も利用可能"""
    rs = h.get("races", [])
    f = {}
    tsis = [r.get("tsi") for r in rs[:5]]
    later = [t for t in tsis[1:] if t is not None]
    f["idx_trend"] = (tsis[0] - sum(later)/len(later)) if (tsis and tsis[0] is not None
                                                          and later) else None
    ws = vs = 0.0
    for j, r in enumerate(rs[:5]):
        if r.get("finish") and r.get("field"):
            w = 1.0/(1+j)
            ws += w
            vs += w * r["finish"]/max(r["field"], 1)
    f["fin_w"] = -(vs/ws) if ws else None
    tt = race.get("today_tier")
    cls = [r["finish"]/max(r["field"], 1) for r in rs
           if r.get("finish") and r.get("field") and r.get("tier") is not None
           and tt is not None and r["tier"] <= tt]
    f["class_fin"] = -(sum(cls)/len(cls)) if cls else None
    big = [r["finish"]/max(r["field"], 1) for r in rs
           if r.get("finish") and r.get("field") and r["field"] >= 14]
    f["bigfield_fin"] = -(sum(big)/len(big)) if big else None
    cg = [(r["corner4"] - r["finish"])/max(r["field"], 1) for r in rs[:3]
          if r.get("corner4") and r.get("finish") and r.get("field")]
    f["corner_gain"] = sum(cg)/len(cg) if cg else None
    wet = [r["finish"]/max(r["field"], 1) for r in rs
           if r.get("finish") and r.get("field") and (r.get("baba_idx") or 0) >= 1]
    f["wet_fin"] = -(sum(wet)/len(wet)) if wet else None
    return f


def race_ctx(race):
    """レース単位の生特徴(全頭共通)"""
    return {
        "field": float(race.get("field") or len(race.get("horses") or []) or 0),
        "baba_today": float(BABA_IDX.get((race.get("baba") or "").strip(), 0)),
        "today_vg": float(race.get("today_vg") or 3),
        "is_dirt": 1.0 if (race.get("surface") or "") == "ダ" else 0.0,
    }


def raw_extra(num, ff, ctx):
    """馬ごとの生特徴(枠番系・今日の馬場との交互作用)。
       ff は horse_feats() の生値(z化前)、ctx は race_ctx()。"""
    field = int(ctx["field"]) or 1
    n = int(num)
    waku = course.jra_waku(n, field) if 1 <= n <= field else 0
    wet = ff.get("wet_apt")
    wet = 0.0 if wet is None else float(wet)
    waku_rel = (waku - 1) / 7.0 if waku else 0.5
    return {
        "waku": float(waku),
        "waku_rel": waku_rel,
        "umaban_rel": (n - 1) / max(field - 1, 1),
        # 今日が道悪なほど、その馬の道悪実績が効く（良の日は0で無効化される）
        "wet_x_baba": wet * ctx["baba_today"],
        # 芝は内有利・ダは外有利のFSI知見を1本の交互作用で表す
        "waku_x_dirt": waku_rel * (1.0 if ctx["is_dirt"] else -1.0),
    }


def build_row(r, n, v4=True, extra=False):
    """1頭分の特徴行。v4=False なら V3 と同じ [FEATS..., 頭数] を返す。
       extra=True で V5 の強さ特徴(EXTRA_FEATS・レース内z済み)を追加。"""
    base = [r["X"][k][n] for k in FEATS]
    if not v4:
        return base + [float(len(r["ns"]))]
    row = (base + [r["raw_extra"][n][k] for k in RAW_FEATS]
           + [r["ctx"][k] for k in CTX_FEATS])
    if extra:
        row += [r["X"][k][n] for k in EXTRA_FEATS]
    return row


def feat_names(v4=True, extra=False):
    if not v4:
        return FEATS + ["field"]
    return FEATS + RAW_FEATS + CTX_FEATS + (EXTRA_FEATS if extra else [])


def z_in_race(vals):
    """レース内z標準化。Noneは0(平均)扱い"""
    xs = [v for v in vals.values() if v is not None]
    if len(xs) < 2:
        return {k: 0.0 for k in vals}
    m = sum(xs)/len(xs)
    sd = (sum((x-m)**2 for x in xs)/len(xs))**0.5 or 1.0
    return {k: ((v-m)/sd if v is not None else 0.0) for k, v in vals.items()}


def horse_feats(h, race):
    rs = h.get("races", [])
    tsis = [r.get("tsi") for r in rs[:5] if r.get("tsi") is not None]
    tsis_sorted = sorted(tsis, reverse=True)
    f = {}
    f["idx_mean3"] = sum(tsis_sorted[:3])/len(tsis_sorted[:3]) if tsis_sorted else None
    f["idx_last"] = rs[0].get("tsi") if rs else None
    f["idx_best"] = tsis_sorted[0] if tsis_sorted else None
    f["n_runs"] = min(len(rs), 9)
    f["fin_frac"] = -(rs[0]["finish"]/max(rs[0]["field"], 1)) if rs else None
    ag = [r.get("agari") for r in rs[:3] if r.get("agari")]
    f["agari_best"] = -min(ag) if ag else None
    f["days_log"] = math.log1p(h.get("last_race_days", 30))
    f["kinryo"] = h.get("kinryo")
    f["wchg"] = h.get("weight_change") or 0
    cf = [r["corner4"]/max(r["field"], 1) for r in rs[:3] if r.get("corner4")]
    f["corner_frac"] = -sum(cf)/len(cf) if cf else None
    f["dist_chg"] = -abs(race.get("distance", 1600) - rs[0]["dist"])/race.get("distance", 1600) if rs else None
    f["csi"] = h.get("csi", 0)
    import features2   # 遅延import(循環回避)。U2統合の12特徴を合流
    f.update(features2.extra_feats(h, race))
    return f


def load_dataset(histdir, featdir):
    ds = []
    for f in sorted(glob.glob(os.path.join(histdir, "*.json"))):
        rid = os.path.basename(f)[:-5]
        try:
            d = json.load(open(f, encoding="utf-8"))
            res = calc.run(d["race"])
        except Exception:
            continue
        top3 = [o["num"] for o in d["result"].get("order", [])
                if o.get("rank") in ("1", "2", "3")]
        if len(top3) < 3:
            continue
        wavg = {r["num"]: r["wavg"] for r in res["rows"]}
        jf, tf = {}, {}
        fp = os.path.join(featdir, f"{rid}.json")
        if os.path.exists(fp):
            fd = json.load(open(fp, encoding="utf-8"))
            jf = fd.get("jockey", {})
            tf = fd.get("trainer", {})
        odds = {o["num"]: o["odds"] for o in d["result"].get("order", []) if o.get("odds")}
        raw = {}
        for h in d["race"]["horses"]:
            ff = horse_feats(h, d["race"])
            ff["wavg"] = wavg.get(h["num"])
            j = jf.get(str(h["num"]))
            ff["j_top3"] = j["j_top3"] if j else None
            t = tf.get(str(h["num"]))
            ff["t_top3"] = t["t_top3"] if t else None
            raw[h["num"]] = ff
        if any(t not in raw for t in top3) or len(raw) < 5:
            continue
        for h in d["race"]["horses"]:
            raw[h["num"]].update(extra_strength(h, d["race"]))
        X = {k: z_in_race({n: raw[n].get(k) for n in raw}) for k in FEATS + EXTRA_FEATS}
        ctx = race_ctx(d["race"])
        rx = {n: raw_extra(n, raw[n], ctx) for n in raw}
        ds.append(dict(X=X, ns=list(raw.keys()), top3=top3, odds=odds,
                       payout=d["result"].get("payout") or {},
                       date=d.get("date", ""), rid=rid,
                       ctx=ctx, raw_extra=rx,
                       surface=d["race"].get("surface"),
                       dist=d["race"].get("distance"),
                       tier=d["race"].get("today_tier"),
                       baba=d["race"].get("baba"),
                       venue=d["race"].get("venue")))
    return ds


def scores(r, w):
    return {n: sum(w[i]*r["X"][k][n] for i, k in enumerate(FEATS)) for n in r["ns"]}


def pl_nll_grad(ds, w, l2):
    nll = 0.0
    g = [0.0]*len(FEATS)
    n_obs = 0
    for r in ds:
        s = scores(r, w)
        alive = list(s.keys())
        for pos in range(3):
            winner = r["top3"][pos]
            mx = max(s[n] for n in alive)
            e = {n: math.exp(s[n]-mx) for n in alive}
            Z = sum(e.values())
            p = {n: e[n]/Z for n in alive}
            nll += -math.log(max(p[winner], 1e-12))
            n_obs += 1
            for i, k in enumerate(FEATS):
                g[i] += -(r["X"][k][winner] - sum(p[n]*r["X"][k][n] for n in alive))
            alive.remove(winner)
    for i in range(len(FEATS)):
        g[i] = g[i]/n_obs + 2*l2*w[i]
    return nll/n_obs + l2*sum(x*x for x in w), g


def fit(train, l2, iters=300, lr=0.3):
    w = [0.0]*len(FEATS)
    m = [0.0]*len(FEATS)
    for it in range(iters):
        nll, g = pl_nll_grad(train, w, l2)
        for i in range(len(FEATS)):
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
        if it % 100 == 0:
            print(f"  iter{it}: NLL={nll:.4f}", file=sys.stderr)
    return w


def eval_nll(ds, prob_fn):
    tot = n = 0
    for r in ds:
        p = prob_fn(r)
        alive = dict(p)
        for pos in range(3):
            winner = r["top3"][pos]
            Z = sum(alive.values())
            tot += -math.log(max(alive[winner]/Z, 1e-12))
            n += 1
            alive.pop(winner)
    return tot/n if n else float("inf")


def probs_v2(r, w):
    s = scores(r, w)
    mx = max(s.values())
    e = {n: math.exp(s[n]-mx) for n in s}
    Z = sum(e.values())
    return {n: e[n]/Z for n in e}


def probs_v1(r, T):
    wv = {n: 0.0 for n in r["ns"]}
    # 現行スコア=wavg特徴量そのもの(z化前の生値はdatasetに残していないためz値×温度で代替)
    for n in r["ns"]:
        wv[n] = r["X"]["wavg"][n]
    e = {n: math.exp(wv[n]*T) for n in wv}
    Z = sum(e.values())
    return {n: e[n]/Z for n in e}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--featdir", default="hist_feat")
    ap.add_argument("--test", default="20260704,20260705,20260711,20260712")
    ap.add_argument("--l2", type=float, default=0.05)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ds = load_dataset(a.histdir, a.featdir)
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: 全{len(ds)}R (train {len(train)} / test {len(test)})")

    w = fit(train, a.l2)
    print("\n学習した重み（レース内z標準化後の生特徴量）:")
    for k, v in zip(FEATS, w):
        print(f"  {k:12s} {v:+.3f}")

    # 現行スコア(wavg単独)の最良温度をtrainで探して公平に比較
    bestT = min([0.4, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0],
                key=lambda T: eval_nll(train, lambda r, T=T: probs_v1(r, T)))
    print(f"\n── 3着内PL-NLL（小さいほど良い / 現行=wavg単独の最良温度{bestT}） ──")
    ok = True
    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        v1 = eval_nll(dset, lambda r: probs_v1(r, bestT))
        v2 = eval_nll(dset, lambda r: probs_v2(r, w))
        mark = "改善" if v2 < v1 else "改善なし"
        print(f"  {name}: 現行 {v1:.4f} → Ver.2 {v2:.4f} （{mark}）")
        if name == "test" and v2 >= v1:
            ok = False

    if a.write:
        if not ok:
            print("\n⚠️ ホールドアウトで改善しなかったため params_v2.json は書かない。")
            return
        json.dump(dict(feats=FEATS, weights=[round(x, 4) for x in w],
                       note="fit_v2 Ver.101 B1"),
                  open("params_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nparams_v2.json に保存した。")


if __name__ == "__main__":
    main()
