# -*- coding: utf-8 -*-
"""POLICY_PROTOCOL.md の機械実行。
レース特徴→7行動(見送り含む)の深さ<=3方策木をMINEで学習し、VAL/CONFで1回評価。
ヌル統制: MINE内でラベル(7行動の掛金/払戻ベクトル)をシャッフルx100 → 偽方策を実VAL/CONFで評価。
決定的(分位グリッドはMINE固定、木は貪欲・タイブレーク固定)。
"""
import json, itertools, numpy as np

ACTIONS = ["見送り", "複勝市場2点", "複勝モデル1点", "ワイド市場1-2",
           "ワイドB-sd16上位2", "三連複市場4BOX", "三連複B-sd16 2軸流し"]
FEATS = ["fav_p", "ent", "sgap16", "field", "fav1_odds", "tier", "surf", "dist"]
MIN_LEAF = 300
MAX_DEPTH = 3

def pair_key(a, b):
    a, b = sorted((int(a), int(b)))
    return f"{a}-{b}"

def tri_key(a, b, c):
    a, b, c = sorted((int(a), int(b), int(c)))
    return f"{a}-{b}-{c}"

def load():
    rows = []
    for line in open("bsd16_races.jsonl"):
        r = json.loads(line)
        odds = {int(k): float(v) for k, v in r["odds"].items()}
        market = sorted(odds, key=lambda h: (odds[h], h))
        rank = r["rank16"]
        po = r["payout"]
        fuku = {int(k): v for k, v in po.get("複勝", {}).items()}
        wide = po.get("ワイド", {})
        trio = po.get("三連複", {})
        S = np.zeros(7); R = np.zeros(7)
        # A1 複勝市場2点
        if len(market) >= 2:
            S[1] = 200; R[1] = sum(fuku.get(h, 0) for h in market[:2])
        # A2 複勝モデル1点
        S[2] = 100; R[2] = fuku.get(int(rank[0]), 0)
        # A3 ワイド市場1-2
        if len(market) >= 2:
            S[3] = 100; R[3] = wide.get(pair_key(*market[:2]), 0)
        # A4 ワイドB-sd16上位2
        S[4] = 100; R[4] = wide.get(pair_key(rank[0], rank[1]), 0)
        # A5 三連複市場4BOX
        if len(market) >= 4:
            combos = list(itertools.combinations(market[:4], 3))
            S[5] = 100 * len(combos)
            R[5] = sum(trio.get(tri_key(*c), 0) for c in combos)
        # A6 三連複B-sd16 2軸流し (相手=rank 3..6位、ある分だけ)
        partners = rank[2:6]
        if partners:
            S[6] = 100 * len(partners)
            R[6] = sum(trio.get(tri_key(rank[0], rank[1], p), 0) for p in partners)
        sd = r["sd"]
        surf = 1.0 if sd.startswith("ダ") else 0.0
        dist = {"S": 0.0, "M": 1.0, "L": 2.0}[sd[-1]]
        x = [r["fav_p"], r["ent"], r["sgap16"], float(r["field"]),
             min(odds.values()), float(r["tier"]), surf, dist]
        rows.append((r["rid"], r["month"], np.array(x), S, R))
    rows.sort(key=lambda t: t[0])
    rid = [t[0] for t in rows]; month = [t[1] for t in rows]
    X = np.array([t[2] for t in rows])
    S = np.array([t[3] for t in rows]); R = np.array([t[4] for t in rows])
    return rid, month, X, S, R

def leaf_action(S, R, idx):
    """ROI最大の行動。最大ROI<=1.0なら0(見送り)。タイブレーク=行動番号の小さい方。"""
    best_a, best_roi = 0, 1.0
    for a in range(1, 7):
        st = S[idx, a].sum()
        if st <= 0:
            continue
        roi = R[idx, a].sum() / st
        if roi > best_roi + 1e-12:
            best_a, best_roi = a, roi
    return best_a

def node_value(S, R, idx):
    a = leaf_action(S, R, idx)
    return (R[idx, a].sum() - S[idx, a].sum()) if a else 0.0, a

def build_grid(Xm):
    grid = []  # list of (fi, thr)
    qs = np.arange(0.1, 0.91, 0.1)
    for fi, name in enumerate(FEATS):
        if name in ("fav_p", "ent", "sgap16", "fav1_odds"):
            for t in np.quantile(Xm[:, fi], qs):
                grid.append((fi, float(t)))
        elif name == "field":
            for t in (7, 9, 11, 13, 15, 17): grid.append((fi, float(t)))
        elif name == "tier":
            for t in (3, 4, 5, 6): grid.append((fi, float(t)))
        elif name == "surf":
            grid.append((fi, 0.0))
        elif name == "dist":
            grid.append((fi, 0.0)); grid.append((fi, 1.0))
    return grid

