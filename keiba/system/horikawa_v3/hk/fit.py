# -*- coding: utf-8 -*-
"""学習。上位3着までの順位そのものを目的にした順位ロジット（Plackett-Luce）と、
   経験ベイズによる階層縮小。縮小定数は掃引ではなく式で決まる（規律R3に触れない）。"""
import numpy as np


def _prepare(DS):
    """頭数ごとにまとめて3次元配列にする。まとめて計算すると桁違いに速い。"""
    by = {}
    for d in DS:
        by.setdefault(len(d["Z"]), []).append(d)
    packs = []
    for n, group in by.items():
        Z = np.stack([np.asarray(d["Z"], np.float32) for d in group])      # (m,n,F)
        T = np.full((len(group), 3), -1, np.int32)
        for i, d in enumerate(group):
            for k, t in enumerate(d["top"][:3]):
                if t is not None:
                    T[i, k] = t
        packs.append((Z, T))
    return packs


def pl_fit(DS, w0=None, parent=None, ridge=0.002, iters=300, lr=0.25,
           mask=None, packs=None):
    """上位3着までの順位ロジット（Plackett-Luce）。
       DS: [{'Z': (n,F), 'top': [1着,2着,3着の添字]}]"""
    packs = packs if packs is not None else _prepare(DS)
    F = packs[0][0].shape[2]
    w = np.zeros(F) if w0 is None else np.array(w0, float)
    par = np.zeros(F) if parent is None else np.array(parent, float)
    msk = np.ones(F) if mask is None else np.asarray(mask, float)
    m = np.zeros(F); v = np.zeros(F); prev = -1e18
    NEG = -1e30
    for it in range(iters):
        g = np.zeros(F); ll = 0.0; cnt = 0
        for Z, T in packs:
            s = Z @ (w * msk)                       # (m,n)
            alive = np.ones(s.shape, bool)
            rows = np.arange(s.shape[0])
            for k in range(3):
                t = T[:, k]
                ok = t >= 0
                if not ok.any():
                    break
                ok &= alive[rows, np.maximum(t, 0)]
                if not ok.any():
                    break
                sm = np.where(alive, s, NEG)
                mx = sm.max(1, keepdims=True)
                e = np.where(alive, np.exp(sm - mx), 0.0)
                Zs = e.sum(1, keepdims=True)
                st = s[rows, np.maximum(t, 0)]
                ll += float(((st - mx[:, 0] - np.log(Zs[:, 0])) * ok).sum())
                cnt += int(ok.sum())
                p = e / Zs                          # (m,n)
                p[~ok] = 0.0
                g += Z[rows[ok], t[ok]].sum(0)
                g -= np.einsum("mn,mnf->f", p, Z)
                alive[rows[ok], t[ok]] = False
        if not cnt:
            break
        g = g / cnt - ridge * (w - par)
        g *= msk
        m = .9 * m + .1 * g
        v = .999 * v + .001 * g * g
        w += lr * (m / (1 - .9 ** (it + 1))) / (np.sqrt(v / (1 - .999 ** (it + 1))) + 1e-8)
        w *= msk
        if it > 40 and abs(ll / cnt - prev) < 1e-7:
            break
        prev = ll / cnt
    return w, prev


def eb_k(dev, ns):
    """E[d^2] = tau^2 + sigma^2/n を成分ごとに分離し、k = sigma^2/tau^2 を返す。
       tau^2 が負なら完全プーリング（k=無限大）＝親に固定する、が正しい扱い。"""
    dev = np.asarray(dev, float); ns = np.asarray(ns, float)
    x = 1.0 / ns
    K = np.full(dev.shape[1], np.inf)
    for j in range(dev.shape[1]):
        y = dev[:, j] ** 2
        N = len(y); sx = x.sum(); sy = y.sum()
        den = N * (x * x).sum() - sx * sx
        if abs(den) < 1e-12:
            continue
        sig = (N * (x * y).sum() - sx * sy) / den
        tau = (sy - sig * sx) / N
        if tau > 1e-12:
            K[j] = max(sig, 0.0) / tau
    return K


def fit_level(groups, parent_of, ridge=0.002, min_n=40, iters=180):
    """1階層ぶん。セルごとに独立に学習し、経験ベイズで親へ縮める。

    大事な点: セル別の学習に「親へ引っぱる罰則」を強くかけると、
    薄いセルほど親に近く見えてしまい、E[d^2]=tau^2+sigma^2/n の分解が壊れる。
    ここでは罰則を最小限にして、縮小は経験ベイズの λ だけに任せる。
    件数が min_n に満たないセルは、そもそも推定せず親そのものにする。"""
    raw, ns = {}, {}
    for c, D in groups.items():
        par = parent_of(c)
        ns[c] = len(D)
        raw[c] = np.array(par) if len(D) < min_n else \
            pl_fit(D, par, par, ridge, iters)[0]
    cs = [c for c in raw if ns[c] >= min_n]
    if not cs:
        return {c: np.array(parent_of(c)) for c in raw}, np.full(len(next(iter(raw.values()))), np.inf), ns, raw
    K = eb_k([raw[c] - np.array(parent_of(c)) for c in cs], [ns[c] for c in cs])
    out = {}
    for c in raw:
        p = np.array(parent_of(c))
        lam = (ns[c] / (ns[c] + K)) if ns[c] >= min_n else np.zeros_like(K)
        out[c] = p + lam * (raw[c] - p)
    return out, K, ns, raw


