# -*- coding: utf-8 -*-
"""ユーザー仕様の目的関数で配点を直接最適化する（2026-08-21）。

指示:
  「点数配分や項目を変えたら、その特定のレースならほとんど的中するように全部細かく作り変える
   理想は上位5頭ボックスで三連複が的中する / 最上位が1着になる /
   軸最上位・紐2〜6位の三連複でもいい」

これまでの最適化目標（順序尤度・複勝）とは別物。以下の3つを**直接**最大化する。
  T5BOX : 1〜3着が全部モデル上位5頭に入る（＝上位5頭BOX 10点で三連複的中）
  WIN1  : モデル1位が1着
  AX16  : モデル1位が3着内 ∧ 残り2頭がモデル2〜6位（＝1位軸-2〜6流し 10点で的中）
"""
import json, collections, itertools, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2

CORNER10 = ['pos_gain', 'pos_var', 'wide4c', 'pace_lv', 'pace_gap',
            'fwd_fin', 'mgn_abs', 'spd_res', 'grind', 'unlucky']
NAMES = list(V.COMPS) + CORNER10          # 22成分
H = 20


def load():
    races = V.load_races()
    z = np.load("corner_ds.npz", allow_pickle=False)
    A, rid_arr, feats = z["A"], z["rid"], [str(x) for x in z["feats"]]
    idx = [feats.index(f) for f in CORNER10]
    F = len(feats)
    ridx = A[:, F + 4].astype(int); num = A[:, F + 5].astype(int)
    mp = {}
    for i in range(len(A)):
        mp[(str(rid_arr[ridx[i]]), int(num[i]))] = A[i, idx]
    ex = json.load(open('/tmp/extra.json'))
    out = []
    for r in races:
        n = len(r["nums"]); C = np.zeros((n, 10))
        for i, nm in enumerate(r["nums"]):
            v = mp.get((r["rid"], nm))
            if v is not None:
                C[i] = v
        r["Z22"] = np.hstack([r["Z"], C])
        e = ex.get(r["rid"], {})
        r["venue"] = e.get("venue"); r["dist"] = e.get("dist")
        r["course"] = f"{e.get('venue')}{r['surface']}{r['distance']}"
        r["sdk"] = "".join(V.axis_key(r, "sd"))
        out.append(r)
    return out


def ranks_of(r, w):
    """モデル順位（馬番の並び）。タイブレークは既存と同じ。"""
    s = r["Z22"] @ w
    o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
    return [r["nums"][i] for i in o]


def hits(r, w):
    """(T5BOX, WIN1, AX16) を 0/1 で返す。"""
    rk = ranks_of(r, w)
    fin = [r["nums"][i] for i in r["top3"]]        # 1,2,3着の馬番
    top5 = set(rk[:5])
    t5 = int(all(f in top5 for f in fin))
    w1 = int(rk[0] == fin[0])
    ax = 0
    if rk[0] in fin:
        legs = set(rk[1:6])
        others = [f for f in fin if f != rk[0]]
        ax = int(len(others) == 2 and all(o in legs for o in others))
    return t5, w1, ax


def score_set(rs, w):
    n = len(rs)
    if not n:
        return None
    a = b = c = 0
    for r in rs:
        t5, w1, ax = hits(r, w)
        a += t5; b += w1; c += ax
    return dict(n=n, t5=a / n * 100, win=b / n * 100, ax=c / n * 100)


def roi_of(rs, w, mode):
    """実払戻でのROI。mode: 't5box'(10点) / 'win'(1点) / 'ax16'(10点)"""
    cost = ret = hit = 0
    for r in rs:
        rk = ranks_of(r, w); pay = r["payout"]
        if mode == "t5box":
            S = {k: float(v) for k, v in (pay.get("三連複") or {}).items()}
            combos = list(itertools.combinations(rk[:5], 3))
            cost += 100 * len(combos); got = 0
            for cmb in combos:
                k = "-".join(str(x) for x in sorted(cmb))
                if k in S: ret += S[k]; got = 1
            hit += got
        elif mode == "win":
            T = {int(k): float(v) for k, v in (pay.get("単勝") or {}).items()}
            cost += 100
            if rk[0] in T: ret += T[rk[0]]; hit += 1
        elif mode == "ax16":
            S = {k: float(v) for k, v in (pay.get("三連複") or {}).items()}
            combos = [(rk[0], a, b) for a, b in itertools.combinations(rk[1:6], 2)]
            cost += 100 * len(combos); got = 0
            for cmb in combos:
                k = "-".join(str(x) for x in sorted(cmb))
                if k in S: ret += S[k]; got = 1
            hit += got
    n = len(rs)
    return dict(n=n, hit=hit / n * 100 if n else 0,
                roi=ret / cost * 100 if cost else 0, pl=ret - cost)


# ── 目的関数を直接最大化する探索（勾配が無いので進化的探索=CEM） ──
def pack_group(rs):
    """高速化: 群のZ22とtop3を行列に詰める。"""
    R = len(rs); K = rs[0]["Z22"].shape[1]
    Xp = np.zeros((R, H, K)); mask = np.zeros((R, H), bool)
    T = np.zeros((R, 3), int); WA = np.zeros((R, H)); NU = np.zeros((R, H), int)
    for i, r in enumerate(rs):
        n = len(r["nums"])
        Xp[i, :n] = r["Z22"]; mask[i, :n] = True; T[i] = r["top3"]
        WA[i, :n] = r["wavg"]; NU[i, :n] = r["nums"]
    return Xp, mask, T, WA, NU


