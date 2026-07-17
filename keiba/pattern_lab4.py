# -*- coding: utf-8 -*-
"""パターン研究所・第4弾: 「軸は来るが勝ちきらない」型の歪み（ヴェルテンベルク型・7/14）。
   鍵: 相手を市場の人気馬に置く(今までの失敗=相手もモデル穴で二重に薄い)。
   - ワイド/三連複: 乖離軸×市場上位
   - 馬単/三連単: 軸の2着・3着固定
   ×生存条件(中距離/上級/ダ/混戦/重賞/オッズ帯)
   usage: python3 pattern_lab4.py
"""
import itertools, json, math
from collections import defaultdict

DEV_END = "202605"
MIN_DEV_BETS = 50
MIN_CONF_BETS = 20


def pay(rec, kind, key):
    return rec["payout"].get(kind, {}).get(key, 0)


def main():
    preds = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]
    print(f"WF予測 {len(preds)}R")
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))

    def book(name, phase, st, ret):
        a = acc[name][phase]
        a[0] += st; a[1] += ret; a[2] += 1

    for rec in preds:
        phase = "dev" if rec["month"] < DEV_END else "conf"
        om = {int(k): v for k, v in rec["odds"].items()}
        order = rec["order"]
        t1 = order[0]
        msort = sorted(om, key=lambda h: om[h])
        mrank = {n: i+1 for i, n in enumerate(msort)}
        if mrank.get(t1, 0) < 4:
            continue    # 乖離レースのみが対象
        # 市場上位(軸自身は除く)
        mtop = [n for n in msort if n != t1][:3]
        if len(mtop) < 2:
            continue
        o1 = om.get(t1, 0)
        sc = {int(k): v for k, v in rec["scores"].items()}
        so = sorted(sc.values(), reverse=True)
        gap12 = so[0]-so[1] if len(so) >= 2 else 0

        conds = {"全乖離": True,
                 "中距離": 1401 <= (rec["dist"] or 0) <= 1900,
                 "上級(2勝+)": (rec["tier"] or 0) >= 6,
                 "重賞級(tier9+)": (rec["tier"] or 0) >= 9,
                 "ダ": rec["surface"] == "ダ",
                 "芝": rec["surface"] == "芝",
                 "混戦(gap小)": gap12 < 0.45,
                 "軸10-30倍": 10 <= o1 <= 30}

        m1, m2, m3 = (mtop + [None]*3)[:3]
        bets = {}
        k_ax1 = "-".join(map(str, sorted((t1, m1))))
        k_ax2 = "-".join(map(str, sorted((t1, m2))))
        bets["ワイド軸×市場1人気"] = [("ワイド", k_ax1)]
        bets["ワイド軸×市場上位2(2点)"] = [("ワイド", k_ax1), ("ワイド", k_ax2)]
        bets["馬連軸×市場上位2(2点)"] = [("馬連", k_ax1), ("馬連", k_ax2)]
        bets["馬単軸2着固定←市場上位2(2点)"] = [("馬単", f"{m1}→{t1}"), ("馬単", f"{m2}→{t1}")]
        bets["馬単軸1着→市場上位2(2点)"] = [("馬単", f"{t1}→{m1}"), ("馬単", f"{t1}→{m2}")]
        bets["三連複軸+市場上位2(1点)"] = [("三連複", "-".join(map(str, sorted((t1, m1, m2)))))]
        if m3:
            bets["三連複軸×市場上位3ながし(3点)"] = [
                ("三連複", "-".join(map(str, sorted((t1,) + p))))
                for p in itertools.combinations((m1, m2, m3), 2)]
            # 三連単: 軸2着固定(市場上位2→軸→市場上位3残り)
            st2 = []
            for x in (m1, m2):
                for y in (m1, m2, m3):
                    if y != x:
                        st2.append(("三連単", f"{x}→{t1}→{y}"))
            bets["三連単軸2着固定F(市場2→軸→市場3)"] = st2
            # 三連単: 軸3着固定
            st3 = []
            for x, y in itertools.permutations((m1, m2, m3), 2):
                st3.append(("三連単", f"{x}→{y}→{t1}"))
            bets["三連単軸3着固定F(市場3→市場3→軸)"] = st3
        # 複勝軸(比較基準)
        bets["複勝軸"] = [("複勝", str(t1))]

        for bname, pts in bets.items():
            st = 100*len(pts)
            ret = sum(pay(rec, kind, key) for kind, key in pts)
            for cname, ok in conds.items():
                if not ok:
                    continue
                book(f"{bname}×{cname}", phase, st, ret)

    survivors = []
    n_cand = 0
    for name, ph in acc.items():
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_BETS or dv[0] == 0:
            continue
        droi = dv[1]/dv[0]*100
        if droi < 103:
            continue
        n_cand += 1
        if cf[2] >= MIN_CONF_BETS and cf[0] > 0 and cf[1]/cf[0]*100 >= 100:
            survivors.append(dict(pattern=name,
                                  dev_roi=round(droi, 1), dev_n=dv[2],
                                  conf_roi=round(cf[1]/cf[0]*100, 1), conf_n=cf[2],
                                  total_roi=round((dv[1]+cf[1])/(dv[0]+cf[0])*100, 1),
                                  total_n=dv[2]+cf[2]))
    survivors.sort(key=lambda x: -x["total_roi"])
    print(f"発見通過: {n_cand}件 / 確認も通過: {len(survivors)}件\n")
    print("==== ヴェルテンベルク型（軸絡み系）の生存者 ====")
    for s in survivors:
        print(f"  {s['pattern']}: 発見{s['dev_roi']}%({s['dev_n']}R) "
              f"確認{s['conf_roi']}%({s['conf_n']}R) 通算{s['total_roi']}%({s['total_n']}R)")
    json.dump(survivors, open("pattern_stats5.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ pattern_stats5.json")


if __name__ == "__main__":
    main()
