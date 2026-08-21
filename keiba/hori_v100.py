# -*- coding: utf-8 -*-
"""堀川システム Ver.100 — 配分を条件ごとに学習し直す（2026-08-21）。

指示:「点数付けしろって 堀川システムという基礎があるんだから」
     「そしてそれを加点や配分変えながら それ固有の堀川システムにしよ」

条件の軸 = **VG（堀川システムのVenue Group）× 距離帯**。
  コース単位(122通り・1コース65R)は使わない。COURSE_SWEEP50_REPORTで
  コース単位の最適化は null control(乱数重み)に8回負けている。
  VGは元から堀川システムが持っているコース特性分類で、標本も足りる。

成分 = Ver.99.27の11成分 + 展開乗数 + 通過順から作った4成分（B-sd16と同じ16本）。
学習 = Plackett-Luce（1-2-3着の並びの尤度）。MINEのみ。
      各セルは**全体1本の重みへ縮小**（L2 shrinkage）。セルが薄いほど全体寄りになる。

検証（3分割厳守・未知期間は各1回）:
  ① 素のVer.99.27（全成分1.0）
  ② 現行の6群（芝ダ×距離帯・B-sd16）
  ③ 今回のVG×距離帯
  ④ null control … セルの割り当てをレースごとにシャッフルして同じ手順
  ④が③に迫るなら、条件別配点は偶然を拾っているだけ。
"""
import json, os, sys, collections, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
import vg as VG

MERGE = {("VG1", "S"): ("VG1", "M"), ("VG3", "M"): ("VG3", "L")}
NAMES16 = ["TSI", "LTS", "FSI", "Bonus", "DSI", "NSI", "CSI", "WAS", "TAS", "HCS",
           "NRJA", "展開乗数", "spd_res", "mgn_abs", "wide4c", "pos_gain"]
JP = {"TSI": "TSI タイム指数", "LTS": "LTS 上がり", "FSI": "FSI 枠×脚質",
      "Bonus": "Bonus TFB/SSC", "DSI": "DSI 距離適性", "NSI": "NSI クラス実績",
      "CSI": "CSI コース適性", "WAS": "WAS 斤量差", "TAS": "TAS 道悪適性",
      "HCS": "HCS 馬体重", "NRJA": "NRJA 間隔", "展開乗数": "展開乗数",
      "spd_res": "spd_res スピード余力", "mgn_abs": "mgn_abs 着差",
      "wide4c": "wide4c 4角外回し", "pos_gain": "pos_gain 位置取り変化"}
BASE_PT = {"TSI": 30, "LTS": 30, "FSI": 15, "Bonus": 15, "DSI": 5, "NSI": 20,
           "CSI": None, "WAS": 15, "TAS": 15, "HCS": None, "NRJA": None,
           "展開乗数": None, "spd_res": None, "mgn_abs": None,
           "wide4c": None, "pos_gain": None}


def cell_of(r):
    g = VG.vg_of(r.get("venue"), r["surface"], r["distance"])
    if not g:
        return None
    d = r["distance"]
    c = "S" if d <= 1400 else ("M" if d <= 1700 else "L")
    g, c = MERGE.get((g, c), (g, c))
    return f"{g}/{c}"


def sd_cell(r):
    """比較対象: 現行の6群（芝ダ×距離帯）"""
    return f"{r['surface']}{r['dist_cat']}"


def fit_cells(races, keyfn, l2, w0):
    """セルごとにPLで学習。全体重み w0 へ縮小。"""
    out = {}
    by = collections.defaultdict(list)
    for r in races:
        k = keyfn(r)
        if k:
            by[k].append(r)
    for k, sub in by.items():
        X, M, W = V2.make_tensor(sub, key="Z22")
        out[k] = V2.fit(X, M, W, l2, w0=w0, wstart=w0)
    return out


def eval_set(races, wfn):
    """モデル1位の勝率 / 3着内率、モデル上位3頭の3着内本数、複勝2点ROI。"""
    n = len(races)
    win = t3 = 0; cost = ret = hit2 = 0
    for r in races:
        w = wfn(r)
        s = r["Z22"] @ w
        o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
        fin = set(r["top3"])
        win += int(o[0] == r["top3"][0])
        t3 += int(o[0] in fin)
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        got = 0
        for i in o[:2]:
            cost += 100
            v = pl.get(r["nums"][i], 0.0)
            ret += v; got |= (v > 0)
        hit2 += got
    return dict(n=n, win=win / n * 100, t3=t3 / n * 100,
                fuku2_hit=hit2 / n * 100, fuku2_roi=ret / cost * 100 if cost else 0)


