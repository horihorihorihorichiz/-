# -*- coding: utf-8 -*-
"""Ver.2-WIN: 「勝つ馬の得点を高く」に照準を合わせた学習（ユーザー指示 7/14）。
   市場情報は一切使わない（ユーザーが送る情報=馬柱・自前指数・騎手だけ）。
   目的関数を勝者の条件付き尤度(+2着3着は低い重み)にして、勝ち馬識別力を直接最大化する。

   評価（勝ち馬識別のものさし）:
     - 勝ち馬がモデル1位である率 / 上位3位以内率 / 勝ち馬の平均モデル順位
     - モデル1位の単勝フラット回収率（=回収率を上げるの直接指標）
     - 乖離バケット（モデル1位が4番人気以下）の単勝回収率

   usage: python3 fit_v2win.py [--test ...] [--l2 0.05] [--wpos 3,1,1] [--write]
"""
import argparse, json, math, sys
import fit_v2 as V2

FEATS = V2.FEATS


def pl_nll_grad_w(ds, w, l2, wpos):
    """位置重み付きPL: 1着の尤度を厚く"""
    nll = 0.0
    g = [0.0]*len(FEATS)
    n_obs = 0.0
    for r in ds:
        s = V2.scores(r, w)
        alive = list(s.keys())
        for pos in range(3):
            pw_ = wpos[pos]
            if pw_ <= 0:
                break
            winner = r["top3"][pos]
            mx = max(s[n] for n in alive)
            e = {n: math.exp(s[n]-mx) for n in alive}
            Z = sum(e.values())
            p = {n: e[n]/Z for n in alive}
            nll += -pw_*math.log(max(p[winner], 1e-12))
            n_obs += pw_
            for i, k in enumerate(FEATS):
                g[i] += -pw_*(r["X"][k][winner] - sum(p[n]*r["X"][k][n] for n in alive))
            alive.remove(winner)
    for i in range(len(FEATS)):
        g[i] = g[i]/n_obs + 2*l2*w[i]
    return nll/n_obs + l2*sum(x*x for x in w), g


def fit(train, l2, wpos, iters=300, lr=0.3):
    w = [0.0]*len(FEATS)
    m = [0.0]*len(FEATS)
    for it in range(iters):
        nll, g = pl_nll_grad_w(train, w, l2, wpos)
        for i in range(len(FEATS)):
            m[i] = 0.9*m[i] + g[i]
            w[i] -= lr*m[i]
        if it % 100 == 0:
            print(f"  iter{it}: NLL={nll:.4f}", file=sys.stderr)
    return w


def winner_metrics(ds, score_fn, label):
    """勝ち馬識別+3着内捕捉のものさし一式"""
    n = at1 = at3 = 0
    ranks = []
    roi_stake = roi_ret = 0.0
    div_stake = div_ret = div_n = 0.0
    cap_h = cap_n = 0     # ★KPI: 3着内に入った馬がモデル5位以内にいる率(馬単位)
    cap_all = 0           # ★KPI: 3頭全員が5位以内(レース単位=三連複がtop5ボックスで獲れる)
    for r in ds:
        s = score_fn(r)
        order = sorted(s, key=lambda x: -s[x])
        top5 = set(order[:5])
        inn = sum(1 for t in r["top3"] if t in top5)
        cap_h += inn
        cap_n += len(r["top3"])
        cap_all += (inn == 3)
        winner = r["top3"][0]
        rk = order.index(winner) + 1
        ranks.append(rk)
        n += 1
        at1 += (rk == 1)
        at3 += (rk <= 3)
        top = order[0]
        o = r["odds"].get(top)
        if o:
            roi_stake += 1
            roi_ret += (o if top == winner else 0)
            mkt_rank = sorted(r["odds"], key=lambda h: r["odds"][h]).index(top) + 1
            if mkt_rank >= 4:
                div_n += 1
                div_stake += 1
                div_ret += (o if top == winner else 0)
    print(f"  {label}")
    print(f"    ★3着内馬が5位以内率 {cap_h/cap_n*100:.1f}% / 3頭全員5位以内率 {cap_all/n*100:.1f}%")
    print(f"    勝ち馬=1位率 {at1/n*100:.1f}% / 3位以内率 {at3/n*100:.1f}% / 勝ち馬の平均順位 {sum(ranks)/n:.2f}")
    print(f"    モデル1位の単勝フラット回収率 {roi_ret/roi_stake*100:.1f}% (n={int(roi_stake)})")
    if div_n:
        print(f"    乖離バケット(1位が4番人気以下 {int(div_n)}R) 単勝回収率 {div_ret/div_stake*100:.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="20260704,20260705,20260711,20260712")
    ap.add_argument("--l2", type=float, default=0.05)
    ap.add_argument("--wpos", default="3,1,0.5", help="1着,2着,3着の尤度重み")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    wpos = [float(x) for x in a.wpos.split(",")]

    ds = V2.load_dataset("hist", "hist_feat")
    test_days = set(a.test.split(","))
    train = [r for r in ds if r["date"] not in test_days]
    test = [r for r in ds if r["date"] in test_days]
    print(f"データ: 全{len(ds)}R (train {len(train)} / test {len(test)}) 位置重み={wpos}")

    w = fit(train, a.l2, wpos)
    print("\n学習した重み（勝ち馬照準・市場情報なし）:")
    for k, v in zip(FEATS, w):
        print(f"  {k:12s} {v:+.3f}")

    # 既存比較: 現行得点(wavg) / Ver.2(3着内フィット) / Ver.2-WIN
    pv = json.load(open("params_v2.json", encoding="utf-8"))
    w_place = (pv["weights"] + [0.0]*len(FEATS))[:len(FEATS)]   # 特徴量追加後も比較可能に
    for name, dset in (("train", train), ("test", test)):
        if not dset:
            continue
        print(f"\n── 勝ち馬識別 ({name}) ──")
        winner_metrics(dset, lambda r: {n: r["X"]["wavg"][n] for n in r["ns"]}, "現行得点(WAvg)")
        winner_metrics(dset, lambda r: V2.scores(r, w_place), "Ver.2(3着内フィット)")
        winner_metrics(dset, lambda r: V2.scores(r, w), "Ver.2-WIN(勝ち馬照準)")

    if a.write:
        pv["weights_win"] = [round(x, 4) for x in w]
        pv["wpos"] = wpos
        json.dump(pv, open("params_v2.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nparams_v2.json に weights_win を保存した。")


if __name__ == "__main__":
    main()
