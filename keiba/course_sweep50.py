# -*- coding: utf-8 -*-
"""全コース × 50パターンの配点総当たり（2026-08-21）。

ユーザー指示:
  「過去の統計を全て列挙 / コースや距離ごとに変える / 1番最適な配点考える /
   追加する項目は追加する / 全コース50パターンは試す」

設計:
  成分は22次元 = Ver.99.27の11成分 + 展開乗数 + 通過順10特徴（未使用6本を含む＝追加項目）。
  各コースで50パターンの配点を試し、MINEで最良を選び、VALIDATE/CONFIRM に1回だけ通す。
  規律: 選択はMINEのみ。50パターン×コース数の多重比較を必ず申告する。
"""
import ast, collections, itertools, json, math, os, pickle, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v99w_fit as V
import v99w2_fit as V2

CORNER10 = ['pos_gain', 'pos_var', 'wide4c', 'pace_lv', 'pace_gap',
            'fwd_fin', 'mgn_abs', 'spd_res', 'grind', 'unlucky']
COMPS12 = V.COMPS                      # 11成分 + kankai
NAMES = list(COMPS12) + CORNER10       # 22次元
H = 20


def load():
    races = V.load_races()
    z = np.load("corner_ds.npz", allow_pickle=False)
    A, rid_arr, feats = z["A"], z["rid"], [str(x) for x in z["feats"]]
    idx = [feats.index(f) for f in CORNER10]
    F = len(feats)
    ridx = A[:, F + 4].astype(int)
    num = A[:, F + 5].astype(int)
    mp = {}
    for i in range(len(A)):
        mp[(str(rid_arr[ridx[i]]), int(num[i]))] = A[i, idx]
    ex = json.load(open('/tmp/extra.json'))
    out = []
    for r in races:
        n = len(r["nums"])
        C = np.zeros((n, 10))
        for i, nm in enumerate(r["nums"]):
            v = mp.get((r["rid"], nm))
            if v is not None:
                C[i] = v
        r["Z22"] = np.hstack([r["Z"], C])
        e = ex.get(r["rid"], {})
        r["course"] = f"{e.get('venue')}{r['surface']}{r['distance']}"
        out.append(r)
    return out


def pack(rs, key="Z22"):
    K = rs[0][key].shape[1]
    R = len(rs)
    Xp = np.zeros((R, H, K)); mask = np.zeros((R, H), bool); T = np.zeros((R, 3), int)
    for i, r in enumerate(rs):
        n = len(r["nums"]); Xp[i, :n] = r[key]; mask[i, :n] = True; T[i] = r["top3"]
    return Xp, mask, T


def ll_grad(w, P):
    Xp, mask, T = P
    s = np.where(mask, Xp @ w, -1e9).copy()
    alive = mask.copy(); ll = 0.0; g = np.zeros(len(w)); R = len(s); idx = np.arange(R)
    for k in range(3):
        m = s.max(1, keepdims=True); e = np.exp(s - m) * alive
        Z = e.sum(1, keepdims=True); p = e / Z; pick = T[:, k]
        ll += (s[idx, pick] - m[:, 0] - np.log(Z[:, 0])).sum()
        g += (Xp[idx, pick] - np.einsum('rh,rhf->rf', p, Xp)).sum(0)
        alive[idx, pick] = False; s[idx, pick] = -1e9
    return ll / R, g / R


def fit(P, w0=None, ridge=0.0, anchor=None, iters=250, lr=0.3):
    K = P[0].shape[2]
    w = np.zeros(K) if w0 is None else w0.copy()
    a = np.zeros(K) if anchor is None else anchor
    m = np.zeros(K); v = np.zeros(K)
    for t in range(1, iters + 1):
        _, g = ll_grad(w, P); g -= ridge * (w - a)
        m = .9 * m + .1 * g; v = .99 * v + .01 * g * g
        w += lr * (m / (1 - .9 ** t)) / (np.sqrt(v / (1 - .99 ** t)) + 1e-8)
    return w


