# -*- coding: utf-8 -*-
"""堀川システム Ver.100 — 加点を「全体1本」で入れて、順位が良くなるか測る（2026-08-21）。

ここまでで分かったこと:
  ・配分を学習し直すと素のVer.99.27を大きく上回る（1位勝率+3pt/3着内+5〜6pt、未知2期とも）。
  ・**配分を条件（VG×距離帯）ごとに変えても全体1本と差が出ない**（null controlと同じ）。
  ・**加点を条件ごとに決めるのも偽物**（符号一致 62/215 = 28.8%。まぐれ25%）。
  → 残る可能性は「加点を全体1本で入れる」。こちらは標本が桁違いに大きい
     （例: 直近3走すべて着外 n=22,084、帯を揃えた残差 +6.49pt）。

やること:
  スコア = Z16 @ w（学習した配分） + Σ 点数_j × ルール_j
  点数_j = 帯を揃えた複勝残差(pt) × スケール（最大 +10点 = SSC相当）
  ※ 点数は**探索しない**。CEMで探索するとnull controlに負けることを実測済み
    （t5box: 実 +104.6pt / 偽 +116.2pt）。実測値をそのまま配点に使う。

判定: 1位勝率 / 3着内率 / 複勝2点ROI が、未知2期間**とも**上がるか。
      null control（ルールを無関係な馬のものに差し替え）を必ず併走。
"""
import json, os, sys, collections, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2
import bonus_fit as F

EDGES = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 25.0, 40.0, 70.0, 120.0, 1e9]
NB = len(EDGES) - 1
MAX_BONUS = 10.0
MIN_N = 2000        # 全体1本なので発火数のしきいは高くする


def band_of(o):
    for i in range(NB):
        if EDGES[i] <= o < EDGES[i + 1]:
            return i
    return NB - 1


