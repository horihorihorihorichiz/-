#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crosspool.py — プール間乖離(クロスプール裁定)の検証。

事前登録: CROSSPOOL_PROTOCOL.md (実行前に確定・変更禁止)
報告:     CROSSPOOL_REPORT.md

モデルを一切使わない。単勝プールの価格だけから 馬連/ワイド/三連複 の理論確率を作り、
実際の各プールの価格と比べて乖離を測り、乖離を突く戦略のROIを3分割で検証する。

使い方:
  python3 crosspool.py --build      # キャッシュ作成 (hist/ + hist_odds/ を1回だけ読む)
  python3 crosspool.py --run        # 本番 (λ推定→較正→乖離→戦略→検定→診断)
  python3 crosspool.py --run --perm 1000
"""
import os, sys, json, glob, pickle, math, argparse, time
from itertools import combinations, permutations
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, 'hist')
ODDS = os.path.join(HERE, 'hist_odds')
CACHE = os.path.join(HERE, 'crosspool_cache.pkl')

# ---- 事前登録された期間分割 (変更禁止) ----
MINE = (202409, 202602)
VALID = (202603, 202605)
CONF = (202606, 202608)
SPLITS = [('MINE', MINE), ('VALIDATE', VALID), ('CONFIRM', CONF)]
EV_THRESHOLDS = [1.10, 1.20, 1.30]
POOLS = ['umaren', 'wide', 'sanrenpuku']
NSUM = {'umaren': 1.0, 'wide': 3.0, 'sanrenpuku': 1.0}   # レース内の理論確率合計
TAKEOUT = {'umaren': 0.225, 'wide': 0.225, 'sanrenpuku': 0.25}

_comb_cache = {}
def combs(n, k):
    key = (n, k)
    if key not in _comb_cache:
        _comb_cache[key] = np.array(list(combinations(range(n), k)), dtype=np.int32)
    return _comb_cache[key]

def pair_index(n, i, j):
    """i<j の組合せ番号 (itertools.combinations(range(n),2) と同じ並び)"""
    return (i * (2 * n - i - 1)) // 2 + (j - i - 1)


# ------------------------------------------------------------------ build
def build_cache():
    files = sorted(glob.glob(os.path.join(HIST, '*.json')))
    races = []
    t0 = time.time()
    for idx, f in enumerate(files):
        rid = os.path.basename(f)[:-5]
        of = os.path.join(ODDS, rid + '.json')
        if not os.path.exists(of):
            continue
        try:
            h = json.load(open(f))
            o = json.load(open(of))
        except Exception:
            continue
        date = str(h.get('date') or '')
        if len(date) < 6:
            continue
        ym = int(date[:6])
        tan = o.get('tan') or {}
        if len(tan) < 6:
            continue
        nums, tv = [], []
        for k, v in tan.items():
            try:
                v = float(v)
            except Exception:
                continue
            if v and v > 0:
                nums.append(int(k)); tv.append(v)
        if len(nums) < 6:
            continue
        order = np.argsort(nums)
        nums = [nums[i] for i in order]; tv = [tv[i] for i in order]
        n = len(nums)
        pos = {m: i for i, m in enumerate(nums)}
        # 着順 (1-3着) を index に
        res = (h.get('result') or {}).get('order') or []
        fin = []
        for e in res:
            try:
                r = int(str(e.get('rank')).strip())
            except Exception:
                continue
            if r in (1, 2, 3):
                m = e.get('num')
                if m in pos:
                    fin.append((r, pos[m]))
        fin.sort()
        if [r for r, _ in fin] != [1, 2, 3]:
            continue
        fin = np.array([i for _, i in fin], dtype=np.int32)

        p = 1.0 / np.array(tv, dtype=np.float64)
        p /= p.sum()

        pr = combs(n, 2); tr = combs(n, 3)
        def pool_arr(key, idxarr, sep='-'):
            d = o.get(key) or {}
            if not d:
                return None
            out = np.full(len(idxarr), np.nan, dtype=np.float32)
            for r_, row in enumerate(idxarr):
                k = sep.join(str(nums[c]) for c in row)
                v = d.get(k)
                if v is None:
                    continue
                try:
                    v = float(v)
                except Exception:
                    continue
                if v > 0:
                    out[r_] = v
            return out
        um = pool_arr('umaren', pr)
        wd = pool_arr('wide', pr)
        sp = pool_arr('sanrenpuku', tr)
        races.append(dict(rid=rid, ym=ym, n=n, p=p.astype(np.float64), fin=fin,
                          umaren=um, wide=wd, sanrenpuku=sp))
        if idx % 1000 == 0:
            print('  build %d/%d  %.0fs' % (idx, len(files), time.time() - t0), flush=True)
    with open(CACHE, 'wb') as fh:
        pickle.dump(races, fh, protocol=4)
    print('cached %d races -> %s (%.0fs)' % (len(races), CACHE, time.time() - t0))
    return races


def load_cache():
    if not os.path.exists(CACHE):
        return build_cache()
    with open(CACHE, 'rb') as fh:
        return pickle.load(fh)


# ------------------------------------------------------- 理論確率 (Harville/Stern)
def triple_probs(p, l2, l3, tr):
    """P(a,b,c が3着以内・順不同) を tr の並びで返す。"""
    f2 = p ** l2; f3 = p ** l3
    F2 = f2.sum(); F3 = f3.sum()
    A, B, C = tr[:, 0], tr[:, 1], tr[:, 2]
    q = np.zeros(len(tr), dtype=np.float64)
    for x, y, z in permutations((A, B, C)):
        q += p[x] * (f2[y] / (F2 - f2[x])) * (f3[z] / (F3 - f3[x] - f3[y]))
    return q


def umaren_probs(p, l2, pr):
    f2 = p ** l2; F2 = f2.sum()
    a, b = pr[:, 0], pr[:, 1]
    return p[a] * f2[b] / (F2 - f2[a]) + p[b] * f2[a] / (F2 - f2[b])


def wide_from_triples(n, tr, qtri):
    """3着以内ペア確率 = そのペアを含む三連複確率の和"""
    npair = n * (n - 1) // 2
    out = np.zeros(npair, dtype=np.float64)
    A, B, C = tr[:, 0].astype(np.int64), tr[:, 1].astype(np.int64), tr[:, 2].astype(np.int64)
    for i, j in ((A, B), (A, C), (B, C)):
        np.add.at(out, pair_index(n, i, j), qtri)
    return out


def fit_lambda(races, mine_mask):
    """λ2,λ3 を MINE期の実着順のみで最尤推定 (グリッド探索)"""
    grid = np.arange(0.30, 1.601, 0.02)
    sel = [r for r, m in zip(races, mine_mask) if m]
    best2, bl2 = -1e18, 1.0
    for l in grid:
        s = 0.0
        for r in sel:
            p = r['p']; f = p ** l
            i0, i1 = r['fin'][0], r['fin'][1]
            s += math.log(max(f[i1] / (f.sum() - f[i0]), 1e-300))
        if s > best2:
            best2, bl2 = s, l
    best3, bl3 = -1e18, 1.0
    for l in grid:
        s = 0.0
        for r in sel:
            p = r['p']; f = p ** l
            i0, i1, i2 = r['fin'][0], r['fin'][1], r['fin'][2]
            s += math.log(max(f[i2] / (f.sum() - f[i0] - f[i1]), 1e-300))
        if s > best3:
            best3, bl3 = s, l
    return float(bl2), float(bl3), float(best2), float(best3)


# ------------------------------------------------------------------ 行の作成
def build_rows(races, l2, l3):
    """券種ごとに、全レース・全組合せの行を作る。"""
    cols = {k: dict(race=[], ym=[], field=[], q=[], qh=[], odds=[], hit=[], mkt=[], wmin=[])
            for k in POOLS}
    for ri, r in enumerate(races):
        n = r['n']; p = r['p']; pr = combs(n, 2); tr = combs(n, 3)
        fin = r['fin']; top3 = set(int(x) for x in fin)
        qtri = triple_probs(p, l2, l3, tr)
        qtri_h = triple_probs(p, 1.0, 1.0, tr)
        qwide = wide_from_triples(n, tr, qtri)
        qwide_h = wide_from_triples(n, tr, qtri_h)
        qum = umaren_probs(p, l2, pr)
        qum_h = umaren_probs(p, 1.0, pr)

        # ワイドの市場乖離 (診断2で三連複に流用)
        wmin_pair = None
        wd = r['wide']
        if wd is not None:
            fin_ = np.isfinite(wd)
            if fin_.sum() >= 3:
                inv = np.zeros(len(wd)); inv[fin_] = 1.0 / wd[fin_]
                s = inv.sum()
                m = np.full(len(wd), np.nan)
                m[fin_] = inv[fin_] / s * NSUM['wide']
                with np.errstate(invalid='ignore', divide='ignore'):
                    wmin_pair = qwide / m     # D_wide (ペア単位)

        pack = [('umaren', pr, qum, qum_h, r['umaren'], 2),
                ('wide', pr, qwide, qwide_h, r['wide'], 2),
                ('sanrenpuku', tr, qtri, qtri_h, r['sanrenpuku'], 3)]
        for key, idxarr, q, qh, od, k in pack:
            if od is None:
                continue
            ok = np.isfinite(od)
            if ok.sum() < 3:
                continue
            inv = np.zeros(len(od)); inv[ok] = 1.0 / od[ok]
            s = inv.sum()
            if s <= 0:
                continue
            mkt = np.full(len(od), np.nan); mkt[ok] = inv[ok] / s * NSUM[key]
            if k == 2:
                a, b = idxarr[:, 0], idxarr[:, 1]
                if key == 'umaren':
                    hit = ((a == fin[0]) & (b == fin[1])) | ((a == fin[1]) & (b == fin[0]))
                else:
                    hit = np.isin(a, fin) & np.isin(b, fin)
            else:
                hit = np.isin(idxarr[:, 0], fin) & np.isin(idxarr[:, 1], fin) & np.isin(idxarr[:, 2], fin)
            c = cols[key]
            c['race'].append(np.full(int(ok.sum()), ri, dtype=np.int32))
            c['ym'].append(np.full(int(ok.sum()), r['ym'], dtype=np.int32))
            c['field'].append(np.full(int(ok.sum()), n, dtype=np.int8))
            c['q'].append(q[ok].astype(np.float64))
            c['qh'].append(qh[ok].astype(np.float64))
            c['odds'].append(od[ok].astype(np.float64))
            c['hit'].append(hit[ok].astype(np.int8))
            c['mkt'].append(mkt[ok].astype(np.float64))
            if key == 'sanrenpuku':
                if wmin_pair is None:
                    c['wmin'].append(np.full(int(ok.sum()), np.nan))
                else:
                    A = tr[:, 0].astype(np.int64); B = tr[:, 1].astype(np.int64); C = tr[:, 2].astype(np.int64)
                    d1 = wmin_pair[pair_index(n, A, B)]
                    d2 = wmin_pair[pair_index(n, A, C)]
                    d3 = wmin_pair[pair_index(n, B, C)]
                    c['wmin'].append(np.nanmin(np.vstack([d1, d2, d3]), axis=0)[ok])
            elif key == 'wide':
                c['wmin'].append(np.full(int(ok.sum()), np.nan))
            else:
                # 馬連行にはワイド乖離(同じペア)を持たせる → 診断1
                if wmin_pair is None:
                    c['wmin'].append(np.full(int(ok.sum()), np.nan))
                else:
                    c['wmin'].append(wmin_pair[ok])
    out = {}
    for key in POOLS:
        c = cols[key]
        if not c['race']:
            continue
        out[key] = {k: np.concatenate(v) for k, v in c.items()}
    return out


# ------------------------------------------------------------------ 較正
def logit(x):
    x = np.clip(x, 1e-9, 1 - 1e-9)
    return np.log(x / (1 - x))

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))

def design(q, field):
    lq = logit(q)
    return np.column_stack([np.ones_like(lq), lq, lq * lq, np.log(field.astype(np.float64))])

def fit_logit(X, y, iters=25):
    b = np.zeros(X.shape[1])
    b[1] = 1.0
    for _ in range(iters):
        z = X @ b
        mu = sigmoid(z)
        W = np.clip(mu * (1 - mu), 1e-9, None)
        g = X.T @ (y - mu)
        H = X.T @ (X * W[:, None])
        H += np.eye(X.shape[1]) * 1e-8
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        b = b + step
        if np.max(np.abs(step)) < 1e-9:
            break
    return b


def renorm_per_race(q, race, target):
    """レース内の理論確率合計を target に合わせる"""
    s = np.bincount(race, weights=q)
    cnt = np.bincount(race)
    scale = np.where(s > 0, target / np.maximum(s, 1e-12), 1.0)
    return q * scale[race]


# ------------------------------------------------------------------ 評価
def split_mask(ym, rng):
    return (ym >= rng[0]) & (ym <= rng[1])

def roi(hit, odds, sel):
    n = int(sel.sum())
    if n == 0:
        return 0, 0.0, 0
    ret = float((hit[sel] * odds[sel]).sum()) * 100.0
    stake = n * 100.0
    return n, ret / stake * 100.0, int(hit[sel].sum())


def perm_test(D, race, odds, hit, thr, reps, rng):
    """レース×オッズ十分位バケット内で乖離Dを入れ替え、同じ閾値で選び直す。"""
    # 全体のオッズ十分位でバケット化
    qs = np.quantile(odds, np.linspace(0, 1, 11)[1:-1])
    bucket = np.searchsorted(qs, odds)
    g = race.astype(np.int64) * 16 + bucket
    order0 = np.argsort(g, kind='stable')
    gs = g[order0]
    Ds = D[order0]
    obs = np.array([roi(hit, odds, D >= t)[1] for t in thr])
    cnt = np.zeros(len(thr))
    hits_ = hit[order0].astype(np.float64)
    odds_ = odds[order0]
    for _ in range(reps):
        rr = rng.random(len(gs))
        idx = np.lexsort((rr, gs))
        Dp = Ds[idx]
        for i, t in enumerate(thr):
            sel = Dp >= t
            n = int(sel.sum())
            r = 0.0 if n == 0 else float((hits_[sel] * odds_[sel]).sum()) / n * 100.0
            if r >= obs[i]:
                cnt[i] += 1
    return (cnt + 1) / (reps + 1)


def fmt_row(name, n, r, h):
    return '| %s | %d | %.1f%% | %d |' % (name, n, r, h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--perm', type=int, default=1000)
    a = ap.parse_args()
    if a.build:
        build_cache(); return
    races = load_cache()
    ym_all = np.array([r['ym'] for r in races])
    # 202409 より前は一切使わない (事前登録)
    keep = ym_all >= MINE[0]
    races = [r for r, k in zip(races, keep) if k]
    print('races in scope: %d (%d-%d)' % (len(races), min(r['ym'] for r in races), max(r['ym'] for r in races)))
    mine_mask = [MINE[0] <= r['ym'] <= MINE[1] for r in races]
    print('MINE races: %d / VALIDATE: %d / CONFIRM: %d' % (
        sum(mine_mask),
        sum(VALID[0] <= r['ym'] <= VALID[1] for r in races),
        sum(CONF[0] <= r['ym'] <= CONF[1] for r in races)))

    t0 = time.time()
    l2, l3, ll2, ll3 = fit_lambda(races, mine_mask)
    ll2h = ll3h = None
    # Harville(λ=1) の対数尤度も出す
    sel = [r for r, m in zip(races, mine_mask) if m]
    s2 = s3 = 0.0
    for r in sel:
        p = r['p']; i0, i1, i2 = r['fin']
        s2 += math.log(max(p[i1] / (1 - p[i0]), 1e-300))
        s3 += math.log(max(p[i2] / (1 - p[i0] - p[i1]), 1e-300))
    ll2h, ll3h = s2, s3
    print('lambda2=%.2f (LL %.1f vs Harville %.1f)  lambda3=%.2f (LL %.1f vs %.1f)  [%.0fs]'
          % (l2, ll2, ll2h, l3, ll3, ll3h, time.time() - t0))

    rows = build_rows(races, l2, l3)
    print('rows built: ' + ', '.join('%s=%d' % (k, len(v['q'])) for k, v in rows.items())
          + '  [%.0fs]' % (time.time() - t0))

    report = []
    R = report.append
    diag = {}
    results = {}

    for key in POOLS:
        d = rows[key]
        m_mine = split_mask(d['ym'], MINE)
        X = design(d['q'], d['field'])
        b = fit_logit(X[m_mine], d['hit'][m_mine].astype(np.float64))
        qcal = sigmoid(X @ b)
        qcal = renorm_per_race(qcal, d['race'], NSUM[key])
        d['qcal'] = qcal
        d['D'] = qcal / d['mkt']
        d['EV'] = qcal * d['odds']
        d['coef'] = b
        print('%s: calib coef = %s' % (key, np.round(b, 4).tolist()))

    # ---------------- 乖離の分布 ----------------
    dist = {}
    for key in POOLS:
        d = rows[key]
        row = {}
        for nm, rng in SPLITS:
            m = split_mask(d['ym'], rng)
            D = d['D'][m]
            D = D[np.isfinite(D)]
            row[nm] = dict(n=len(D), q=[float(np.quantile(D, x)) for x in (0.05, 0.25, 0.5, 0.75, 0.95)],
                           gt11=float((D >= 1.1).mean()), gt13=float((D >= 1.3).mean()))
        dist[key] = row

    # ---------------- 較正チェック ----------------
    calib = {}
    for key in POOLS:
        d = rows[key]
        c = {}
        for nm, rng in SPLITS:
            m = split_mask(d['ym'], rng)
            q = d['qcal'][m]; h = d['hit'][m]
            ed = np.quantile(q, np.linspace(0, 1, 11))
            bins = np.clip(np.searchsorted(ed[1:-1], q), 0, 9)
            rowl = []
            for i in range(10):
                s = bins == i
                if s.sum() == 0:
                    continue
                rowl.append((float(q[s].mean()), float(h[s].mean()), int(s.sum())))
            c[nm] = rowl
        calib[key] = c

    # ---------------- 戦略A ----------------
    strat = {}
    rng_ = np.random.default_rng(20260818)
    for key in POOLS:
        d = rows[key]
        ok = np.isfinite(d['D']) & np.isfinite(d['EV'])
        res = {}
        for thr in EV_THRESHOLDS:
            res[thr] = {}
            for nm, rr in SPLITS:
                m = split_mask(d['ym'], rr) & ok
                sel = m & (d['EV'] >= thr)
                n, r, h = roi(d['hit'], d['odds'], sel)
                res[thr][nm] = (n, r, h)
        # 並べ替え検定 (MINE のみ)
        m = split_mask(d['ym'], MINE) & ok
        t1 = time.time()
        pv = perm_test(d['EV'][m], d['race'][m], d['odds'][m], d['hit'][m].astype(np.float64),
                       EV_THRESHOLDS, a.perm, rng_)
        print('%s perm test done %.0fs  p=%s' % (key, time.time() - t1, np.round(pv, 4).tolist()))
        for i, thr in enumerate(EV_THRESHOLDS):
            res[thr]['p'] = float(pv[i])
        strat[key] = res

    # ---------------- 戦略B (参考) ----------------
    stratB = {}
    for key in POOLS:
        d = rows[key]
        ok = np.isfinite(d['EV'])
        b = {}
        for nm, rr in SPLITS:
            m = split_mask(d['ym'], rr) & ok
            n_all, r_all, _ = roi(d['hit'], d['odds'], m)
            cut = np.quantile(d['EV'][m], 0.20)
            sel = m & (d['EV'] > cut)
            n2, r2, _ = roi(d['hit'], d['odds'], sel)
            b[nm] = (n_all, r_all, n2, r2)
        stratB[key] = b

    # ---------------- 診断1: プール間一貫性 ----------------
    d = rows['umaren']
    m = split_mask(d['ym'], MINE) & np.isfinite(d['D']) & np.isfinite(d['wmin'])
    lu = np.log(d['D'][m]); lw = np.log(d['wmin'][m])
    g = np.isfinite(lu) & np.isfinite(lw)
    lu, lw = lu[g], lw[g]
    corr = float(np.corrcoef(lu, lw)[0, 1])
    cov = float(np.cov(lu, lw)[0, 1])
    diag['d1'] = dict(n=int(len(lu)), corr=corr, cov=cov,
                      var_um=float(lu.var()), var_wd=float(lw.var()))

    # ---------------- 診断2: クロスチェック (三連複×ワイド一致) ----------------
    d = rows['sanrenpuku']
    ok = np.isfinite(d['EV']) & np.isfinite(d['wmin'])
    d2 = {}
    for thr in EV_THRESHOLDS:
        d2[thr] = {}
        for nm, rr in SPLITS:
            m = split_mask(d['ym'], rr) & ok & (d['EV'] >= thr) & (d['wmin'] > 1.0)
            n, r, h = roi(d['hit'], d['odds'], m)
            d2[thr][nm] = (n, r, h)
    diag['d2'] = d2

    # ---------------- 生Harvilleとの比較 (較正なし) ----------------
    raw = {}
    for key in POOLS:
        d = rows[key]
        rr_ = {}
        for tag, qq in (('harville', d['qh']), ('stern', d['q'])):
            qn = renorm_per_race(qq, d['race'], NSUM[key])
            ev = qn * d['odds']
            sub = {}
            for nm, rgn in SPLITS:
                m = split_mask(d['ym'], rgn) & np.isfinite(ev)
                sel = m & (ev >= 1.2)
                n, r, h = roi(d['hit'], d['odds'], sel)
                sub[nm] = (n, r, h)
            rr_[tag] = sub
        raw[key] = rr_

    out = dict(lam=(l2, l3, ll2, ll2h, ll3, ll3h), dist=dist, calib=calib,
               strat=strat, stratB=stratB, diag=diag, raw=raw,
               coef={k: rows[k]['coef'].tolist() for k in POOLS},
               nrows={k: int(len(rows[k]['q'])) for k in POOLS},
               nraces=dict(MINE=sum(mine_mask),
                           VALIDATE=sum(VALID[0] <= r['ym'] <= VALID[1] for r in races),
                           CONFIRM=sum(CONF[0] <= r['ym'] <= CONF[1] for r in races)),
               perm=a.perm)
    with open(os.path.join(HERE, 'crosspool_result.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float)[:6000])
    print('total %.0fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
