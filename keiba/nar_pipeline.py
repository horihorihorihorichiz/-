# -*- coding: utf-8 -*-
"""NAR専用パイプライン（地方は別フォーマット・7/19）。
   hist_nar_flat/ から: ①NAR基準タイム→自前指数DB ②地方騎手as-of DB
   ③データセット構築(V2特徴+NAR指数注入) ④V3-NAR学習(LambdaRank・時系列split)
   ⑤パターン2段階判定(乖離単勝7倍+×条件・三連複ながし)
   usage: python3 nar_pipeline.py
   出力: nar_speedidx.json / nar_jockey.json / model_nar.txt / 判定レポート(標準出力)
"""
import glob, itertools, json, math, sys
from collections import defaultdict

import numpy as np
import lightgbm as lgb

import calc
import fit_v2 as V2
from fit_v3 import to_matrix, scores_from

FILES = sorted(glob.glob("hist_nar_flat/*.json"),
               key=lambda f: json.load(open(f)).get("date", ""))


def load_all():
    out = []
    for f in FILES:
        try:
            d = json.load(open(f, encoding="utf-8"))
            if len(d.get("result", {}).get("order", [])) >= 5:
                out.append(d)
        except Exception:
            continue
    return out


def build_index(data):
    """NAR基準タイム(場×距離×クラス概算) → idx = -(残差)×(1400/dist)"""
    acc = defaultdict(list)
    for d in data:
        v = d["race"].get("venue", "")
        dist = d["race"].get("distance", 0)
        for o in d["result"]["order"]:
            t = o.get("time_sec")
            if t and dist:
                acc[(v, dist)].append(t)
    base = {k: sorted(v)[len(v)//2] for k, v in acc.items() if len(v) >= 20}
    db = {}
    for d in data:
        v = d["race"].get("venue", "")
        dist = d["race"].get("distance", 0)
        b = base.get((v, dist))
        if not b:
            continue
        for o in d["result"]["order"]:
            t = o.get("time_sec")
            if not t:
                continue
            raw = -(t - b) * (1400.0/max(dist, 800))
            idx = 80 + 8*max(-3, min(3, raw))
            db[f"{o['name']}|{d['date']}"] = round(idx, 1)
    json.dump(db, open("nar_speedidx.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"NAR指数DB: {len(db)}走 (基準{len(base)}コース)", flush=True)
    return db


def build_jockey(data):
    g = [0, 0]
    for d in data:
        for o in d["result"]["order"]:
            g[0] += 1
            g[1] += (1 if o["rank"] in ("1", "2", "3") else 0)
    g_top3 = g[1]/g[0]
    acc = defaultdict(lambda: [0, 0])
    feat = {}
    for d in data:   # 時系列順(FILESがdateソート済み)
        jmap = {h["num"]: h.get("jockey_id") for h in d["race"]["horses"]}
        fr = {}
        for num, jid in jmap.items():
            if not jid:
                continue
            n, t3 = acc[jid]
            fr[num] = (t3 + g_top3*40)/(n + 40)
        feat[d["race"].get("race_id", "") or d["result"].get("race_id", "")] = fr
        for o in d["result"]["order"]:
            jid = jmap.get(o["num"])
            if jid:
                acc[jid][0] += 1
                acc[jid][1] += (1 if o["rank"] in ("1", "2", "3") else 0)
    json.dump({k: dict(n=v[0], top3=(v[1]+g_top3*40)/(v[0]+40)) for k, v in acc.items()},
              open("nar_jockey.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"NAR騎手: {len(acc)}人 (全体複勝率{g_top3*100:.1f}%)", flush=True)
    return feat


def build_dataset(data, idxdb, jfeat):
    import datetime as DT
    ds = []
    for d in data:
        race = d["race"]
        rd = d["date"]
        rdate = DT.date(int(rd[:4]), int(rd[4:6]), int(rd[6:8]))
        # NAR指数を馬柱に注入(name|date)
        for h in race.get("horses", []):
            for run in h.get("races", []):
                if run.get("tsi") is None and run.get("days"):
                    dt = (rdate - DT.timedelta(days=run["days"])).strftime("%Y%m%d")
                    v = idxdb.get(f"{h['name']}|{dt}")
                    if v is not None:
                        run["tsi"] = v
        try:
            res = calc.run(race)
        except Exception:
            continue
        wavg = {r["num"]: r["wavg"] for r in res["rows"]}
        rid = race.get("race_id", "")
        jf = jfeat.get(rid, {})
        top3 = [o["num"] for o in d["result"]["order"] if o["rank"] in ("1", "2", "3")]
        om = {o["num"]: o["odds"] for o in d["result"]["order"] if o.get("odds")}
        raw = {}
        for h in race["horses"]:
            ff = V2.horse_feats(h, race)
            ff["wavg"] = wavg.get(h["num"])
            ff["j_top3"] = jf.get(h["num"])
            ff["t_top3"] = None
            raw[h["num"]] = ff
        if len(raw) < 6 or len(top3) < 3 or any(t not in raw for t in top3):
            continue
        X = {k: V2.z_in_race({n: raw[n].get(k) for n in raw}) for k in V2.FEATS}
        ds.append(dict(X=X, ns=list(raw.keys()), top3=top3, odds=om,
                       date=rd, rid=rid, payout=d["result"].get("payout", {}),
                       surface=race.get("surface"), dist=race.get("distance"),
                       venue=race.get("venue"), field=len(raw)))
    return ds


def main():
    data = load_all()
    print(f"NARレース: {len(data)}R ({data[0]['date']}〜{data[-1]['date']})", flush=True)
    idxdb = build_index(data)
    jfeat = build_jockey(data)
    ds = build_dataset(data, idxdb, jfeat)
    print(f"データセット: {len(ds)}R", flush=True)
    # 時系列split: 前70%=train(dev), 後30%=conf
    cut = int(len(ds)*0.7)
    train, conf = ds[:cut], ds[cut:]
    # V3-NAR学習
    nv = max(30, len(train)//10)
    Xt, yt, gt, _ = to_matrix(train[:-nv])
    Xv, yv, gv, _ = to_matrix(train[-nv:])
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=0.05, num_leaves=15, min_data_in_leaf=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    model = lgb.train(params, lgb.Dataset(Xt, label=yt, group=gt),
                      num_boost_round=400,
                      valid_sets=[lgb.Dataset(Xv, label=yv, group=gv)],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
    model.save_model("model_nar.txt", num_iteration=model.best_iteration)
    print(f"model_nar.txt保存 (iter{model.best_iteration})", flush=True)

    # 評価: 捕捉 + パターン2段階
    def kpi(dset):
        cap = capm = at1 = at1m = n = 0
        for r in dset:
            s = scores_from(model, r)
            order = sorted(s, key=lambda x: -s[x])
            msort = sorted(r["odds"], key=lambda h: r["odds"][h]) if r["odds"] else []
            t5, m5 = set(order[:5]), set(msort[:5])
            cap += sum(1 for t in r["top3"] if t in t5)
            capm += sum(1 for t in r["top3"] if t in m5)
            at1 += (order[0] == r["top3"][0])
            at1m += (bool(msort) and msort[0] == r["top3"][0])
            n += 1
        return cap/(3*n)*100, capm/(3*n)*100, at1/n*100, at1m/n*100, n
    for name, dset in (("train", train), ("conf", conf)):
        c, cm, a, am, n = kpi(dset)
        print(f"[{name}] 捕捉5 モデル{c:.1f}% vs 市場{cm:.1f}% / 勝1位 {a:.1f}% vs {am:.1f}% ({n}R)", flush=True)

    P = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for phase, dset in (("dev", train), ("conf", conf)):
        for r in dset:
            s = scores_from(model, r)
            order = sorted(s, key=lambda x: -s[x])
            t1 = order[0]
            o1 = r["odds"].get(t1, 0)
            if o1 < 7:
                continue
            ret = r["payout"].get("単勝", {}).get(str(t1), 0)
            conds = {"全乖離": True, "7-15倍": o1 <= 15, "15倍+": o1 > 15,
                     "南関東": r["venue"] in ("大井", "船橋", "川崎", "浦和"),
                     "小頭数": r["field"] <= 10, "多頭数": r["field"] >= 12}
            for cn, ok in conds.items():
                if ok:
                    a2 = P[f"乖離単勝×{cn}"][phase]
                    a2[0] += 100; a2[1] += ret; a2[2] += 1
            msort = sorted(r["odds"], key=lambda h: r["odds"][h])
            mtop = [n2 for n2 in msort if n2 != t1][:3]
            if len(mtop) >= 3:
                pts = ["-".join(map(str, sorted((t1,)+p))) for p in itertools.combinations(mtop, 2)]
                tret = sum(r["payout"].get("三連複", {}).get(k, 0) for k in pts)
                a2 = P["三連複軸ながし×全乖離"][phase]
                a2[0] += 300; a2[1] += tret; a2[2] += 1
    print("\n==== NARパターン判定(dev=前70% / conf=後30%) ====", flush=True)
    for name, ph in sorted(P.items()):
        dv, cf = ph["dev"], ph["conf"]
        droi = dv[1]/dv[0]*100 if dv[0] else 0
        croi = cf[1]/cf[0]*100 if cf[0] else 0
        star = "★" if droi >= 103 and croi >= 100 and cf[2] >= 15 else " "
        print(f" {star}{name:18s} dev{droi:6.1f}%({dv[2]:3d}) conf{croi:6.1f}%({cf[2]:3d})", flush=True)


if __name__ == "__main__":
    main()
