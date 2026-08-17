# -*- coding: utf-8 -*-
"""V7 評価（V7_PROTOCOL_20260817.md の3分割・機械適用）。
usage: python3 eval_v7.py MINE|VALIDATE|CONFIRM [seed]
  分割ごとに 1 回だけ実行する運用（VALIDATE/CONFIRM は各1回・後からの変更禁止）。
出力: EV閾値1.2/1.3/1.5 の n/投下/回収/ROI/的中率、ベンチマーク
      （市場1位flat・モデル1位flat・旧乖離flat近似・同オッズ帯ランダム1000回）、
      主閾値1.3のブートストラップ P(ROI>100%)。
"""
import json
import sys
import numpy as np

SPLITS = {
    "MINE": ("202410", "202602"),      # 202409は学習データ無しで評価除外（fit_v7参照）
    "VALIDATE": ("202603", "202605"),
    "CONFIRM": ("202606", "202608"),
}
THRESHOLDS = [1.2, 1.3, 1.5]
MAIN_T = 1.3
BANDS = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0, 1e9]


def band_of(o):
    for i in range(len(BANDS) - 1):
        if BANDS[i] <= o < BANDS[i + 1]:
            return i
    return len(BANDS) - 2


def load(split):
    lo, hi = SPLITS[split]
    rows = []
    for line in open("v7_bets.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if lo <= d["month"] <= hi:
            rows.append(d)
    return rows


def roi_line(bets):
    n = len(bets)
    spend = 100 * n
    ret = sum(b["pay"] for b in bets if b["win"])
    hits = sum(b["win"] for b in bets)
    return n, spend, ret, (ret / spend * 100 if spend else 0.0), \
        (hits / n * 100 if n else 0.0), hits


def bootstrap_p(bets, iters=2000, rng=None):
    if not bets:
        return float("nan")
    rng = rng or np.random.default_rng(7)
    pays = np.array([b["pay"] if b["win"] else 0 for b in bets], dtype=float)
    n = len(pays)
    idx = rng.integers(0, n, size=(iters, n))
    rois = pays[idx].sum(axis=1) / (100.0 * n)
    return float((rois > 1.0).mean())


def main():
    split = sys.argv[1]
    rows = load(split)
    by_race = {}
    for r in rows:
        by_race.setdefault(r["rid"], []).append(r)
    n_races = len(by_race)
    print(f"=== V7 {split} ({SPLITS[split][0]}-{SPLITS[split][1]}) races={n_races} ===")

    # --- EV閾値別 ---
    print("\n-- EV閾値別 (flat100円・全馬対象・1R複数可) --")
    print(f"{'EV≥':>5} {'n':>5} {'投下':>8} {'回収':>8} {'ROI%':>7} {'的中%':>6} {'的中':>4}")
    main_bets = None
    for t in THRESHOLDS:
        bets = [r for r in rows if r["ev"] >= t]
        n, sp, ret, roi, hit, hits = roi_line(bets)
        tag = " ←主判定" if t == MAIN_T else ""
        print(f"{t:>5} {n:>5} {sp:>8} {ret:>8} {roi:>7.1f} {hit:>6.1f} {hits:>4}{tag}")
        if t == MAIN_T:
            main_bets = bets

    # --- ブートストラップ（主閾値） ---
    p = bootstrap_p(main_bets)
    print(f"\nブートストラップ2000回 P(ROI>100%) @EV≥{MAIN_T}: {p:.3f}")

    # --- 主閾値の中身（オッズ帯分布） ---
    if main_bets:
        odds_arr = np.array([b["odds"] for b in main_bets])
        print(f"EV≥{MAIN_T} 買い目オッズ: 中央値{np.median(odds_arr):.1f} "
              f"min{odds_arr.min():.1f} max{odds_arr.max():.1f} "
              f"/ モデル1位比率 {np.mean([b['model_rank']==1 for b in main_bets])*100:.0f}%")

    # --- ベンチマーク ---
    print("\n-- ベンチマーク (同期間・flat100円) --")
    fav_bets, mdl_bets, kairi_bets = [], [], []
    for rid, hs in by_race.items():
        fav = min(hs, key=lambda x: x["odds"])
        fav_bets.append(fav)
        m1 = next(x for x in hs if x["model_rank"] == 1)
        mdl_bets.append(m1)
        mkt_rank = 1 + sum(1 for x in hs if x["odds"] < m1["odds"])
        if mkt_rank >= 4:                      # 旧乖離flat近似(モデル1位=市場4番人気以下)
            kairi_bets.append(m1)
    for name, bs in [("市場1位flat", fav_bets), ("モデル1位flat", mdl_bets),
                     ("旧乖離flat近似", kairi_bets)]:
        n, sp, ret, roi, hit, hits = roi_line(bs)
        print(f"{name:<14} n={n:>5} ROI={roi:6.1f}% 的中率={hit:5.1f}%")

    # 同オッズ帯ランダム（主閾値の買い集合とオッズ帯マッチ・1000回平均）
    if main_bets:
        rng = np.random.default_rng(11)
        pool = {}
        for r in rows:
            pool.setdefault(band_of(r["odds"]), []).append(
                r["pay"] if r["win"] else 0)
        pool = {k: np.array(v, dtype=float) for k, v in pool.items()}
        bet_bands = [band_of(b["odds"]) for b in main_bets]
        rois = []
        for _ in range(1000):
            ret = sum(float(rng.choice(pool[bb])) for bb in bet_bands)
            rois.append(ret / (100.0 * len(main_bets)))
        rois = np.array(rois)
        print(f"同オッズ帯ランダム n={len(main_bets)} ROI平均={rois.mean()*100:.1f}% "
              f"(sd {rois.std()*100:.1f}) P(>100%)={float((rois>1).mean()):.2f}")

    # --- 合否（機械適用・事前登録基準） ---
    if split in ("VALIDATE", "CONFIRM"):
        n = len(main_bets)
        _, _, _, roi, _, _ = roi_line(main_bets)
        if split == "VALIDATE":
            ok = n >= 40 and roi >= 110.0
            print(f"\n[基準] VALIDATE n≥40 & ROI≥110%: n={n} ROI={roi:.1f}% → "
                  f"{'合格' if ok else '不合格'}")
        else:
            ok = n >= 25 and roi >= 105.0
            print(f"\n[基準] CONFIRM n≥25 & ROI≥105%: n={n} ROI={roi:.1f}% → "
                  f"{'合格' if ok else '不合格'}")
        print(f"[基準] ブートストラップ P(ROI>100%)≥0.80: {p:.3f} → "
              f"{'合格' if p >= 0.80 else '不合格'}")

    # --- 月別内訳（主閾値） ---
    print("\n-- 月別 (EV≥1.3) --")
    months = sorted({r["month"] for r in rows})
    for m in months:
        bs = [b for b in (main_bets or []) if b["month"] == m]
        n, sp, ret, roi, hit, hits = roi_line(bs)
        print(f"{m}: n={n:>4} ROI={roi:6.1f}% 的中{hits}")


if __name__ == "__main__":
    main()
