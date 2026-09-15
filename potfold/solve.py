"""Pot Fold の継続基準を、繰り返し最適応答で求める。

考え方
------
・全員が参加料 a を出す → 最初のポット P = n*a
・続けるための額は P に固定。行動は「続ける」か「降りる」の二択、一巡のみ
・2人以上残れば残り2枚が自動で開いて勝負

続けた人が合計 m 人のとき、最後のポットは P + m*P。
自分の取り分の期待値を e とすると、続けたときの損得（P を1単位として）は

    e * (1 + m) - 1

つまり損益分岐となる勝率は 1/(1+m)。相手が k 人続けるなら 1/(k+2) で済む。
これは「人数で等分した取り分」1/(k+1) より低いので、直感より広く続けてよい。

各席の戦略は「タイマン勝率がある値以上なら続ける」という形とし、
自分より前で何人続けたかによって基準を変える。これを全席について
繰り返し最適化する。
"""
import numpy as np

N_BINS = 40


def _decide(eq, thresholds, n, force_seat=None):
    """各席の継続判断を前の席から順に決める。force_seat は必ず続ける扱いにする。"""
    d = eq.shape[0]
    cont = np.zeros((d, n), dtype=bool)
    c = np.zeros(d, dtype=np.int64)
    c_before = None
    for j in range(n):
        if j == force_seat:
            c_before = c.copy()
            cont[:, j] = True
        else:
            cont[:, j] = eq[:, j] >= thresholds[j][np.minimum(c, j)]
        c = c + cont[:, j]
    return cont, c, c_before


def _payoff(cont, m, sc, seat, n):
    """席 seat が続けたときの損得（最初のポット P を1単位とする）。"""
    msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
    mx = msc.max(axis=1)
    ties = (msc == mx[:, None]).sum(axis=1)
    share = np.where(sc[:, seat] == mx, 1.0 / ties, 0.0)
    return share * (1.0 + m) - 1.0


def _threshold_from(eqv, pay):
    """勝率 eqv に対する損得 pay から、損益分岐の勝率を求める。"""
    if eqv.size < 60:
        return None
    order = np.argsort(eqv)
    eqv, pay = eqv[order], pay[order]
    edges = np.linspace(0, eqv.size, N_BINS + 1).astype(int)
    centers, means = [], []
    for i in range(N_BINS):
        a, b = edges[i], edges[i + 1]
        if b - a < 10:
            continue
        centers.append(eqv[a:b].mean())
        means.append(pay[a:b].mean())
    if not centers:
        return None
    centers = np.array(centers)
    means = np.maximum.accumulate(np.array(means))   # 勝率が上がれば得も増えるはず
    if means[0] > 0:
        return 0.0
    if means[-1] <= 0:
        return 1.0
    k = int(np.argmax(means > 0))
    x0, x1, y0, y1 = centers[k - 1], centers[k], means[k - 1], means[k]
    return float(x0 + (x1 - x0) * (-y0) / (y1 - y0))


def cell_counts(eq, sc, n, thresholds):
    """各 (席, 前で続けた人数) の場面が何回現れたかを数える。"""
    out = []
    for seat in range(n):
        _, _, c_before = _decide(eq, thresholds, n, force_seat=seat)
        out.append(np.bincount(c_before, minlength=seat + 1)[:seat + 1])
    return out


def solve(eq, sc, n, rounds=14, damping=0.5, verbose=False):
    """n 人卓の継続基準 thresholds[seat][前で続けた人数] を返す。"""
    thresholds = [np.full(j + 1, 0.5) for j in range(n)]
    for r in range(rounds):
        moved = 0.0
        for seat in range(n):
            cont, m, c_before = _decide(eq, thresholds, n, force_seat=seat)
            pay = _payoff(cont, m, sc, seat, n)
            new = thresholds[seat].copy()
            for c in range(seat + 1):
                if seat == n - 1 and c == 0:
                    # 自分が最後で、前が全員降りている → 続ければ必ずポットを取れる
                    new[c] = 0.0
                    continue
                sel = c_before == c
                t = _threshold_from(eq[sel, seat], pay[sel])
                if t is not None:
                    new[c] = (1 - damping) * thresholds[seat][c] + damping * t
            # 前で続けた人数が多いほど基準は厳しくなるはず（ばらつきをならす）
            new = np.maximum.accumulate(new)
            moved = max(moved, float(np.abs(new - thresholds[seat]).max()))
            thresholds[seat] = new
        if verbose:
            print('   周回 %2d: 変化量 %.4f' % (r + 1, moved), flush=True)
        if moved < 0.0015:
            break
    return thresholds


def evaluate_strategy(eq, sc, n, thresholds):
    """求めた戦略での、席ごとの継続率と1ハンドあたりの損得を返す。"""
    cont, m, _ = _decide(eq, thresholds, n)
    ante = 1.0 / n                       # 参加料は P の 1/n
    res = []
    for seat in range(n):
        msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
        mx = msc.max(axis=1)
        ties = (msc == mx[:, None]).sum(axis=1)
        share = np.where((sc[:, seat] == mx) & cont[:, seat], 1.0 / ties, 0.0)
        pot = 1.0 + m
        gain = np.where(cont[:, seat], share * pot - 1.0, 0.0) - ante
        res.append((float(cont[:, seat].mean()), float(gain.mean())))
    return res
