# -*- coding: utf-8 -*-
"""実装済みJRAパターンを wf_preds.jsonl から全部再計算し一覧表にする。
   コードの発火条件と、台帳に書いてある数字がズレていないかの監査を兼ねる。
   usage: python3 verify_all.py [--md]"""
import ast, itertools, json, math, sys

rows = []
for l in open("wf_preds.jsonl", encoding="utf-8"):
    d = json.loads(l)
    for k in ("order", "odds", "payout", "scores"):
        if isinstance(d.get(k), str):
            try: d[k] = ast.literal_eval(d[k])
            except Exception: d[k] = None
    for k in ("dist", "tier", "field"):
        try: d[k] = int(d.get(k))
        except (TypeError, ValueError): d[k] = None
    if d.get("order") and d.get("odds"):
        d["odds"] = {int(k): v for k, v in d["odds"].items() if v}
        d["day"] = int(d["rid"][8:10]) if len(d["rid"]) >= 10 else None
        rows.append(d)

def pwin(d):
    s = d.get("scores") or {}
    if not s: return 0
    v = {int(k): float(x) for k, x in s.items()}
    mx = max(v.values()); e = {k: math.exp(x - mx) for k, x in v.items()}
    t = sum(e.values())
    return e.get(d["order"][0], 0) / t if t else 0

def pay(d, kind, key):
    p = (d.get("payout") or {}).get(kind) or {}
    tgt = set(str(key).replace(" ", "").split("-"))
    for k, v in p.items():
        if set(str(k).replace(" ", "").replace("→", "-").split("-")) == tgt:
            return v
    return 0

O1 = lambda d: d["odds"].get(d["order"][0], 0)
UP = lambda d: d["tier"] is not None and 6 <= d["tier"] <= 9   # 上級(未勝利除く)
MAIDEN = lambda d: d["tier"] is not None and d["tier"] >= 10
FIRE = lambda d: O1(d) >= 7.0 and not MAIDEN(d)

def bet_tan(d, num=None):
    return [("単勝", str(num if num else d["order"][0]))]

def trio(d, legs):
    m1 = d["order"][0]
    legs = [n for n in legs if n != m1]
    return [("三連複", f"{m1}-{a}-{b}") for a, b in itertools.combinations(sorted(legs), 2)]

def mkt(d, k):
    return [n for n in sorted(d["odds"], key=lambda x: d["odds"][x]) if n != d["order"][0]][:k]

