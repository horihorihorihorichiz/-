# -*- coding: utf-8 -*-
"""パターン研究所・第6弾: ハイブリッド型（7/18ユーザー指示「システム評価も・人気でもいい」）。
   新構造: 軸=モデルと市場の意見が一致した人気馬（ダブル確認・的中率高い）
           相手=モデルだけが高評価の人気薄（システムの独自情報を相手側に置く）
   ＋モデル自信度(gap)×人気帯の細分も再測定。
   usage: python3 pattern_lab6.py
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
        sc = {int(k): v for k, v in rec["scores"].items()}
        so = sorted(sc.values(), reverse=True)
        gap12 = so[0]-so[1] if len(so) >= 2 else 0

        # === 型1: 一致軸（モデル1位=市場1-2人気） + 乖離相手（モデル2-4位×市場6人気+） ===
        agree = mrank.get(t1, 99) <= 2
        div_partners = [n for n in order[1:4] if mrank.get(n, 0) >= 6]
        if agree and div_partners:
            d = div_partners[0]   # モデル順で最上位の乖離相手
            kd = "-".join(map(str, sorted((t1, d))))
            m2 = [n for n in msort if n not in (t1, d)][:2]
            for cname, ok in {"基本": True, "自信大": gap12 >= 0.9,
                              "相手10倍+": om.get(d, 0) >= 10}.items():
                if not ok:
                    continue
                book(f"H1.ワイド一致軸×乖離相手[{cname}]", phase, 100, pay(rec, "ワイド", kd))
                book(f"H1.馬連一致軸×乖離相手[{cname}]", phase, 100, pay(rec, "馬連", kd))
                book(f"H1.馬単一致軸→乖離相手[{cname}]", phase, 100, pay(rec, "馬単", f"{t1}→{d}"))
                # 三連複: 一致軸+乖離相手+市場2位 (1点) / +市場上位2への2点
                if len(m2) >= 2:
                    k3a = "-".join(map(str, sorted((t1, d, m2[0]))))
                    k3b = "-".join(map(str, sorted((t1, d, m2[1]))))
                    book(f"H1.三連複軸+乖離+市場上位(2点)[{cname}]", phase, 200,
                         pay(rec, "三連複", k3a) + pay(rec, "三連複", k3b))

        # === 型2: ダブル確認の厚張り（1位=1人気×自信度細分） ===
        if mrank.get(t1, 99) == 1:
            for gname, ok in {"gap0.9+": gap12 >= 0.9, "gap1.3+": gap12 >= 1.3}.items():
                if not ok:
                    continue
                book(f"H2.単勝ダブル確認[{gname}]", phase, 100, pay(rec, "単勝", str(t1)))
                m23 = [n for n in msort if n != t1][:2]
                if len(m23) >= 2:
                    book(f"H2.馬単1着固定→市場2頭[{gname}]", phase, 200,
                         pay(rec, "馬単", f"{t1}→{m23[0]}") + pay(rec, "馬単", f"{t1}→{m23[1]}"))

        # === 型3: モデル2位の乖離（1位人気馬が堅い時の相方） ===
        t2 = order[1] if len(order) > 1 else None
        if t2 and mrank.get(t1, 99) <= 2 and mrank.get(t2, 0) >= 5:
            for cname, ok in {"基本": True, "自信大": gap12 >= 0.9}.items():
                if not ok:
                    continue
                book(f"H3.単勝モデル2位乖離[{cname}]", phase, 100, pay(rec, "単勝", str(t2)))
                kd = "-".join(map(str, sorted((t1, t2))))
                book(f"H3.ワイド1位×2位乖離[{cname}]", phase, 100, pay(rec, "ワイド", kd))

    rows = []
    for name, ph in sorted(acc.items()):
        dv, cf = ph["dev"], ph["conf"]
        if dv[2] < MIN_DEV_RACES:
            continue
        droi = dv[1]/dv[0]*100 if dv[0] else 0
        croi = cf[1]/cf[0]*100 if cf[0] else 0
        tot = (dv[1]+cf[1])/(dv[0]+cf[0])*100 if (dv[0]+cf[0]) else 0
        rows.append((name, droi, dv[2], croi, cf[2], tot))
    rows.sort(key=lambda x: -x[5])
    print("\n==== ハイブリッド型の全測定 ====")
    for name, droi, dn, croi, cn, tot in rows:
        mark = "★" if (droi >= 103 and croi >= 100 and cn >= MIN_CONF_RACES) else " "
        print(f" {mark}{name:36s}: 発見{droi:6.1f}%({dn:3d}R) 確認{croi:6.1f}%({cn:3d}R) 通算{tot:6.1f}%")


if __name__ == "__main__":
    main()
