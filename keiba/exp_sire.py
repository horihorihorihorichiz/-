# -*- coding: utf-8 -*-
"""R5: 血統（種牡馬）特徴。sire_map.json(11,367頭)×1年の結果から
   as-of累積(リーク無し)で 種牡馬の複勝率 / 表面別 / 距離帯別 を作る。
   ゲート: U2統合チャンピオン(train68.7/test70.6)超え。
   usage: python3 exp_sire.py
"""
import glob, json, os, sys
from collections import defaultdict

import exp_harness as H

PRIOR = 60
SIRE = {k: v.split("|")[0] for k, v in
        json.load(open("sire_map.json", encoding="utf-8")).items()}


def build_asof():
    files = []
    for f in glob.glob("hist_enrich/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        files.append((d.get("date", ""), d["race_id"], d))
    files.sort()
    tot = [0, 0]
    for _, _, d in files:
        for h in d["horses"]:
            if h.get("rank", "").isdigit():
                tot[0] += 1
                tot[1] += (1 if int(h["rank"]) <= 3 else 0)
    g = tot[1]/tot[0]
    acc = defaultdict(lambda: [0, 0])       # sire -> [n, top3]
    acc_s = defaultdict(lambda: [0, 0])     # (sire,surface)
    acc_d = defaultdict(lambda: [0, 0])     # (sire,距離帯)
    feat = {}
    for date, rid, d in files:
        surf = d.get("surface", "")
        db = int(round(d.get("distance", 1600)/400.0)*400)
        fr = {}
        for h in d["horses"]:
            sire = SIRE.get(h.get("horse_id") or "")
            if not sire:
                continue
            n, t = acc[sire]
            ns, ts = acc_s[(sire, surf)]
            nd, td = acc_d[(sire, db)]
            fr[h["num"]] = dict(
                s_top3=(t + g*PRIOR)/(n + PRIOR),
                s_surf=(ts + g*PRIOR)/(ns + PRIOR),
                s_dist=(td + g*PRIOR)/(nd + PRIOR))
        feat[rid] = fr
        for h in d["horses"]:
            sire = SIRE.get(h.get("horse_id") or "")
            if not sire or not h.get("rank", "").isdigit():
                continue
            hit = 1 if int(h["rank"]) <= 3 else 0
            acc[sire][0] += 1; acc[sire][1] += hit
            acc_s[(sire, surf)][0] += 1; acc_s[(sire, surf)][1] += hit
            acc_d[(sire, db)][0] += 1; acc_d[(sire, db)][1] += hit
    return feat, g


if __name__ == "__main__":
    FEAT, g = build_asof()
    print(f"as-of血統特徴: {len(FEAT)}レース分 (全体複勝率{g*100:.1f}%)", flush=True)
    ds = H.load_base()
    print(f"dataset: {len(ds)}R", flush=True)

    # rid経由でas-of表を引く(fnはh,race,ridを受ける)
    def mk(key):
        def fn(h, race, rid):
            v = FEAT.get(rid, {}).get(h["num"])
            return v[key] if v else None
        return fn
    for k in ("s_top3", "s_surf", "s_dist"):
        H.add_feature(ds, k, mk(k))
        print("feat +", k, flush=True)

    r1 = H.run_experiment(ds, extra=["s_top3"], label="S1_種牡馬全体")
    r2 = H.run_experiment(ds, extra=["s_surf", "s_dist"], label="S2_表面+距離別")
    r3 = H.run_experiment(ds, extra=["s_top3", "s_surf", "s_dist"], label="S3_全部")
    print("\n==== summary ====")
    for r in (r1, r2, r3):
        print(f"{r['label']}: train={r['train']['capture5']:.1f} test={r['test']['capture5']:.1f} gate={r['gate']}")
    best = max((r1, r2, r3), key=lambda r: (r["gate"], r["test"]["capture5"] + r["train"]["capture5"]))
    json.dump(best, open("exp_sire_best.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("best →", best["label"])