# (表示名, レース選択, 買い目生成)
PATTERNS = [
    ("乖離単勝ベース(1位7倍+・未勝利除く)", lambda d: FIRE(d), bet_tan),
    ("  +開催2日目以降", lambda d: FIRE(d) and d["day"] and d["day"] >= 2, bet_tan),
    ("★10倍+×上級", lambda d: O1(d) >= 10 and UP(d), bet_tan),
    ("★中距離1301-1900×上級", lambda d: FIRE(d) and UP(d) and d["dist"] and 1301 <= d["dist"] <= 1900, bet_tan),
    ("  中距離1401-1900×上級", lambda d: FIRE(d) and UP(d) and d["dist"] and 1401 <= d["dist"] <= 1900, bet_tan),
    ("  +モデル価値1.30+", lambda d: FIRE(d) and UP(d) and d["dist"] and 1401 <= d["dist"] <= 1900
     and pwin(d) * O1(d) >= 1.30, bet_tan),
    ("★上級(2勝+)", lambda d: FIRE(d) and UP(d), bet_tan),
    ("★ダート", lambda d: FIRE(d) and d["surface"] == "ダ", bet_tan),
    ("★ダ×上級", lambda d: FIRE(d) and d["surface"] == "ダ" and UP(d), bet_tan),
    ("★多頭15+", lambda d: FIRE(d) and d["field"] and d["field"] >= 15, bet_tan),
    ("★モデル価値1.6+", lambda d: FIRE(d) and pwin(d) * O1(d) >= 1.6, bet_tan),
    ("★1人気モデル売り(5位以下)", lambda d: FIRE(d) and
     {n: i+1 for i, n in enumerate(d["order"])}.get(min(d["odds"], key=lambda x: d["odds"][x]), 99) >= 5, bet_tan),
    ("✕開催初日", lambda d: FIRE(d) and d["day"] == 1, bet_tan),
    ("✕未勝利の1位単勝", lambda d: O1(d) >= 7.0 and MAIDEN(d), bet_tan),
    ("✕中距離×条件級", lambda d: FIRE(d) and d["dist"] and 1401 <= d["dist"] <= 1900
     and d["tier"] and d["tier"] < 6, bet_tan),
    ("✕芝", lambda d: FIRE(d) and d["surface"] == "芝", bet_tan),
    ("未勝利 g12>=0.6×2位5-10倍 → 2位単勝", lambda d: MAIDEN(d) and len(d["order"]) > 1
     and (max(float(v) for v in d["scores"].values()) - sorted((float(v) for v in d["scores"].values()), reverse=True)[1]) >= 0.6
     and 5.0 <= d["odds"].get(d["order"][1], 0) < 10.0,
     lambda d: bet_tan(d, d["order"][1])),
    ("三連複 軸10-30倍×市場1-3(3点)", lambda d: FIRE(d) and 10 <= O1(d) <= 30 and (not d["dist"] or d["dist"] <= 1900),
     lambda d: trio(d, mkt(d, 3))),
    ("★三連複 軸10-30倍×市場1-4(6点)", lambda d: FIRE(d) and 10 <= O1(d) <= 30 and (not d["dist"] or d["dist"] <= 1900),
     lambda d: trio(d, mkt(d, 4))),
    ("★三連複 混合紐×中距離", lambda d: FIRE(d) and 10 <= O1(d) <= 30 and d["dist"] and 1401 <= d["dist"] <= 1900,
     lambda d: trio(d, list(dict.fromkeys([n for n in d["order"][1:4] if n in set(mkt(d, 5))] + mkt(d, 2))))),
    ("ワイド 軸-モデル2位×芝", lambda d: FIRE(d) and d["surface"] == "芝" and len(d["order"]) > 1,
     lambda d: [("ワイド", f"{d['order'][0]}-{d['order'][1]}")]),
]

def run(sel, mk):
    dv = dict(b=0, p=0, h=0); cf = dict(b=0, p=0, h=0); mx = 0
    for d in sel:
        bs = mk(d)
        if not bs: continue
        t = dv if d["month"] <= "202603" else cf
        for kind, key in bs:
            t["b"] += 100
            v = pay(d, kind, key)
            if v:
                t["p"] += v; t["h"] += 1; mx = max(mx, v)
    n = (dv["b"] + cf["b"]) // 100; hits = dv["h"] + cf["h"]
    if not n: return None
    tot = dv["p"] + cf["p"]
    return dict(n=n, hits=hits, roi=100.0*tot/(n*100),
                dev=100.0*dv["p"]/dv["b"] if dv["b"] else 0,
                conf=100.0*cf["p"]/cf["b"] if cf["b"] else 0,
                devn=dv["b"]//100, confn=cf["b"]//100,
                excl=100.0*(tot-mx)/((n-1)*100) if n > 1 else 0)

md = sys.argv[1:2] == ["--md"]
res = []
for name, cond, mk in PATTERNS:
    r = run([d for d in rows if cond(d)], mk)
    if r: res.append((name, r))

if md:
    print("| パターン | 通算ROI | n | 的中 | dev | conf | 最大的中除外 |")
    print("|---|---|---|---|---|---|---|")
    for name, r in res:
        print(f"| {name} | **{r['roi']:.1f}%** | {r['n']} | {r['hits']} | "
              f"{r['dev']:.1f}%/{r['devn']} | {r['conf']:.1f}%/{r['confn']} | {r['excl']:.1f}% |")
else:
    print(f"{'パターン':<38}{'通算':>8}{'n':>6}{'的中':>5}{'dev':>9}{'conf':>9}{'除外後':>9}")
    print("-" * 86)
    for name, r in res:
        print(f"{name:<38}{r['roi']:7.1f}%{r['n']:6d}{r['hits']:5d}"
              f"{r['dev']:8.1f}%{r['conf']:8.1f}%{r['excl']:8.1f}%")
