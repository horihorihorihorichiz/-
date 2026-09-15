"""コーラーが2人以上のとき、その位置でどう変わるかを求める。

1人のときと同じく、均衡での全員の戦略は固定したまま、自分だけ
「いちばん早いコーラーが何人前か」を見て最善の基準を取り直す。
"""
import json
import numpy as np
from solve import _decide, _threshold_from

# いちばん早いコーラーまでの距離のまとめ方
GROUPS = [(1, 2, '2人前以内'), (3, 4, '3〜4人前'), (5, 7, '5人以上前')]


def run(eq, sc, th_by_n, n_callers, min_n=60):
    bank = {}
    for n in range(2, 9):
        th = [np.array(t) for t in th_by_n[str(n)]['thresholds']]
        for seat in range(n_callers, n):
            behind = n - 1 - seat
            cont, m, c_before = _decide(eq, th, n, force_seat=seat)
            msc = np.where(cont[:, :n], sc[:, :n], np.int64(-1))
            mx = msc.max(axis=1)
            ties = (msc == mx[:, None]).sum(axis=1)
            share = np.where(sc[:, seat] == mx, 1.0 / ties, 0.0)
            pay = share * (1.0 + m) - 1.0

            hit = (c_before == n_callers) if n_callers < 3 else (c_before >= 3)
            if not hit.any():
                continue
            first = np.argmax(cont[:, :seat], axis=1)      # いちばん早いコーラー
            dist = seat - first
            for lo, hi, _ in GROUPS:
                sel = hit & (dist >= lo) & (dist <= hi)
                if sel.sum() < min_n:
                    continue
                a, b = bank.get((behind, lo), ([], []))
                a.append(eq[sel, seat]); b.append(pay[sel])
                bank[(behind, lo)] = (a, b)

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
    base = json.load(open('grid.json'))['grid']
    res = {}
    for k, label in [(2, '2人コール'), (3, '3人以上コール')]:
        r = run(eq, sc, th, k)
        res[str(k)] = r
        print('\n%s ── いちばん早いコーラーの位置別に必要なエクイティ' % label)
        print(' 後ろ   2人前以内        3〜4人前         5人以上前      （位置を見ない場合）')
        for b in range(8):
            row = []
            for lo, hi, nm in GROUPS:
                x = r.get('%d-%d' % (b, lo))
                row.append('%4.0f%% (n=%6d)' % (100 * x['thr'], x['n']) if x else '      —       ')
            ref = base[b][k if k < 3 else 3]
            if any('%' in c for c in row):
                print(' %d人  %s   %s' % (b, '  '.join(row), '%.0f%%' % (100 * ref) if ref else '—'))
    json.dump(res, open('callerpos2.json', 'w'), indent=1)
    print('\n保存: callerpos2.json')
