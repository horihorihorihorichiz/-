# -*- coding: utf-8 -*-
"""パターン研究所・第5弾: 大穴軸×相手を広げた三連複ながし（7/18ユーザー仮説）。
   仮説: 軸が15倍・30倍級の大穴の時、相手を人気上位4〜6頭に広げれば
   爆発配当が的中率の低さを上回るのでは？
   usage: python3 pattern_lab5.py
"""
import itertools, json
from collections import defaultdict

DEV_END = "202605"
MIN_DEV_RACES = 30
MIN_CONF_RACES = 12


def pay(rec, kind, key):
    return rec["payout"].get(kind, {}).get(key, 0)


def main():
    preds = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]
    print(f"WF予測 {len(preds)}R")
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))

    for rec in preds:
        phase = "dev" if rec["month"] < DEV_END else "conf"
        om = {int(k): v for k, v in rec["odds"].items()}
        order = rec["order"]
        t1 = order[0]
        msort = sorted(om, key=lambda h: om[h])
        mrank = {n: i+1 for i, n in enumerate(msort)}
        if mrank.get(t1, 0) < 4:
            continue
        o1 = om.get(t1, 0)
        bands = {"全乖離": True, "軸8倍+": o1 >= 8, "軸10倍+": o1 >= 10,
                 "軸15倍+": o1 >= 15, "軸20倍+": o1 >= 20, "軸30倍+": o1 >= 30,
                 "軸10-20倍": 10 <= o1 <= 20}
        mtop = [n for n in msort if n != t1]
        for N in (3, 4, 5, 6):
            partners = mtop[:N]
            if len(partners) < N:
                continue
            pts = [("三連複", "-".join(map(str, sorted((t1,) + p))))
                   for p in itertools.combinations(partners, 2)]
            wpts = [("ワイド", "-".join(map(str, sorted((t1, x))))) for x in partners]
            for bname, ok in bands.items():
                if not ok:
                    continue
                st = 100*len(pts)
                ret = sum(pay(rec, k, key) for k, key in pts)
                a = acc[(f"三連複軸ながし相手{N}頭", bname)][phase]
                a[0] += st; a[1] += ret; a[2] += 1
                st2 = 100*len(wpts)
                ret2 = sum(pay(rec, k, key) for k, key in wpts)
                a2 = acc[(f"ワイド軸ながし相手{N}頭", bname)][phase]
                a2[0] += st2; a2[1] += ret2; a2[2] += 1
        # 参考: 単勝・複勝の帯別
        for bname, ok in bands.items():
            if not ok:
                continue
            a = acc[("単勝軸", bname)][phase]
            a[0] += 100; a[1] += pay(rec, "単勝", str(t1)); a[2] += 1
            a = acc[("複勝軸", bname)][phase]
            a[0] += 100; a[1] += pay(rec, "複勝", str(t1)); a[2] += 1

    rows = []
    for (bet, band), ph in sorted(acc.items()):
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_RACES:
            continue
        droi = dv[1]/dv[0]*100 if dv[0] else 0
        croi = cf[1]/cf[0]*100 if cf[0] else 0
        tot = (dv[1]+cf[1])/(dv[0]+cf[0])*100 if (dv[0]+cf[0]) else 0
        rows.append((bet, band, droi, dv[2], croi, cf[2], tot))
    rows.sort(key=lambda x: -x[6])
    print(f"\n==== 大穴軸×ながし幅の全測定（発見/確認/通算ROI） ====")
    for bet, band, droi, dn, croi, cn, tot in rows:
        mark = "★" if (droi >= 103 and croi >= 100 and cn >= MIN_CONF_RACES) else " "
        print(f" {mark}{bet:22s}×{band:8s}: 発見{droi:6.1f}%({dn:3d}R) "
              f"確認{croi:6.1f}%({cn:3d}R) 通算{tot:6.1f}%")


if __name__ == "__main__":
    main()
