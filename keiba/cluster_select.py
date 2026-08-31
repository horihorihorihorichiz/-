# -*- coding: utf-8 -*-
"""cluster_select.py — CLUSTER_PROTOCOL.md §10（三次＝見送り戦略）の実装。

「汎用モデルは据え置き。クラスタは『どのレースを買うか』の判定にだけ使う」を測る。
買い目は全て **市場（単勝オッズ）順** で決める＝モデルを買い目に使わない。

  base   固定ベースライン A∧B∧C（コーディネータ提供の閾値）を本ユニバースで実測
  sel    クラスタ由来の除外ルール T1/T2/T3（選抜は全てMINEのみ）
  all    両方 + 全構成の診断表 -> cluster_select.json

usage: python3 cluster_select.py all
"""
import json
import pickle
import sys
import time
from collections import defaultdict

import numpy as np

import cluster_feats as CF
import cluster_system as CSY

# ── 固定ベースライン閾値（コーディネータ提供・MINEのみで決定済み・変更禁止）
TH_A_IMPLIED = 0.341      # 市場1番人気の implied 確率 >= これ
TH_B_ENTROPY = 1.904      # implied エントロピー <= これ
TH_C_GAP = 0.066          # モデル1位-2位の得点差 >= これ

# ── 合格基準（§10-4・凍結）
PASS_ROI = 100.0
PASS_HIT = 85.0
PASS_N = 80

T1_MIN_ROI = 100.0        # T1: MINE 複勝2点 ROI がこれ以上のクラスタ
T1_MIN_N = 100
T2_CUM_N = 300            # T2: MINE ROI 降順に累積 n がこれ以上になるまで
SEL_MIN_N = 300           # 構成選択の制約
SEL_MIN_RATE = 0.15

KINDS = ["複勝2点", "複勝1点", "ワイド3点", "三連複1点"]


def pkey(ns):
    return "-".join(str(x) for x in sorted(ns))


class Board:
    """レースごとに『市場順で買った時の払戻と点数』を前計算しておく台帳"""

    def __init__(self):
        F, cols, rows = CF.load()
        self.F, self.cols = F, cols
        self.rid = [r["rid"] for r in rows]
        n = len(self.rid)
        self.i_mine, self.i_val = int(n * 0.70), int(n * 0.85)
        self.split = np.array(["MINE"] * self.i_mine
                              + ["VALIDATE"] * (self.i_val - self.i_mine)
                              + ["CONFIRM"] * (n - self.i_val))
        with open("course_cache_meta.pkl", "rb") as f:
            meta = {m["rid"]: m for m in pickle.load(f)}
        ci = {c: i for i, c in enumerate(cols)}
        self.entropy = F[:, ci["entropy"]]
        self.gap = F[:, ci["score_gap12"]]
        self.fav1_imp = np.zeros(n)
        self.pay = {k: np.zeros(n) for k in KINDS}
        self.hit = {k: np.zeros(n) for k in KINDS}
        self.pts = {"複勝2点": 2, "複勝1点": 1, "ワイド3点": 3, "三連複1点": 1}
        for i, rid in enumerate(self.rid):
            m = meta[rid]
            ns = list(m["ns"])
            od = np.array([m["odds"][x] for x in ns], dtype=float)
            imp = (1.0 / od) / (1.0 / od).sum()
            self.fav1_imp[i] = imp.max()
            order = [ns[j] for j in np.lexsort((np.array(ns), od))]   # オッズ昇順・同値は馬番順
            P = m["payout"] or {}
            fk = P.get("複勝") or {}
            wd = {pkey([int(a) for a in k.split("-")]): v
                  for k, v in (P.get("ワイド") or {}).items()}
            sf = {pkey([int(a) for a in k.split("-")]): v
                  for k, v in (P.get("三連複") or {}).items()}
            t2, t3 = order[:2], order[:3]
            p = sum(fk.get(str(h), 0) for h in t2)
            self.pay["複勝2点"][i] = p
            self.hit["複勝2点"][i] = 1.0 if p else 0.0
            p = fk.get(str(order[0]), 0)
            self.pay["複勝1点"][i] = p
            self.hit["複勝1点"][i] = 1.0 if p else 0.0
            p = 0
            for a in range(3):
                for b in range(a + 1, 3):
                    if len(t3) == 3:
                        p += wd.get(pkey([t3[a], t3[b]]), 0)
            self.pay["ワイド3点"][i] = p
            self.hit["ワイド3点"][i] = 1.0 if p else 0.0
            p = sf.get(pkey(t3), 0) if len(t3) == 3 else 0
            self.pay["三連複1点"][i] = p
            self.hit["三連複1点"][i] = 1.0 if p else 0.0

    def ev(self, mask, kind):
        idx = np.where(mask)[0]
        n = len(idx)
        if n == 0:
            return dict(n=0, roi=None, hit=None)
        return dict(n=int(n),
                    roi=round(float(self.pay[kind][idx].sum()
                                    / (100 * self.pts[kind] * n) * 100), 1),
                    hit=round(float(self.hit[kind][idx].mean() * 100), 1))

    def by_window(self, mask, kind):
        return {w: self.ev(mask & (self.split == w), kind)
                for w in ("MINE", "VALIDATE", "CONFIRM")}


