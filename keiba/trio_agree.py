# -*- coding: utf-8 -*-
"""三連複×「人気とシステムの一致」スイープ（7/19ユーザー案）。
   モデル順位と市場人気の合意/不合意を条件に、三連複構造を二段階検証。
   dev(<202605) ROI>=103% & n>=25R / conf(>=202605) ROI>=100% & n>=10R
"""
import json, collections

recs = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]

def tp(p, combo):
    return p.get("三連複", {}).get("-".join(str(x) for x in sorted(combo)), 0)

def pairs_cost_ret(pay, axis, pairs):
    return len(pairs)*100, sum(tp(pay, (axis, a, b)) for a, b in pairs)

tests = collections.defaultdict(lambda: {"dev": [0, 0], "conf": [0, 0],
                                         "mon": collections.defaultdict(lambda: [0, 0])})

def book(name, month, cost, ret):
    ph = "dev" if month < "202605" else "conf"
    tests[name][ph][0] += cost
    tests[name][ph][1] += ret
    tests[name]["mon"][month][0] += cost
    tests[name]["mon"][month][1] += ret

for r in recs:
    odds = {int(k): v for k, v in r["odds"].items() if v}
    order = r["order"]
    if not order or len(odds) < 6:
        continue
    mkt = sorted(odds, key=lambda h: odds[h])          # 市場人気順
    t1 = order[0]
    o1 = odds.get(t1, 0)
    fav = mkt[0]
    ofav = odds[fav]
    m3, m5 = set(order[:3]), set(order[:5])
    k3 = set(mkt[:3])
    dist = r.get("dist") or 0
    pay = r["payout"]
    mo = r["month"]

    # ---- T1: 完全一致BOX（モデルtop3 == 市場top3）→ その3頭の1点 ----
    if m3 == k3:
        book("T1.完全一致top3→その3頭1点", mo, 100, tp(pay, tuple(m3)))
        if ofav >= 2.0:
            book("T1b.完全一致×1人気2倍+", mo, 100, tp(pay, tuple(m3)))

    # ---- T2: 一致軸（モデル1位=1人気）× 相手市場2-4位 3点 ----
    if t1 == fav:
        p234 = mkt[1:4]
        if len(p234) >= 3:
            prs = [(p234[0], p234[1]), (p234[0], p234[2]), (p234[1], p234[2])]
            c, ret = pairs_cost_ret(pay, t1, prs)
            book("T2.一致軸×相手2-4人気3点", mo, c, ret)
            if 2.0 <= o1 <= 4.0:
                book("T2b.一致軸(2-4倍)×相手2-4人気", mo, c, ret)
            if o1 >= 3.0:
                book("T2c.一致軸(3倍+)×相手2-4人気", mo, c, ret)
            # 相手にシステム上位条件
            if all(p in m5 for p in p234):
                book("T2d.一致軸×相手2-4人気全員モデルtop5", mo, c, ret)

    # ---- 発火ゾーン（乖離軸）系 ----
    fire = o1 >= 7.0
    if fire:
        p13 = [n for n in mkt if n != t1][:3]
        if len(p13) >= 3:
            prs = [(p13[0], p13[1]), (p13[0], p13[2]), (p13[1], p13[2])]
            c, ret = pairs_cost_ret(pay, t1, prs)
            n_agree = sum(1 for p in p13 if p in m5)
            if 10 <= o1 <= 30 and dist <= 1900:
                book("T0.現行3点(基準)", mo, c, ret)
                # T4/T5: 紐のシステム一致フィルタ
                if n_agree == 3:
                    book("T4.現行+紐3頭全員モデルtop5", mo, c, ret)
                if n_agree >= 2:
                    book("T5.現行+紐2頭以上モデルtop5", mo, c, ret)
                if n_agree <= 1:
                    book("T5x.現行+紐一致1以下(不一致)", mo, c, ret)
            # T6: 却下済み軸7-10倍ゾーンの救済
            if 7 <= o1 < 10:
                book("T6.軸7-10倍3点(却下済基準)", mo, c, ret)
                if n_agree == 3:
                    book("T6a.軸7-10倍+紐全員モデルtop5", mo, c, ret)
                if n_agree >= 2 and dist <= 1900:
                    book("T6b.軸7-10倍+紐2+一致+≤1900m", mo, c, ret)
            # T7: 距離制限なしの10-30倍+一致条件（1900m制限の代替になるか）
            if 10 <= o1 <= 30:
                if n_agree == 3:
                    book("T7.軸10-30倍+紐全一致(距離不問)", mo, c, ret)
        # T8: 紐を「モデル2-3位∩市場top5」+「市場1-2位」のハイブリッド
        hyb = []
        for h in order[1:4]:
            if h in set(mkt[:5]) and h not in hyb:
                hyb.append(h)
        for h in mkt[:2]:
            if h != t1 and h not in hyb:
                hyb.append(h)
        hyb = hyb[:3]
        if len(hyb) == 3 and 10 <= o1 <= 30 and dist <= 1900:
            prs = [(hyb[0], hyb[1]), (hyb[0], hyb[2]), (hyb[1], hyb[2])]
            c, ret = pairs_cost_ret(pay, t1, prs)
            book("T8.紐=モデル×市場ハイブリッド3点", mo, c, ret)

    # ---- T9: モデル2位が市場1人気（=1位乖離+2位一致）×2位軸ながし ----
    if len(order) >= 2 and order[1] == fav and o1 >= 7.0:
        ax2 = order[1]
        p3 = [n for n in mkt[1:] if n != ax2][:3]
        if len(p3) >= 3:
            prs = [(p3[0], p3[1]), (p3[0], p3[2]), (p3[1], p3[2])]
            c, ret = pairs_cost_ret(pay, ax2, prs)
            book("T9.モデル2位=1人気を軸に3点", mo, c, ret)

print(f"総レース {len(recs)}R\n")
rows = []
for name, d in tests.items():
    dv, cf = d["dev"], d["conf"]
    if not dv[0] or not cf[0]:
        continue
    droi, croi = dv[1]/dv[0], cf[1]/cf[0]
    tot = (dv[1]+cf[1])/(dv[0]+cf[0])
    ok = droi >= 1.03 and dv[0] >= 25*100 and croi >= 1.00 and cf[0] >= 10*100
    rows.append((ok, tot, name, droi, dv[0]//100, croi, cf[0]//100))
rows.sort(key=lambda x: (-x[0], -x[1]))
for ok, tot, name, droi, dn, croi, cn in rows:
    mark = "★" if ok else " "
    print(f"{mark}{name:34s} 発見{100*droi:6.1f}%({dn:4d}点) 確認{100*croi:6.1f}%({cn:4d}点) 通算{100*tot:6.1f}%")
