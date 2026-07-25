import json, itertools

ROWS = []
for line in open('/home/user/-/keiba/wf_preds.jsonl'):
    line = line.strip()
    if not line:
        continue
    d = json.loads(line)
    d['month'] = int(d['month'])
    d['dist'] = int(d['dist']); d['tier'] = int(d['tier']); d['field'] = int(d['field'])
    d['odds'] = {int(k): float(v) for k, v in d['odds'].items()}
    d['scores'] = {int(k): float(v) for k, v in d['scores'].items()}
    d['order'] = [int(x) for x in d['order']]
    tp = d['payout'].get('三連複', {})
    trio = None; trio_pay = 0
    for k, v in tp.items():
        trio = frozenset(int(x) for x in k.split('-')); trio_pay = float(v)
    d['trio'] = trio; d['trio_pay'] = trio_pay
    # market ranks
    ok = [h for h in d['odds'] if d['odds'][h] > 0]
    d['pop'] = sorted(ok, key=lambda h: (d['odds'][h], h))
    ROWS.append(d)


def evaluate(name, selector, verbose=True):
    """selector(row) -> list of frozenset trios (bets) or None/[]"""
    buckets = {'dev': [], 'conf': []}
    allbets = []
    for r in ROWS:
        if r['trio'] is None:
            continue
        bets = selector(r)
        if not bets:
            continue
        bets = list({frozenset(b) for b in bets})
        bets = [b for b in bets if len(b) == 3]
        if not bets:
            continue
        cost = 100 * len(bets)
        ret = r['trio_pay'] if r['trio'] in bets else 0.0
        seg = 'dev' if r['month'] <= 202603 else 'conf'
        buckets[seg].append((cost, ret))
        allbets.append((cost, ret))

    def agg(lst):
        c = sum(x[0] for x in lst); ret = sum(x[1] for x in lst)
        n = len(lst); h = sum(1 for x in lst if x[1] > 0)
        return c, ret, n, h, (100.0 * ret / c if c else 0.0)

    dc, dr, dn, dh, droi = agg(buckets['dev'])
    cc, cr, cn, ch, croi = agg(buckets['conf'])
    ac, ar, an, ah, aroi = agg(allbets)
    mx = max([x[1] for x in allbets], default=0.0)
    if ac - 0 > 0:
        # exclude the single biggest hit (remove its return, keep its cost)
        exroi = 100.0 * (ar - mx) / ac if ac else 0.0
    else:
        exroi = 0.0
    res = dict(rule=name, dev_roi=round(droi, 1), dev_n=dn, dev_hits=dh,
               conf_roi=round(croi, 1), conf_n=cn, conf_hits=ch,
               overall_roi=round(aroi, 1), n=an, hits=ah,
               excl_max_roi=round(exroi, 1), maxpay=mx)
    if verbose:
        print(f"{name}: dev {droi:.1f}% n={dn} h={dh} | conf {croi:.1f}% n={cn} h={ch} "
              f"| all {aroi:.1f}% n={an} h={ah} exclmax {exroi:.1f}% max={mx:.0f}")
    return res


def passes(res):
    return (res['dev_roi'] >= 110 and res['conf_roi'] >= 100 and res['n'] >= 40
            and res['hits'] >= 5 and res['excl_max_roi'] >= 95)
