# -*- coding: utf-8 -*-
"""紐(相手)構成: システム(モデル順位)ベース vs 人気ベース の直接対決。
   軸=乖離発火のモデル1位。紐だけを入れ替えて同一レース集合で比較する。
   dev(<=202603)/conf(>=202604)・各点100円。"""
import ast, itertools, json

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
        rows.append(d)

fires = [d for d in rows if d["order"][0] in d["odds"] and d["odds"][d["order"][0]] >= 7.0
         and not (d["tier"] and d["tier"] >= 10)]
print(f"乖離発火(未勝利除く)={len(fires)}R\n")

def pay(d, kind, key):
    p = (d.get("payout") or {}).get(kind) or {}
    for k, v in p.items():
        if set(str(k).replace(" ", "").split("-")) == set(str(key).split("-")):
            return v
    return 0

def mkt(d, k, ex):
    return [n for n in sorted(d["odds"], key=lambda x: d["odds"][x]) if n not in ex][:k]

def sysleg(d, k, ex):
    return [n for n in d["order"] if n not in ex][:k]

# 紐構成: (名前, 紐を返す関数)
LEGS = {
    "人気: 市場1-3人気(3点)": lambda d, m1: mkt(d, 3, (m1,)),
    "人気: 市場1-4人気(6点)": lambda d, m1: mkt(d, 4, (m1,)),
    "★システム: モデル2-4位(3点)": lambda d, m1: sysleg(d, 3, (m1,)),
    "★システム: モデル2-5位(6点)": lambda d, m1: sysleg(d, 4, (m1,)),
    "★システム: モデル2-6位(10点)": lambda d, m1: sysleg(d, 5, (m1,)),
    "混合: モデル2-3位+市場1人気(3点)": lambda d, m1: list(dict.fromkeys(
        sysleg(d, 2, (m1,)) + mkt(d, 1, (m1,)))),
    "混合: モデル2-4位+市場1人気(6点)": lambda d, m1: list(dict.fromkeys(
        sysleg(d, 3, (m1,)) + mkt(d, 1, (m1,)))),
    "混合: モデル2-3位∩市場5人気内+市場1-2(可変)": lambda d, m1: list(dict.fromkeys(
        [n for n in sysleg(d, 3, (m1,)) if mkt(d, 5, (m1,)).count(n)] + mkt(d, 2, (m1,)))),
}

CONDS = {
    "全発火": lambda d: True,
    "軸10-30倍": lambda d: 10 <= d["odds"][d["order"][0]] <= 30,
    "軸10-30倍×中距離": lambda d: 10 <= d["odds"][d["order"][0]] <= 30 and d["dist"] and 1401 <= d["dist"] <= 1900,
    "多頭15+": lambda d: bool(d["field"] and d["field"] >= 15),
    "上級": lambda d: bool(d["tier"] and d["tier"] >= 6),
}

print(f"{'紐構成':<40}{'条件':<18}{'通算':>8}{'dev':>9}{'conf':>9}{'n':>6}{'hits':>6}{'除外後':>9}")
print("-" * 106)
best = []
for cn, cf in CONDS.items():
    sub = [d for d in fires if cf(d)]
    for ln, lf in LEGS.items():
        dv = dict(b=0, p=0, h=0, mx=0); cn2 = dict(b=0, p=0, h=0, mx=0)
        for d in sub:
            m1 = d["order"][0]
            legs = [n for n in lf(d, m1) if n != m1]
            if len(legs) < 3:
                continue
            t = dv if d["month"] <= "202603" else cn2
            for a, b in itertools.combinations(sorted(legs), 2):
                t["b"] += 100
                v = pay(d, "三連複", f"{m1}-{a}-{b}")
                if v:
                    t["p"] += v; t["h"] += 1; t["mx"] = max(t["mx"], v)
        n = (dv["b"] + cn2["b"]) // 100; hits = dv["h"] + cn2["h"]
        if n < 40 or hits < 3:
            continue
        dr = 100.0 * dv["p"] / dv["b"] if dv["b"] else 0
        cr = 100.0 * cn2["p"] / cn2["b"] if cn2["b"] else 0
        tot = dv["p"] + cn2["p"]; mx = max(dv["mx"], cn2["mx"])
        ar = 100.0 * tot / (n * 100); ex = 100.0 * (tot - mx) / ((n - 1) * 100)
        mark = "◎" if (dr >= 110 and cr >= 100 and ex >= 95) else " "
        print(f"{mark}{ln:<39}{cn:<18}{ar:7.1f}%{dr:8.1f}%{cr:8.1f}%{n:6d}{hits:6d}{ex:8.1f}%")
        best.append((ar, ln, cn, n, hits, dr, cr, ex))
    print()
print("=== 同一条件での システム紐 vs 人気紐 (点数を揃えた比較) ===")
for cn in CONDS:
    p3 = [b for b in best if b[1].startswith("人気: 市場1-3") and b[2] == cn]
    s3 = [b for b in best if b[1].startswith("★システム: モデル2-4") and b[2] == cn]
    p6 = [b for b in best if b[1].startswith("人気: 市場1-4") and b[2] == cn]
    s6 = [b for b in best if b[1].startswith("★システム: モデル2-5") and b[2] == cn]
    if p3 and s3:
        print(f" {cn:<18} 3点: 人気{p3[0][0]:6.1f}% vs システム{s3[0][0]:6.1f}%  → {'システム勝ち' if s3[0][0] > p3[0][0] else '人気勝ち'}")
    if p6 and s6:
        print(f" {cn:<18} 6点: 人気{p6[0][0]:6.1f}% vs システム{s6[0][0]:6.1f}%  → {'システム勝ち' if s6[0][0] > p6[0][0] else '人気勝ち'}")
