# -*- coding: utf-8 -*-
"""加点方式（離散ボーナス）の点数最適化（2026-08-21）。

指示: 「システム組み替えたらいけるよ 加点方式入れたりしたら」

土台 = Ver.99.27の素の合算スコア（22成分のうち先頭11を1.0）。
その上に「条件を満たしたら ±N点」を積む。Ver.99.27のTFB(+8)/SSC(+10)と同じ構造を、
点数だけデータに決めさせる。

★前回(box5_optimize)の教訓を目的関数に反映:
  的中率を最大化すると最適化が「人気どおりの並び」に収束し、
  的中1回の払戻が-38%落ちてROIが下がった。
  → **今回は的中率でなくROIそのものを最大化する**。的中率と平均払戻を必ず併記。

券種（ユーザー指定）:
  t5box : モデル上位5頭BOX 三連複 10点=1000円
  ax16  : モデル1位軸 - 2〜6位 三連複 10点=1000円
  win   : モデル1位 単勝 1点=100円
  wbox5 : モデル上位5頭BOX ワイド 10点=1000円

検証は3分割を厳守: MINE(≤202602)で決め、VALIDATE/CONFIRMは各1回だけ測る。
偽陽性対策: 同じ手順を「ルール行列をレース内でシャッフルした偽データ」でも回す(null control)。
"""
import json, itertools, os, sys, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import box5_optimize as B

H = B.H
RAWP = '/tmp/rawhist.json'


# ────────────────────────────────────────────────────────────────
# 加点ルールの候補（過去走の生データから作る。Ver.99.27の成分を経由しない）
# ────────────────────────────────────────────────────────────────
def rules():
    R = []
    def add(nm, fn): R.append((nm, fn))

    # --- 脚質・位置取りの型 ---
    for k in (1, 2, 3):
        for th in (0.25, 0.35, 0.45):
            add(f"4角正規化<={th}が{k}走以上",
                lambda rec, r, k=k, th=th: sum(1 for p in rec['c4n'] if p is not None and p <= th) >= k)
    for k in (2, 3):
        add(f"4角先頭級(<=0.15)が{k}走以上",
            lambda rec, r, k=k: sum(1 for p in rec['c4n'] if p is not None and p <= 0.15) >= k)
    add("道中5番手以上押し上げが1走以上",
        lambda rec, r: any(ca and len(ca) >= 4 and ca[0] and ca[3] and (ca[0] - ca[3]) >= 5 for ca in rec['c_all']))
    add("道中5番手以上押し上げが2走以上",
        lambda rec, r: sum(1 for ca in rec['c_all']
                           if ca and len(ca) >= 4 and ca[0] and ca[3] and (ca[0] - ca[3]) >= 5) >= 2)

    # --- 着差（勝ち馬との差）で見る「負けても内容が良い」型 ---
    for th in (0.2, 0.5):
        for k in (1, 2):
            add(f"着差{th}秒以内の敗戦が{k}走以上",
                lambda rec, r, th=th, k=k: sum(
                    1 for m, rk in zip(rec['margin'], rec['rank'])
                    if m is not None and rk and rk > 1 and abs(m) <= th) >= k)

    # --- 相手関係 ---
    for fld in (12, 14):
        add(f"{fld}頭以上で3着内",
            lambda rec, r, fld=fld: any(f and f >= fld and rk and rk <= 3
                                        for f, rk in zip(rec['field'], rec['rank'])))
    add("上級クラス(tier<=5)を経験", lambda rec, r: any(t is not None and t <= 5 for t in rec['tier']))
    for k in (1, 2):
        add(f"格上げ後も3着内が{k}走以上",
            lambda rec, r, k=k: sum(1 for a, b, rk in zip(rec['tier'], rec['tier'][1:], rec['rank'])
                                    if a is not None and b is not None and a < b and rk and rk <= 3) >= k)

    # --- 条件替わり ---
    for d in (200, 400):
        add(f"前走から{d}m以上の短縮",
            lambda rec, r, d=d: bool(rec['dist'] and rec['dist'][0] and rec['dist'][0] - r['distance'] >= d))
        add(f"前走から{d}m以上の延長",
            lambda rec, r, d=d: bool(rec['dist'] and rec['dist'][0] and r['distance'] - rec['dist'][0] >= d))
    add("休み明け(85日以上)", lambda rec, r: bool(rec['days'] and rec['days'][0] and rec['days'][0] >= 85))
    add("連戦(21日以内)", lambda rec, r: bool(rec['days'] and rec['days'][0] and 0 < rec['days'][0] <= 21))
    add("芝ダ替わり", lambda rec, r: bool(rec['surface'] and rec['surface'][0]
                                          and rec['surface'][0] != r.get('surface')))
    add("同距離で3着内",
        lambda rec, r: any(d == r['distance'] and rk and rk <= 3
                           for d, rk in zip(rec['dist'], rec['rank'])))
    add("道悪(baba>=2)で3着内",
        lambda rec, r: any(b is not None and b >= 2 and rk and rk <= 3
                           for b, rk in zip(rec['baba'], rec['rank'])))
    add("ハイペース経験(前後半差<=-1.0)",
        lambda rec, r: any(pf is not None and pl is not None and (pf - pl) <= -1.0
                           for pf, pl in zip(rec['pf'], rec['pl'])))
    add("スロー経験(前後半差>=+1.0)",
        lambda rec, r: any(pf is not None and pl is not None and (pf - pl) >= 1.0
                           for pf, pl in zip(rec['pf'], rec['pl'])))

    # --- 直近の形（★市場が過大/過小評価している型。実測lift参照）---
    add("前走3着内", lambda rec, r: bool(rec['rank'] and rec['rank'][0] and rec['rank'][0] <= 3))
    for th in (8, 10):
        add(f"前走{th}着以下", lambda rec, r, th=th: bool(rec['rank'] and rec['rank'][0]
                                                          and rec['rank'][0] >= th))
    add("直近3走すべて掲示板(5着内)",
        lambda rec, r: len([x for x in rec['rank'][:3] if x and x <= 5]) == 3)
    add("直近3走すべて着外(6着以下)",
        lambda rec, r: len([x for x in rec['rank'][:3] if x and x >= 6]) == 3)
    add("前走大敗(8着以下)だが着差0.5秒以内",
        lambda rec, r: bool(rec['rank'] and rec['rank'][0] and rec['rank'][0] >= 8
                            and rec['margin'] and rec['margin'][0] is not None
                            and abs(rec['margin'][0]) <= 0.5))
    add("前走大敗(8着以下)だが4角3番手以内",
        lambda rec, r: bool(rec['rank'] and rec['rank'][0] and rec['rank'][0] >= 8
                            and rec['c4n'] and rec['c4n'][0] is not None and rec['c4n'][0] <= 0.25))
    return R


