# -*- coding: utf-8 -*-
"""place_seg.py — PLACE_SEG_PROTOCOL.md の実装。

問い:「セグメント別学習が失敗したのは *1着当て* という土俵が悪かったからで、
       *3着内* を目的変数にすればセグメント専用が汎用を上回るのではないか」

  SPECIALIST実験 = 1着(LambdaRank) × セグメント別  → 11中10で不成立
  PLACE実験      = 3着内(binary)   × 汎用          → α_place が史上初めて正
  本実験         = 3着内(binary)   × セグメント別  ← 未検証の組合せ

設計（事前登録書どおり・実行前凍結）:
  - 専用モデルは汎用と同一特徴・同一ハイパラ・同一手順（fit_place.PLACE_VARIANTS["v8place"] /
    fit_place.train_place_fold をそのまま呼ぶ）。差は「学習データをセグメントに絞る」ことだけ。
  - ベースライン: 既存 place_preds_v8place.jsonl（主）/ place_preds_v3place.jsonl（副・参考）。
  - S-A 場10 / S-B 馬場×距離帯6 / S-C 場×馬場20 = 36セグメント。
  - fold=月次・start 202403・MINE〜202602 / VALIDATE 202603-05 / CONFIRM 202606-08。
  - fold時点のセグメント学習データ<800頭 → 「専用なし=汎用流用」と記録。
  - α_place: fold月 m の係数は「当該セグメントの m より前の月」だけで推定（最低200R）。
    Δα = α_spec − α_gen（同一レース集合・同一市場側・q_model の列だけ差し替え）。

既存経路（fit_place.py / place_run.py / place_eval.py / wf_compare.py / fit_v2.py）は
**1行も変更していない**。本ファイルはそれらを読むだけ。

usage:
  python3 place_seg.py run                 # WF実行 → place_preds_seg_{sa,sb,sc}.jsonl
  python3 place_seg.py eval                # α_place / 複勝ROI / 参考EV → place_seg_result.json
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

import wf_compare as W
import fit_place as FP
import place_eval as PE

VARIANT = "v8place"                    # 専用モデルの学習設定（汎用ベースラインと同一）
BASE_MAIN = "place_preds_v8place.jsonl"
BASE_SUB = "place_preds_v3place.jsonl"
START_FOLD = "202403"
MIN_HORSES = 800                       # 事前登録: これ未満は専用なし=汎用流用
MIN_ALPHA_RACES = 200                  # 事前登録: α推定に要する当該セグメントの学習レース数
VENUES = ["札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉"]


# ── セグメント定義（凍結） ──────────────────────────────────────────
def band(d):
    d = d or 0
    return "短" if d < 1400 else ("ﾏｲﾙ" if d < 1800 else "中長")


def seg_a(r):
    return r["venue"]


def seg_b(r):
    return f"{r['surface']}{band(r['dist'])}"


def seg_c(r):
    return f"{r['venue']}{r['surface']}"


SCHEMES = {"sa": seg_a, "sb": seg_b, "sc": seg_c}
SCHEME_JP = {"sa": "S-A 場(10)", "sb": "S-B 馬場×距離帯(6)", "sc": "S-C 場×馬場(20)"}


def split_of(m):
    return PE.split_of(m)


# ── run ────────────────────────────────────────────────────────────
def load_base(path):
    base = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        base[d["rid"]] = d
    return base


def run():
    t0 = time.time()
    ds = W.load_ds(False, v8=True)
    base = load_base(BASE_MAIN)
    sp = FP.PLACE_VARIANTS[VARIANT]
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= START_FOLD]
    print(f"dataset {len(ds)}R / baseline {len(base)}R / folds {folds[0]}..{folds[-1]} "
          f"({len(folds)}) / variant={VARIANT} {len(FP.PLACE_VARIANTS[VARIANT])}spec",
          flush=True)

    fh = {sc: open(f"place_preds_seg_{sc}.jsonl", "w", encoding="utf-8") for sc in SCHEMES}
    n_train = 0
    fallback = []                       # (month, scheme, seg, races, horses)
    guard = []
    for m in folds:
        train_all = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train_all) < 400 or not fold:
            print(f"[{m}] skip (train={len(train_all)})", flush=True)
            continue
        tm = time.time()
        nfb = 0
        for sc, fn in SCHEMES.items():
            by_seg = defaultdict(list)
            for r in fold:
                by_seg[fn(r)].append(r)
            for seg, fold_rs in sorted(by_seg.items()):
                tr = [r for r in train_all if fn(r) == seg]
                horses = sum(len(r["ns"]) for r in tr)
                n_val = max(50, len(tr) // 10)
                ok = horses >= MIN_HORSES and len(tr) - n_val >= 1
                if horses >= MIN_HORSES and not ok:
                    guard.append((m, sc, seg, len(tr), horses))
                if ok:
                    model = FP.train_place_fold(tr, sp)
                    n_train += 1
                    preds = [FP.predict_place(model, r, sp) for r in fold_rs]
                else:
                    preds = None
                    fallback.append((m, sc, seg, len(tr), horses))
                    nfb += len(fold_rs)
                for i, r in enumerate(fold_rs):
                    b = base[r["rid"]]
                    if preds is None:
                        order, scores = b["order"], b["scores"]
                    else:
                        s = preds[i]
                        order = sorted(s, key=lambda x: -s[x])
                        scores = [round(s[n], 6) for n in order]
                    fh[sc].write(json.dumps(dict(
                        rid=r["rid"], month=m, date=r["date"], segment=seg,
                        spec_used=bool(preds is not None),
                        train_races=len(tr), train_horses=horses,
                        order=order, scores=scores,
                        odds=r["odds"], top3=r["top3"], payout=r.get("payout") or {},
                        surface=r["surface"], dist=r["dist"], tier=r["tier"],
                        baba=r["baba"], venue=r["venue"], field=len(r["ns"])),
                        ensure_ascii=False) + "\n")
            fh[sc].flush()
        print(f"[{m}] {len(fold)}R×3scheme 済 (学習累計 {n_train} / 当月汎用流用 {nfb}行 / "
              f"{time.time()-tm:.0f}s)", flush=True)
    for sc in SCHEMES:
        fh[sc].close()
    json.dump(dict(n_train=n_train, fallback=fallback, guard=guard),
              open("place_seg_runlog.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n総学習回数 {n_train} / 汎用流用(セグメント×月) {len(fallback)}件 / "
          f"分割不能ガード {len(guard)}件", flush=True)
    print(f"done ({(time.time()-t0)/60:.1f}min)", flush=True)


# ── eval ───────────────────────────────────────────────────────────
def load_with_seg(path):
    """PE.load_ledger と同じ取捨で読み、segment / spec_used を付ける。"""
    races, dropped = PE.load_ledger(path)
    meta = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        meta[d["rid"]] = (d.get("segment", "ALL"), bool(d.get("spec_used", True)))
    for r in races:
        r["segment"], r["spec_used"] = meta[r["rid"]]
    return races, dropped


def alpha_fit(races, key):
    """key='q_model' の列で α を推定（PE.stack と同一形）。返り値 (alpha, se, beta)。"""
    X = np.concatenate([np.stack([PE._logit(r[key]), PE._logit(r["q_market"]),
                                  np.ones(len(r["ns"]))], axis=1) for r in races])
    y = np.concatenate([r["y"] for r in races])
    g = np.concatenate([np.full(len(r["ns"]), i) for i, r in enumerate(races)])
    th = PE.fit_logit(X, y)
    se = PE.cluster_se(X, y, g, th)
    return float(th[0]), float(se[0]), float(th[1]), th


def logloss(races, key, th):
    X = np.concatenate([np.stack([PE._logit(r[key]), PE._logit(r["q_market"]),
                                  np.ones(len(r["ns"]))], axis=1) for r in races])
    y = np.concatenate([r["y"] for r in races])
    p = PE._sig(X @ th)
    return float(-(y * np.log(np.clip(p, 1e-12, None))
                   + (1 - y) * np.log(np.clip(1 - p, 1e-12, None))).sum()), len(y)


def attach_gen(races, gen_main, gen_sub):
    """汎用の q_model を **馬番で対応付けて** セグメント側の並びに揃える。
       （汎用とセグメント専用では order が違うので、位置で貼ると壊れる）"""
    keep = []
    for r in races:
        g = gen_main.get(r["rid"])
        if g is None:
            continue
        gm = dict(zip(g["ns"], g["q_model"]))
        if any(h not in gm for h in r["ns"]):
            continue
        r["q_gen"] = np.array([gm[h] for h in r["ns"]], dtype=float)
        gs = gen_sub.get(r["rid"])
        if gs is not None:
            g3 = dict(zip(gs["ns"], gs["q_model"]))
            r["q_gen3"] = (np.array([g3[h] for h in r["ns"]], dtype=float)
                           if all(h in g3 for h in r["ns"]) else None)
        else:
            r["q_gen3"] = None
        keep.append(r)
    return keep


def eval_scheme(races):
    """1スキームを評価。races は prep + attach_gen 済み。"""
    have_sub = all(r["q_gen3"] is not None for r in races)

    by_seg = defaultdict(list)
    for r in races:
        by_seg[r["segment"]].append(r)

    out = {}
    for seg, rs in sorted(by_seg.items()):
        months = sorted({r["month"] for r in rs})
        by_m = {m: [r for r in rs if r["month"] == m] for m in months}
        folds = {}
        for mi, m in enumerate(months):
            tr = [r for mm in months[:mi] for r in by_m[mm]]
            row = dict(split=split_of(m), train_races=len(tr),
                       n=len(by_m[m]),
                       spec_used=sum(1 for r in by_m[m] if r["spec_used"]))
            if len(tr) < MIN_ALPHA_RACES:
                row["alpha_ok"] = False
            else:
                a_s, se_s, b_s, th_s = alpha_fit(tr, "q_model")
                a_g, se_g, b_g, th_g = alpha_fit(tr, "q_gen")
                row.update(alpha_ok=True,
                           a_spec=round(a_s, 4), se_spec=round(se_s, 4),
                           a_gen=round(a_g, 4), se_gen=round(se_g, 4),
                           d_alpha=round(a_s - a_g, 4),
                           beta_spec=round(b_s, 3))
                if have_sub:
                    a_3, se_3, _, _ = alpha_fit(tr, "q_gen3")
                    row["a_gen_v3"] = round(a_3, 4)
                # out-of-sample 対数損失（fold月・1頭あたり・参考）
                ls, ns = logloss(by_m[m], "q_model", th_s)
                lg, _ = logloss(by_m[m], "q_gen", th_g)
                row["oos_spec"] = round(ls / ns, 6)
                row["oos_gen"] = round(lg / ns, 6)
                row["oos_n"] = ns
            folds[m] = row

        # 一次判定: VALIDATE 3fold 連続で Δα>0
        vmon = [m for m in months if split_of(m) == "VALIDATE"]
        vals = [folds[m] for m in vmon]
        prim_ok = (len(vmon) == 3
                   and all(f.get("alpha_ok") and f["d_alpha"] > 0 for f in vals))

        # 複勝flat（専用 / 汎用 / 市場1-3人気）
        fuku = {}
        for spn in ("MINE", "VALIDATE", "CONFIRM"):
            sub = [r for r in rs if r["split"] == spn]
            d = {}
            for tag, key in (("spec", "q_model"), ("gen", "q_gen")):
                n = pay = hit = 0
                for r in sub:
                    i = int(np.argmax(r[key]))
                    h = r["ns"][i]
                    n += 1
                    pay += r["pay_fuku"].get(h, 0)
                    hit += (h in r["top3"])
                d[tag] = dict(n=n, roi=round(pay / (100 * n) * 100, 1) if n else None,
                              hit=round(hit / n * 100, 1) if n else None)
            n = pay = hit = 0
            for r in sub:
                pop = np.argsort(r["odds"])
                for k in range(min(3, len(pop))):
                    h = r["ns"][int(pop[k])]
                    n += 1
                    pay += r["pay_fuku"].get(h, 0)
                    hit += (h in r["top3"])
            d["mkt13"] = dict(n=n, roi=round(pay / (100 * n) * 100, 1) if n else None,
                              hit=round(hit / n * 100, 1) if n else None)
            d["spec_used"] = sum(1 for r in sub if r["spec_used"])
            fuku[spn] = d

        sec_ok = (fuku["VALIDATE"]["spec"]["roi"] is not None
                  and fuku["CONFIRM"]["spec"]["roi"] is not None
                  and fuku["VALIDATE"]["spec"]["roi"] >= 95.0
                  and fuku["CONFIRM"]["spec"]["roi"] >= 95.0)

        out[seg] = dict(n_races=len(rs), folds=folds, fukusho=fuku,
                        primary_pass=bool(prim_ok), secondary_pass=bool(sec_ok),
                        d_alpha_val=[folds[m].get("d_alpha") for m in vmon],
                        d_alpha_conf=[folds[m].get("d_alpha")
                                      for m in months if split_of(m) == "CONFIRM"])
    return out


# ── 参考: 組合せ（三連複・ワイド）— PLACE_SYSTEM §2 の通り推定オッズ依存で壊れる ──
def combo_ref(races):
    months = sorted({r["month"] for r in races})
    by_m = {m: [r for r in races if r["month"] == m] for m in months}
    hist3, hist2 = [], []
    acc = defaultdict(float)
    for m in months:
        cal3, cal2 = PE.calib_fit(hist3), PE.calib_fit(hist2)
        for r in by_m[m]:
            T = PE.combo_tables(r)
            if T is None:
                continue
            w3 = tuple(sorted(r["top3"]))
            p3 = r["pay_trio"].get(w3, 0)
            if p3 and w3 in T["k3"]:
                i3 = T["k3"].index(w3)
                hist3.append((float(np.log(1.0 / max(T["p3k"][i3], 1e-12))),
                              float(np.log(p3 / 100.0))))
            for pr, pv in r["pay_wide"].items():
                if pr in T["k2"]:
                    hist2.append((float(np.log(1.0 / max(T["p2k"][T["k2"].index(pr)], 1e-12))),
                                  float(np.log(pv / 100.0))))
            key = (r["segment"], r["split"])
            # flat: モデル上位3頭の三連複BOX1点 / 上位2頭のワイド1点
            t3 = tuple(sorted(r["ns"][i] for i in np.argsort(-r["q_model"])[:3]))
            t2 = tuple(sorted(r["ns"][i] for i in np.argsort(-r["q_model"])[:2]))
            acc[(key, "trioflat_n")] += 1
            acc[(key, "trioflat_pay")] += r["pay_trio"].get(t3, 0)
            acc[(key, "trioflat_hit")] += (1 if r["pay_trio"].get(t3, 0) else 0)
            acc[(key, "wideflat_n")] += 1
            acc[(key, "wideflat_pay")] += r["pay_wide"].get(t2, 0)
            acc[(key, "wideflat_hit")] += (1 if r["pay_wide"].get(t2, 0) else 0)
            if cal3 is None or cal2 is None:
                continue
            for tag, keys, pmod, pmkt, cal, paydict in (
                    ("trio", T["k3"], T["p3m"], T["p3k"], cal3, r["pay_trio"]),
                    ("wide", T["k2"], T["p2m"], T["p2k"], cal2, r["pay_wide"])):
                a_, b_ = cal
                ev = pmod * np.exp(a_ + b_ * np.log(1.0 / np.clip(pmkt, 1e-12, None)))
                for i4 in np.where(ev >= PE.EV_TH)[0]:
                    p = paydict.get(keys[i4], 0)
                    acc[(key, f"{tag}ev_n")] += 1
                    acc[(key, f"{tag}ev_pay")] += p
                    acc[(key, f"{tag}ev_hit")] += (1 if p else 0)
    res = defaultdict(dict)
    for (key, fld), v in acc.items():
        res[key][fld] = v
    out = {}
    for (seg, spn), d in res.items():
        e = {}
        for tag in ("trioflat", "wideflat", "trioev", "wideev"):
            n = d.get(f"{tag}_n", 0)
            e[tag] = dict(n=int(n), hits=int(d.get(f"{tag}_hit", 0)),
                          roi=round(d.get(f"{tag}_pay", 0) / (100 * n) * 100, 1) if n else None)
        out[f"{seg}|{spn}"] = e
    return out


def evaluate():
    t0 = time.time()
    print("汎用ベースライン読み込み中…", flush=True)
    gm, _ = PE.load_ledger(BASE_MAIN)
    PE.prep(gm)
    gen_main = {r["rid"]: r for r in gm}
    gen_sub = {}
    if os.path.exists(BASE_SUB):
        gs, _ = PE.load_ledger(BASE_SUB)
        PE.prep(gs)
        gen_sub = {r["rid"]: r for r in gs}
    print(f"  v8place {len(gen_main)}R / v3place {len(gen_sub)}R ({time.time()-t0:.0f}s)",
          flush=True)

    result, prepped = {}, {}
    for sc in SCHEMES:
        print(f"\n===== {SCHEME_JP[sc]} =====", flush=True)
        races, dropped = load_with_seg(f"place_preds_seg_{sc}.jsonl")
        PE.prep(races)
        races = attach_gen(races, gen_main, gen_sub)
        prepped[sc] = races
        res = eval_scheme(races)
        result[sc] = res
        print(f"races={len(races)} dropped={len(dropped)} segments={len(res)}")
        print(f"{'segment':<10s} {'n':>5s} {'流用':>4s} "
              f"{'Δα VAL(3fold)':>26s} {'複勝ROI V/C(専)':>18s} {'一次':>4s} {'二次':>4s}")
        for seg, d in res.items():
            da = "/".join(f"{x:+.4f}" if x is not None else "  n/a " for x in d["d_alpha_val"])
            v = d["fukusho"]["VALIDATE"]["spec"]
            c = d["fukusho"]["CONFIRM"]["spec"]
            fb = sum(1 for m, f in d["folds"].items() if f["spec_used"] < f["n"])
            print(f"{seg:<10s} {d['n_races']:>5d} {fb:>4d} {da:>26s} "
                  f"{str(v['roi']):>8s}/{str(c['roi']):<8s} "
                  f"{'○' if d['primary_pass'] else '×':>4s} "
                  f"{'○' if d['secondary_pass'] else '×':>4s}")

    # 参考: 組合せ
    print("\n参考: 組合せ(三連複/ワイド)…", flush=True)
    combo = {}
    for sc in SCHEMES:
        combo[sc] = combo_ref(prepped[sc])
        print(f"  {sc} done ({time.time()-t0:.0f}s)", flush=True)

    n_seg = sum(len(result[sc]) for sc in SCHEMES)
    prim = [(sc, seg) for sc in SCHEMES for seg, d in result[sc].items() if d["primary_pass"]]
    both = [(sc, seg) for sc, seg in prim if result[sc][seg]["secondary_pass"]]
    print(f"\nセグメント総数 {n_seg} / 偶然期待(一次) {n_seg*0.125:.1f}")
    print(f"一次通過 {len(prim)}: {prim}")
    print(f"一次+二次通過 {len(both)}: {both if both else 'なし'}")
    json.dump(dict(result=result, combo=combo, n_seg=n_seg,
                   primary=prim, both=both, chance_expect=n_seg * 0.125),
              open("place_seg_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(f"saved place_seg_result.json ({(time.time()-t0)/60:.1f}min)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run()
    elif cmd == "eval":
        evaluate()
    else:
        sys.exit(f"unknown cmd {cmd}")
