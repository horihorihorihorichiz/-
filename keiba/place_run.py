# -*- coding: utf-8 -*-
"""3着内(複勝圏)特化モデルの月次ウォークフォワード実行。

PLACE_SYSTEM_20260817.md の事前登録どおり:
  variant  = v3place (V3の28特徴) / v8place (V3 + V8新特徴22本 = 50特徴)
  ラベル   = 3着内なら1
  fold     = 月次。fold月 m の学習は「m より前の全レース」(V8と完全同一手順)
  分割     = MINE(〜202602) / VALIDATE(202603-202605) / CONFIRM(202606-202608)

既存経路(V3/V4/V5/V8)は**一切変更しない**。wf_compare.load_ds と fit_v2.build_row を
読むだけで、学習ラベルと目的関数は fit_place.py 側に閉じている。

出力: place_preds_<variant>.jsonl   … 1行1レース。scores は「3着内スコア」
      place_importance.json         … LightGBM gain のfold横断合計

usage: python3 place_run.py --variants v3place,v8place --start-fold 202403
"""
import argparse, json, time

import numpy as np

import wf_compare as W
import fit_v2 as V2
import fit_place as FP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v3place,v8place")
    ap.add_argument("--start-fold", default="202403")
    ap.add_argument("--reload", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    ds = W.load_ds(a.reload, v8=True)
    print(f"dataset {len(ds)}R  ({time.time()-t0:.0f}s)", flush=True)
    months = sorted({r["date"][:6] for r in ds})
    folds = [m for m in months if m >= a.start_fold]
    variants = a.variants.split(",")
    print(f"months {months[0]}..{months[-1]} / folds {folds}", flush=True)

    fh = {v: open(f"place_preds_{v}.jsonl", "w", encoding="utf-8") for v in variants}
    imp, names = {}, {}
    for v in variants:
        sp = FP.PLACE_VARIANTS[v]
        names[v] = V2.feat_names(sp["v4"], False, False, sp.get("v8"))
        imp[v] = np.zeros(len(names[v]))
        print(f"  {v}: {len(names[v])}特徴 / mode={sp['mode']}", flush=True)

    for m in folds:
        train = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train) < 400 or not fold:
            print(f"[{m}] skip (train={len(train)})", flush=True)
            continue
        line = [f"[{m}] {len(fold)}R train={len(train)}R"]
        for v in variants:
            ts = time.time()
            sp = FP.PLACE_VARIANTS[v]
            model = FP.train_place_fold(train, sp)
            imp[v] += np.array(model.feature_importance("gain"), dtype=float)
            n1 = hit = 0
            for r in fold:
                s = FP.predict_place(model, r, sp)
                order = sorted(s, key=lambda x: -s[x])
                inm = set(r["top3"])
                n1 += 1
                hit += (order[0] in inm)
                fh[v].write(json.dumps(dict(
                    rid=r["rid"], month=m, date=r["date"], order=order,
                    scores=[round(s[n], 6) for n in order],
                    odds=r["odds"], top3=r["top3"],
                    payout=r.get("payout") or {},
                    surface=r["surface"], dist=r["dist"], tier=r["tier"],
                    baba=r["baba"], venue=r["venue"], field=len(r["ns"])),
                    ensure_ascii=False) + "\n")
            fh[v].flush()
            line.append(f"{v}:1位複勝{hit/max(n1,1)*100:.1f}%({time.time()-ts:.0f}s)")
        print(" | ".join(line), flush=True)

    for v in variants:
        fh[v].close()
    json.dump({v: dict(names=names[v], gain=[round(x, 1) for x in imp[v]])
               for v in variants},
              open("place_importance.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"done ({(time.time()-t0)/60:.1f}min)", flush=True)


if __name__ == "__main__":
    main()