def rank_of(r, w):
    s = r["Z22"] @ w
    o = sorted(range(len(s)), key=lambda i: (-s[i], -r["wavg"][i], r["nums"][i]))
    return [r["nums"][i] for i in o]


def mktrank(r):
    return [int(n) for n, _ in sorted(r["odds"].items(), key=lambda kv: kv[1])]


def evaluate(rs, w, plan):
    """plan: 'fuku1'/'fuku2'/'wide12'/'trio3'。(n, hit%, roi%, 損益円)"""
    c = ret = hit = 0
    for r in rs:
        rk = rank_of(r, w)
        pay = r["payout"]
        if plan == "fuku1":
            f = {int(k): v for k, v in (pay.get("複勝") or {}).items()}
            c += 100; v = f.get(rk[0])
            if v: ret += v; hit += 1
        elif plan == "fuku2":
            f = {int(k): v for k, v in (pay.get("複勝") or {}).items()}
            c += 200; got = 0
            for h in rk[:2]:
                v = f.get(h)
                if v: ret += v; got = 1
            hit += got
        elif plan == "wide12":
            k = "%d-%d" % tuple(sorted(rk[:2]))
            c += 100; v = (pay.get("ワイド") or {}).get(k)
            if v: ret += v; hit += 1
        elif plan == "trio3":
            k = "-".join(str(x) for x in sorted(rk[:3]))
            c += 100; v = (pay.get("三連複") or {}).get(k)
            if v: ret += v; hit += 1
    n = len(rs)
    return dict(n=n, hit=hit / n * 100 if n else 0, roi=ret / c * 100 if c else 0, pl=ret - c)



# ── 50パターンの定義 ──────────────────────────────────
ALL_GROUP_W = None   # 6群の配点辞書（main で設定）


def build_patterns(base_global, base_group, course_races):
    """コースごとに試す50パターンの (名前, 重みベクトル) を返す。
       - 1〜3   : 汎用（全体22 / 群別22 / Ver.99.27素の合算）
       - 4〜13  : そのコースだけで学習（縮小λを10段階）
       - 14〜35 : 群別配点から成分を1本ずつ強調（22成分 ×1.5倍）
       - 36〜45 : 同じく1本ずつ抑制（×0.5倍）
       - 46〜50 : 通過順特徴の使い方を変える（4本のみ/10本全部/なし/2倍/半分）
    """
    K = len(base_global)
    pats = []
    pats.append(("汎用22(全体1本)", base_global.copy()))
    pats.append(("群別22(芝ダ×距離帯)", base_group.copy()))
    raw = np.zeros(K); raw[:11] = 1.0                     # Ver.99.27 素の合算
    pats.append(("Ver.99.27素", raw))
    P = pack(course_races)
    for lam in [30.0, 10.0, 3.0, 1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.0]:
        w = fit(P, w0=base_group, ridge=lam, anchor=base_group, iters=200)
        pats.append((f"コース学習 λ={lam}", w))
    # 成分の強調/抑制は「効きそうな12成分」に絞って ×1.5 と ×0.5（計24）＝合計50
    KEY = ["tsi", "lts", "fsi", "dsi", "nsi", "csi", "tas", "was",
           "spd_res", "mgn_abs", "grind", "fwd_fin"]
    for nm in KEY:
        i = NAMES.index(nm)
        w = base_group.copy(); w[i] *= 1.5
        pats.append((f"{nm}×1.5", w))
    for nm in KEY:
        i = NAMES.index(nm)
        w = base_group.copy(); w[i] *= 0.5
        pats.append((f"{nm}×0.5", w))
    # 他群の配点を借りる（6本）— コース固有性が本当にあるなら他群は劣るはず
    for gk, gw in (ALL_GROUP_W or {}).items():
        pats.append((f"他群の配点={gk[0]}{gk[1]}", gw.copy()))
    # 全体1本をアンカーにしたコース学習（2本）
    Pc = pack(course_races)
    for lam in [1.0, 0.1]:
        pats.append((f"コース学習(全体アンカー) λ={lam}",
                     fit(Pc, w0=base_global, ridge=lam, anchor=base_global, iters=200)))
    # ヌル対照（2本）— 無作為な配点。これに負ける案は意味がない
    rs_ = np.random.RandomState(0)
    for j in range(2):
        pats.append((f"ヌル対照{j+1}(無作為配点)", rs_.randn(K) * 0.1))
    # 通過順の使い方（3本）
    w = base_group.copy(); w[12:] = 0.0
    pats.append(("通過順なし(12成分のみ)", w))
    w = base_group.copy(); w[12:] *= 2.0
    pats.append(("通過順×2", w))
    w = base_group.copy(); w[12:] *= 0.5
    pats.append(("通過順×0.5", w))
    assert len(pats) == 50, f"パターン数が50でない: {len(pats)}"
    return pats


