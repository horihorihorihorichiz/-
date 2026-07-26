# -*- coding: utf-8 -*-
"""実装済み全パターンを馬場(良/稍/重不)で分割してROIを実測する。

   目的: 「良で測った数字を道悪の日にもそのまま使う」問題の解消。
   方針(RULES準拠): 抑止を足すのは 道悪n>=15 かつ 道悪ROI<70% かつ 良側が明確に上、
   のように差が大きい場合だけ。n が薄いセルで gate を増やすのは過学習(7/25の
   道悪フィルタ不採用 dev313.8/conf55.6 の教訓)なので、警告表示に留める。

   usage: python3 baba_impact.py
"""
import json
from collections import defaultdict

JRA_CODE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
            "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def key_of(nums):
    return "-".join(str(x) for x in sorted(nums))


def load():
    rows = []
    for l in open("wf_preds.jsonl", encoding="utf-8"):
        d = json.loads(l)
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        o = [int(x) for x in d["order"]]
        rid = d["rid"]
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        sc = d.get("scores") or {}
        sc = {int(k): float(v) for k, v in sc.items()}
        so = sorted(sc, key=lambda n: -sc[n])
        g12 = sc[so[0]] - sc[so[1]] if len(so) >= 2 else 0
        sp15 = sc[so[0]] - sc[so[4]] if len(so) >= 5 else 99
        b = (d.get("baba") or "?").strip()
        rows.append(dict(
            m=d["month"], rid=rid, order=o, odds=odds, pay=pay,
            tier=int(d["tier"]) if d.get("tier") is not None else None,
            surface=d.get("surface"), dist=int(d.get("dist") or 0),
            field=int(d.get("field") or len(o)), day=int(rid[8:10]),
            venue=d.get("venue") or JRA_CODE.get(rid[4:6], ""),
            baba=("良" if b == "良" else ("稍" if b in ("稍", "稍重") else
                                         ("重不" if b in ("重", "不", "不良") else "?"))),
            g12=g12, sp15=sp15,
            win=int(list(pay["単勝"].keys())[0])))
    return rows


def mkret(r, kind, sel):
    p = r["pay"].get(kind) or {}
    if kind == "単勝":
        return float(p.get(str(sel), 0))
    return float(p.get(key_of(sel), 0))


def pop1(r):
    t1 = r["order"][0]
    mk = sorted([n for n in r["order"] if n in r["odds"]], key=lambda n: r["odds"][n])
    return (mk.index(t1) + 1) if t1 in mk else 99


# ── 実装済みパターンの発火条件とベット(patterns.pyと同一定義) ──────────────
def o1(r):
    return r["odds"].get(r["order"][0], 0)


def kairi(r):
    return pop1(r) >= 4 and o1(r) >= 7 and (r["tier"] or 0) < 10 and r["day"] >= 2


