# -*- coding: utf-8 -*-
"""V8 ウォークフォワード実行（V8_PROTOCOL_20260817.md）。

wf_compare.py の学習・予測関数をそのまま使い、
  ・全 variant を **同一fold・同一学習集合** で回す
  ・variant ごとに予測台帳 wf_preds_<v>.jsonl を出す（fit_v7 と同じスキーマ）
  ・LightGBM の gain 重要度をfold横断で積算する
だけを追加したドライバ。特徴・閾値の定義には一切触っていない。

usage: python3 v8_run.py --variants v8base,v8f1,v8f2,v8f4,v8all --start-fold 202403
"""
import argparse, json, os, time
import numpy as np

import wf_compare as W
import fit_v2 as V2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="v8base,v8f1,v8f2,v8f4,v8all")
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

    fh = {v: open(f"wf_preds_{v}.jsonl", "w", encoding="utf-8") for v in variants}
    imp = {v: None for v in variants}
    names = {}
    for v in variants:
        sp = W.VARIANTS[v]
        names[v] = V2.feat_names(sp["v4"], bool(sp.get("extra")),
                                 bool(sp.get("tenkai")), sp.get("v8"))
        imp[v] = np.zeros(len(names[v]))
        print(f"  {v}: {len(names[v])}特徴", flush=True)

    for m in folds:
        train = [r for r in ds if r["date"][:6] < m]
        fold = [r for r in ds if r["date"][:6] == m]
        if len(train) < 400 or not fold:
            print(f"[{m}] skip (train={len(train)})", flush=True)
            continue
        line = [f"[{m}] {len(fold)}R train={len(train)}R"]
        for v in variants:
            ts = time.time()
            sp = W.VARIANTS[v]
            model = W.train_fold(train, sp)
            imp[v] += np.array(model.feature_importance("gain"), dtype=float)
            n1 = hit = 0
            for r in fold:
                s = W.predict(model, r, sp["v4"], bool(sp.get("extra")),
                              bool(sp.get("tenkai")), sp.get("v8"))
                order = sorted(s, key=lambda x: -s[x])
                n1 += 1
                hit += (order[0] == r["top3"][0])
                fh[v].write(json.dumps(dict(
                    rid=r["rid"], month=m, date=r["date"], order=order,
                    scores=[round(s[n], 4) for n in order],
                    odds=r["odds"], top3=r["top3"],
                    payout=r.get("payout") or {},
                    surface=r["surface"], dist=r["dist"], tier=r["tier"],
                    baba=r["baba"], venue=r["venue"], field=len(r["ns"])),
                    ensure_ascii=False) + "\n")
            fh[v].flush()
            line.append(f"{v}:1位{hit/max(n1,1)*100:.1f}%({time.time()-ts:.0f}s)")
        print(" | ".join(line), flush=True)

    for v in variants:
        fh[v].close()
    json.dump({v: dict(names=names[v], gain=[round(x, 1) for x in imp[v]])
               for v in variants},
              open("v8_importance.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"done ({(time.time()-t0)/60:.1f}min)", flush=True)


if __name__ == "__main__":
    main()
