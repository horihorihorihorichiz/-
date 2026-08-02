# -*- coding: utf-8 -*-
"""台帳更新: wf_preds(現行台帳)上で全◎パターンのROIを測り直す(統一原則)。
   パターン毎に: 全発火ROI / dev(≤202603) / conf(≥202604) / 新規区間(7/18+) / 最良発火時ROI。
   usage: python3 pattern_refresh.py [--path wf_preds_v3.jsonl]
"""
import argparse, glob, json
from collections import defaultdict

import sim_rank as SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="wf_preds_v3.jsonl")
    a = ap.parse_args()
    rid_date = {}
    for f in glob.glob("hist/*.json"):
        try:
            rid_date[f.split("/")[-1][:12]] = json.load(open(f, encoding="utf-8")).get("date", "")
        except Exception:
            pass
    rows = SR.load(a.path)
    for r in rows:
        r["date"] = rid_date.get(r["rid"], "")
    agg = defaultdict(lambda: defaultdict(float))
    for r in rows:
        buy, hc = SR.classify_race(r)
        if not buy:
            continue
        best = max(buy, key=lambda f: f[2])
        for f in buy:
            st = SR.settle_fire(r, f[0], f[3])
            if st is None:
                continue
            pts, pay100 = st
            for seg in ["all",
                        "dev" if r["m"] <= "202603" else "conf",
                        "fresh" if r["date"] >= "20260718" else None,
                        "best" if f is best else None]:
                if seg is None:
                    continue
                s = agg[f[0]]
                s[seg+"_n"] += 1
                s[seg+"_inv"] += pts*100
                s[seg+"_ret"] += pay100
                s[seg+"_hit"] += (1 if pay100 > 0 else 0)
    def fmt(s, seg):
        n, inv, ret, hit = (s[seg+"_n"], s[seg+"_inv"], s[seg+"_ret"], s[seg+"_hit"])
        if not inv:
            return f"{'-':>16s}"
        return f"{ret/inv*100:6.1f}%/{int(n):3d}R({int(hit):2d})"
    names = sorted(agg, key=lambda k: -agg[k]["all_inv"])
    print(f"{'パターン':<38s} {'全期間':>16s} {'dev':>16s} {'conf':>16s} {'新規7/18+':>16s} {'最良発火時':>16s}")
    for k in names:
        s = agg[k]
        print(f"{k[:37]:<38s} {fmt(s,'all')} {fmt(s,'dev')} {fmt(s,'conf')} {fmt(s,'fresh')} {fmt(s,'best')}")


if __name__ == "__main__":
    main()