RL = rules()
RN = [nm for nm, _ in RL]


def rule_matrix(races, RAW):
    out = []
    for r in races:
        per = RAW.get(r["rid"], {})
        M = np.zeros((len(r["nums"]), len(RL)), np.float32)
        rr = dict(distance=r["distance"], surface=r["surface"])
        for i, num in enumerate(r["nums"]):
            rec = per.get(str(num)) or per.get(num)
            if not rec:
                continue
            for j, (_, fn) in enumerate(RL):
                try:
                    if fn(rec, rr):
                        M[i, j] = 1.0
                except Exception:
                    pass
        out.append(M)
    return out


# ────────────────────────────────────────────────────────────────
# 高速評価: ROIも的中率も一気に出す
# ────────────────────────────────────────────────────────────────
def pack(rs, MS):
    """Xp(素点), Mb(ルール), mask, T(1-3着のindex), WA, NU, 払戻ベクトル"""
    R = len(rs); K = rs[0]["Z22"].shape[1]; J = len(RL)
    Xp = np.zeros((R, H, K), np.float32); Mb = np.zeros((R, H, J), np.float32)
    mask = np.zeros((R, H), bool); T = np.zeros((R, 3), int)
    WA = np.zeros((R, H), np.float32); NU = np.zeros((R, H), np.int32)
    P3 = np.zeros(R); P1 = np.zeros(R); PW = np.zeros((R, 3))
    for i, r in enumerate(rs):
        n = len(r["nums"])
        Xp[i, :n] = r["Z22"]; Mb[i, :n] = MS[i]; mask[i, :n] = True
        T[i] = r["top3"]; WA[i, :n] = r["wavg"]; NU[i, :n] = r["nums"]
        pay = r["payout"] or {}
        fin = sorted(r["nums"][k] for k in r["top3"])
        s3 = (pay.get("三連複") or {}).get("-".join(str(x) for x in fin))
        P3[i] = float(s3) if s3 else 0.0
        t1 = (pay.get("単勝") or {}).get(str(r["nums"][r["top3"][0]]))
        P1[i] = float(t1) if t1 else 0.0
        wd = pay.get("ワイド") or {}
        for k, (a, b) in enumerate(itertools.combinations(fin, 2)):
            v = wd.get(f"{a}-{b}") or wd.get(f"{b}-{a}")
            PW[i, k] = float(v) if v else 0.0
    return dict(Xp=Xp, Mb=Mb, mask=mask, T=T, WA=WA, NU=NU, P3=P3, P1=P1, PW=PW, R=R)


