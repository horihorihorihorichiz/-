# -*- coding: utf-8 -*-
"""Ver.100エンジンのバックテスト検証。
   hist/*.json（レース+結果）に、最終オッズ盤（fetch_jra、hist_odds/にキャッシュ）を合わせ、
   build_buylist_ev をそのまま走らせて実際の払戻でROIを計測する。

   usage:
     python3 validate.py --fetch-odds            # オッズ盤の収穫(初回のみ)
     python3 validate.py --test 20260711,20260712 [--scales 0.8,1.0,1.2,1.4]

   注意: オッズは「最終オッズ」なので実際に買える時点のオッズとはズレる（特に直前変動）。
   結果はやや楽観方向に出うる点を必ず添えて解釈する。"""
import argparse, glob, json, os, sys
from concurrent.futures import ThreadPoolExecutor

import calc
import predict as PR


def fetch_all_odds(histdir, oddsdir, workers=4):
    os.makedirs(oddsdir, exist_ok=True)
    rids = [os.path.basename(f)[:-5] for f in glob.glob(os.path.join(histdir, "*.json"))]
    todo = [r for r in rids if not os.path.exists(os.path.join(oddsdir, f"{r}.json"))]
    print(f"オッズ盤収穫: {len(todo)}/{len(rids)}レース", file=sys.stderr)
    def one(rid):
        try:
            o = PR.fetch_jra(rid)
            if not o.get("tan"):
                return f"{rid} EMPTY"
            json.dump(o, open(os.path.join(oddsdir, f"{rid}.json"), "w",
                              encoding="utf-8"), ensure_ascii=False)
            return f"{rid} OK"
        except Exception as e:
            return f"{rid} FAIL {e}"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, msg in enumerate(ex.map(one, todo)):
            if "OK" not in msg:
                print(" ", msg, file=sys.stderr)
            if (i+1) % 25 == 0:
                print(f"  ...{i+1}/{len(todo)}", file=sys.stderr)


def settle(picks, payout):
    """買い目リストを実際の払戻で精算。返り値=払戻合計円"""
    ret = 0
    PAYKEY = {"単勝": "単勝", "複勝": "複勝", "馬連": "馬連", "ワイド": "ワイド",
              "三連複": "三連複", "馬単": "馬単", "三連単": "三連単"}
    for kind, lbl, o, st, p, ev in picks:
        table = payout.get(PAYKEY.get(kind, kind), {})
        if kind in ("単勝", "複勝"):
            key = lbl
        else:
            key = lbl.replace(">", "→")
        if key in table:
            ret += st//100 * table[key]
    return ret


def run_sim(files, oddsdir, scale, budget=10000):
    n_go = staked = returned = 0
    bykind = {}
    details = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        rid = d["race"].get("race_id", "")
        op = os.path.join(oddsdir, f"{rid}.json")
        if not os.path.exists(op):
            continue
        odds = json.load(open(op, encoding="utf-8"))
        try:
            res = calc.run(d["race"])
        except Exception:
            continue
        picks, total, dec = PR.build_buylist_ev(res["rows"], odds,
                                                budget=budget, edge_scale=scale)
        if not picks:
            continue
        ret = settle(picks, d["result"].get("payout", {}))
        n_go += 1
        staked += total
        returned += ret
        for kind, lbl, o, st, p, ev in picks:
            hit = settle([(kind, lbl, o, st, p, ev)], d["result"].get("payout", {}))
            bk = bykind.setdefault(kind, [0, 0, 0, 0])  # n, staked, returned, hits
            bk[0] += 1; bk[1] += st; bk[2] += hit; bk[3] += (1 if hit else 0)
        details.append((rid, total, ret))
    return dict(n_races=len(files), n_go=n_go, staked=staked, returned=returned,
                roi=(returned/staked*100 if staked else 0), bykind=bykind,
                details=details)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdir", default="hist")
    ap.add_argument("--oddsdir", default="hist_odds")
    ap.add_argument("--fetch-odds", action="store_true")
    ap.add_argument("--test", default="", help="テスト日(YYYYMMDD,カンマ区切り)")
    ap.add_argument("--scales", default="0.8,0.9,1.0,1.1,1.2,1.4")
    a = ap.parse_args()

    if a.fetch_odds:
        fetch_all_odds(a.histdir, a.oddsdir)
        return

    files = sorted(glob.glob(os.path.join(a.histdir, "*.json")))
    test_days = set(a.test.split(",")) if a.test else set()
    def day_of(f):
        try:
            return json.load(open(f, encoding="utf-8")).get("date", "")
        except Exception:
            return ""
    days = {f: day_of(f) for f in files}
    train = [f for f in files if days[f] not in test_days]
    test = [f for f in files if days[f] in test_days]
    print(f"train {len(train)}R / test {len(test)}R")

    for scale in [float(x) for x in a.scales.split(",")]:
        r = run_sim(train, a.oddsdir, scale)
        print(f"\n== scale={scale} (train) == GO {r['n_go']}/{r['n_races']}R "
              f"投{r['staked']}円 戻{r['returned']}円 ROI {r['roi']:.1f}%")
        for kind, (n, st, ret, hits) in sorted(r["bykind"].items()):
            print(f"   {kind}: {n}点 的中{hits} 投{st} 戻{ret} ROI {ret/st*100 if st else 0:.0f}%")
    if test:
        print("\n──── ホールドアウト(test) ────")
        for scale in [float(x) for x in a.scales.split(",")]:
            r = run_sim(test, a.oddsdir, scale)
            print(f"== scale={scale} (test) == GO {r['n_go']}/{r['n_races']}R "
                  f"投{r['staked']}円 戻{r['returned']}円 ROI {r['roi']:.1f}%")
            for kind, (n, st, ret, hits) in sorted(r["bykind"].items()):
                print(f"   {kind}: {n}点 的中{hits} 投{st} 戻{ret} ROI {ret/st*100 if st else 0:.0f}%")


if __name__ == "__main__":
    main()
