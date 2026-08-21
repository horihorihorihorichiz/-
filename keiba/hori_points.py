# -*- coding: utf-8 -*-
"""堀川システム Ver.100 — 加点表を条件ごとに作る（2026-08-21）。

指示:「点数付けしろって 堀川システムという基礎があるんだから」
     「全コースごとに配点変えたりすれば的中できる」

土台 = Ver.99.27（堀川システム）の11成分 + 展開乗数。ここは触らない。
その上に**加点項目**を積む。点数の決め方はこう:

  各ルールについて「同じ単勝オッズ帯の馬と比べて、複勝の実払戻が何pt高いか」を測る。
  ＝ 市場が既に織り込んでいる分を差し引いた、そのルール固有の上乗せ。
  これを堀川システムの尺度に載せる（SSC=+10点 が最大加点なので、
  全群を通じた最大残差を +10点 に合わせる線形換算）。

  点数 = round( 残差pt × スケール )      スケール = 10 / (全群最大残差)

条件の切り方は 芝ダ×距離帯の6群（芝S/芝M/芝L/ダS/ダM/ダL）。
コース単位(122通り)にすると1コースあたり65Rしか無く、偶然を配点にしてしまうため。
  ※ 50パターン掃引(COURSE_SWEEP50_REPORT.md)で、コース単位の最適化は
    null control(乱数重み)に8回負けている。その反省をここに反映している。

出力:
  hori_points.json  … 群×ルールの点数表（predict.pyから読む用）
  標準出力          … 人が読む配点表
"""
import json, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B
import bonus_fit as F
import vg as VG

EDGES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 25.0, 40.0, 70.0, 120.0, 1e9]
NB = len(EDGES) - 1
MAX_BONUS = 10.0          # SSC(+10) に合わせた最大加点
MIN_N = 400               # これ未満の発火数は配点しない（偶然を配点にしない）

# 条件セル = VG（堀川システムのVenue Group）× 距離帯。
# 標本が薄いセルは同VG内で併合する（VG1/S=99R などをそのまま配点にしない）。
MERGE = {("VG1", "S"): ("VG1", "M"), ("VG3", "M"): ("VG3", "L")}


def cell_of(r):
    g = VG.vg_of(r.get("venue"), r["surface"], r["distance"])
    if not g:
        return None
    d = r["distance"]
    c = "S" if d <= 1400 else ("M" if d <= 1700 else "L")
    g, c = MERGE.get((g, c), (g, c))
    return f"{g}/{c}"



def band_of(o):
    for i in range(NB):
        if EDGES[i] <= o < EDGES[i + 1]:
            return i
    return NB - 1