PATTERNS = [
    ("◎◎◎10倍+×1勝クラス 単勝", lambda r: kairi(r) and r["tier"] == 6 and o1(r) >= 10,
     lambda r: mkret(r, "単勝", r["order"][0]) if r["order"][0] == r["win"] else 0),
    ("◎◎◎実用コア(7倍+×11-17頭×1勝×2日+) 単勝",
     lambda r: kairi(r) and r["tier"] == 6 and 11 <= r["field"] <= 17
     and not (r["surface"] == "芝" and 1800 <= r["dist"] <= 1999),
     lambda r: mkret(r, "単勝", r["order"][0]) if r["order"][0] == r["win"] else 0),
    ("◎◎メイン4場×1勝×2日+ 単勝",
     lambda r: kairi(r) and r["tier"] == 6 and r["venue"] in ("東京", "中山", "京都", "阪神"),
     lambda r: mkret(r, "単勝", r["order"][0]) if r["order"][0] == r["win"] else 0),
    ("◎◎中距離×1勝クラス 単勝",
     lambda r: kairi(r) and r["tier"] == 6 and 1301 <= r["dist"] <= 1900,
     lambda r: mkret(r, "単勝", r["order"][0]) if r["order"][0] == r["win"] else 0),
    ("◎三連複 軸10-30倍×市場1-4(6点)",
     lambda r: kairi(r) and 10 <= o1(r) <= 30 and len(r["order"]) >= 4,
     None),   # 特殊: 下で個別実装
    ("◎◎芝馬連1600-1800×g12>=0.3",
     lambda r: r["surface"] == "芝" and 1600 <= r["dist"] <= 1800 and r["g12"] >= 0.3
     and len(r["order"]) >= 2,
     lambda r: mkret(r, "馬連", r["order"][:2])),
    ("◎◎芝×10頭以下×g12 0.2-0.6 馬連",
     lambda r: r["surface"] == "芝" and r["field"] <= 10 and 0.2 <= r["g12"] < 0.6
     and len(r["order"]) >= 2,
     lambda r: mkret(r, "馬連", r["order"][:2])),
    ("◎上位平坦×12頭以下×ダ 馬連",
     lambda r: r["surface"] == "ダ" and r["field"] <= 12 and r["sp15"] < 1.0
     and r["day"] >= 2 and len(r["order"]) >= 2,
     lambda r: mkret(r, "馬連", r["order"][:2])),
    ("◎未勝利 g12>=0.6×2位5-10倍 単勝",
     lambda r: (r["tier"] or 0) >= 10 and r["g12"] >= 0.6 and len(r["order"]) >= 2
     and 5.0 <= r["odds"].get(r["order"][1], 0) < 10.0,
     lambda r: mkret(r, "単勝", r["order"][1]) if r["order"][1] == r["win"] else 0),
]


def trio6(r):
    """三連複6点: 軸=モデル1位、紐=市場1-4人気(軸除く)から3頭"""
    import itertools
    t1 = r["order"][0]
    mk = [n for n in sorted(r["odds"], key=lambda n: r["odds"][n]) if n != t1][:4]
    tot = 0.0
    npts = 0
    for pair in itertools.combinations(mk, 2):
        npts += 1
        tot += mkret(r, "三連複", [t1, *pair])
    return tot, npts


def main():
    rows = load()
    print(f"WF {len(rows)}R（良{sum(1 for r in rows if r['baba']=='良')} "
          f"稍{sum(1 for r in rows if r['baba']=='稍')} "
          f"重不{sum(1 for r in rows if r['baba']=='重不')}）\n")
    hdr = f"{'パターン':40s} {'馬場':4s} {'n':>4s} {'的中':>3s} {'ROI':>7s} {'dev':>7s} {'conf':>7s}"
    print(hdr)
    print("-" * len(hdr))
    for name, cond, bet in PATTERNS:
        for bb in ("良", "稍", "重不", "全体"):
            sel = [r for r in rows if cond(r) and (bb == "全体" or r["baba"] == bb)]
            if not sel:
                continue
            if bet is None:
                s = h = 0
                ret = 0.0
                dret = ds = cret = cs = 0.0
                for r in sel:
                    t, npts = trio6(r)
                    s += npts * 100
                    ret += t
                    h += t > 0
                    if r["m"] <= "202603":
                        ds += npts*100; dret += t
                    else:
                        cs += npts*100; cret += t
            else:
                s = len(sel) * 100
                rets = [bet(r) for r in sel]
                ret = sum(rets)
                h = sum(1 for x in rets if x > 0)
                dret = sum(x for r, x in zip(sel, rets) if r["m"] <= "202603")
                ds = sum(100 for r in sel if r["m"] <= "202603")
                cret = ret - dret
                cs = s - ds
            roi = ret/s*100 if s else 0
            dv = dret/ds*100 if ds else 0
            cf = cret/cs*100 if cs else 0
            mark = " ←" if bb != "全体" and roi < 70 and len(sel) >= 15 else ""
            print(f"{name:40s} {bb:4s} {len(sel):4d} {h:3d} {roi:6.1f}% {dv:6.1f}% {cf:6.1f}%{mark}")
        print()


if __name__ == "__main__":
    main()
