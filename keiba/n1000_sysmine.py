# -*- coding: utf-8 -*-
"""新潟芝1000直: システム(V3得点)ベース×枠の合成パターン採掘。
   n1000_races.jsonl(結果+オッズ+枠) × n1000_model.jsonl(V3遡及得点) を結合し、
   「モデル順位」を主軸に枠・g12・オッズ帯を重ねてdev(2021-23)/conf(2024-25)で評価。
   人気順位は選定条件に使わない(=システム主軸)。オッズは払戻計算のみ。"""
import json, itertools

res = {}
for l in open("n1000_races.jsonl", encoding="utf-8"):
    d = json.loads(l); res[d["rid"]] = d
mod = {}
for l in open("n1000_model.jsonl", encoding="utf-8"):
    d = json.loads(l); mod[d["rid"]] = d

rows = []
for rid, r in res.items():
    m = mod.get(rid)
    if not m:
        continue
    vr = {x["num"]: i + 1 for i, x in enumerate(m["model"])}
    pw = {x["num"]: x["pwin"] for x in m["model"]}
    for h in r["rows"]:
        if h["odds"] is None:
            continue
        rows.append(dict(rid=rid, date=r["date"], field=r["field"], waku=h["waku"],
                         num=h["num"], odds=h["odds"], pop=h["pop"],
                         win=1 if h["fin"] == "1" else 0,
                         top3=1 if h["fin"] in ("1", "2", "3") else 0,
                         vrank=vr.get(h["num"], 99), pwin=pw.get(h["num"], 0),
                         g12=m["g12"]))
print(f"結合: {len(mod)}R / 出走{len(rows)}頭  期間{min(r['date'] for r in rows)}-{max(r['date'] for r in rows)}")

DEV = lambda x: x["date"] < "20240101"

def roi(sel):
    hit = [r for r in sel if r["win"]]
    n = len(sel)
    tot = sum(r["odds"] * 100 for r in hit)
    mx = max((r["odds"] * 100 for r in hit), default=0)
    return n, len(hit), (100.0 * tot / (n * 100) if n else 0), \
        (100.0 * (tot - mx) / ((n - 1) * 100) if n > 1 else 0)

# --- モデル順位の基礎性能(このコースでV3は使えるのか) ---
print("\n=== モデル順位別の基礎性能(全期間) ===")
for k in range(1, 7):
    sel = [r for r in rows if r["vrank"] == k]
    n, h, ro, _ = roi(sel)
    t3 = sum(r["top3"] for r in sel)
    print(f"モデル{k}位: n={n:3d} 勝{h:2d}({100*h/n:4.1f}%) 複勝圏{100*t3/n:4.1f}% 単勝ROI{ro:6.1f}%")

WAKU = {"外7-8": (7, 8), "中4-6": (4, 6), "内1-3": (1, 3), "枠不問": (1, 8)}
VR = {"1位": (1, 1), "1-2位": (1, 2), "2位": (2, 2), "1-3位": (1, 3),
      "2-3位": (2, 3), "4-6位": (4, 6), "順位不問": (1, 99)}
OD = {"~4.9": (0, 4.9), "5-9.9": (5, 9.9), "10-19.9": (10, 19.9),
      "20+": (20, 9999), "~9.9": (0, 9.9), "オッズ不問": (0, 9999)}
G12 = {"g12>=0.3": (0.3, 9), "g12<0.3": (-9, 0.3), "g12不問": (-9, 9)}

out = []
for (wn, wk), (vn, vv), (on, oo), (gn, gg) in itertools.product(
        WAKU.items(), VR.items(), OD.items(), G12.items()):
    sel = [r for r in rows if wk[0] <= r["waku"] <= wk[1] and vv[0] <= r["vrank"] <= vv[1]
           and oo[0] <= r["odds"] <= oo[1] and gg[0] <= r["g12"] < gg[1]]
    if len(sel) < 40:
        continue
    dn, dh, dr, _ = roi([r for r in sel if DEV(r)])
    cn, ch, cr, _ = roi([r for r in sel if not DEV(r)])
    n, hits, ar, exr = roi(sel)
    if hits < 5:
        continue
    ok = dr >= 110 and cr >= 100 and exr >= 95
    out.append(dict(rule=f"{wn}×モデル{vn}×{on}×{gn}", n=n, hits=hits, all_roi=ar,
                    dev=f"{dr:.1f}%/{dn}", conf=f"{cr:.1f}%/{cn}", excl=exr, ok=ok))
out.sort(key=lambda x: -x["all_roi"])
print("\n=== 合格(dev>=110 & conf>=100 & n>=40 & hits>=5 & 除外後>=95) ===")
for x in out:
    if x["ok"]:
        print(f"◎ {x['rule']:<40} 通算{x['all_roi']:6.1f}% n={x['n']:3d} hits={x['hits']:2d} "
              f"dev{x['dev']} conf{x['conf']} 除外{x['excl']:.1f}%")
print("\n=== 上位15(参考) ===")
for x in out[:15]:
    print(f"{'◎' if x['ok'] else ' '} {x['rule']:<40} 通算{x['all_roi']:6.1f}% n={x['n']:3d} "
          f"hits={x['hits']:2d} dev{x['dev']} conf{x['conf']} 除外{x['excl']:.1f}%")
json.dump(out, open("n1000_sysmine_result.json", "w", encoding="utf-8"), ensure_ascii=False)
print("\nWROTE n1000_sysmine_result.json")