def fast_hits(w, P):
    """(T5BOX率, WIN率, AX率) をベクトル化して一気に測る。"""
    Xp, mask, T, WA, NU = P
    R, Hh, _ = Xp.shape
    s = np.where(mask, Xp @ w, -1e18)
    # タイブレーク: スコア↓ → WAvg↓ → 馬番↑
    key = (-s) * 1e9 + (-WA) * 1e3 + NU
    key = np.where(mask, key, 1e30)
    order = np.argsort(key, axis=1)              # 各レースの順位→行index
    pos = np.empty_like(order)
    rows = np.arange(R)[:, None]
    pos[rows, order] = np.arange(Hh)[None, :]    # 行index→順位
    p1, p2, p3 = pos[rows[:, 0], T[:, 0]], pos[rows[:, 0], T[:, 1]], pos[rows[:, 0], T[:, 2]]
    t5 = ((p1 < 5) & (p2 < 5) & (p3 < 5)).mean() * 100
    win = (p1 == 0).mean() * 100
    axis_in = (p1 == 0) | (p2 == 0) | (p3 == 0)
    legs_ok = np.zeros(R, bool)
    for a, b in ((p1, p2), (p1, p3), (p2, p3)):
        pass
    # 軸(=順位0)が3着内 かつ 残り2頭が順位1..5
    allp = np.stack([p1, p2, p3], 1)
    has0 = (allp == 0).any(1)
    rest = np.where(allp == 0, 99, allp)         # 軸を除いた残り2頭
    rest_sorted = np.sort(rest, 1)[:, :2]
    legs_ok = has0 & (rest_sorted[:, 0] >= 1) & (rest_sorted[:, 1] <= 5)
    return t5, win, legs_ok.mean() * 100


def cem_optimize(P, w0, target="t5", iters=40, pop=120, elite=0.15, seed=0):
    """交差エントロピー法。targetの率を最大化する重みを返す。"""
    rs_ = np.random.RandomState(seed)
    mu = w0.copy(); sd = np.abs(w0) * 0.5 + 0.05
    ti = {"t5": 0, "win": 1, "ax": 2}[target]
    best_w, best_v = w0.copy(), fast_hits(w0, P)[ti]
    for _ in range(iters):
        C = rs_.randn(pop, len(mu)) * sd + mu
        vals = np.array([fast_hits(C[i], P)[ti] for i in range(pop)])
        k = max(3, int(pop * elite))
        idx = np.argsort(-vals)[:k]
        mu = C[idx].mean(0); sd = C[idx].std(0) + 1e-3
        if vals[idx[0]] > best_v:
            best_v, best_w = vals[idx[0]], C[idx[0]].copy()
    return best_w, best_v


def main():
    races = load()
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    raw = np.zeros(22); raw[:11] = 1.0          # Ver.99.27 素の合算

    # 条件の切り方: 芝ダ×距離帯6群（コース単位は標本不足で偶然を拾うため）
    def gk(r): return r["sdk"]
    groups = sorted({gk(r) for r in MINE})
    print(f"条件: {groups}", file=sys.stderr)

    out = {"baseline": {}, "groups": {}}
    for nm, S in (("MINE", MINE), ("VALIDATE", VAL), ("CONFIRM", CONF)):
        P = pack_group(S)
        t5, wi, ax = fast_hits(raw, P)
        out["baseline"][nm] = dict(n=len(S), t5=t5, win=wi, ax=ax)

    for g in groups:
        gm = [r for r in MINE if gk(r) == g]
        gv = [r for r in VAL if gk(r) == g]
        gc = [r for r in CONF if gk(r) == g]
        Pm = pack_group(gm)
        rec = {"n": [len(gm), len(gv), len(gc)], "targets": {}}
        for tgt in ("t5", "win", "ax"):
            w, v = cem_optimize(Pm, raw, target=tgt, iters=40, pop=150, seed=7)
            r = {"mine": dict(zip(("t5", "win", "ax"), fast_hits(w, Pm)))}
            for nm, gs in (("val", gv), ("conf", gc)):
                r[nm] = dict(zip(("t5", "win", "ax"), fast_hits(w, pack_group(gs)))) if gs else None
            # 素の同群ベースライン
            r["base_mine"] = dict(zip(("t5", "win", "ax"), fast_hits(raw, Pm)))
            r["base_val"] = dict(zip(("t5", "win", "ax"), fast_hits(raw, pack_group(gv)))) if gv else None
            r["base_conf"] = dict(zip(("t5", "win", "ax"), fast_hits(raw, pack_group(gc)))) if gc else None
            r["w"] = [round(float(x), 5) for x in w]
            # ROI（実払戻）
            mode = {"t5": "t5box", "win": "win", "ax": "ax16"}[tgt]
            r["roi_mine"] = roi_of(gm, w, mode)
            r["roi_val"] = roi_of(gv, w, mode) if gv else None
            r["roi_conf"] = roi_of(gc, w, mode) if gc else None
            r["roi_base_conf"] = roi_of(gc, raw, mode) if gc else None
            rec["targets"][tgt] = r
            print(f"  {g} {tgt}: MINE {r['mine'][tgt]:.1f}% (素{r['base_mine'][tgt]:.1f}%) "
                  f"→ VAL {r['val'][tgt] if r['val'] else float('nan'):.1f}% "
                  f"CONF {r['conf'][tgt] if r['conf'] else float('nan'):.1f}%", file=sys.stderr)
        out["groups"][g] = rec
    json.dump(out, open("box5_result.json", "w"), ensure_ascii=False, indent=1)
    print("saved box5_result.json", file=sys.stderr)


if __name__ == "__main__":
    main()
