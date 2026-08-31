# -*- coding: utf-8 -*-
"""cluster_bet.py — CLUSTER_PROTOCOL.md §11 の実装。

問い:「残したレースの中で、どの馬をどの複勝オッズ条件で買えば ROI 100% を超えるか」

  軸② 買う馬 6通り: M12(市場1・2位) / M1 / M2 / M3 / G1(モデル1位) / G1L(モデル1位かつ市場3番人気以下)
  軸① 複勝オッズ下限フィルタ: hist_odds の fuku(下限) >= X。X=1.0..2.5 の0.1刻み(16値)
  軸③ = ①×② = 96セル。**決定は MINE のみ**。選んだ1セルを VAL/CONF に1回だけ通す。

usage: python3 cluster_bet.py
"""
import json
import os
import pickle
import time
from collections import defaultdict

import numpy as np

import cluster_feats as CF
import cluster_select as CSL

XS = [round(1.0 + 0.1 * i, 1) for i in range(16)]        # 1.0 .. 2.5
VARIANTS = ["M12", "M1", "M2", "M3", "G1", "G1L"]
MINE_MIN_N, MINE_MIN_HIT = 300, 50.0
PASS_ROI, PASS_HIT, PASS_N = 100.0, 50.0, 80
MC_ITERS = 2000
SEED = 20260818


class Bets:
    """レースごとに『買う馬の候補・複勝下限オッズ・複勝払戻』を前計算"""

    def __init__(self):
        F, cols, rows = CF.load()
        self.rid = [r["rid"] for r in rows]
        n = len(self.rid)
        i_m, i_v = int(n * 0.70), int(n * 0.85)
        self.split = np.array(["MINE"] * i_m + ["VALIDATE"] * (i_v - i_m)
                              + ["CONFIRM"] * (n - i_v))
        ci = {c: i for i, c in enumerate(cols)}
        self.entropy, self.gap = F[:, ci["entropy"]], F[:, ci["score_gap12"]]
        self.fav1_imp = np.zeros(n)
        with open("course_cache_meta.pkl", "rb") as f:
            meta = {m["rid"]: m for m in pickle.load(f)}
        gen = CF.load_gen_place()
        self.sets = []      # [{variant: [(horse, fuku_lo, payout), ...]}]
        nofuku = 0
        for i, rid in enumerate(self.rid):
            m = meta[rid]
            ns = list(m["ns"])
            od = np.array([m["odds"][x] for x in ns], dtype=float)
            imp = (1.0 / od) / (1.0 / od).sum()
            self.fav1_imp[i] = imp.max()
            order = [ns[j] for j in np.lexsort((np.array(ns), od))]   # 市場人気順
            mrank = {h: r + 1 for r, h in enumerate(order)}
            gs = gen.get(rid, {})
            gorder = sorted(ns, key=lambda h: (-gs.get(h, 0.0), h))
            with open(os.path.join("hist_odds", f"{rid}.json"), encoding="utf-8") as f:
                fk = (json.load(f).get("fuku") or {})
            if not fk:
                nofuku += 1
            payd = m["payout"].get("複勝") or {}

            def mk(hs):
                out = []
                for h in hs:
                    lo = fk.get(str(h))
                    if lo is None:
                        continue
                    out.append((h, float(lo), float(payd.get(str(h), 0))))
                return out
            g1 = gorder[0]
            self.sets.append(dict(
                M12=mk(order[:2]), M1=mk(order[:1]), M2=mk(order[1:2]),
                M3=mk(order[2:3]), G1=mk([g1]),
                G1L=mk([g1] if mrank.get(g1, 99) >= 3 else [])))
        self.n = n
        print(f"races={n} / fuku欠損レース={nofuku}", flush=True)

    def evaluate(self, mask, variant, x):
        """mask のレース集合で variant を下限オッズ>=x で買った成績"""
        nb = tick = pay = hit = 0
        for i in np.where(mask)[0]:
            sel = [t for t in self.sets[i][variant] if t[1] >= x]
            if not sel:
                continue
            nb += 1
            tick += len(sel)
            p = sum(t[2] for t in sel)
            pay += p
            hit += 1 if p > 0 else 0
        if nb == 0 or tick == 0:
            return dict(n=0, tickets=0, roi=None, hit=None)
        return dict(n=nb, tickets=tick, roi=round(pay / (100 * tick) * 100, 1),
                    hit=round(hit / nb * 100, 1))

    def by_window(self, mask, variant, x):
        return {w: self.evaluate(mask & (self.split == w), variant, x)
                for w in ("MINE", "VALIDATE", "CONFIRM")}


