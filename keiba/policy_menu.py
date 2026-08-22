# -*- coding: utf-8 -*-
"""レースごとに5つの型から最良の1つを選ぶポリシー（2026-08-22・ユーザー設計のメニュー）。

メニュー: 単勝1位1点 / 複勝1位1点 / ワイド1-2位1点 / 三連複1位軸→2-5位流し6点 /
         三連複1位軸→2-6位流し10点   （+見送り）
選択: レースの条件セルごとに、MINEで最もROIが高かった型を採用。
     「セルの最良型でもMINE ROI<100なら見送り」の期待値プラス方針も併測。
軸の候補(セルの切り方)は4つ用意し、**MINEの成績だけで**1つ選ぶ(VAL/CONFは触らない)。
検証: 選んだポリシーをVAL/CONFで各1回測定。null=順位乱数で全パイプライン(軸選択→
     セルごとの型選択)を10回再現(R2/R3遵守)。
"""
import json, os, sys, itertools, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V, v99w2_fit as V2
from verify_export import scorer_from_artifact

FORMS = ["単勝1位", "複勝1位", "ワイド1-2位", "三連複軸流し4頭(6点)", "三連複軸流し5頭(10点)"]
COSTS = np.array([100.0, 100.0, 100.0, 600.0, 1000.0])
OB = [0, 1.5, 2.0, 2.6, 3.5, 5.0, 8.0, 10**9]

def obl(o):
    for i in range(len(OB)-1):
        if OB[i] <= o < OB[i+1]:
            return f"{OB[i]:g}-{OB[i+1]:g}倍" if OB[i+1] < 10**8 else f"{OB[i]:g}倍+"
    return "?"

