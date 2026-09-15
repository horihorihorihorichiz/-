"""矛盾検知。計算結果に筋の通らない点がないかを一通り調べる。

すべて通れば「検閲通過」。1つでも落ちれば直す。
"""
import itertools
import json
import sys
import numpy as np

from evaluator import evaluate7
from sampling import draw
from classify2 import hand_type, board_texture, HAND, TEXTURE

PASS, FAIL, WARN = [], [], []


def check(name, ok, detail=''):
    (PASS if ok else FAIL).append((name, detail))


def warn(name, detail):
    WARN.append((name, detail))


# ---------- 1. 役の判定器 ----------
def slow5(cards):
    ranks = sorted((c >> 2 for c in cards), reverse=True)
    suits = [c & 3 for c in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    g = sorted(cnt.items(), key=lambda kv: (-kv[1], -kv[0]))
    shape, vals = [x[1] for x in g], [x[0] for x in g]
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    sh = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            sh = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:
            sh = 3
    if flush and sh is not None:
        return (8, [sh])
    if shape == [4, 1]:
        return (7, vals)
    if shape == [3, 2]:
        return (6, vals)
    if flush:
        return (5, ranks)
    if sh is not None:
        return (4, [sh])
    if shape == [3, 1, 1]:
        return (3, vals)
    if shape == [2, 2, 1]:
        return (2, vals)
    if shape == [2, 1, 1, 1]:
        return (1, vals)
    return (0, ranks)


def check_evaluator():
    rng = np.random.default_rng(101)
    hands, _ = draw(rng, 1500, 7)
    fast = evaluate7(hands)
    slow = [max(slow5(list(c)) for c in itertools.combinations(h, 5)) for h in hands.tolist()]
    order = sorted(range(len(slow)), key=lambda i: slow[i])
    bad = 0
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        same = slow[a] == slow[b]
        if same != (fast[a] == fast[b]) or (not same and fast[a] >= fast[b]):
            bad += 1
    check('役の判定器が5枚総当たりと一致', bad == 0, '不一致 %d 件' % bad)


# ---------- 2. 分類の網羅性 ----------
def check_classify():
    rng = np.random.default_rng(102)
    c, _ = draw(rng, 200000, 5)
    t = hand_type(c[:, :2], c[:, 2:])
    x = board_texture(c[:, 2:])
    check('ハンドの型が全て範囲内', bool(t.min() >= 0 and t.max() < len(HAND)),
          '範囲 %d〜%d / 種類 %d' % (t.min(), t.max(), len(HAND)))
    check('ボードの型が全て範囲内', bool(x.min() >= 0 and x.max() < len(TEXTURE)))
    counts = np.bincount(t, minlength=len(HAND))
    empty = [HAND[i] for i in range(len(HAND)) if counts[i] == 0]
    check('使われていない型がない', not empty, '、'.join(empty))


# ---------- 3. エクイティの基準 ----------
def check_equity_baseline():
    from gen_data import generate
    eq, _ = generate(1500, verbose=False, seed=103)
    m = float(eq.mean())
    check('全ハンドの平均エクイティが 0.5', abs(m - 0.5) < 0.01, '平均 %.4f' % m)


# ---------- 4. 役の強さの順序 ----------
# (強いはず, 弱いはず) ── 同じボードの型どうしで必ず成り立つべき関係
# 注: (7,8) は入れない。「トップペア（ボードのAをペア）」はキッカー全部の
# 平均なので、キッカーを限定した「Aキッカー」より低く出ることがある（矛盾ではない）。
ORDER_NAMES = [
    ('ストレート以上', 'セット'), ('セット', 'ツーペア'), ('ツーペア', 'ミドルヒット'),
    ('トップヒット Aキッカー', 'トップヒット K・Qキッカー'),
    ('トップヒット K・Qキッカー', 'トップヒット 8以下キッカー'),
    ('ミドルヒット', 'ボトムヒット'),
    ('アンダーペア（ミドルヒットより上）', 'アンダーペア（ボトムヒットより上）'),
    ('アンダーペア（ボトムヒットより上）', 'アンダーペア（ボードより下）'),
    ('ボトムヒット', 'アンダーペア（ボードより下）'),
    ('オーバーペア QQ以上', 'オーバーペア JJ以下'),
    ('ナッツフラッシュドロー', 'フラッシュドロー K・Qハイ'),
    ('フラッシュドロー K・Qハイ', 'フラッシュドロー 弱い'),
    ('オープンエンダー A・K持ち', 'オープンエンダー Q〜T持ち'),
    ('オープンエンダー Q〜T持ち', 'オープンエンダー 9以下'),
    ('ガットショット A・K持ち', 'ガットショット Q〜T持ち'),
    ('ガットショット Q〜T持ち', 'ガットショット 9以下'),
    ('オープンエンダー A・K持ち', 'ガットショット A・K持ち'),
    ('オープンエンダー Q〜T持ち', 'ガットショット Q〜T持ち'),
    ('オープンエンダー 9以下', 'ガットショット 9以下'),
    ('コンボドロー（フラドロ＋ストレート）', 'フラッシュドロー 弱い'),
    ('ツーオーバー（A含む）', 'ツーオーバー（Aなし）'),
    ('Aハイ', 'ノーペア'),
]
# 名前から番号を引く。並びを変えても検査が壊れない。
ORDER = [(HAND.index(a), HAND.index(b)) for a, b in ORDER_NAMES]

TOL = 0.016          # 乱数のぶれの許容幅


def check_order():
    rows = json.load(open('handtable.json'))['rows']
    keys = ['all'] + [str(i) for i in range(len(TEXTURE))]
    bad = []
    for k in keys:
        for hi, lo in ORDER:
            a, b = rows.get('%s-%d' % (k, hi)), rows.get('%s-%d' % (k, lo))
            if not a or not b:
                continue
            if a['eq'] < b['eq'] - TOL:
                nm = 'まとめて' if k == 'all' else TEXTURE[int(k)]
                bad.append('%s: %s %.0f%% ＜ %s %.0f%%'
                           % (nm, HAND[hi], 100*a['eq'], HAND[lo], 100*b['eq']))
    check('役の強さの順序が守られている', not bad, ' / '.join(bad[:6]))


# ---------- 5. 必要エクイティの単調性 ----------
SIT_CHAIN = [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (1, 4), (4, 7)]


def check_threshold_monotone():
    fields = json.load(open('fields.json'))
    bad = []
    for name, f in fields.items():
        g = f['grid']
        for lo, hi in SIT_CHAIN:
            for b in range(8):
                a, c = g[lo][b], g[hi][b]
                if a is None or c is None:
                    continue
                if c < a - 0.02:
                    bad.append('%s 後ろ%d人: %d→%d で %.0f%%→%.0f%%' % (name, b, lo, hi, 100*a, 100*c))
        # 誰も入っていない場面は、後ろの人数が増えるほど厳しくなるはず
        row = [g[0][b] for b in range(8)]
        for b in range(7):
            if row[b] is not None and row[b+1] is not None and row[b+1] < row[b] - 0.02:
                bad.append('%s コーラーなし 後ろ%d→%d人で緩くなっている' % (name, b, b+1))
    check('必要エクイティが単調（コーラーが増える/後ろが増えるほど厳しい）', not bad, ' / '.join(bad[:6]))


# ---------- 6. 理論値との整合 ----------
def check_theory():
    from solve import RAKE
    fields = json.load(open('fields.json'))
    g = fields['標準']['grid']
    # 3人以上入っている場面は、自分を入れて4人以上。理論上の下限は 1/((1-rake)*4)
    lower = 1 / ((1 - RAKE) * 4)
    vals = [v for v in g[7] if v is not None]
    check('3人以上入った場面の基準が理論下限を上回る',
          all(v > lower for v in vals), '下限 %.0f%% / 最小 %.0f%%' % (100*lower, 100*min(vals)))


# ---------- 7. 標本数とばらつき ----------
def check_samples():
    rows = json.load(open('handtable.json'))['rows']
    thin = [k for k, v in rows.items() if v['n'] < 400]
    check('表示する行の標本が400件以上', not thin, '%d 行が不足' % len(thin))
    wide = [(k, v) for k, v in rows.items() if v.get('q3', 0) - v.get('q1', 0) >= 0.20]
    if wide:
        warn('ばらつきの大きい行', '%d 行（幅20ポイント以上）' % len(wide))


# ---------- 8. 出現率 ----------
def check_coverage():
    d = json.load(open('handtable.json'))
    rows = d['rows']
    tot = sum(v.get('f', 0) for k, v in rows.items() if k.startswith('all-'))
    check('まとめての出現率の合計が100%', abs(tot - 1.0) < 0.02, '合計 %.1f%%' % (100 * tot))
    bad = []
    for t in range(len(TEXTURE)):
        s2 = sum(v.get('f', 0) for k, v in rows.items() if k.startswith('%d-' % t))
        if abs(s2 - 1.0) >= 0.03:
            bad.append('%s %.0f%%' % (TEXTURE[t], 100 * s2))
    check('各ボードの型でも出現率の合計が100%', not bad, ' / '.join(bad))
    ts = d.get('texShare', [])
    check('ボードの型の出現率の合計が100%', abs(sum(ts) - 1.0) < 0.02 if ts else False,
          '合計 %.1f%%' % (100 * sum(ts)) if ts else '未記録')


# ---------- 9. 表に渡すデータの整合 ----------
def check_chartdata():
    d = json.load(open('chartdata.json'))
    check('ハンド名の数が一致', len(d['hands']) == len(HAND), '%d / %d' % (len(d['hands']), len(HAND)))
    ok = all(len(v) == int(k) for k, v in d['pos'].items())
    check('ポジション名の数が卓の人数と一致', ok)
    shape_ok = all(len(f['grid']) == 8 and all(len(r) == 8 for r in f['grid']) for f in d['fields'])
    check('必要エクイティの表の形が正しい', shape_ok)
    miss = [i for i in range(len(d['hands'])) if ('all-%d' % i) not in d['rows']]
    check('まとめての行が全ハンド分ある', not miss,
          '欠け: ' + '、'.join(d['hands'][i] for i in miss))
    check('ボードの型の数が一致', len(d['textures']) == len(TEXTURE),
          '%d / %d' % (len(d['textures']), len(TEXTURE)))
    nrow = all(len(v) == 5 for v in d['rows'].values())
    check('各行が [エクイティ, 標本数, 下位, 上位, 出現率] の5つ組', nrow)


if __name__ == '__main__':
    only = sys.argv[1:] 
    steps = [('判定器', check_evaluator), ('分類', check_classify),
             ('エクイティ基準', check_equity_baseline), ('役の順序', check_order),
             ('単調性', check_threshold_monotone), ('理論整合', check_theory),
             ('標本', check_samples), ('出現率', check_coverage),
             ('データ整合', check_chartdata)]
    for nm, fn in steps:
        if only and nm not in only:
            continue
        fn()
    print('■ 通過 (%d)' % len(PASS))
    for n, d in PASS:
        print('   ○ %s%s' % (n, ('  ' + d) if d else ''))
    if WARN:
        print('■ 注意 (%d)' % len(WARN))
        for n, d in WARN:
            print('   △ %s  %s' % (n, d))
    print('■ 不合格 (%d)' % len(FAIL))
    for n, d in FAIL:
        print('   × %s  %s' % (n, d))
    sys.exit(1 if FAIL else 0)