def mc_expect(B, mask, variant, x, rng):
    """実力ゼロ(そのレースの出走馬から一様ランダムに同数だけ買う)での
       VAL>100% ∧ CONF>100% 同時達成確率。買い目の点数と対象レースは実物のまま。"""
    with open("course_cache_meta.pkl", "rb") as f:
        meta = {m["rid"]: m for m in pickle.load(f)}
    pools = {}
    for w in ("VALIDATE", "CONFIRM"):
        rows = []
        for i in np.where(mask & (B.split == w))[0]:
            sel = [t for t in B.sets[i][variant] if t[1] >= x]
            if not sel:
                continue
            m = meta[B.rid[i]]
            payd = m["payout"].get("複勝") or {}
            allp = np.array([float(payd.get(str(h), 0)) for h in m["ns"]])
            rows.append((len(sel), allp))
        pools[w] = rows
    if not pools["VALIDATE"] or not pools["CONFIRM"]:
        return None
    ok = 0
    for _ in range(MC_ITERS):
        good = True
        for w in ("VALIDATE", "CONFIRM"):
            pay = tick = 0
            for k, allp in pools[w]:
                pick = rng.choice(len(allp), size=min(k, len(allp)), replace=False)
                pay += allp[pick].sum()
                tick += min(k, len(allp))
            if pay / (100 * tick) * 100 <= PASS_ROI:
                good = False
                break
        ok += int(good)
    return ok / MC_ITERS


def run():
    t0 = time.time()
    B = Bets()
    base = ((B.fav1_imp >= CSL.TH_A_IMPLIED) & (B.entropy <= CSL.TH_B_ENTROPY)
            & (B.gap >= CSL.TH_C_GAP))
    A = json.load(open("cluster_assign.json", encoding="utf-8"))
    lab = np.array(A["configs"]["KMk8"]["labels"])
    subsets = {"baseline": base, "all": np.ones(B.n, bool),
               "KMk8T3": base & np.isin(lab, [1, 5])}
    out = {"grid": {}, "subsets": {}}
    rng = np.random.default_rng(SEED)

    for sname, mask in subsets.items():
        grid = {}
        for v in VARIANTS:
            for x in XS:
                grid[f"{v}|{x}"] = B.by_window(mask, v, x)
        out["grid"][sname] = grid
        # ── MINE のみで最良セルを選ぶ
        cand = [(k, g) for k, g in grid.items()
                if g["MINE"]["n"] >= MINE_MIN_N and (g["MINE"]["hit"] or 0) >= MINE_MIN_HIT
                and g["MINE"]["roi"] is not None]
        best = max(cand, key=lambda kv: kv[1]["MINE"]["roi"])[0] if cand else None
        # ── 診断: VAL/CONF 両方で ROI>100 のセル数
        hits = [k for k, g in grid.items()
                if g["VALIDATE"]["roi"] is not None and g["CONFIRM"]["roi"] is not None
                and g["VALIDATE"]["n"] >= PASS_N and g["CONFIRM"]["n"] >= PASS_N
                and g["VALIDATE"]["roi"] > PASS_ROI and g["CONFIRM"]["roi"] > PASS_ROI]
        rec = dict(n_cells=len(grid), n_candidates=len(cand), chosen=best,
                   cells_pass_both=hits)
        if best:
            g = grid[best]
            v, x = best.split("|")
            rec["chosen_result"] = g
            rec["chosen_pass"] = bool(
                all(g[w]["n"] >= PASS_N and g[w]["roi"] is not None
                    and g[w]["roi"] > PASS_ROI and g[w]["hit"] >= PASS_HIT
                    for w in ("VALIDATE", "CONFIRM")))
            rec["mc_expect_chosen"] = mc_expect(B, mask, v, float(x), rng)
        out["subsets"][sname] = rec
        print(f"\n=== subset={sname} 候補{len(cand)}/96 chosen={best}", flush=True)
        if best:
            g = grid[best]
            for w in ("MINE", "VALIDATE", "CONFIRM"):
                print(f"    {w:9} n={g[w]['n']:5} 点={g[w]['tickets']:5} "
                      f"的中={g[w]['hit']}% ROI={g[w]['roi']}%")
            print(f"    pass={rec['chosen_pass']}  MC偶然期待={rec['mc_expect_chosen']}")
        print(f"    VAL/CONF両方でROI>100のセル: {len(hits)} -> {hits[:12]}")

    json.dump(out, open("cluster_bet.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(f"\nsaved cluster_bet.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    run()