def main():
    races = V.load_races(); V2.attach_corner(races)
    wfn = scorer_from_artifact(json.load(open("hori52_w.json")))
    R = len(races)
    seg = np.zeros(R, int)
    rows = []
    for i, r in enumerate(races):
        s = r["Z16"] @ wfn(r)
        o = sorted(range(len(s)), key=lambda k: (-s[k], -r["wavg"][k], r["nums"][k]))
        rows.append([r["nums"][k] for k in o])
        m = r["month"]
        seg[i] = 0 if m <= "202602" else (1 if m <= "202605" else 2)
    segm = [seg == k for k in range(3)]

    def rets_of(order_list):
        RET = np.zeros((R, len(FORMS)))
        for i, r in enumerate(races):
            od = order_list[i]
            pay = r.get("payout") or {}
            def g(k, key):
                d = pay.get(k) or {}
                v = d.get(key); return float(v) if v else 0.0
            a = od[0]; b = od[1] if len(od) > 1 else None
            tri = pay.get("三連複") or {}
            def trio_ret(par):
                t = 0.0
                for c1, c2 in itertools.combinations(par, 2):
                    k = "-".join(str(x) for x in sorted((a, c1, c2)))
                    v = tri.get(k)
                    if v: t += float(v)
                return t
            RET[i] = [g("単勝", str(a)), g("複勝", str(a)),
                      g("ワイド", "-".join(str(x) for x in sorted((a, b)))) if b else 0.0,
                      trio_ret(od[1:5]), trio_ret(od[1:6])]
        return RET

    def conds_of(order_list):
        axes = {
            "1位オッズ帯": [], "芝ダ×距離帯": [], "1位オッズ×芝ダ": [], "頭数×芝ダ": [],
        }
        for i, r in enumerate(races):
            o1 = (r.get("odds") or {}).get(str(order_list[i][0]))
            ob = obl(float(o1)) if o1 else "?"
            f = len(r["nums"])
            fb = "≤10頭" if f <= 10 else "11-14頭" if f <= 14 else "15頭+"
            axes["1位オッズ帯"].append(ob)
            axes["芝ダ×距離帯"].append(f"{r['surface']}{r['dist_cat']}")
            axes["1位オッズ×芝ダ"].append(f"{ob}×{r['surface']}")
            axes["頭数×芝ダ"].append(f"{fb}×{r['surface']}")
        return axes

    def run_policy(order_list, verbose=False):
        RET = rets_of(order_list)
        axes = conds_of(order_list)
        best_axis, best_detail = None, None
        for axname, labels in axes.items():
            labels = np.array(labels)
            cost_sum = ret_sum = 0.0
            cost_sum_p = ret_sum_p = 0.0     # 期待値プラス方針(セル最良<100は見送り)
            policy = {}
            for lab in set(labels):
                m = (labels == lab) & segm[0]
                n = int(m.sum())
                if n < 80:
                    policy[lab] = None; continue
                rois = RET[m].sum(0) / (COSTS * n) * 100
                bi = int(np.argmax(rois))
                policy[lab] = (bi, float(rois[bi]))
                cost_sum += COSTS[bi] * n; ret_sum += RET[m, bi].sum()
                if rois[bi] >= 100:
                    cost_sum_p += COSTS[bi] * n; ret_sum_p += RET[m, bi].sum()
            mine_roi = ret_sum / cost_sum * 100 if cost_sum else 0
            mine_roi_p = ret_sum_p / cost_sum_p * 100 if cost_sum_p else 0
            score = mine_roi_p if cost_sum_p else mine_roi
            if best_axis is None or score > best_detail["score"]:
                best_axis = axname
                best_detail = dict(score=score, policy=policy, mine=mine_roi, mine_plus=mine_roi_p)
        # 選んだ軸でVAL/CONFを1回測定
        axname = best_axis
        labels = np.array(conds_of(order_list)[axname])
        out = {"axis": axname, "policy": best_detail["policy"]}
        for si, nm in ((0, "MINE"), (1, "VAL"), (2, "CONF")):
            cost = ret = 0.0; cost_p = ret_p = 0.0; n_bet = n_bet_p = 0
            for lab, pol in best_detail["policy"].items():
                if pol is None: continue
                bi, mroi = pol
                m = (labels == lab) & segm[si]
                n = int(m.sum())
                cost += COSTS[bi] * n; ret += rets_all[si] if False else RET[m, bi].sum()
                n_bet += n
                if mroi >= 100:
                    cost_p += COSTS[bi] * n; ret_p += RET[m, bi].sum(); n_bet_p += n
            out[nm] = dict(roi=ret / cost * 100 if cost else 0, n=n_bet,
                           roi_plus=ret_p / cost_p * 100 if cost_p else None, n_plus=n_bet_p)
        return out

    real = run_policy(rows)
    print(f"選ばれた軸: {real['axis']}")
    print(f"{'':>8}{'全レースで型選択':^26}{'期待値プラス方針(他は見送り)':^30}")
    for nm in ("MINE", "VAL", "CONF"):
        d = real[nm]
        rp = f"{d['roi_plus']:.1f}% (n={d['n_plus']})" if d["roi_plus"] else "対象なし"
        print(f"{nm:>8}  ROI {d['roi']:6.1f}% (n={d['n']})      {rp}")
    print("\nセルごとの選択(MINE):")
    for lab, pol in sorted(real["policy"].items()):
        if pol is None:
            print(f"  {lab:<16} 標本不足→見送り"); continue
        bi, mroi = pol
        tag = "★買い" if mroi >= 100 else "(参考・期待値負)"
        print(f"  {lab:<16} {FORMS[bi]:<18} MINE ROI {mroi:6.1f}% {tag}")

    # null: 順位乱数で全パイプライン×10
    rs = np.random.RandomState(83)
    null_v, null_c = [], []
    for t in range(10):
        fake = []
        for r in races:
            o = list(r["nums"]); rs.shuffle(o); fake.append(o)
        nr = run_policy(fake)
        v = nr["VAL"]["roi_plus"] if nr["VAL"]["roi_plus"] else nr["VAL"]["roi"]
        c = nr["CONF"]["roi_plus"] if nr["CONF"]["roi_plus"] else nr["CONF"]["roi"]
        null_v.append(v); null_c.append(c)
        print(f"  null#{t+1}: VAL {v:.1f}% / CONF {c:.1f}%", file=sys.stderr)
    print(f"\nnull(順位乱数×10・同じ全パイプライン): VAL 平均{np.mean(null_v):.1f}% 最大{max(null_v):.1f}% "
          f"/ CONF 平均{np.mean(null_c):.1f}% 最大{max(null_c):.1f}%")
    json.dump({"real": {k: (v if k != "policy" else {kk: vv for kk, vv in v.items()})
                        for k, v in real.items()},
               "null_v": null_v, "null_c": null_c},
              open("policy_menu.json", "w"), ensure_ascii=False, indent=1, default=str)
    print("saved policy_menu.json")


if __name__ == "__main__":
    main()