def main():
    races = V.load_races()
    V2.attach_corner(races)
    for r in races:
        r["Z16"] = r["Z16"]
    K = races[0]["Z16"].shape[1]
    RAW = json.load(open(F.RAWP))
    RL = F.RL; J = len(RL)

    # ルール行列を作る（レース×馬×ルール）
    for r in races:
        per = RAW.get(r["rid"], {})
        Mx = np.zeros((len(r["nums"]), J), np.float32)
        rr = dict(distance=r["distance"], surface=r["surface"])
        for i, num in enumerate(r["nums"]):
            rec = per.get(str(num)) or per.get(num)
            if not rec:
                continue
            for j, (_, fn) in enumerate(RL):
                try:
                    if fn(rec, rr):
                        Mx[i, j] = 1.0
                except Exception:
                    pass
        r["RM"] = Mx

    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')

    # ── 配分（MINEで学習） ──
    X, M, W = V2.make_tensor(MINE, key="Z16")
    w = V2.fit(X, M, W, 1.0, w0=np.zeros(K), wstart=np.zeros(K))
    raw = np.zeros(K); raw[:11] = 1.0

    # ── 加点（MINEで実測。帯を揃えた複勝残差） ──
    A = np.zeros((J, NB, 2)); Base = np.zeros((NB, 2))
    for r in MINE:
        pay = r["payout"] or {}
        pl = {int(k): float(v) for k, v in (pay.get("複勝") or {}).items()}
        if not pl:
            continue
        for i, num in enumerate(r["nums"]):
            o = r["odds"].get(num)
            if not o:
                continue
            k = band_of(float(o)); v = pl.get(num, 0.0)
            Base[k] += [1, v]
            A[:, k, 0] += r["RM"][i]
            A[:, k, 1] += r["RM"][i] * v
    broi = np.where(Base[:, 0] > 0, Base[:, 1] / np.maximum(100 * Base[:, 0], 1), 0)
    n_j = A[:, :, 0].sum(1)
    act = np.where(n_j > 0, A[:, :, 1].sum(1) / np.maximum(100 * n_j, 1), 0)
    exp = np.where(n_j > 0, (A[:, :, 0] * broi[None, :]).sum(1) / np.maximum(n_j, 1), 0)
    resid = (act - exp) * 100
    ok = n_j >= MIN_N
    scale = MAX_BONUS / max(1e-9, float(np.max(np.abs(resid[ok]))))
    pts = np.where(ok, np.round(resid * scale), 0.0)

    print("=" * 96)
    print("堀川システム Ver.100 加点表（全体1本・SSC=+10点の尺度）")
    print("=" * 96)
    print(f"{'加点項目':<36}{'点数':>6}{'発火率':>8}{'残差pt':>9}")
    for j in np.argsort(-np.abs(pts)):
        if pts[j] == 0:
            continue
        print(f"{F.RN[j]:<36}{('+' if pts[j]>0 else '')+str(int(pts[j])):>6}"
              f"{n_j[j]/Base[:,0].sum()*100:7.1f}%{resid[j]:+9.2f}")

    # ── 加点の大きさを何段階か振って測る（0=加点なし） ──
    def ev(S, wv, b, scl):
        n = len(S); win = t3 = 0; cost = ret = 0
        for r in S:
            s = r["Z16"] @ wv + (r["RM"] @ b) * scl
            o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
            win += int(o[0] == r["top3"][0]); t3 += int(o[0] in set(r["top3"]))
            pl = {int(k): float(v) for k, v in ((r["payout"] or {}).get("複勝") or {}).items()}
            for i in o[:2]:
                cost += 100; ret += pl.get(r["nums"][i], 0.0)
        return win / n * 100, t3 / n * 100, (ret / cost * 100 if cost else 0)

    # 加点はスコアの尺度に合わせる: 学習スコアのSDを基準に、10点=SDの何倍かを振る
    sds = np.std(np.concatenate([r["Z16"] @ w for r in MINE]))
    print(f"\n学習スコアのSD = {sds:.3f}。加点10点を SD×k として k を振る。")

    # null control: ルール行列を別の馬のものに差し替え
    rs = np.random.RandomState(9)
    allRM = [r["RM"] for r in races]
    shuffled = {}
    for r in races:
        src = allRM[rs.randint(len(allRM))]
        n = len(r["nums"])
        Mx = np.zeros((n, J), np.float32)
        m = min(n, src.shape[0])
        Mx[:m] = src[:m]
        shuffled[r["rid"]] = Mx

    print("\n" + "=" * 96)
    print("加点の効果（k=0が加点なし。未知2期とも上がるかで判定）")
    print("=" * 96)
    print(f"{'k':>5} {'種別':<6}" + "".join(f"{s:^24}" for s in ("MINE", "VALIDATE", "CONFIRM")))
    print(f"{'':>5} {'':<6}" + "".join(f"{'1位勝率 3着内 複2ROI':^24}" for _ in range(3)))
    out = {"pts": pts.tolist(), "names": F.RN, "resid": resid.tolist(),
           "n": n_j.tolist(), "rows": []}
    for k in (0.0, 0.02, 0.05, 0.10, 0.20):
        scl = sds * k / MAX_BONUS
        for tag in ("実", "偽"):
            if tag == "偽" and k == 0:
                continue
            line = f"{k:5.2f} {tag:<6}"
            rec = {}
            for sn, S in (("MINE", MINE), ("VALIDATE", VAL), ("CONFIRM", CONF)):
                if tag == "偽":
                    for r in S:
                        r["_RMsave"] = r["RM"]; r["RM"] = shuffled[r["rid"]]
                a, b_, c = ev(S, w, pts, scl)
                if tag == "偽":
                    for r in S:
                        r["RM"] = r["_RMsave"]
                rec[sn] = (a, b_, c)
                line += f"{a:8.1f}%{b_:7.1f}%{c:8.1f}%"
            out["rows"].append(dict(k=k, kind=tag, **{s: v for s, v in rec.items()}))
            print(line)

    json.dump(out, open("hori_bonus.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved hori_bonus.json")


if __name__ == "__main__":
    main()