# ── main ────────────────────────────────────────────
def main():
    global ALL_GROUP_W
    races = load()
    seg = lambda lo, hi: [r for r in races if lo <= r["month"] <= hi]
    MINE, VAL, CONF = seg('000000', '202602'), seg('202603', '202605'), seg('202606', '202608')
    print(f"データ: 全{len(races)}R (MINE {len(MINE)} / VAL {len(VAL)} / CONF {len(CONF)})", file=sys.stderr)

    # 土台: 22次元の全体1本と6群別（MINEのみで学習）
    wg22 = fit(pack(MINE), iters=300)
    byg = collections.defaultdict(list)
    for r in MINE:
        byg[V.axis_key(r, "sd")].append(r)
    ws22 = {k: fit(pack(v), w0=wg22, ridge=0.1, anchor=wg22, iters=250)
            for k, v in byg.items()}
    ALL_GROUP_W = ws22
    print("土台の学習おわり（全体1本 + 6群）", file=sys.stderr)

    byc = {'M': collections.defaultdict(list), 'V': collections.defaultdict(list),
           'C': collections.defaultdict(list)}
    for w, S in (('M', MINE), ('V', VAL), ('C', CONF)):
        for r in S:
            byc[w][r["course"]].append(r)

    courses = [c for c, v in byc['M'].items() if len(v) >= 40]
    print(f"対象コース: {len(courses)}（MINE 40R以上）", file=sys.stderr)

    PLANS = ["fuku1", "fuku2", "wide12", "trio3"]
    out = {}
    for ci, c in enumerate(sorted(courses), 1):
        mine_r = byc['M'][c]
        pats = build_patterns(wg22, ws22[V.axis_key(mine_r[0], "sd")], mine_r)
        rec = {"n_mine": len(mine_r), "n_val": len(byc['V'].get(c, [])),
               "n_conf": len(byc['C'].get(c, [])), "group": "".join(V.axis_key(mine_r[0], "sd")),
               "patterns": len(pats), "best": {}}
        for plan in PLANS:
            scored = [(evaluate(mine_r, w, plan), nm, w) for nm, w in pats]
            scored.sort(key=lambda x: -x[0]["roi"])
            bm, bnm, bw = scored[0]
            bv = evaluate(byc['V'][c], bw, plan) if byc['V'].get(c) else None
            bc = evaluate(byc['C'][c], bw, plan) if byc['C'].get(c) else None
            rec["best"][plan] = dict(name=bnm, mine=bm, val=bv, conf=bc,
                                     mine_median_roi=float(np.median([s[0]["roi"] for s in scored])),
                                     null_best=max(s[0]["roi"] for s in scored
                                                   if s[1].startswith("ヌル")))
        out[c] = rec
        print(f"  [{ci}/{len(courses)}] {c} done", file=sys.stderr)
    json.dump(out, open("course_sweep50_result.json", "w"), ensure_ascii=False, indent=1)
    print("saved course_sweep50_result.json", file=sys.stderr)


if __name__ == "__main__":
    main()
