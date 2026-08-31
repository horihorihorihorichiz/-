# -*- coding: utf-8 -*-
"""凍結パターン(◎買い級)の全発火レース一覧を出す(2026-08-23・指示「過去走で期待値プラスのやつ 全レース結果送ってよ」)。

wf_preds_v3.jsonl(2394R台帳=8/2版)に対して patterns.classify を再生し、
◎が付く発火(買い推奨級)を全件、日付順に 場R/馬/オッズ/結果/払戻 で列挙する。
集計はパターン別に n/的中/ROI/収支(100円建て)。
※これは採掘に使った台帳での成績＝in-sample。8月の前向き分(paper_rank_log)は別表で出す。
"""
import glob, json, sys, collections
sys.path.insert(0, ".")
import sim_rank as SR

VEN = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京",
       "06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}


def main():
    rid_date = {}
    for f in glob.glob("hist/*.json"):
        try:
            rid_date[f.split("/")[-1][:12]] = json.load(open(f, encoding="utf-8")).get("date", "")
        except Exception:
            pass
    rows = SR.load("wf_preds_v3.jsonl")
    for r in rows:
        r["date"] = rid_date.get(r["rid"], "")
    rows.sort(key=lambda r: (r["date"], r["rid"]))

    per = collections.defaultdict(list)
    for r in rows:
        buy, hc = SR.classify_race(r)
        for f in buy:
            name, desc, roi_claim, verdict = f[0], f[1], f[2], f[3]
            st = SR.settle_fire(r, name, desc)
            if st is None:
                continue
            pts, pay100 = st
            ven = VEN.get(r["rid"][4:6], r.get("venue") or "?")
            rno = int(r["rid"][10:12])
            o1 = r["odds"].get(r["order"][0])
            per[name].append(dict(date=r["date"], ba=f"{ven}{rno}R", desc=desc,
                                  o1=o1, pts=pts, pay=pay100,
                                  hit=pay100 > 0, pl=pay100 - pts * 100))
    out = []
    out.append("# 凍結パターン(◎買い級) 全発火レース一覧 — 台帳2394R(〜2026/8月頭)\n")
    out.append("> 100円/点建て。**この表は採掘に使った台帳上の成績(in-sample)**。"
               "8月は凍結後の前向き検証月＝別表参照。\n")
    order_names = sorted(per, key=lambda k: -sum(x["pl"] for x in per[k]))
    for name in order_names:
        L = per[name]
        n = len(L); hits = sum(x["hit"] for x in L)
        cost = sum(x["pts"] for x in L) * 100
        ret = sum(x["pay"] for x in L)
        out.append(f"\n## {name}")
        out.append(f"**n={n} / 的中{hits} ({hits/n*100:.0f}%) / ROI {ret/cost*100:.1f}% / "
                   f"収支{ret-cost:+,.0f}円**\n")
        out.append("| 日付 | 場R | 買い目 | 1位オッズ | 結果 | 払戻 | 損益 |")
        out.append("|---|---|---|---|---|---|---|")
        for x in L:
            d = x["date"]
            ds = f"{d[4:6]}/{d[6:8]}" if len(d) == 8 else d
            out.append(f"| {ds} | {x['ba']} | {x['desc'][:28]} | {x['o1']}倍 | "
                       f"{'○的中' if x['hit'] else '✕'} | {x['pay']:,.0f} | {x['pl']:+,.0f} |")
    open("PATTERN_ALL_RESULTS.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"WROTE PATTERN_ALL_RESULTS.md ({sum(len(v) for v in per.values())}発火 / "
          f"{len(per)}パターン)")
    for name in order_names:
        L = per[name]
        cost = sum(x['pts'] for x in L) * 100; ret = sum(x['pay'] for x in L)
        print(f"  {name:<40} n={len(L):<4} hit={sum(x['hit'] for x in L):<3} "
              f"ROI={ret/cost*100:6.1f}% P/L={ret-cost:+9,.0f}円")


if __name__ == "__main__":
    main()
