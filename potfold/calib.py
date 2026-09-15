"""タイマン勝率を「実際の場面での取り分」に換算する対応表を作る。

判断そのものは
    取り分の期待値 × (1 + 参加人数) ≧ 1
で決まる。画面に「相手1人に対する勝率」を出すのは実感に合わないので、
各場面（後ろの人数, 前で続けた人数）ごとに

  ・その勝率の手が実際に得る取り分
  ・最終的な参加人数の平均

を求めて、取り分どうしの比較で見せられるようにする。
"""
import json
import numpy as np
from solve import _decide, _payoff

NB = 20                      # 勝率の刻み（5%ずつ）


def build(eq, sc, thresholds_by_n):
    share_sum = np.zeros((8, 8, NB))
    share_cnt = np.zeros((8, 8, NB))
    m_sum = np.zeros((8, 8))
    m_cnt = np.zeros((8, 8))

    for n in range(2, 9):
        th = [np.array(t) for t in thresholds_by_n[str(n)]['thresholds']]
        for seat in range(n):
            behind = n - 1 - seat
            cont, m, c_before = _decide(eq, th, n, force_seat=seat)
            msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
            mx = msc.max(axis=1)
            ties = (msc == mx[:, None]).sum(axis=1)
            share = np.where(sc[:, seat] == mx, 1.0 / ties, 0.0)

            b = np.clip((eq[:, seat] * NB).astype(int), 0, NB - 1)
            for c in range(seat + 1):
                sel = c_before == c
                if not sel.any():
                    continue
                np.add.at(share_sum[behind, c], b[sel], share[sel])
                np.add.at(share_cnt[behind, c], b[sel], 1)
                m_sum[behind, c] += m[sel].sum()
                m_cnt[behind, c] += sel.sum()

    share = np.where(share_cnt > 0, share_sum / np.maximum(share_cnt, 1), np.nan)
    # 勝率が上がれば取り分も増えるはず。欠けた刻みは前後から補う
    out = np.zeros((8, 8, NB))
    for bh in range(8):
        for c in range(8):
            v = share[bh, c]
            if np.isnan(v).all():
                out[bh, c] = np.nan
                continue
            idx = np.where(~np.isnan(v))[0]
            v = np.interp(np.arange(NB), idx, v[idx])
            out[bh, c] = np.maximum.accumulate(v)
    mean_m = np.where(m_cnt > 0, m_sum / np.maximum(m_cnt, 1), np.nan)
    return out, mean_m, share_cnt


if __name__ == '__main__':
    d = np.load('deals.npz')
    eq, sc = d['equity'].astype(float), d['score']
    th = json.load(open('thresholds.json'))
    share, mean_m, cnt = build(eq, sc, th)
    grid = json.load(open('grid.json'))['grid']

    def share_at(bh, c, x):
        """勝率 x のときの取り分を、対応表から線形に読む。"""
        v = share[bh, c]
        pos = np.clip(x * NB - 0.5, 0, NB - 1)
        lo = int(np.floor(pos)); hi = min(lo + 1, NB - 1)
        f = pos - lo
        return v[lo] * (1 - f) + v[hi] * f

    print('場面ごとの目安')
    print(' 後ろ 前継続  予想参加人数  続けるのに必要な取り分  (基準の勝率)')
    table = {}
    for bh in range(8):
        for c in range(8):
            t = grid[bh][c]
            if t is None or np.isnan(mean_m[bh, c]):
                continue
            need = share_at(bh, c, t)
            table['%d-%d' % (bh, c)] = {'need_share': round(float(need), 4),
                                        'mean_m': round(float(mean_m[bh, c]), 3)}
            if c <= 2:
                print('  %d人  %d人   %5.2f 人      %5.1f%%            (%.0f%%)'
                      % (bh, c, mean_m[bh, c], 100 * need, 100 * t))
    json.dump({'share': np.nan_to_num(share, nan=-1).round(4).tolist(),
               'mean_m': np.nan_to_num(mean_m, nan=-1).round(3).tolist(),
               'nb': NB, 'cell': table},
              open('calib.json', 'w'), indent=1)
    print('\n保存: calib.json')
