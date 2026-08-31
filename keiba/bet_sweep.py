# -*- coding: utf-8 -*-
"""買い目バリエーション総当たり: 乖離ベース(モデル1位7倍+)のレースで
   券種(単勝/ワイド/三連複)×紐構成×条件(距離/馬場/クラス/頭数)を全部試す。
   dev(<=202603)/conf(>=202604) 2分割・各点100円・合格=dev>=110&conf>=100&n>=40&hits>=5&除外後>=95"""
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
    if not (d.get("order") and d.get("odds")):
        continue
    d["odds"] = {int(k): v for k, v in d["odds"].items() if v}
    rows.append(d)
print(f"races={len(rows)}")

def payget(d, kind, key):
    p = (d.get("payout") or {}).get(kind) or {}
    for k, v in p.items():
        if set(str(k).replace(" ", "").split("-")) == set(str(key).replace(" ", "").split("-")):
            return v
    return 0

def base_fire(d):
    o = d["odds"]; m1 = d["order"][0]
    return m1 in o and o[m1] >= 7.0

def mkt(d, k, ex=()):
    return [n for n in sorted(d["odds"], key=lambda x: d["odds"][x]) if n not in ex][:k]

# --- 買い目コンストラクタ: レース -> [(kind, key, 点数)] ---
def bets_tan(d):
    return [("単勝", str(d["order"][0]))]

def bets_wide_fav(d):
    m1 = d["order"][0]; f = mkt(d, 1, (m1,))
    return [("ワイド", f"{m1}-{f[0]}")] if f else []

def bets_wide_m2(d):
    return [("ワイド", f"{d['order'][0]}-{d['order'][1]}")] if len(d["order"]) > 1 else []

def bets_wide_top2(d):
    m1 = d["order"][0]; f = mkt(d, 2, (m1,))
    return [("ワイド", f"{m1}-{x}") for x in f] if len(f) == 2 else []

def bets_trio3(d):  # 既知ベースC
    m1 = d["order"][0]; f = mkt(d, 3, (m1,))
    if len(f) < 3: return []
    return [("三連複", f"{m1}-{a}-{b}") for a, b in itertools.combinations(f, 2)]

def bets_trio_m2(d):  # 紐=市場1-2人気+モデル2位
    m1 = d["order"][0]; f = mkt(d, 2, (m1,))
    m2 = d["order"][1] if len(d["order"]) > 1 else None
    ps = list(dict.fromkeys(f + ([m2] if m2 and m2 != m1 else [])))
    if len(ps) < 3: return []
    return [("三連複", f"{m1}-{a}-{b}") for a, b in itertools.combinations(ps, 2)]

def bets_trio4(d):  # 紐=市場1-4人気(6点)
    m1 = d["order"][0]; f = mkt(d, 4, (m1,))
    if len(f) < 4: return []
    return [("三連複", f"{m1}-{a}-{b}") for a, b in itertools.combinations(f, 2)]

def bets_trio_dark(d):  # 紐=市場1-2人気 + モデル上位×人気薄1頭(取り逃し対策)
    m1 = d["order"][0]; o = d["odds"]; f = mkt(d, 2, (m1,))
    dark = [n for n in d["order"][1:5] if n in o and o[n] >= 15 and n not in f]
    ps = f + dark[:1]
    if len(ps) < 3: return []
    return [("三連複", f"{m1}-{a}-{b}") for a, b in itertools.combinations(ps, 2)]

BETS = {"単勝": bets_tan, "ワイド軸-1人気": bets_wide_fav, "ワイド軸-モデル2位": bets_wide_m2,
        "ワイド軸-市場1,2(2点)": bets_wide_top2, "三連複紐=市場1-3(3点)": bets_trio3,
        "三連複紐=市場1-2+モデル2位(3点)": bets_trio_m2, "三連複紐=市場1-4(6点)": bets_trio4,
        "三連複紐=市場1-2+モデル上位穴15倍+(3点)": bets_trio_dark}