class Model:
    """全体1本 → 6群 → 場／クラス → コース単位、の4段。
       各段は経験ベイズで親へ縮むので、細かくしても壊れない。"""

    def __init__(self):
        self.G = None; self.L1 = {}; self.A = {}; self.B = {}; self.C = {}
        self.K = {}; self.n = {}; self.names = None

    def fit(self, TR, names, verbose=True):
        self.names = names
        grp = lambda f: _group(TR, f)
        self.G, _ = pl_fit(TR, iters=300)
        if verbose: print(f"  全体1本  ({len(TR)}R)")
        self.L1, self.K["L1"], self.n["L1"], _ = fit_level(
            grp(lambda d: d["k"]["L1"]), lambda c: self.G)
        if verbose: print(f"  6群      ({len(self.L1)}セル)")
        p1 = lambda c: self.L1.get(c, self.G)
        self.A, self.K["A"], self.n["A"], self.rawA = fit_level(
            grp(lambda d: d["k"]["A"]), lambda c: p1(c[2:]))
        self.B, self.K["B"], self.n["B"], self.rawB = fit_level(
            grp(lambda d: d["k"]["B"]), lambda c: p1(c.split("/")[0]))
        if verbose: print(f"  場{len(self.A)} / クラス{len(self.B)}")
        byC = grp(lambda d: d["k"]["C"])
        rep = {c: D[0]["k"] for c, D in byC.items()}
        self.C, self.K["C"], self.n["C"], _ = fit_level(byC, lambda c: self.mid(rep[c]))
        self.rep = rep
        if verbose: print(f"  コース単位({len(self.C)}セル)")
        return self

    def mid(self, k):
        l = self.L1.get(k["L1"], self.G)
        a = self.A.get(k["A"], l); b = self.B.get(k["B"], l)
        return a + b - l

    def w(self, k, level="C"):
        if level == "G": return self.G
        if level == "L1": return self.L1.get(k["L1"], self.G)
        if level == "mid": return self.mid(k)
        return self.C.get(k["C"], self.mid(k))


def _group(DS, f):
    g = {}
    for d in DS:
        g.setdefault(f(d), []).append(d)
    return g


def evaluate(DS, model, level="C", top_k=6):
    """未知期間での成績。1位が1着 / 1位が3着内 / 上位k頭で3着独占 / 対数尤度。"""
    n = h1 = i3 = cov = 0; ll = 0.0; c = 0; per = []
    for d in DS:
        w = model.w(d["k"], level) if hasattr(model, "w") else np.asarray(model)
        s = d["Z"] @ w
        order = np.argsort(-s)
        rank = np.empty(len(s), int); rank[order] = np.arange(len(s))
        n += 1
        p1 = d["ord"][order[0]]
        win = (p1 == 1); in3 = (p1 is not None and p1 <= 3)
        t3 = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
        cv = len(t3) == 3 and all(rank[i] < top_k for i in t3)
        h1 += win; i3 += in3; cov += cv
        per.append((win, in3, cv))
        mx = s.max(); Zs = np.exp(s - mx).sum()
        if 1 in d["ord"]:
            wi = d["ord"].index(1)
            ll += s[wi] - mx - np.log(Zs); c += 1
    return {"n": n, "1位が1着": round(h1 / n * 100, 2), "1位が3着内": round(i3 / n * 100, 2),
            f"上位{top_k}頭で3着独占": round(cov / n * 100, 2),
            "対数尤度": round(ll / c, 4)}, per


def mcnemar(a, b, i):
    bb = sum(1 for x, y in zip(a, b) if x[i] and not y[i])
    cc = sum(1 for x, y in zip(a, b) if not x[i] and y[i])
    d = (bb - cc) / len(a) * 100
    se = (bb + cc) ** .5 / len(a) * 100
    return {"差pt": round(d, 2), "SE": round(se, 2),
            "t": round(d / se, 2) if se else None, "不一致": bb + cc}


def choose_level(TR, names, inner_frac=0.25, top_k=6, verbose=True):
    """学習期間の内側でさらに時系列に切り、どの段階まで細かくすべきかを決める。
       未知期間には一切触れないので、規律R3の掃引には当たらない。"""
    TR = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TR) * (1 - inner_frac))
    inner_tr, inner_va = TR[:cut], TR[cut:]
    m = Model().fit(inner_tr, names, verbose=False)
    best, table = None, {}
    for lv, nm in [("G", "全体1本"), ("L1", "6群"), ("mid", "場+クラス"), ("C", "コース単位")]:
        r, _ = evaluate(inner_va, m, lv, top_k)
        score = r[f"上位{top_k}頭で3着独占"] + r["1位が1着"]
        table[nm] = dict(r, 合計=round(score, 2))
        if best is None or score > best[1]:
            best = (lv, score, nm)
    if verbose:
        print(f"  内側検証 {len(inner_va)}R で段階を選びます")
        for nm, r in table.items():
            print(f"    {nm:10s} 1位が1着={r['1位が1着']:5.2f} "
                  f"上位{top_k}頭で3着独占={r[f'上位{top_k}頭で3着独占']:5.2f} → 合計{r['合計']}")
        print(f"    採用: {best[2]}")
    return best[0], table