def main():
    races = V.load_races()
    info = V2.attach_corner(races)              # r["Z16"] = 11成分+展開+通過順4 = 16成分
    print(f"通過順の結合: {info['joined_horses']}/{info['horses']}頭", file=sys.stderr)
    for r in races:
        r["Z22"] = r["Z16"]
    K = races[0]["Z22"].shape[1]
    print(f"レース {len(races)}R / 成分 {K}本", file=sys.stderr)

    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    print(f"MINE {len(MINE)} / VALIDATE {len(VAL)} / CONFIRM {len(CONF)}", file=sys.stderr)

    # 全体1本
    X, M, W = V2.make_tensor(MINE, key="Z22")
    w_all = V2.fit(X, M, W, 1.0, w0=np.zeros(K), wstart=np.zeros(K))
    raw = np.zeros(K); raw[:11] = 1.0           # 素のVer.99.27

    # 縮小の強さを振る。強すぎると条件別が全体1本に潰れるので、
    # 条件別配点に公平な機会を与えてから判定する。
    rs = np.random.RandomState(17)
    L2S = [float(x) for x in (os.environ.get("L2S") or "0.2,1.0,8.0").split(",")]
    L2 = L2S[-1]
    models = {"①素のVer.99.27": lambda r: raw, "②全体1本(学習)": lambda r: w_all}
    w_vg = w_sd = None
    for lam in L2S:
        wv = fit_cells(MINE, cell_of, lam, w_all)
        ws = fit_cells(MINE, sd_cell, lam, w_all)
        keys = sorted(wv.keys())
        fake = {r["rid"]: keys[rs.randint(len(keys))] for r in races}
        wn = fit_cells(MINE, lambda r: fake[r["rid"]], lam, w_all)
        models[f"③現行6群 λ={lam:g}"] = (lambda r, ws=ws: ws.get(sd_cell(r), w_all))
        models[f"④VG×距離帯 λ={lam:g}"] = (lambda r, wv=wv: wv.get(cell_of(r), w_all))
        models[f"⑤null割当 λ={lam:g}"] = (lambda r, wn=wn, fk=fake: wn.get(fk[r["rid"]], w_all))
        if lam == L2:
            w_vg, w_sd = wv, ws
    print("\n" + "=" * 96)
    print("配分の比較（MINEで学習、未知2期は1回だけ測定）")
    print("=" * 96)
    print(f"{'モデル':<26}" + "".join(f"{s:^23}" for s in ("MINE", "VALIDATE", "CONFIRM")))
    print(f"{'':<26}" + "".join(f"{'1位勝率 3着内 複2ROI':^23}" for _ in range(3)))
    out = {}
    for nm, fn in models.items():
        line = f"{nm:<26}"
        rec = {}
        for sn, S in (("MINE", MINE), ("VALIDATE", VAL), ("CONFIRM", CONF)):
            e = eval_set(S, fn); rec[sn] = e
            line += f"{e['win']:7.1f}%{e['t3']:7.1f}%{e['fuku2_roi']:8.1f}%"
        out[nm] = rec
        print(line)

    # ── 配点表（TSI=30点基準） ──
    print("\n" + "=" * 96)
    print("堀川システム Ver.100 配点表 — VG×距離帯ごと（TSI=30点を基準にした相対点）")
    print("=" * 96)
    cells = sorted(w_vg.keys())
    cnt = collections.Counter(cell_of(r) for r in MINE)
    print(f"{'成分':<24}{'Ver.99.27':>10}" + "".join(f"{c:>9}" for c in cells))
    print(f"{'（MINE R数）':<24}{'':>10}" + "".join(f"{cnt[c]:>9}" for c in cells))
    print("-" * (34 + 9 * len(cells)))
    for j, nm in enumerate(NAMES16[:K]):
        base = BASE_PT.get(nm)
        row = f"{JP.get(nm,nm):<24}{(str(base)+'点' if base else '—'):>10}"
        for c in cells:
            w = w_vg[c]
            t = w[0] if abs(w[0]) > 1e-9 else 1.0
            row += f"{w[j]/t*30:>9.0f}"
        print(row)
    print("\n※ 値は「TSIを30点としたときの相対点」。マイナスは減点方向に効く成分。")

    pickle.dump({"w_all": w_all, "w_vg": w_vg, "w_sd": w_sd, "cells": cells,
                 "names": NAMES16[:K], "l2": L2},
                open("hori_v100_weights.pkl", "wb"))
    json.dump({nm: {s: v for s, v in rec.items()} for nm, rec in out.items()},
              open("hori_v100_eval.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved hori_v100_weights.pkl / hori_v100_eval.json")


if __name__ == "__main__":
    main()