def main():
    races = B.load()
    RAW = json.load(open(F.RAWP))
    RL = F.RL; J = len(RL)

    # 群 × ルール × 帯 → [n, 複勝払戻合計]、および 群 × 帯 → [n, 合計]（基準）
    G = collections.defaultdict(lambda: np.zeros((J, NB, 2)))
    GB = collections.defaultdict(lambda: np.zeros((NB, 2)))
    # 期間別に同じものを（MINEで配点を決め、VAL/CONFで1回だけ確認するため）
    seg_of = lambda m: "MINE" if m <= '202602' else ("VALIDATE" if m <= '202605' else "CONFIRM")
    SG = collections.defaultdict(lambda: np.zeros((J, NB, 2)))
    SGB = collections.defaultdict(lambda: np.zeros((NB, 2)))

    for r in races:
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        if not pl:
            continue
        g = cell_of(r)
        if not g:
            continue
        sg = seg_of(r["month"])
        odds = r.get("odds") or {}
        rec_all = RAW.get(r["rid"], {})
        rr = dict(distance=r["distance"], surface=r["surface"])
        for num in r["nums"]:
            o = odds.get(str(num)) or odds.get(num)
            if not o:
                continue
            k = band_of(float(o))
            v = pl.get(num, 0.0)
            GB[g][k] += [1, v]; SGB[(g, sg)][k] += [1, v]
            rec = rec_all.get(str(num)) or rec_all.get(num)
            if not rec:
                continue
            for j, (_, fn) in enumerate(RL):
                try:
                    if fn(rec, rr):
                        G[g][j, k] += [1, v]; SG[(g, sg)][j, k] += [1, v]
                except Exception:
                    pass

    groups = sorted(G.keys())

    def resid(A, Base):
        """帯構成をそろえた残差ROI(pt)。A=(J,NB,2), Base=(NB,2)"""
        base_roi = np.where(Base[:, 0] > 0, Base[:, 1] / np.maximum(100 * Base[:, 0], 1), 0)
        n = A[:, :, 0].sum(1)
        act = np.where(n > 0, A[:, :, 1].sum(1) / np.maximum(100 * n, 1), 0)
        exp = np.where(n > 0, (A[:, :, 0] * base_roi[None, :]).sum(1) / np.maximum(n, 1), 0)
        return (act - exp) * 100, n

    # MINEだけで配点を決める
    RES = {}; NN = {}
    for g in groups:
        d, n = resid(SG[(g, "MINE")], SGB[(g, "MINE")])
        RES[g] = d; NN[g] = n

    # スケール: 発火数が足りるセルの中の最大残差を +10点 に
    valid = np.concatenate([RES[g][NN[g] >= MIN_N] for g in groups])
    scale = MAX_BONUS / max(1e-9, float(np.max(valid)))

    table = {}
    for g in groups:
        pts = np.where(NN[g] >= MIN_N, np.round(RES[g] * scale), 0.0)
        pts = np.clip(pts, -MAX_BONUS, MAX_BONUS)
        table[g] = {F.RN[j]: float(pts[j]) for j in range(J) if pts[j] != 0}

    # ── 人が読む形で出す ──
    print("=" * 108)
    print("堀川システム Ver.100 — 加点表（土台=Ver.99.27の11成分+展開乗数。以下はその上に足す点）")
    print("=" * 108)
    print(f"点数の意味: 同じ単勝オッズ帯の馬と比べた複勝実払戻の上乗せ(pt)を、"
          f"SSC=+10点の尺度に換算（×{scale:.2f}）")
    print(f"発火{MIN_N}回未満のセルは配点しない（偶然を配点にしないため）\n")

    hdr = f"{'加点項目':<34}" + "".join(f"{g:>9}" for g in groups)
    print(hdr); print("-" * len(hdr))
    order = sorted(range(J), key=lambda j: -max(abs(table[g].get(F.RN[j], 0)) for g in groups))
    for j in order:
        nm = F.RN[j]
        row = [table[g].get(nm, 0.0) for g in groups]
        if not any(row):
            continue
        print(f"{nm:<34}" + "".join(f"{('+' if v>0 else '')+str(int(v)) if v else '·':>9}" for v in row))

    # 群ごとの発火率も出す（実務で「何頭に効くか」が分かるように）
    print(f"\n{'加点項目':<34}" + "".join(f"{g:>9}" for g in groups) + "   ←発火率")
    for j in order:
        nm = F.RN[j]
        row = [table[g].get(nm, 0.0) for g in groups]
        if not any(row):
            continue
        fr = []
        for g in groups:
            tot = SGB[(g, "MINE")][:, 0].sum()
            fr.append(NN[g][j] / tot * 100 if tot else 0)
        print(f"{nm:<34}" + "".join(f"{v:8.1f}%" for v in fr))

    # ── 未知期間で1回だけ確認 ──
    print("\n" + "=" * 108)
    print("配点の検算: MINEで決めた点数の符号が、未知期間でも同じ向きか")
    print("=" * 108)
    print(f"{'加点項目':<34}{'群':>6}{'MINE':>9}{'VALIDATE':>10}{'CONFIRM':>9}  一致")
    agree = tot_chk = 0
    for j in order:
        nm = F.RN[j]
        for g in groups:
            p = table[g].get(nm, 0.0)
            if not p:
                continue
            vals = []
            for sgn in ("MINE", "VALIDATE", "CONFIRM"):
                d, n = resid(SG[(g, sgn)], SGB[(g, sgn)])
                vals.append(d[j] if n[j] >= 60 else float('nan'))
            v, va, vc = vals
            ok = (va == va and vc == vc and np.sign(va) == np.sign(p) and np.sign(vc) == np.sign(p))
            if va == va and vc == vc:
                tot_chk += 1; agree += int(ok)
                print(f"{nm:<34}{g:>6}{v:+9.2f}{va:+10.2f}{vc:+9.2f}  {'○' if ok else '×'}")
    print(f"\n符号一致 {agree}/{tot_chk} = {agree/max(1,tot_chk)*100:.1f}%"
          f"（まぐれなら25%。50%を大きく超えていれば配点に意味がある）")

    json.dump({"scale": scale, "min_n": MIN_N, "max_bonus": MAX_BONUS,
               "groups": groups, "table": table,
               "agree": [agree, tot_chk]},
              open("hori_points.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved hori_points.json")


if __name__ == "__main__":
    main()