CONDS = {
    "無条件": lambda d: True,
    "中距離1401-1900": lambda d: d["dist"] and 1401 <= d["dist"] <= 1900,
    "短距離~1300": lambda d: d["dist"] and d["dist"] <= 1300,
    "長距離1901+": lambda d: d["dist"] and d["dist"] >= 1901,
    "ダ": lambda d: d["surface"] == "ダ",
    "芝": lambda d: d["surface"] == "芝",
    "上級tier6+": lambda d: d["tier"] and d["tier"] >= 6,
    "中距離×上級": lambda d: d["dist"] and 1401 <= d["dist"] <= 1900 and d["tier"] and d["tier"] >= 6,
    "ダ×上級": lambda d: d["surface"] == "ダ" and d["tier"] and d["tier"] >= 6,
    "道悪(稍重以上)": lambda d: d.get("baba") in ("稍重", "重", "不良"),
    "良馬場": lambda d: d.get("baba") == "良",
    "多頭15+": lambda d: d["field"] and d["field"] >= 15,
    "軸10-30倍": lambda d: 10 <= d["odds"][d["order"][0]] <= 30,
    "軸10-30倍×中距離": lambda d: 10 <= d["odds"][d["order"][0]] <= 30 and d["dist"] and 1401 <= d["dist"] <= 1900,
    "軸7-15倍": lambda d: 7 <= d["odds"][d["order"][0]] <= 15,
}

fires = [d for d in rows if base_fire(d) and not (d["tier"] and d["tier"] >= 10)]
print(f"乖離発火(未勝利除く)={len(fires)}R")

out = []
for bn, bf in BETS.items():
    for cn, cf in CONDS.items():
        dev = dict(bet=0, pay=0, hit=0, mx=0); conf = dict(bet=0, pay=0, hit=0, mx=0)
        for d in fires:
            if not cf(d): continue
            bs = bf(d)
            if not bs: continue
            tgt = dev if d["month"] <= "202603" else conf
            for kind, key in bs:
                tgt["bet"] += 100
                p = payget(d, kind, key)
                if p:
                    tgt["pay"] += p; tgt["hit"] += 1; tgt["mx"] = max(tgt["mx"], p)
        n = (dev["bet"] + conf["bet"]) // 100; hits = dev["hit"] + conf["hit"]
        if n < 40 or hits < 5: continue
        dr = 100.0 * dev["pay"] / dev["bet"] if dev["bet"] else 0
        cr = 100.0 * conf["pay"] / conf["bet"] if conf["bet"] else 0
        tot = dev["pay"] + conf["pay"]; mx = max(dev["mx"], conf["mx"])
        ar = 100.0 * tot / (n * 100); ex = 100.0 * (tot - mx) / ((n - 1) * 100)
        ok = dr >= 110 and cr >= 100 and ex >= 95
        out.append(dict(rule=f"{bn} × {cn}", n=n, hits=hits, all_roi=ar, dev_roi=dr,
                        conf_roi=cr, dev_n=dev["bet"] // 100, conf_n=conf["bet"] // 100,
                        excl=ex, ok=ok))
out.sort(key=lambda x: -x["all_roi"])
print("\n=== 合格 ===")
for x in out:
    if x["ok"]:
        print(f"◎ {x['rule']:<46} 通算{x['all_roi']:6.1f}% n={x['n']:4d} hits={x['hits']:3d} "
              f"dev{x['dev_roi']:6.1f}%/{x['dev_n']} conf{x['conf_roi']:6.1f}%/{x['conf_n']} 除外{x['excl']:6.1f}%")
print("\n=== 上位25(参考) ===")
for x in out[:25]:
    print(f"{'◎' if x['ok'] else ' '} {x['rule']:<46} 通算{x['all_roi']:6.1f}% n={x['n']:4d} hits={x['hits']:3d} "
          f"dev{x['dev_roi']:6.1f}% conf{x['conf_roi']:6.1f}% 除外{x['excl']:6.1f}%")
json.dump(out, open("bet_sweep_result.json", "w", encoding="utf-8"), ensure_ascii=False)
print("\nWROTE bet_sweep_result.json")
