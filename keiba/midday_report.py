# -*- coding: utf-8 -*-
"""当日ここまでの答え合わせ: デイボードの判定×実結果を会場別に一覧化(2026-08-23指示)。
board_YYYYMMDD.md の主表 + odds_timeline のrid + fetch_result で、終了済みレースの
モデル1位の成績(勝ち/複勝圏/圏外)と発火の損益を出す。
usage: python3 midday_report.py [YYYYMMDD]
"""
import json, re, sys, datetime, collections
sys.path.insert(0, ".")
import fetch_result as FR

VEN = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
       "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else jst_now().strftime("%Y%m%d")
    # 会場ごとのrid接頭辞(年+場+回+日=10桁)を当日の観測ridから引き、全Rを復元する
    # (午前の時点が欠けていてもprefixは午後のridから取れる)
    prefix = {}
    for line in open(f"odds_timeline/{day}.jsonl", encoding="utf-8"):
        try:
            d = json.loads(line)
            rid = d.get("race_id") or d.get("rid")
            if rid:
                prefix[VEN.get(rid[4:6], "?")] = rid[:10]
        except Exception:
            pass
    rid_of = {(v, r): p + f"{r:02d}" for v, p in prefix.items() for r in range(1, 13)}

    rows = []
    for line in open(f"board_{day}.md", encoding="utf-8"):
        m = re.match(r"\| (\S+) \| (\d+) \| (\d+:\d+) \| (\S+) \| \S+ \| (\d+) (\S+) \| "
                     r"([\d.]+)倍\((\d+)人\) \| ([\d.]+) \| \*\*(\S+)\*\* \|", line)
        if m:
            rows.append(dict(ven=m.group(1), r=int(m.group(2)), post=m.group(3),
                             race=m.group(4), axis=int(m.group(5)), aname=m.group(6),
                             odds=float(m.group(7)), pop=int(m.group(8)),
                             g12=float(m.group(9)), tier=m.group(10)))
    now = jst_now().strftime("%H:%M")
    done = [x for x in rows if x["post"] <= now]
    out = [f"# {day[4:6]}/{day[6:8]} 途中経過 — システム判定×実結果（{now}時点・{len(done)}R終了）\n"]
    agg = collections.defaultdict(lambda: dict(n=0, win=0, top3=0, tan=0.0, fuku=0.0))
    for ven in ("札幌", "新潟", "中京"):
        sub = [x for x in done if x["ven"] == ven]
        if not sub:
            continue
        out.append(f"\n## {ven}\n")
        out.append("| R | 判定 | モデル1位 | 事前オッズ | 結果1-2-3着 | 1位の成績 | 単勝払戻 | 複勝払戻 |")
        out.append("|---|---|---|---|---|---|---|---|")
        for x in sub:
            rid = rid_of.get((ven, x["r"]))
            res = None
            if rid:
                try:
                    res = FR.get_result(rid)
                except Exception:
                    pass
            if not res or not (res.get("payout") or {}).get("単勝"):
                out.append(f"| {x['r']} | {x['tier']} | {x['axis']} {x['aname']} | "
                           f"{x['odds']}倍({x['pop']}人) | 結果未確定 | — | — | — |")
                continue
            order = res["order"]
            top3n = [o["num"] for o in order[:3]]
            pay = res["payout"]
            fin = next((int(o["rank"]) for o in order
                        if o["num"] == x["axis"] and str(o["rank"]).isdigit()), None)
            tan = float(pay["単勝"].get(str(x["axis"]), 0))
            fuku = float((pay.get("複勝") or {}).get(str(x["axis"]), 0))
            a = agg[ven]
            a["n"] += 1
            a["win"] += int(fin == 1)
            a["top3"] += int(bool(fuku))
            a["tan"] += tan
            a["fuku"] += fuku
            mark = "◎1着" if fin == 1 else (f"○{fin}着(複勝圏)" if fuku else
                                            (f"{fin}着" if fin else "着外"))
            out.append(f"| {x['r']} | {x['tier']} | {x['axis']} {x['aname']} | "
                       f"{x['odds']}倍({x['pop']}人) | {'-'.join(map(str, top3n))} | {mark} | "
                       f"{tan:,.0f} | {fuku:,.0f} |")
        a = agg[ven]
        if a["n"]:
            out.append(f"\n**{ven}集計: {a['n']}R / モデル1位の勝率 {a['win']}/{a['n']} / "
                       f"複勝圏 {a['top3']}/{a['n']} ({a['top3']/a['n']*100:.0f}%) / "
                       f"仮に1位単勝100円ずつ→回収{a['tan']/a['n']:.0f}% / "
                       f"1位複勝100円ずつ→回収{a['fuku']/a['n']:.0f}%**")
    tn = sum(a["n"] for a in agg.values())
    if tn:
        tw = sum(a["win"] for a in agg.values()); t3 = sum(a["top3"] for a in agg.values())
        tt = sum(a["tan"] for a in agg.values()); tf = sum(a["fuku"] for a in agg.values())
        out.append(f"\n## 全場計: {tn}R / 1位勝率 {tw/tn*100:.0f}% / 複勝圏 {t3/tn*100:.0f}% / "
                   f"単勝回収 {tt/tn:.0f}% / 複勝回収 {tf/tn:.0f}%")
    fn = f"MIDDAY_{day}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"WROTE {fn}")


if __name__ == "__main__":
    main()
