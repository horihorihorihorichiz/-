# -*- coding: utf-8 -*-
"""DISCOVER ヌル検査（補正版）。

事前登録(§4)の「レース内で着順を一様シャッフル」は、**市場log-oddsをオフセットに固定した**
モデルでは検定として成立しない（オフセットが偽データに対して誤特定になり、βがオフセットを
打ち消す方向に動いて|z|が100超になる＝discover_mine_result.json の z_null* で実測）。
そこで「市場が知っていること以上の情報は無い」という帰無仮説を、
**市場implied確率から1〜3着を生成する偽データ**（Gumbel-top3 = Plackett-Luce サンプリング）で作る。
帰無が正しければ z は概ね N(0,1) になる。この較正自体も出力して確認する。

usage: python3 discover_null.py
既存ファイルは変更しない。
"""
import json
import numpy as np

import v99w_fit as V
import discover_feats as DF
import discover_mine as DM

SEEDS = [20260821, 20260822, 20260823]


def market_null_W(OFF, M, seed):
    """市場implied確率から top3 を生成（Gumbel top-k = PL サンプリング）"""
    rng = np.random.default_rng(seed)
    g = rng.gumbel(size=OFF.shape)
    s = np.where(M, OFF + g, -1e18)
    idx = np.argsort(-s, axis=1, kind="stable")
    return idx[:, :3].astype(int)


def main():
    races = V.load_races()
    A, race_idx, num, keep, ctx, st = DF.load_ds()
    grid = DF.Grid(race_idx, len(races))
    D = DF.derive(A)
    OFF, W, ok, dstat = DM.build_market(races, grid)
    month = np.array([r["month"] for r in races])
    mine = ok & (month <= "202602")
    Mm, OFFm = grid.MASK[mine], OFF[mine]
    Wn = [market_null_W(OFFm, Mm, s) for s in SEEDS]
    print(f"MINE={mine.sum()}R / 市場整合ヌル seeds={SEEDS}")

    prev = json.load(open("discover_mine_result.json", encoding="utf-8"))
    zc = prev["z_crit"]
    rows = []
    n = 0
    for name, ja, v, Z in DF.iter_candidates(D, A, ctx, race_idx, grid):
        cov = float(np.isfinite(v[np.isin(race_idx, np.where(mine)[0])]).mean())
        Zm = Z[mine]
        if cov < DM.COV_MIN or Zm[Mm].std() < 1e-9:
            continue
        n += 1
        r = dict(name=name)
        for si, Wx in enumerate(Wn):
            _, dll, z, _ = DM.fit_beta(Zm, OFFm, Mm, Wx)
            r[f"z{si}"] = round(z, 3)
            r[f"dll{si}"] = round(dll, 2)
        rows.append(r)
        if n % 200 == 0:
            print(f"  ... {n}本", flush=True)

    npass = []
    for si in range(len(SEEDS)):
        z = np.array([r[f"z{si}"] for r in rows])
        npass.append(int((np.abs(z) >= zc).sum()))
        print(f"null{si}: mean={z.mean():+.3f} sd={z.std():.3f} "
              f"|z|>=2 {int((np.abs(z)>=2).sum())}本 "
              f"|z|>={zc:.2f} {npass[-1]}本")
    real = prev["n_pass"]
    print(f"\n実データ通過={real} / 市場整合ヌル通過={npass} "
          f"(平均{np.mean(npass):.2f} 最大{max(npass)})")
    ok_null = real > max(npass) and real > 3 * max(np.mean(npass), 1e-9)
    print(f"ヌル判定(補正版): {'通過' if ok_null else '棄却'}")
    json.dump(dict(z_crit=zc, n_tested=n, null_pass=npass,
                   real_pass=real, null_ok=bool(ok_null), seeds=SEEDS,
                   rows=rows),
              open("discover_null_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ discover_null_result.json 保存")


if __name__ == "__main__":
    main()
