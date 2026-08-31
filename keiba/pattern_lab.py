# -*- coding: utf-8 -*-
"""パターン研究所（7/14「幅広いアイデアから条件を絞って増やせ」）。
   2段階の規律: 発見(dev=202511-202604)で採掘 → 確認(conf=202605-202607)で追試。
   両方プラスのものだけ「買いパターン」としてカタログ入り（多重比較のインチキ防止）。

   usage:
     python3 pattern_lab.py build    # WFのV3予測を一括生成(wf_preds.jsonl・約1時間・1回だけ)
     python3 pattern_lab.py sweep    # 数百パターンを瞬時に精算→2段階判定→pattern_stats2.json
"""
import itertools, json, os, sys
from collections import defaultdict

import fit_v2 as V2

DEV_END = "202605"      # これより前=発見用 / これ以降=確認用
MIN_DEV_BETS = 60
MIN_CONF_BETS = 25


def month_of(r):
    return r["date"][:6]


def build():
    import numpy as np
    import lightgbm as lgb
    from fit_v3 import to_matrix, scores_from
    ds = V2.load_dataset("hist", "hist_feat")
    months = sorted({month_of(r) for r in ds})
    folds = [m for m in months if m >= "202511"]
    params = dict(objective="lambdarank", metric="ndcg", ndcg_eval_at=[5],
                  learning_rate=0.05, num_leaves=15, min_data_in_leaf=50,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=5.0, verbose=-1, label_gain=[0, 1, 3, 7])
    out = open("wf_preds.jsonl", "w", encoding="utf-8")
    for m in folds:
        train = [r for r in ds if month_of(r) < m]
        fold = [r for r in ds if month_of(r) == m]
        if len(train) < 400 or not fold:
            continue
        nv = max(50, len(train)//10)
        Xt, yt, gt, _ = to_matrix(train[:-nv])
        Xv, yv, gv, _ = to_matrix(train[-nv:])
        dtr = lgb.Dataset(Xt, label=yt, group=gt)
        dva = lgb.Dataset(Xv, label=yv, group=gv, reference=dtr)
        model = lgb.train(params, dtr, num_boost_round=400, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(50, verbose=False)])
        for r in fold:
            hp = os.path.join("hist", f"{r['rid']}.json")
            if not os.path.exists(hp):
                continue
            d = json.load(open(hp, encoding="utf-8"))
            s = scores_from(model, r)
            order = sorted(s, key=lambda x: -s[x])
            rec = dict(rid=r["rid"], month=m, order=order,
                       scores={str(k): round(v, 4) for k, v in s.items()},
                       odds=r["odds"],
                       payout=d["result"].get("payout", {}),
                       surface=d["race"].get("surface"),
                       dist=d["race"].get("distance"),
                       tier=d["race"].get("today_tier"),
                       baba=d["race"].get("baba"),
                       field=len(r["ns"]))
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{m}] 済", flush=True)
    out.close()
    print("wf_preds.jsonl 完成")


# ---------- sweep ----------
def load_preds():
    return [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]


