# -*- coding: utf-8 -*-
"""「市場の歪みの大きさ」を控除率と同じ土俵で比較する。
   各オッズ帯で 実勝率 / 正規implied確率 − 1 = 「控除率を除いた後の相対ズレ」。
   これが控除率(約20%)を上回らない限りエッジにならない。
   usage: python3 nar_calib.py
"""
import glob, json, math, os
from collections import defaultdict

import market_eff as ME

BANDS = [("~1.3", 0, 1.3), ("1.3-1.8", 1.3, 1.8), ("1.8-2.5", 1.8, 2.5),
         ("2.5-4", 2.5, 4), ("4-6", 4, 6), ("6-10", 6, 10), ("10-20", 10, 20),
         ("20-50", 20, 50), ("50-100", 50, 100), ("100+", 100, 1e9)]


def key(r):
    for lab, lo, hi in BANDS:
        if lo < r["odds"] <= hi:
            return lab
    return None


def run(name, races):
    B = defaultdict(lambda: [0, 0, 0.0, 0.0])   # n, wins, exp(正規), ret
    for _rid, _v, rs in races:
        tot = sum(1.0 / r["odds"] for r in rs)
        for r in rs:
            k = key(r)
            if not k:
                continue
            d = B[k]
            d[0] += 1
            d[1] += r["win"]
            d[2] += (1.0 / r["odds"]) / tot
            d[3] += (r["odds"] * 100 if r["win"] else 0)
    print(f"\n### {name} ({len(races)}R)")
    print(f"{'オッズ帯':>9} {'頭数':>7} {'実勝':>6} {'期待(正規)':>10} "
          f"{'相対ズレ%':>9} {'z':>6} {'単ROI%':>7}")
    for lab, _lo, _hi in BANDS:
        d = B.get(lab)
        if not d or d[0] < 100:
            continue
        n, w, e, ret = d
        p = e / n
        se = math.sqrt(max(n * p * (1 - p), 1e-9))
        z = (w - e) / se
        rel = (w / e - 1) * 100 if e > 0 else 0
        print(f"{lab:>9} {n:>7} {w:>6} {e:>10.1f} {rel:>9.1f} {z:>6.2f} {ret/n:>7.1f}")


def main():
    jra = ME.load_jra()
    nar = ME.load_nar()
    m, md, _n = ME.overround(jra)
    print(f"JRA 実効控除率(中央) {(1-1/md)*100:.1f}%")
    m2, md2, _ = ME.overround(nar)
    print(f"NAR 実効控除率(中央) {(1-1/md2)*100:.1f}%")
    run("JRA", jra)
    run("NAR(実オッズ取得済み分)", nar)
    print("\n※『相対ズレ%』は控除率を除去した後の過小評価率。"
          "これが控除率(約20%)を上回らない限り単勝では勝てない。")


if __name__ == "__main__":
    main()