def fit(X, S, R, idx, grid, depth=0):
    val, act = node_value(S, R, idx)
    if depth >= MAX_DEPTH:
        return {"leaf": True, "action": act, "n": len(idx), "value": val}
    best = None  # (gain, order, fi, thr, li, rix)
    for order, (fi, thr) in enumerate(grid):
        m = X[idx, fi] <= thr
        li, rix = idx[m], idx[~m]
        if len(li) < MIN_LEAF or len(rix) < MIN_LEAF:
            continue
        vl, _ = node_value(S, R, li); vr, _ = node_value(S, R, rix)
        gain = vl + vr - val
        if gain > 1e-9 and (best is None or gain > best[0] + 1e-9):
            best = (gain, order, fi, thr, li, rix)
    if best is None:
        return {"leaf": True, "action": act, "n": len(idx), "value": val}
    _, _, fi, thr, li, rix = best
    return {"leaf": False, "fi": fi, "thr": thr,
            "left": fit(X, S, R, li, grid, depth + 1),
            "right": fit(X, S, R, rix, grid, depth + 1)}

def apply_tree(tree, X, idx):
    """各レースに行動を割り当てる。returns action array."""
    a = np.zeros(len(X), dtype=int)
    def rec(node, ids):
        if node["leaf"]:
            a[ids] = node["action"]; return
        m = X[ids, node["fi"]] <= node["thr"]
        rec(node["left"], ids[m]); rec(node["right"], ids[~m])
    rec(tree, idx)
    return a

def evaluate(tree, X, S, R, idx):
    a = apply_tree(tree, X, idx)
    st = S[idx, a[idx]].sum(); ret = R[idx, a[idx]].sum()
    nbet = int((a[idx] != 0).sum())
    by = {}
    for act in range(1, 7):
        sel = idx[a[idx] == act]
        if len(sel):
            by[ACTIONS[act]] = dict(n=len(sel), stake=float(S[sel, act].sum()),
                                    ret=float(R[sel, act].sum()))
    return dict(n=len(idx), n_bet=nbet, stake=float(st), ret=float(ret),
                roi=float(ret / st) if st > 0 else None,
                profit=float(ret - st), by=by)

def print_tree(tree, lines, cond="ROOT"):
    if tree["leaf"]:
        lines.append((cond, tree["action"], tree["n"], tree["value"]))
        return
    name = FEATS[tree["fi"]]; thr = tree["thr"]
    print_tree(tree["left"], lines, f"{cond} & {name}<={thr:.4g}")
    print_tree(tree["right"], lines, f"{cond} & {name}>{thr:.4g}")

def main():
    rid, month, X, S, R = load()
    month = np.array(month)
    mine = np.where(month <= "202602")[0]
    val = np.where((month >= "202603") & (month <= "202605"))[0]
    conf = np.where((month >= "202606") & (month <= "202608"))[0]
    print(f"MINE={len(mine)} VAL={len(val)} CONF={len(conf)}")
    grid = build_grid(X[mine])
    tree = fit(X, S, R, mine, grid)
    lines = []
    print_tree(tree, lines)
    print("\n== 学習された方策の木 (MINE) ==")
    for cond, act, n, v in lines:
        # leaf MINE roi of chosen action
        print(f"IF {cond} -> {ACTIONS[act]}  [n={n}, MINE利益={v:+.0f}円]")
    for name, idx in (("MINE", mine), ("VAL", val), ("CONF", conf)):
        ev = evaluate(tree, X, S, R, idx)
        print(f"\n== {name} == {ev}")
    # null control
    print("\n== NULL (100 shuffles of MINE labels) ==")
    rng_master = np.random.default_rng(20260820)
    null_stats = []
    for seed in range(100):
        rng = np.random.default_rng(seed)
        perm = rng.permutation(len(mine))
        S2, R2 = S.copy(), R.copy()
        S2[mine] = S[mine[perm]]; R2[mine] = R[mine[perm]]
        t2 = fit(X, S2, R2, mine, grid)
        # evaluate fake policy on REAL val/conf outcomes
        ev_v = evaluate(t2, X, S, R, val)
        ev_c = evaluate(t2, X, S, R, conf)
        null_stats.append((ev_v["roi"], ev_v["profit"], ev_v["n_bet"],
                           ev_c["roi"], ev_c["profit"], ev_c["n_bet"]))
        if seed % 20 == 0:
            print(f"  seed {seed}: VAL roi={ev_v['roi']} nbet={ev_v['n_bet']}")
    np.save("policy_null_stats.npy", np.array(null_stats, dtype=object), allow_pickle=True)
    vroi = [s[0] for s in null_stats if s[0] is not None]
    vprof = [s[1] for s in null_stats]
    croi = [s[3] for s in null_stats if s[3] is not None]
    cprof = [s[4] for s in null_stats]
    def pct(a, q): return float(np.percentile(a, q)) if len(a) else None
    print(f"VAL null ROI: n_defined={len(vroi)} p5={pct(vroi,5)} p50={pct(vroi,50)} p95={pct(vroi,95)}")
    print(f"VAL null profit: p5={pct(vprof,5)} p50={pct(vprof,50)} p95={pct(vprof,95)}")
    print(f"CONF null ROI: n_defined={len(croi)} p5={pct(croi,5)} p50={pct(croi,50)} p95={pct(croi,95)}")
    print(f"CONF null profit: p5={pct(cprof,5)} p50={pct(cprof,50)} p95={pct(cprof,95)}")

if __name__ == "__main__":
    main()
