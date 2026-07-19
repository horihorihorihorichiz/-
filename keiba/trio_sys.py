# -*- coding: utf-8 -*-
"""三連複ながし×システム側条件のグリッドスイープ（7/19ユーザー要望:
   「4番人気だから、は嫌い。システム何位以上とか、モデル側の量で条件を切れ」）。

   軸=モデル1位(乖離ゾーン)固定。紐の選び方 × システム側フィルタの全組合せを
   二段階(dev<202605 / conf>=202605)で検証。
   使う量: モデル順位, 生スコアz, スコア差(g12=1-2位差, g34=3-4位差=「3頭の崖」),
           モデル価値 p1*オッズ, 紐のスコア密度。
"""
import json, itertools, collections, math

recs = [json.loads(l) for l in open("wf_preds.jsonl", encoding="utf-8")]

def tp(pay, c):
    return pay.get("三連複", {}).get("-".join(str(x) for x in sorted(c)), 0)

# ---- 紐セット定義（システム駆動）----
def partners(kind, order, odds, mkt, t1):
    m = [h for h in order if h != t1]
    k = [h for h in mkt if h != t1]
    if kind == "市場1-3(基準)":
        return k[:3]
    if kind == "モデル2-4位":
        return m[:3]
    if kind == "モデル2-5位の内オッズ最短3頭":
        c = sorted(m[:4], key=lambda h: odds.get(h, 999))
        return c[:3]
    if kind == "モデルtop5∩市場top5→人気順3頭":
        both = [h for h in k[:5] if h in set(m[:4])]
        return both[:3]
    if kind == "モデル2-6位の内市場6人気内3頭":
        c = [h for h in m[:5] if h in set(k[:6])]
        return c[:3]
    return []

# ---- システム側フィルタ ----
def softmax_p(scores, t1):
    vs = list(scores.values())
    mx = max(vs)
    ex = {h: math.exp(v - mx) for h, v in scores.items()}
    z = sum(ex.values())
    return ex[t1] / z

def filters(sc_list, scores, t1, o1, order):
    """sc_list=モデル順スコア降順list"""
    g12 = sc_list[0] - sc_list[1] if len(sc_list) > 1 else 0
    g34 = sc_list[2] - sc_list[3] if len(sc_list) > 3 else 0
    g45 = sc_list[3] - sc_list[4] if len(sc_list) > 4 else 0
    p1 = softmax_p(scores, t1)
    val = p1 * o1
    return {
        "F0.なし": True,
        "F1.モデル価値p1×o1≥1.0": val >= 1.0,
        "F2.モデル価値p1×o1≥1.3": val >= 1.3,
        "F3.首位確信g12≥0.3": g12 >= 0.3,
        "F4.3頭の崖g34≥0.3": g34 >= 0.3,
        "F5.3頭の崖g34≥0.5": g34 >= 0.5,
        "F6.混戦g12<0.15": g12 < 0.15,
        "F7.4頭の崖g45≥0.3": g45 >= 0.3,
    }

tests = collections.defaultdict(lambda: {"dev": [0, 0, 0], "conf": [0, 0, 0], "hits": []})

def book(name, mo, cost, ret, rid, o1):
    ph = "dev" if mo < "202605" else "conf"
    t = tests[name]
    t[ph][0] += cost
    t[ph][1] += ret
    t[ph][2] += 1
    if ret:
        t["hits"].append((mo, rid, o1, ret))

for r in recs:
    odds = {int(k): v for k, v in r["odds"].items() if v}
    order = r["order"]
    scores = {int(k): v for k, v in r.get("scores", {}).items()}
    if not order or len(odds) < 6 or len(scores) < 6:
        continue
    mkt = sorted(odds, key=lambda h: odds[h])
    t1 = order[0]
    o1 = odds.get(t1, 0)
    if not (10 <= o1 <= 30):        # 主戦場=乖離軸10-30倍に固定
        continue
    if (r.get("dist") or 0) > 1900:
        continue
    sc_list = sorted(scores.values(), reverse=True)
    fl = filters(sc_list, scores, t1, o1, order)
    mo, pay, rid = r["month"], r["payout"], r["rid"]
    for kind in ["市場1-3(基準)", "モデル2-4位", "モデル2-5位の内オッズ最短3頭",
                 "モデルtop5∩市場top5→人気順3頭", "モデル2-6位の内市場6人気内3頭"]:
        pt = partners(kind, order, odds, mkt, t1)
        if len(pt) < 3:
            continue
        prs = list(itertools.combinations(pt[:3], 2))
        ret = sum(tp(pay, (t1, a, b)) for a, b in prs)
        cost = len(prs) * 100
        for fname, on in fl.items():
            if on:
                book(f"{kind} × {fname}", mo, cost, ret, rid, o1)

rows = []
for name, t in tests.items():
    d, c = t["dev"], t["conf"]
    if not d[0] or not c[0]:
        continue
    droi, croi = d[1]/d[0], c[1]/c[0]
    tot = (d[1]+c[1])/(d[0]+c[0])
    ok = droi >= 1.03 and d[2] >= 20 and croi >= 1.00 and c[2] >= 8
    rows.append((ok, tot, name, droi, d[2], croi, c[2], len(t["hits"])))
rows.sort(key=lambda x: (-x[0], -x[1]))
print(f"母集団: 乖離軸10-30倍×≤1900m\n")
print("★=二段階通過(dev≥103%×20R+ / conf≥100%×8R+)\n")
for ok, tot, name, droi, dn, croi, cn, nh in rows:
    mark = "★" if ok else " "
    print(f"{mark}{name:44s} 発見{100*droi:6.1f}%({dn:3d}R) 確認{100*croi:6.1f}%({cn:3d}R) 通算{100*tot:6.1f}% 的中{nh}")
print()
for name, t in sorted(tests.items(), key=lambda kv: -((kv[1]['dev'][1]+kv[1]['conf'][1])/(kv[1]['dev'][0]+kv[1]['conf'][0]) if kv[1]['dev'][0] and kv[1]['conf'][0] else 0))[:3]:
    print(f"---- {name} 的中内訳 ----")
    for mo, rid, o1, ret in t["hits"]:
        print(f"  {mo} {rid} 軸{o1}倍 → {ret}円")
