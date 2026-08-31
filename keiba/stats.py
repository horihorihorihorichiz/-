# -*- coding: utf-8 -*-
"""results.jsonl から的中率・回収率を集計する。
   各レコードに stake(投資額) と return(払戻) があれば正確、無ければ pnl から逆算。"""
import json, sys

def load():
    return [json.loads(l) for l in open('results.jsonl', encoding='utf-8') if l.strip()]

def stake_of(r):
    if r.get('stake') is not None: return r['stake']
    b = r.get('bet', '')
    for amt in ('10000', '5000', '20000'):
        if amt in b.replace(',', ''): return int(amt)
    # pnl と hit から: ハズレなら stake = -pnl
    if r.get('hit') is False and r.get('pnl') is not None: return -r['pnl']
    return 0

def ret_of(r):
    if r.get('return') is not None: return r['return']
    if r.get('hit') is False: return 0
    if r.get('hit') and r.get('pnl') is not None and r.get('stake') is not None:
        return r['stake'] + r['pnl']
    return 0

def main():
    rows = load()
    graded = [r for r in rows if r.get('pnl') is not None]     # 結果が出たもの
    miken = [r for r in graded if str(r.get('verdict', '')).startswith('見送り')]
    go = [r for r in graded if r not in miken and stake_of(r) > 0]
    hits = [r for r in go if r.get('hit')]
    staked = sum(stake_of(r) for r in go)
    returned = sum(ret_of(r) for r in go)
    print("=" * 56)
    print(" 競馬予想 通算成績 (results.jsonl)")
    print("=" * 56)
    print(" 明細:")
    for r in graded:
        st = stake_of(r); rt = ret_of(r)
        mark = "○的中" if r.get('hit') else ("―見送" if str(r.get('verdict', '')).startswith('見送り') else ("・無効" if stake_of(r) == 0 else "×ハズレ"))
        res = r.get('result', {})
        rs = "→".join(str(res[k]) for k in ('1st', '2nd', '3rd') if k in res) if res else ""
        print("  %-10s %-24s %s 投%5d 戻%6d 損益%+6d  着[%s]"
              % (r.get('date', ''), r.get('race', '')[:24], mark, st, rt, rt - st, rs))
    n = len(go)
    print("-" * 56)
    print(" GO(勝負)レース数 : %d" % n)
    print(" 的中             : %d  (的中率 %.0f%%)" % (len(hits), len(hits) / n * 100 if n else 0))
    print(" 見送り(正しく回避): %d" % len(miken))
    print(" 総投資           : %,d 円" .replace(",d", "d") % staked if False else " 総投資           : %d 円" % staked)
    print(" 総払戻           : %d 円" % returned)
    print(" 通算損益         : %+d 円" % (returned - staked))
    print(" 回収率           : %.0f%%" % (returned / staked * 100 if staked else 0))
    print("=" * 56)

if __name__ == "__main__":
    main()