def sweep():
    preds = load_preds()
    print(f"WF予測 {len(preds)}R", flush=True)

    def mrank(rec, n):
        o = rec["odds"]
        if str(n) not in map(str, o) and n not in o:
            return 99
        om = {int(k): v for k, v in o.items()} if isinstance(next(iter(o)), str) else o
        return sorted(om, key=lambda h: om[h]).index(n) + 1

    def pay(rec, kind, key):
        return rec["payout"].get(kind, {}).get(key, 0)

    # 条件ディメンション(レース単位)
    def conds(rec):
        t1 = rec["order"][0]
        om = {int(k): v for k, v in rec["odds"].items()}
        mr = sorted(om, key=lambda h: om[h]).index(t1) + 1 if t1 in om else 99
        o1 = om.get(t1, 0)
        sc = rec["scores"]
        so = [sc[str(n)] for n in rec["order"][:3] if str(n) in sc]
        gap12 = (so[0] - so[1]) if len(so) >= 2 else 0
        fav_odds = min(om.values()) if om else 0
        c = {
            "全レース": True,
            "芝": rec["surface"] == "芝", "ダ": rec["surface"] == "ダ",
            "短距離": (rec["dist"] or 0) <= 1400, "中距離": 1401 <= (rec["dist"] or 0) <= 1900,
            "長距離": (rec["dist"] or 0) >= 1901,
            "少頭数": rec["field"] <= 12, "多頭数": rec["field"] >= 13,
            "下級(未勝利/1勝)": (rec["tier"] or 0) <= 5, "上級(2勝+)": (rec["tier"] or 0) >= 6,
            "道悪": rec["baba"] in ("稍", "重", "不"), "良馬場": rec["baba"] == "良",
            "自信大(gap上位)": gap12 >= 0.9, "混戦(gap小)": gap12 < 0.45,
            "1位が中人気(4-6)": 4 <= mr <= 6, "1位が大穴(7+)": mr >= 7,
            "1位オッズ5-15倍": 5 <= o1 <= 15, "1位オッズ15倍+": o1 > 15,
            "本命サイド薄(1人気3倍+)": fav_odds >= 3.0,
        }
        return c, t1, om, mr

    # 買い方(レース→(stake, ret))
    def bets(rec, t1, om, mr):
        o12 = "-".join(map(str, sorted(rec["order"][:2])))
        b = {
            "単勝1位": (100, pay(rec, "単勝", str(t1))),
            "複勝1位": (100, pay(rec, "複勝", str(t1))),
            "単勝1位_乖離(4人気+)": (100, pay(rec, "単勝", str(t1))) if mr >= 4 else None,
            "複勝1位_乖離(4人気+)": (100, pay(rec, "複勝", str(t1))) if mr >= 4 else None,
            "複勝2位": (100, pay(rec, "複勝", str(rec["order"][1]))) if len(rec["order"]) > 1 else None,
            "ワイド1-2位": (100, pay(rec, "ワイド", o12)),
            "馬連1-2位": (100, pay(rec, "馬連", o12)),
            "馬単1位→2位": (100, pay(rec, "馬単", f"{t1}→{rec['order'][1]}")) if len(rec["order"]) > 1 else None,
        }
        return {k: v for k, v in b.items() if v}

    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # (bet,cond) -> phase -> [st,ret,n]
    for rec in preds:
        phase = "dev" if rec["month"] < DEV_END else "conf"
        c, t1, om, mr = conds(rec)
        bs = bets(rec, t1, om, mr)
        for bname, (st, ret) in bs.items():
            for cname, ok in c.items():
                if not ok:
                    continue
                a = acc[(bname, cname)][phase]
                a[0] += st; a[1] += ret; a[2] += 1

    # 2段階判定
    survivors, candidates = [], []
    for (bname, cname), ph in acc.items():
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_BETS or dv[0] == 0:
            continue
        droi = dv[1]/dv[0]*100
        if droi < 103:
            continue
        candidates.append((bname, cname, droi, dv[2]))
        if cf[2] >= MIN_CONF_BETS and cf[0] > 0:
            croi = cf[1]/cf[0]*100
            if croi >= 100:
                tot_st = dv[0]+cf[0]; tot_rt = dv[1]+cf[1]
                survivors.append(dict(
                    bet=bname, cond=cname,
                    dev_roi=round(droi, 1), dev_n=dv[2],
                    conf_roi=round(croi, 1), conf_n=cf[2],
                    total_roi=round(tot_rt/tot_st*100, 1), total_n=dv[2]+cf[2]))
    survivors.sort(key=lambda x: -x["total_roi"])
    print(f"\n発見フェーズ通過(dev ROI≥103%, n≥{MIN_DEV_BETS}): {len(candidates)}件")
    print(f"確認フェーズも通過(conf ROI≥100%, n≥{MIN_CONF_BETS}): {len(survivors)}件\n")
    print("==== 2段階を生き残った買いパターン ====")
    for s in survivors:
        print(f"  {s['bet']} × {s['cond']}: 発見{s['dev_roi']}%({s['dev_n']}点) "
              f"確認{s['conf_roi']}%({s['conf_n']}点) 通算{s['total_roi']}%({s['total_n']}点)")
    json.dump(survivors, open("pattern_stats2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ pattern_stats2.json")


if __name__ == "__main__":
    (build if (len(sys.argv) > 1 and sys.argv[1] == "build") else sweep)()
