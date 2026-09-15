"""thresholds.json から早見表（markdown）を作る。"""
import json

d = json.load(open('thresholds.json'))
out = []
for n in range(2, 9):
    v = d[str(n)]
    th, st, cnt = v['thresholds'], v['stats'], v['counts']
    out.append('### %d人卓\n' % n)
    head = ['行動順'] + ['前で%d人' % c for c in range(n)] + ['継続率', '1ハンド収支']
    out.append('| ' + ' | '.join(head) + ' |')
    out.append('|' + '---|' * len(head))
    for i in range(n):
        row = ['%d番目' % (i + 1)]
        for c in range(n):
            if c > i:
                row.append('')
            elif cnt[i][c] == 0:
                row.append('—')
            elif cnt[i][c] < 100:
                row.append('(%.0f%%)' % (100 * th[i][c]))
            else:
                row.append('%.0f%%' % (100 * th[i][c]))
        row.append('%.0f%%' % (100 * st[i][0]))
        row.append('%+.3f' % st[i][1])
        out.append('| ' + ' | '.join(row) + ' |')
    out.append('')
open('table.md', 'w').write('\n'.join(out))
print('\n'.join(out[:14]))
print('...\n保存: table.md')
