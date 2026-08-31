# -*- coding: utf-8 -*-
"""Ver.99.27 成分データセット構築（V99W: 配点学習用）。
hist/*.json を calc.run（params無効=素のVer.99.27）で回し、
各馬の11成分+展開乗数+着順+単勝オッズ+払戻を comps_v99.pkl に保存する。

検算: 各レースで sum(成分)=S2, S2×乗数=WAvg を全馬照合（許容1e-6）。
usage: python3 build_comps_v99.py
"""
import glob, json, pickle, sys
import calc

COMPS = ["tsi", "lts", "fsi", "bonus", "dsi", "nsi", "csi",
         "was", "tas", "hcs", "nrja"]


def main():
    calc._PARAMS = {}   # 素のVer.99.27（score_weights/kankai_scaleを使わない）
    files = sorted(glob.glob("hist/*.json"))
    out, errs, checkfail = [], [], 0
    for i, f in enumerate(files):
        rid = f.split("/")[-1].replace(".json", "")
        try:
            d = json.load(open(f, encoding="utf-8"))
            race = d["race"]
            res = calc.run(race)
        except Exception as e:
            errs.append((rid, repr(e)))
            continue
        # 検算: 成分合計=S2, S2×乗数=WAvg
        for r in res["rows"]:
            s = sum(r[k] for k in COMPS)
            if abs(s - r["s2"]) > 0.011 or abs(s * r["mult"] - r["wavg"]) > 0.011:
                checkfail += 1
                print(f"検算NG {rid} num={r['num']} sum={s} s2={r['s2']} "
                      f"mult={r['mult']} wavg={r['wavg']}", file=sys.stderr)
        order = d["result"].get("order", [])
        fin = {o["num"]: int(o["rank"]) for o in order
               if str(o.get("rank", "")).isdigit()}
        odds = {o["num"]: o.get("odds") for o in order}
        ninki = {o["num"]: o.get("ninki") for o in order}
        horses = []
        for r in res["rows"]:
            horses.append(dict(
                num=r["num"], style=r["style"],
                comps={k: float(r[k]) for k in COMPS},
                mult=float(r["mult"]), s2=float(r["s2"]), wavg=float(r["wavg"]),
                finish=fin.get(r["num"]), odds=odds.get(r["num"]),
                ninki=ninki.get(r["num"])))
        date = str(d.get("date", ""))
        out.append(dict(
            rid=rid, date=date, month=date[:6],
            venue=race["venue"], surface=race["surface"],
            distance=race["distance"], dist_cat=race["dist_cat"],
            today_vg=race["today_vg"], today_tier=race["today_tier"],
            baba=race["baba"], field=race["field"], stage=res["stage"],
            horses=horses, payout=d["result"].get("payout", {})))
        if (i + 1) % 1000 == 0:
            print(f"{i+1}/{len(files)}", file=sys.stderr)
    pickle.dump(dict(races=out, errors=errs, comps=COMPS),
                open("comps_v99.pkl", "wb"))
    print(f"保存: comps_v99.pkl  races={len(out)}  例外除外={len(errs)}  "
          f"検算NG={checkfail}")
    for rid, e in errs[:20]:
        print("  除外:", rid, e)


if __name__ == "__main__":
    main()
