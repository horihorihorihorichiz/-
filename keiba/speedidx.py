# -*- coding: utf-8 -*-
"""自前スピード指数（Ver.101 A1）。
   hist_enrich/（全馬の走破タイム）から基準タイムを推定し、全出走に指数を付与する。

   モデル: time_sec ≈ base(場×芝ダ×距離) + tier_adj(クラス) + baba_adj(芝ダ×馬場) + 残差
   指数  : idx_raw = -残差×(2000/距離)  → 距離あたりの速さに正規化
   較正  : 手元のrace_*.jsonにあるnetkeiba純正タイム指数(貼り付け分)と突き合わせ、
           idx = a + b×idx_raw で純正スケールに線形写像（混在してもランクが壊れない）。

   usage:
     python3 speedidx.py build     # 基準タイム推定→speedidx.json(DB)生成→較正
     python3 speedidx.py attach    # hist/の全馬柱にtsiとして付与(tsi=Noneの走のみ)
"""
import glob, json, os, statistics, sys

DB = "speedidx.json"


def load_runs():
    runs = []
    for f in glob.glob("hist_enrich/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        for h in d["horses"]:
            if not h.get("time_sec") or not h.get("rank", "").isdigit():
                continue
            runs.append(dict(
                venue=d["venue"], surface=d["surface"], dist=d["distance"],
                baba=d["baba"], tier=d.get("tier", 0), date=d["date"],
                name=h["name"], horse_id=h.get("horse_id"),
                t=h["time_sec"]))
    return runs


def build():
    runs = load_runs()
    print(f"出走データ: {len(runs)}本", file=sys.stderr)
    key_vsd = lambda r: (r["venue"], r["surface"], r["dist"])
    key_tier = lambda r: r["tier"]
    key_baba = lambda r: (r["surface"], r["baba"])
    tier_adj = {}
    baba_adj = {}
    base = {}
    for it in range(3):
        # base: 残差(基準からのずれ)を除いた中央値
        grp = {}
        for r in runs:
            adj = tier_adj.get(key_tier(r), 0.0) + baba_adj.get(key_baba(r), 0.0)
            grp.setdefault(key_vsd(r), []).append(r["t"] - adj)
        base = {k: statistics.median(v) for k, v in grp.items() if len(v) >= 20}
        # tier_adj
        g2 = {}
        for r in runs:
            if key_vsd(r) not in base:
                continue
            resid = r["t"] - base[key_vsd(r)] - baba_adj.get(key_baba(r), 0.0)
            g2.setdefault(key_tier(r), []).append(resid)
        tier_adj = {k: statistics.median(v) for k, v in g2.items() if len(v) >= 50}
        # baba_adj
        g3 = {}
        for r in runs:
            if key_vsd(r) not in base:
                continue
            resid = r["t"] - base[key_vsd(r)] - tier_adj.get(key_tier(r), 0.0)
            g3.setdefault(key_baba(r), []).append(resid)
        baba_adj = {k: statistics.median(v) for k, v in g3.items() if len(v) >= 50}
    # 指数化
    idx = {}   # (name,date)->raw / (horse_id,date)->raw
    n_ok = 0
    for r in runs:
        b = base.get(key_vsd(r))
        if b is None:
            continue
        resid = (r["t"] - b - tier_adj.get(key_tier(r), 0.0)
                 - baba_adj.get(key_baba(r), 0.0))
        raw = -resid * (2000.0/max(r["dist"], 800))
        idx[f"{r['name']}|{r['date']}"] = raw
        if r.get("horse_id"):
            idx[f"id{r['horse_id']}|{r['date']}"] = raw
        n_ok += 1
    print(f"指数付与: {n_ok}本 / 基準タイム{len(base)}コース", file=sys.stderr)

    # 較正: 既存race_*.jsonのnetkeiba純正tsi(貼り付け分)との線形回帰
    pairs = []
    import datetime as DT
    for f in glob.glob("race_2026*.json"):
        try:
            race = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rid = race.get("race_id", "")
        if len(rid) != 12 or rid[4:6] not in {"%02d" % i for i in range(1, 11)}:
            continue   # 日付が引けるJRAキャッシュのみ
        rd = None
        for hf in glob.glob(os.path.join("hist", f"{rid}.json")):
            rd = json.load(open(hf, encoding="utf-8")).get("date")
        if not rd:
            continue
        rdate = DT.date(int(rd[:4]), int(rd[4:6]), int(rd[6:8]))
        for h in race.get("horses", []):
            for run in h.get("races", []):
                if run.get("tsi") is None or not run.get("days"):
                    continue
                d = (rdate - DT.timedelta(days=run["days"])).strftime("%Y%m%d")
                raw = idx.get(f"{h['name']}|{d}")
                if raw is not None:
                    pairs.append((raw, run["tsi"]))
    a, b = 80.0, 2.0
    if len(pairs) >= 30:
        xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
        cov = sum((x-mx)*(y-my) for x, y in pairs)
        var = sum((x-mx)**2 for x in xs)
        b = cov/var if var else 2.0
        a = my - b*mx
        ss_res = sum((y-(a+b*x))**2 for x, y in pairs)
        ss_tot = sum((y-my)**2 for y in ys)
        r2 = 1 - ss_res/ss_tot if ss_tot else 0
        print(f"較正: netkeiba純正tsiと{len(pairs)}対 → idx = {a:.1f} + {b:.2f}×raw (R²={r2:.2f})",
              file=sys.stderr)
    else:
        print(f"較正ペア{len(pairs)}対のみ→既定スケール(80+2×raw)", file=sys.stderr)
    out = {k: round(a + b*v, 1) for k, v in idx.items()}
    json.dump(out, open(DB, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{DB} 保存: {len(out)}キー", file=sys.stderr)


def attach():
    """hist/の馬柱のtsi=Noneの走に自前指数を付与（tsi_srcで由来を記録）"""
    import datetime as DT
    db = json.load(open(DB, encoding="utf-8"))
    n_set = n_run = 0
    for f in glob.glob("hist/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        rd = d.get("date")
        if not rd:
            continue
        rdate = DT.date(int(rd[:4]), int(rd[4:6]), int(rd[6:8]))
        changed = False
        for h in d["race"]["horses"]:
            for run in h.get("races", []):
                n_run += 1
                if run.get("tsi") is not None or not run.get("days"):
                    continue
                dt = (rdate - DT.timedelta(days=run["days"])).strftime("%Y%m%d")
                v = db.get(f"{h['name']}|{dt}")
                if v is not None:
                    run["tsi"] = v
                    run["tsi_src"] = "own"
                    n_set += 1
                    changed = True
        if changed:
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"付与: {n_set}走 / 全{n_run}走 ({n_set/n_run*100:.0f}%)", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "attach":
        attach()
    else:
        build()
