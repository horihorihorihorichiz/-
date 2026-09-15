"""コーラーがどの位置から入ったかで、必要エクイティがどう変わるかを求める。

均衡での全員の戦略は固定したまま、自分だけ「コーラーの位置」を見て
最善のコール基準を取り直す（最適応答）。
"""
import json
import numpy as np
from solve import _decide, _threshold_from

DGROUP = [(1, 1, '直前の席'), (2, 3, '2〜3人前'), (4, 7, '4人以上前')]


def run(eq, sc, th_by_n):
    # acc[(後ろの人数, 距離の群)] = [勝率, 損得] の並び
    bank = {}
    for n in range(2, 9):
        th = [np.array(t) for t in th_by_n[str(n)]['thresholds']]
        for seat in range(1, n):
            behind = n - 1 - seat
            cont, m, c_before = _decide(eq, th, n, force_seat=seat)
            msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
            mx = msc.max(axis=1)
            ties = (msc == mx[:, None]).sum(axis=1)
            share = np.where(sc[:, seat] == mx, 1.0 / ties, 0.0)
            pay = share * (1.0 + m) - 1.0

            one = c_before == 1
            if not one.any():
                continue
            caller = np.argmax(cont[:, :seat], axis=1)
            dist = seat - caller
            for lo, hi, _ in DGROUP:
                sel = one & (dist >= lo) & (dist <= hi)
                if sel.sum() < 60:
                    continue
                key = (behind, lo)
                a, b = bank.get(key, ([], []))
                a.append(eq[sel, seat]); b.append(pay[sel])
                bank[key] = (a, b)

    out = {}
    for (behind, lo), (a, b) in bank.items():
        e = np.concatenate(a); p = np.concatenate(b)
        t = _threshold_from(e, p)
        if t is not None:
            out['%d-%d' % (behind, lo)] = {'thr': round(float(t), 4), 'n': int(e.size)}
    return out


if __name__ == '__main__':
    d = np.load('deals.npz')
    eq, sc = d['equity'].astype(float), d['score']
    th = json.load(open('thresholds.json'))
    res = run(eq, sc, th)
    base = json.load(open('grid.json'))['grid']
    print('コーラー1人のとき、その位置別に必要なエクイティ')
    print(' 後ろ   直前の席      2〜3人前      4人以上前   （位置を見ない場合）')
    for b in range(8):
        row = []
        for lo, hi, nm in DGROUP:
            r = res.get('%d-%d' % (b, lo))
            row.append('%5.0f%% (n=%6d)' % (100 * r['thr'], r['n']) if r else '      —        ')
        ref = base[b][1]
        print(' %d人  %s   %s' % (b, '  '.join(row), '%.0f%%' % (100 * ref) if ref else '—'))
    json.dump(res, open('callerpos.json', 'w'), indent=1)
    print('\n保存: callerpos.json')