def verdict(bw):
    v, c = bw["VALIDATE"], bw["CONFIRM"]
    ok = all(x["n"] >= PASS_N and x["roi"] is not None and x["roi"] > PASS_ROI
             and x["hit"] >= PASS_HIT for x in (v, c))
    return bool(ok)


def run():
    t0 = time.time()
    B = Board()
    A = CSY.load_assign()
    out = {"n": len(B.rid),
           "windows": {w: int((B.split == w).sum()) for w in ("MINE", "VALIDATE", "CONFIRM")}}
    print(f"universe {len(B.rid)}R {out['windows']}", flush=True)

    # ── 0. 無選別（全レース）
    out["no_filter"] = {k: B.by_window(np.ones(len(B.rid), bool), k) for k in KINDS}

    # ── 1. 固定ベースライン A∧B∧C（提供閾値そのまま）
    base = ((B.fav1_imp >= TH_A_IMPLIED) & (B.entropy <= TH_B_ENTROPY)
            & (B.gap >= TH_C_GAP))
    out["baseline"] = dict(
        thresholds=dict(A=TH_A_IMPLIED, B=TH_B_ENTROPY, C=TH_C_GAP),
        keep={w: dict(n=int((base & (B.split == w)).sum()),
                      of=int((B.split == w).sum()),
                      pct=round(float((base & (B.split == w)).sum()
                                      / (B.split == w).sum() * 100), 1))
              for w in ("MINE", "VALIDATE", "CONFIRM")},
        result={k: B.by_window(base, k) for k in KINDS})
    # 参考: 本ユニバースのMINE分位で引き直した閾値（診断のみ・主判定に使わない）
    mm = B.split == "MINE"
    out["baseline_refit"] = dict(
        thresholds=dict(A=round(float(np.percentile(B.fav1_imp[mm], 60)), 4),
                        B=round(float(np.percentile(B.entropy[mm], 40)), 4),
                        C=round(float(np.percentile(B.gap[mm], 40)), 4)))
    th = out["baseline_refit"]["thresholds"]
    b2 = ((B.fav1_imp >= th["A"]) & (B.entropy <= th["B"]) & (B.gap >= th["C"]))
    out["baseline_refit"]["keep"] = {
        w: dict(n=int((b2 & (B.split == w)).sum()), of=int((B.split == w).sum()))
        for w in ("MINE", "VALIDATE", "CONFIRM")}
    out["baseline_refit"]["result"] = {k: B.by_window(b2, k) for k in KINDS}

    # ── 2. クラスタ由来の除外ルール（選抜は全てMINEのみ）
    cfgs = {}
    for cfg, info in A["configs"].items():
        lab = np.array(info["labels"])
        k = info["k"]
        per = {}
        for c in range(k):
            m = (lab == c)
            per[c] = dict(mine=B.ev(m & mm, "複勝2点"),
                          all_windows={kk: B.by_window(m, kk) for kk in KINDS})
        # --- T1: MINE 複勝2点ROI >= 100% かつ n>=100
        t1 = [c for c in range(k) if per[c]["mine"]["n"] >= T1_MIN_N
              and (per[c]["mine"]["roi"] or 0) >= T1_MIN_ROI]
        # --- T2: MINE ROI 降順に累積 n>=300 まで
        rank = sorted([c for c in range(k) if per[c]["mine"]["n"] > 0],
                      key=lambda c: -(per[c]["mine"]["roi"] or 0))
        t2, cum = [], 0
        for c in rank:
            t2.append(c)
            cum += per[c]["mine"]["n"]
            if cum >= T2_CUM_N:
                break
        sets = {}
        for nm, sel in (("T1", t1), ("T2", t2)):
            msk = np.isin(lab, sel) if sel else np.zeros(len(lab), bool)
            sets[nm] = dict(selected=sel, keep_mine=int((msk & mm).sum()),
                            result={kk: B.by_window(msk, kk) for kk in KINDS})
            sets[nm]["pass"] = verdict(sets[nm]["result"]["複勝2点"]) if sel else False
        msk3 = (np.isin(lab, t2) if t2 else np.zeros(len(lab), bool)) & base
        sets["T3"] = dict(selected=t2, keep_mine=int((msk3 & mm).sum()),
                          result={kk: B.by_window(msk3, kk) for kk in KINDS})
        sets["T3"]["pass"] = verdict(sets["T3"]["result"]["複勝2点"]) if t2 else False
        cfgs[cfg] = dict(k=k, per_cluster={str(c): per[c] for c in range(k)}, sets=sets,
                         mine_roi_T2=sets["T2"]["result"]["複勝2点"]["MINE"]["roi"],
                         mine_keep_T2=sets["T2"]["keep_mine"])
        print(f"  {cfg}: T1={t1} T2={t2} MINE(T2) n={sets['T2']['keep_mine']} "
              f"roi={cfgs[cfg]['mine_roi_T2']} ({time.time()-t0:.0f}s)", flush=True)
    out["configs"] = cfgs

    # ── 3. 構成の選択（MINEのみ・§10-3）
    nm = (B.split == "MINE").sum()
    cand = [(c, v) for c, v in cfgs.items()
            if v["mine_keep_T2"] >= SEL_MIN_N and v["mine_keep_T2"] / nm >= SEL_MIN_RATE
            and v["mine_roi_T2"] is not None]
    chosen = max(cand, key=lambda kv: kv[1]["mine_roi_T2"])[0] if cand else None
    out["chosen_config"] = chosen
    out["chosen_reason"] = dict(
        n_candidates=len(cand),
        table=sorted([(c, v["mine_keep_T2"], v["mine_roi_T2"]) for c, v in cfgs.items()],
                     key=lambda x: -(x[2] or 0)))
    if chosen:
        out["primary"] = {nmm: cfgs[chosen]["sets"][nmm] for nmm in ("T1", "T2", "T3")}
        print(f"\nchosen config = {chosen}")
        for nmm in ("T1", "T2", "T3"):
            r = cfgs[chosen]["sets"][nmm]["result"]["複勝2点"]
            print(f"  {nmm}: sel={cfgs[chosen]['sets'][nmm]['selected']} "
                  f"MINE {r['MINE']} VAL {r['VALIDATE']} CONF {r['CONFIRM']} "
                  f"pass={cfgs[chosen]['sets'][nmm]['pass']}")
    json.dump(out, open("cluster_select.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    print(f"\nsaved cluster_select.json ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    run()
