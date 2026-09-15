"""相手の傾向（タイト〜ルース）を変えたときの、自分の最善のコール基準を求める。

均衡の基準を全席一律にずらしたものを「相手のレンジ」とみなし、
そのレンジを固定したうえで自分だけ最善手を取り直す（最適応答）。
相手が緩いほど相手のレンジは弱くなるが、人数も増えるので、
必要エクイティは単純には下がらない。
"""
import json
import numpy as np
from solve import _decide, _threshold_from

D1 = [(1, 1), (2, 3), (4, 7)]          # コーラー1人のときの距離のまとめ方
D2 = [(1, 2), (3, 4), (5, 7)]          # コーラー2人のとき（いちばん早い人までの距離）
MIN_N = 1500

SIT_NAMES = ['コーラーなし', '1人：直前の席', '1人：2〜3人前', '1人：4人以上前',
             '2人：2人前以内', '2人：3〜4人前', '2人：5人以上前', '3人以上']


def loosen(th_by_n, eq_all, gamma):
    """相手のレンジを、コール頻度を尺度にして緩める／締める。

    均衡でのコール頻度 p を p^gamma に置き換える（gamma<1 で緩く、>1 で固く）。
    頻度で操作するので、「必ずコールする場面」（頻度1）はそのまま残る。
    """
    srt = np.sort(eq_all.ravel())
    out = {}
    for n in range(2, 9):
        rows = []
        for t in th_by_n[str(n)]['thresholds']:
            new = []
            for x in t:
                p = 1.0 - np.searchsorted(srt, x) / srt.size      # コールする割合
                p2 = min(1.0, max(0.0, p ** gamma))
                new.append(0.0 if p2 >= 1.0 else float(srt[int((1 - p2) * (srt.size - 1))]))
            rows.append(new)
        out[str(n)] = {'thresholds': rows}
    return out


def observables(eq, opp_th, n=8):
    """利用者が卓で数えられる目安を返す。

    callers : その人数の卓で、1ハンドあたり平均何人がコールするか
    rate    : 1人あたりのコール率
    allfold : 1人がコールしたあと、後ろが全員降りる割合（8人卓・席1基準）
    """
    th = [np.array(t) for t in opp_th[str(n)]['thresholds']]
    cont, m, _ = _decide(eq, th, n)
    callers = float(cont[:, :n].sum(axis=1).mean())
    rate = float(cont[:, :n].mean())
    cont2, m2, _ = _decide(eq, th, n, force_seat=0)
    allfold = float((m2 == 1).mean())
    return callers, rate, allfold


def situation_thresholds(eq, sc, opp_th):
    """8つの状況 × 後ろの人数 の必要エクイティを返す。"""
    bank = {}

    def add(key, e, p):
        a, b = bank.get(key, ([], []))
        a.append(e); b.append(p); bank[key] = (a, b)

    for n in range(2, 9):
        th = [np.array(t) for t in opp_th[str(n)]['thresholds']]
        for seat in range(n):
            behind = n - 1 - seat
            cont, m, c_before = _decide(eq, th, n, force_seat=seat)
            msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
            mx = msc.max(axis=1)
            ties = (msc == mx[:, None]).sum(axis=1)
            share = np.where(sc[:, seat] == mx, 1.0 / ties, 0.0)
            pay = share * (1.0 + m) - 1.0
            e_seat = eq[:, seat]

            sel = c_before == 0
            if sel.any():
                add((behind, 0), e_seat[sel], pay[sel])

            if seat >= 1:
                first = np.argmax(cont[:, :seat], axis=1)
                dist = seat - first
                one = c_before == 1
                for i, (lo, hi) in enumerate(D1):
                    s = one & (dist >= lo) & (dist <= hi)
                    if s.any():
                        add((behind, 1 + i), e_seat[s], pay[s])
                two = c_before == 2
                for i, (lo, hi) in enumerate(D2):
                    s = two & (dist >= lo) & (dist <= hi)
                    if s.any():
                        add((behind, 4 + i), e_seat[s], pay[s])
                many = c_before >= 3
                if many.any():
                    add((behind, 7), e_seat[many], pay[many])

    grid = [[None] * 8 for _ in range(8)]
    counts = [[0] * 8 for _ in range(8)]
    for (behind, s), (a, b) in bank.items():
        e = np.concatenate(a); p = np.concatenate(b)
        counts[s][behind] = int(e.size)
        if e.size >= MIN_N:
            t = _threshold_from(e, p)
            if t is not None:
                grid[s][behind] = round(float(t), 4)
    return grid, counts


if __name__ == '__main__':
    d = np.load('deals.npz')
    eq, sc = d['equity'].astype(float), d['score']
    base = json.load(open('thresholds.json'))

    LEVELS = [('固い', 2.6), ('標準', 1.0), ('緩い', 0.55), ('とても緩い', 0.28)]
    out = {}
    for name, gamma in LEVELS:
        opp = loosen(base, eq, gamma)
        callers, rate, allfold = observables(eq, opp)
        grid, counts = situation_thresholds(eq, sc, opp)
        out[name] = {'callers': round(callers, 2), 'rate': round(rate, 4),
                     'allfold': round(allfold, 3), 'gamma': gamma,
                     'grid': grid, 'counts': counts}
        print('\n=== %s（8人卓で平均 %.1f 人がコール／1人あたり %.0f%%／コールに全員降りる割合 %.0f%%）==='
              % (name, callers, 100 * rate, 100 * allfold))
        print('%-16s %s' % ('前の状況', ' '.join('後ろ%d' % b for b in range(7, -1, -1))))
        for s in range(8):
            row = ' '.join(('%4.0f%%' % (100 * grid[s][b]) if grid[s][b] is not None else '   —')
                           for b in range(7, -1, -1))
            print('%-16s %s' % (SIT_NAMES[s], row))
    json.dump(out, open('fields.json', 'w'), ensure_ascii=False, indent=1)
    print('\n保存: fields.json')
