# -*- coding: utf-8 -*-
"""Ver.2モデル × 市場ブレンドのフィットとROI検証（Ver.101 B1の最終判定）。
   1. pv2(生特徴量PLモデル)と市場確率の対数線形ブレンドを3着内尤度でフィット
   2. build_buylist_ev に注入して実払戻ROIをtrain/testで計測
   usage: python3 v2_blend.py [--test 20260704,...] [--write] [--scales 0.9,1.0,1.1]
"""
import argparse, json, math, os, sys
import fit_v2 as V2
import predict as PR
import validate as VAL


def p_market_from(odds_map):
    inv = {n: 1.0/o for n, o in odds_map.items() if o and o > 0}
    s = sum(inv.values())
    return {n: v/s for n, v in inv.items()} if s else {}


def blend(pm, q, a, b):
    ns = [n for n in pm if n in q]
    if not ns:
        return pm
    lg = {n: a*math.log(max(pm[n], 1e-9)) + b*math.log(max(q[n], 1e-9)) for n in ns}
    mx = max(lg.values())
    e = {n: math.exp(lg[n]-mx) for n in ns}
    s = sum(e.values())
    out = {n: e[n]/s for n in ns}
    for n in pm:
        out.setdefault(n, 1e-4)
    return out


def nll_top3(ds, w, a, b):
    tot = n = 0
    for r in ds:
        p = blend(V2.probs_v2(r, w), p_market_from(r["odds"]), a, b)
        alive = dict(p)
        for pos in range(3):
            winner = r["top3"][pos]
            if winner not in alive:
                break
            Z = sum(alive.values())
            tot += -math.log(max(alive[winner]/Z, 1e-12))
            n += 1
            alive.pop(winner)
    return tot/n if n else float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="20260704,20260705,20260711,20260712")
    ap.add_argument("--scales", default="0.9,1.0,1.1")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    pv = json.load(open("params_v2.json", encoding="utf-8"))
    w = pv["weights"]
    ds = V2.load_dataset("hist", "hist_feat")
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: train {len(train)} / test {len(test)}")

    # ブレンドのフィット(3着内の並び)
    best = (float("inf"), 0.0, 1.0)
    for aa in [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7]:
        for bb in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]:
            v = nll_top3(train, w, aa, bb)
            if v < best[0]:
                best = (v, aa, bb)
    _, a2, b2 = best
    print(f"Ver.2ブレンド: α_v2={a2} β_market={b2}")
    for name, dset in (("train", train), ("test", test)):
        mkt = nll_top3(dset, w, 0.0, 1.0)
        v2b = nll_top3(dset, w, a2, b2)
        print(f"  {name}: 市場のみ {mkt:.4f} → Ver.2ブレンド {v2b:.4f} "
              f"({'改善' if v2b < mkt else '改善なし'})")

    # ROI検証: build_buylist_ev にVer.2ブレンド確率を注入
    for name, dset in (("train", train), ("test", test)):
        for scale in [float(x) for x in a.scales.split(",")]:
            n_go = staked = returned = 0
            bykind = {}
            for r in dset:
                op = os.path.join("hist_odds", f"{r['rid']}.json")
                hp = os.path.join("hist", f"{r['rid']}.json")
                if not os.path.exists(op):
                    continue
                odds = json.load(open(op, encoding="utf-8"))
                tan_map = {int(k): v for k, v in odds.get("tan", {}).items() if v}
                q = p_market_from(tan_map)
                pm = V2.probs_v2(r, w)
                pp = blend(pm, q, a2, b2)
                pw = blend(pm, q, 0.0, 1.0)   # 勝者はα=0(市場)のまま
                picks, total, dec = PR.build_buylist_ev(
                    [], odds, edge_scale=scale, pb_override=dict(win=pw, place=pp))
                if not picks:
                    continue
                d = json.load(open(hp, encoding="utf-8"))
                ret = VAL.settle(picks, d["result"].get("payout", {}))
                n_go += 1
                staked += total
                returned += ret
                for kind, lbl, o, st, p, ev in picks:
                    hit = VAL.settle([(kind, lbl, o, st, p, ev)], d["result"].get("payout", {}))
                    bk = bykind.setdefault(kind, [0, 0, 0, 0])
                    bk[0] += 1; bk[1] += st; bk[2] += hit; bk[3] += (1 if hit else 0)
            roi = returned/staked*100 if staked else 0
            print(f"== {name} scale={scale} == GO {n_go}/{len(dset)}R "
                  f"投{staked}円 戻{returned}円 ROI {roi:.1f}%")
            for kind, (n, st, ret_, hits) in sorted(bykind.items()):
                print(f"   {kind}: {n}点 的中{hits} 投{st} 戻{ret_} "
                      f"ROI {ret_/st*100 if st else 0:.0f}%")

    if a.write:
        pv["blend_place_v2"] = dict(alpha=a2, beta=b2)
        json.dump(pv, open("params_v2.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("params_v2.json にブレンドを保存した。")


if __name__ == "__main__":
    main()