def positions(P, w, b):
    """各レースで 1,2,3着馬がモデル何位か(0始まり)。"""
    s = P["Xp"] @ w + P["Mb"] @ b
    s = np.where(P["mask"], s, -1e18)
    key = (-s) * 1e9 + (-P["WA"]) * 1e3 + P["NU"]
    key = np.where(P["mask"], key, 1e30)
    order = np.argsort(key, axis=1)
    pos = np.empty_like(order)
    rows = np.arange(P["R"])[:, None]
    pos[rows, order] = np.arange(H)[None, :]
    ri = np.arange(P["R"])
    return np.stack([pos[ri, P["T"][:, 0]], pos[ri, P["T"][:, 1]], pos[ri, P["T"][:, 2]]], 1)


def evaluate(P, w, b):
    """4券種の (的中率, ROI, 的中時平均払戻) をまとめて返す。"""
    p = positions(P, w, b)
    p1, p2, p3 = p[:, 0], p[:, 1], p[:, 2]
    n = P["R"]
    res = {}

    t5 = (p < 5).all(1)
    res["t5box"] = _r(t5, P["P3"], 1000, n)

    has0 = (p == 0).any(1)
    rest = np.sort(np.where(p == 0, 99, p), 1)[:, :2]
    ax = has0 & (rest[:, 0] >= 1) & (rest[:, 1] <= 5)
    res["ax16"] = _r(ax, P["P3"], 1000, n)

    wn = (p1 == 0)
    res["win"] = _r(wn, P["P1"], 100, n)

    # ワイドBOX5: 上位5頭内に入った「3着内のペア」全部が当たる
    inb = (p < 5)
    pw = P["PW"]
    pairs = [(0, 1), (0, 2), (1, 2)]
    ret = np.zeros(n); hitw = np.zeros(n, bool)
    for k, (a, c) in enumerate(pairs):
        ok = inb[:, a] & inb[:, c]
        ret += np.where(ok, pw[:, k], 0.0)
        hitw |= ok
    res["wbox5"] = dict(n=n, hit=hitw.mean() * 100, roi=ret.sum() / (1000 * n) * 100,
                        avgpay=float(ret[hitw].mean()) if hitw.any() else 0.0,
                        pl=float(ret.sum() - 1000 * n))
    return res


def _r(hit, pay, cost, n):
    ret = np.where(hit, pay, 0.0)
    return dict(n=n, hit=float(hit.mean() * 100), roi=float(ret.sum() / (cost * n) * 100),
                avgpay=float(pay[hit].mean()) if hit.any() else 0.0,
                pl=float(ret.sum() - cost * n))


def obj(P, w, b, mode):
    return evaluate(P, w, b)[mode]["roi"]


# ────────────────────────────────────────────────────────────────
# CEM: 加点ベクトル b を探索（点数は -10〜+15 に制限。Ver.99.27の+8/+10と同じ桁）
# ────────────────────────────────────────────────────────────────
LO, HI = -10.0, 15.0


