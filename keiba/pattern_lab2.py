# -*- coding: utf-8 -*-
"""パターン研究所・第2弾: S軸フォーメーション系（7/14ユーザー指示）。
   wf_preds.jsonl(未来を知らないV3予測)からS/A/Bランクを再構成し、
   ながし・フォーメーション・1着固定系×条件を2段階規律(発見/確認)で一斉測定。
   usage: python3 pattern_lab2.py
"""
import itertools, json
from collections import defaultdict

DEV_END = "202605"
MIN_DEV_RACES = 40
MIN_CONF_RACES = 15


def tiers_of(rec):
    """v2_liveと同じ流儀でS/A/Bランクを再構成"""
    sc = {int(k): v for k, v in rec["scores"].items()}
    disp = {n: 100.0 + 12.0*s for n, s in sc.items()}
    top = max(disp.values())
    out = {"S": [], "A": [], "B": [], "C": []}
    for n in sorted(disp, key=lambda x: -disp[x]):
        gr = (top - disp[n]) / top if top > 0 else 0
        k = "S" if gr <= 0.03 else "A" if gr <= 0.08 else "B" if gr <= 0.14 else "C"
        out[k].append(n)
    return out


def pay(rec, kind, key):
    return rec["payout"].get(kind, {}).get(key, 0)


def trio_key(c):
    return "-".join(map(str, sorted(c)))


def formations(rec):
    """(名前, 点数リスト[(kind,key)]) を返す。点数が0のものは出さない"""
    T = tiers_of(rec)
    S, A, B = T["S"], T["A"], T["B"]
    order = rec["order"]
    t1 = order[0]
    out = {}
    AB = A + B
    SA = S + A
    SAB = S + A + B

    if len(S) >= 1 and len(AB) >= 2:
        # 三連複 S1頭軸ながし→A+B
        pts = [("三連複", trio_key((S[0],) + p)) for p in itertools.combinations(AB[:6], 2)]
        out["三連複S軸ながしAB"] = pts
        # 馬連/ワイド S軸→AB
        out["馬連S軸→AB"] = [("馬連", "-".join(map(str, sorted((S[0], x))))) for x in AB[:5]]
        out["ワイドS軸→AB"] = [("ワイド", "-".join(map(str, sorted((S[0], x))))) for x in AB[:5]]
        # 馬単 S→AB / 三連単 S→AB→SAB
        out["馬単S1着→AB"] = [("馬単", f"{S[0]}→{x}") for x in AB[:5]]
        st3 = []
        for x in AB[:4]:
            for y in SAB[:6]:
                if y in (S[0], x):
                    continue
                st3.append(("三連単", f"{S[0]}→{x}→{y}"))
        out["三連単S1着→AB→SAB"] = st3
    if len(S) >= 2:
        # S2頭軸三連複ながし→A+B
        pts = [("三連複", trio_key((S[0], S[1], x))) for x in (A + B)[:6]]
        if pts:
            out["三連複S2頭軸→AB"] = pts
        out["馬連S1-S2"] = [("馬連", "-".join(map(str, sorted((S[0], S[1])))))]
    if len(S) >= 1 and len(SA) >= 3 and len(SAB) >= 4:
        # 三連複フォーメーション S-SA-SAB
        pts = set()
        for a in S:
            for b in SA:
                for c in SAB:
                    if len({a, b, c}) == 3:
                        pts.add(trio_key((a, b, c)))
        out["三連複F(S-SA-SAB)"] = [("三連複", k) for k in pts]
    return out


def conds(rec):
    om = {int(k): v for k, v in rec["odds"].items()}
    t1 = rec["order"][0]
    mr = sorted(om, key=lambda h: om[h]).index(t1) + 1 if t1 in om else 99
    T = tiers_of(rec)
    return {
        "全レース": True,
        "乖離(1位4人気+)": mr >= 4,
        "ダ": rec["surface"] == "ダ",
        "中距離": 1401 <= (rec["dist"] or 0) <= 1900,
        "上級(2勝+)": (rec["tier"] or 0) >= 6,
        "S単独": len(T["S"]) == 1,
        "S複数": len(T["S"]) >= 2,
        "乖離×ダ": mr >= 4 and rec["surface"] == "ダ",
        "乖離×上級": mr >= 4 and (rec["tier"] or 0) >= 6,
    }


def main():
    preds = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]
    print(f"WF予測 {len(preds)}R")
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for rec in preds:
        phase = "dev" if rec["month"] < DEV_END else "conf"
        C = conds(rec)
        F = formations(rec)
        for fname, pts in F.items():
            if not pts:
                continue
            st = 100*len(pts)
            ret = sum(pay(rec, kind, key) for kind, key in pts)
            for cname, ok in C.items():
                if not ok:
                    continue
                a = acc[(fname, cname)][phase]
                a[0] += st; a[1] += ret; a[2] += 1

    survivors = []
    n_cand = 0
    for (fname, cname), ph in acc.items():
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_RACES or dv[0] == 0:
            continue
        droi = dv[1]/dv[0]*100
        if droi < 103:
            continue
        n_cand += 1
        if cf[2] >= MIN_CONF_RACES and cf[0] > 0 and cf[1]/cf[0]*100 >= 100:
            survivors.append(dict(
                bet=fname, cond=cname,
                dev_roi=round(droi, 1), dev_races=dv[2],
                conf_roi=round(cf[1]/cf[0]*100, 1), conf_races=cf[2],
                total_roi=round((dv[1]+cf[1])/(dv[0]+cf[0])*100, 1),
                total_races=dv[2]+cf[2],
                total_stake=dv[0]+cf[0]))
    survivors.sort(key=lambda x: -x["total_roi"])
    print(f"発見通過: {n_cand}件 / 確認も通過: {len(survivors)}件\n")
    print("==== フォーメーション系の生存者 ====")
    for s in survivors:
        print(f"  {s['bet']} × {s['cond']}: 発見{s['dev_roi']}%({s['dev_races']}R) "
              f"確認{s['conf_roi']}%({s['conf_races']}R) 通算{s['total_roi']}% "
              f"({s['total_races']}R 投{s['total_stake']}円)")
    json.dump(survivors, open("pattern_stats3.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ pattern_stats3.json")


if __name__ == "__main__":
    main()
