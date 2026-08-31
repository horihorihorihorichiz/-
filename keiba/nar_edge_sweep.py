# -*- coding: utf-8 -*-
"""「NARのどこかに控除率を超える帯があるか」をセル総当りで採掘し、
   同時にラベルシャッフルの偽陽性率(null sweep)を測って、見つかった数が
   偶然の範囲かどうかを判定する。RULES.md の採掘プロトコル準拠。
   usage: python3 nar_edge_sweep.py [--jra] [--nulls 200]
"""
import argparse, glob, json, random
from collections import defaultdict

VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
         "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
         "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀"}
NANKAN = {"42", "43", "44", "45"}
MIN_N = 150


def fbin(f):
    return "~9頭" if f <= 9 else "10-12頭" if f <= 12 else "13-14頭" if f <= 14 else "15頭+"


def dbin(d):
    return "短" if d <= 1300 else "マ" if d <= 1700 else "中長"


def load(nar=True):
    """-> list of bet rows: dict(cells=[...], win_ret, plc_ret)"""
    rows = []
    files = (sorted(glob.glob("hist_nar_flat/*.json") + glob.glob("hist_nar/*.json"))
             if nar else sorted(glob.glob("hist/*.json")))
    seen = set()
    for f in files:
        rid = f.split("/")[-1][:12]
        if rid in seen:
            continue
        seen.add(rid)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        race = d.get("race", {})
        res = d.get("result", {})
        order = res.get("order") or []
        po = res.get("payout") or {}
        tan = {str(k): v for k, v in (po.get("単勝") or {}).items()}
        fuku = {str(k): v for k, v in (po.get("複勝") or {}).items()}
        if not tan or not fuku or len(order) < 5:
            continue
        v = VENUE.get(rid[4:6], "JRA") if nar else "JRA"
        fb = fbin(len(order))
        db = dbin(race.get("distance") or 0)
        ba = race.get("baba") or "?"
        sf = race.get("surface") or "?"
        for o in order:
            p = o.get("ninki") if not nar else o.get("odds")   # NARのoddsは人気列
            rk = str(o.get("rank", ""))
            if not p or not rk.isdigit():
                continue
            p = int(p)
            if p > 6:
                continue
            num = str(o["num"])
            cells = [f"{v}/人気{p}", f"{v}/人気{p}/{fb}", f"人気{p}/{fb}",
                     f"{v}/人気{p}/{db}", f"人気{p}/{db}", f"{v}/人気{p}/{ba}",
                     f"人気{p}/{fb}/{db}", f"{v}/人気{p}/{sf}"]
            rows.append(dict(cells=cells,
                             w=(tan.get(num, 0) if int(rk) == 1 else 0),
                             p=fuku.get(num, 0)))
    return rows


def sweep(rows, key):
    C = defaultdict(lambda: [0, 0.0])
    for r in rows:
        for c in r["cells"]:
            C[c][0] += 1
            C[c][1] += r[key]
    return {c: (n, s / n) for c, (n, s) in C.items() if n >= MIN_N}


def null_rate(rows, key, nulls, seed=3):
    """各ベットの払戻を全体からシャッフル(セル構造は保持)して、
       ROI>100%のセルが何個出るかの分布を測る＝採掘手順の偽陽性率。"""
    rnd = random.Random(seed)
    vals = [r[key] for r in rows]
    counts = []
    for _ in range(nulls):
        sh = vals[:]
        rnd.shuffle(sh)
        C = defaultdict(lambda: [0, 0.0])
        for r, v in zip(rows, sh):
            for c in r["cells"]:
                C[c][0] += 1
                C[c][1] += v
        counts.append(sum(1 for n, s in C.values() if n >= MIN_N and s / n > 100.0))
    counts.sort()
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jra", action="store_true")
    ap.add_argument("--nulls", type=int, default=200)
    a = ap.parse_args()
    for nar in ([False] if a.jra else [True, False]):
        rows = load(nar)
        nm = "NAR" if nar else "JRA"
        print(f"\n{'='*70}\n{nm}: ベット行 {len(rows)} 件（人気1〜6のみ）")
        for key, lab in (("w", "単勝"), ("p", "複勝")):
            S = sweep(rows, key)
            hits = sorted([(c, n, r) for c, (n, r) in S.items() if r > 100.0],
                          key=lambda x: -x[2])
            nl = null_rate(rows, key, a.nulls)
            exp = sum(nl) / len(nl)
            p95 = nl[int(len(nl) * .95)]
            print(f"\n[{nm} {lab}] 検定セル {len(S)} 個 / ROI>100%のセル {len(hits)} 個 "
                  f"| nullシャッフル期待 {exp:.2f}個 (95%上限 {p95}個)")
            for c, n, r in hits[:10]:
                print(f"    {c:32s} n={n:6d} ROI {r:6.1f}%")
            if not hits:
                print("    （該当なし）")
            best = max(S.items(), key=lambda x: x[1][1])
            print(f"    最良セル: {best[0]} n={best[1][0]} ROI {best[1][1]:.1f}%")


if __name__ == "__main__":
    main()