def cem(P, w, mode, iters=45, pop=160, elite=0.12, seed=0, sd0=4.0):
    rs = np.random.RandomState(seed)
    J = len(RL)
    mu = np.zeros(J); sd = np.full(J, sd0)
    best_b, best_v = np.zeros(J), obj(P, w, np.zeros(J), mode)
    for _ in range(iters):
        C = np.clip(rs.randn(pop, J) * sd + mu, LO, HI)
        C[0] = best_b                                  # エリート保存
        vals = np.array([obj(P, w, C[i], mode) for i in range(pop)])
        k = max(4, int(pop * elite))
        idx = np.argsort(-vals)[:k]
        mu = C[idx].mean(0); sd = C[idx].std(0) + 0.15
        if vals[idx[0]] > best_v:
            best_v, best_b = vals[idx[0]], C[idx[0]].copy()
    return best_b, best_v


def lift_table(Pm):
    """各ルールの「実際の3着内率 ÷ 市場想定3着内率」。加点の方向を人が確認するため。"""
    # 市場想定は使えないのでここでは実測の3着内率と発火率のみ（market比は別途）
    pos = positions(Pm, RAWW, np.zeros(len(RL)))
    return pos


RAWW = np.zeros(22); RAWW[:11] = 1.0


def main():
    mode_list = sys.argv[1:] or ["t5box", "ax16", "win", "wbox5"]
    print("読み込み中...", file=sys.stderr)
    races = B.load()
    RAW = json.load(open(RAWP))
    MS = rule_matrix(races, RAW)
    for r, m in zip(races, MS):
        r["_M"] = m

    seg = lambda lo, hi: [(r, r["_M"]) for r in races if lo <= r["month"] <= hi]
    parts = {"MINE": seg('000000', '202602'), "VALIDATE": seg('202603', '202605'),
             "CONFIRM": seg('202606', '202608')}
    packs = {k: pack([a for a, _ in v], [m for _, m in v]) for k, v in parts.items()}
    print({k: v["R"] for k, v in packs.items()}, file=sys.stderr)

    # 発火率（MINE）
    fire = packs["MINE"]["Mb"].sum((0, 1)) / packs["MINE"]["mask"].sum()
    out = {"rules": RN, "fire": [round(float(x), 4) for x in fire], "modes": {}}

    zero = np.zeros(len(RL))
    for nm, P in packs.items():
        out.setdefault("baseline", {})[nm] = evaluate(P, RAWW, zero)

    for mode in mode_list:
        print(f"\n=== {mode} ===", file=sys.stderr)
        b, v = cem(packs["MINE"], RAWW, mode, seed=11)
        rec = {"b": [round(float(x), 2) for x in b], "mine_roi": v}
        for nm, P in packs.items():
            rec[nm] = evaluate(P, RAWW, b)
        # null control: レース内で行(=馬)をシャッフルした偽ルールで同じ最適化
        rs = np.random.RandomState(5)
        Pn = dict(packs["MINE"]); Mb = Pn["Mb"].copy()
        for i in range(Pn["R"]):
            k = int(Pn["mask"][i].sum())
            Mb[i, :k] = Mb[i, rs.permutation(k)]
        Pn["Mb"] = Mb
        bn, vn = cem(Pn, RAWW, mode, seed=11)
        rec["null_mine_roi"] = vn
        base = out["baseline"]["MINE"][mode]["roi"]
        rec["gain_real"] = v - base
        rec["gain_null"] = vn - base
        out["modes"][mode] = rec
        for nm in ("MINE", "VALIDATE", "CONFIRM"):
            e = rec[nm][mode]; be = out["baseline"][nm][mode]
            print(f"  {nm:9s} 的中 {be['hit']:5.1f}%→{e['hit']:5.1f}%  "
                  f"ROI {be['roi']:6.1f}%→{e['roi']:6.1f}%  "
                  f"平均払戻 {be['avgpay']:7.0f}→{e['avgpay']:7.0f}円", file=sys.stderr)
        print(f"  MINE上昇 実 +{rec['gain_real']:.1f}pt / 偽データ +{rec['gain_null']:.1f}pt",
              file=sys.stderr)

    json.dump(out, open("bonus_result.json", "w"), ensure_ascii=False, indent=1)
    print("\nsaved bonus_result.json", file=sys.stderr)


if __name__ == "__main__":
    main()
