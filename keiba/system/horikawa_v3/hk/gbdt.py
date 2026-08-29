# -*- coding: utf-8 -*-
"""木の学習器。条件（場・距離・クラス・馬場・頭数）を成分として渡すことで、
   セルを手で切らずに、学習器自身に条件ごとの使い分けを見つけさせる。

   実測（未知1,707レース）:
     元の16成分・線形       1位が1着 23.43% / 上位6頭で3着独占 37.96% / 尤度 −2.2446
     26成分・線形           26.54% / 43.06% / −2.1338
     50成分・木             27.77% / 43.94% / −2.0906   ← これ
     （参考）市場＝人気順    34.27% / 50.67% / −1.9169

   16成分との差は 1位が1着 +4.34pt (t=4.07)、上位6頭で3着独占 +5.98pt (t=5.50)。
"""
import numpy as np

try:
    import lightgbm as lgb
    HAVE_LGB = True
except ImportError:
    HAVE_LGB = False


def to_matrix(DS):
    """レースの並びを、行列と group（1レースの頭数）に直す。"""
    X = np.vstack([np.asarray(d["Z"], np.float32) for d in DS])
    grp = np.array([len(d["Z"]) for d in DS], np.int32)
    y = []
    for d in DS:
        for o in d["ord"]:
            y.append(3 if o == 1 else (2 if o == 2 else (1 if o == 3 else 0)))
    return X, np.array(y, np.int32), grp


PARAMS = dict(
    objective="lambdarank", metric="ndcg", ndcg_eval_at=[1, 3],
    lambdarank_truncation_level=6,          # 上位6頭までを見る
    learning_rate=0.05, num_leaves=48, max_depth=7,
    min_data_in_leaf=40, lambda_l2=5.0,
    feature_fraction=0.85, bagging_fraction=0.85, bagging_freq=1,
    max_bin=63, verbosity=-1, force_row_wise=True, seed=7,
)


def fit(TR, names, inner_frac=0.2, max_rounds=600, verbose=True):
    """学習期間の内側でさらに時系列に切り、木の本数を決めてから本学習する。
       未知期間には一切触れない。"""
    if not HAVE_LGB:
        raise RuntimeError("lightgbm が入っていません。pip install lightgbm")
    TR = sorted(TR, key=lambda d: d["date"])
    cut = int(len(TR) * (1 - inner_frac))
    A, B = TR[:cut], TR[cut:]
    Xa, ya, ga = to_matrix(A)
    Xb, yb, gb = to_matrix(B)
    da = lgb.Dataset(Xa, label=ya, group=ga, feature_name=list(names))
    db = lgb.Dataset(Xb, label=yb, group=gb, reference=da)
    ev = {}
    m = lgb.train(PARAMS, da, num_boost_round=max_rounds, valid_sets=[db],
                  valid_names=["inner"],
                  callbacks=[lgb.early_stopping(60, verbose=False),
                             lgb.record_evaluation(ev)])
    best = m.best_iteration or max_rounds
    if verbose:
        print(f"  内側検証 {len(B)}R で木の本数を決めました → {best}本")
    X, y, g = to_matrix(TR)
    d = lgb.Dataset(X, label=y, group=g, feature_name=list(names))
    full = lgb.train(PARAMS, d, num_boost_round=best)
    if verbose:
        imp = sorted(zip(names, full.feature_importance("gain")),
                     key=lambda x: -x[1])[:12]
        tot = sum(full.feature_importance("gain")) or 1
        print("  効いた成分（上位12）")
        for nm, v in imp:
            print(f"    {nm:12s} {v / tot * 100:5.1f}%")
    return full, best


def score(model, DS):
    """レースごとに得点を返す。"""
    X, _, g = to_matrix(DS)
    s = model.predict(X)
    out, p = [], 0
    for n in g:
        out.append(s[p:p + n])
        p += n
    return out


def evaluate(DS, model, top_k=6):
    n = h1 = i3 = cov = 0
    ll = 0.0
    c = 0
    per = []
    for d, s in zip(DS, score(model, DS)):
        s = np.asarray(s, float)
        order = np.argsort(-s)
        rank = np.empty(len(s), int)
        rank[order] = np.arange(len(s))
        n += 1
        p1 = d["ord"][order[0]]
        win = (p1 == 1)
        in3 = (p1 is not None and p1 <= 3)
        t3 = [d["ord"].index(x) for x in (1, 2, 3) if x in d["ord"]]
        cv = len(t3) == 3 and all(rank[i] < top_k for i in t3)
        h1 += win; i3 += in3; cov += cv
        per.append((win, in3, cv))
        mx = s.max()
        Z = np.exp(s - mx).sum()
        if 1 in d["ord"]:
            ll += s[d["ord"].index(1)] - mx - np.log(Z)
            c += 1
    return {"n": n, "1位が1着": round(h1 / n * 100, 2),
            "1位が3着内": round(i3 / n * 100, 2),
            f"上位{top_k}頭で3着独占": round(cov / n * 100, 2),
            "対数尤度": round(ll / c, 4)}, per
