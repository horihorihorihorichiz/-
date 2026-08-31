# -*- coding: utf-8 -*-
"""g12(得点1-2位差)系パターンを、新エンジンのWF予測で再採掘する。

   patterns.py のg12閾値はV3の生スコアで採掘した値。エンジンを替えると得点の
   スケールと分布が変わるため、**そのままの閾値は事前情報の不一致**になる。
   このスクリプトは wf_preds_<engine>.jsonl から各g12系パターンの閾値を引き直し、
   RULES準拠のゲート(dev≥110 ∧ conf≥100 ∧ n≥40 ∧ hits≥5 ∧ 最大的中除外≥95)で
   合否を判定する。エンジン切替は「全キーパターンがここで再確立できた時」だけ。

   usage: python3 remine_g12.py wf_preds_v5s.jsonl [--baseline wf_preds.jsonl]
"""
import argparse, itertools, json

JRA_CODE = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
            "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}
MAIN4 = ("東京", "中山", "京都", "阪神")


def key_of(nums):
    return "-".join(str(x) for x in sorted(nums))


def load(path):
    rows = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        o = [int(x) for x in d["order"]]
        sc = d["scores"]
        sc = ([float(x) for x in sc] if isinstance(sc, list)
              else [float(sc[str(n)]) for n in o])
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        rid = d["rid"]
        rows.append(dict(
            m=d.get("month") or rid[:6], order=o, pay=pay, odds=odds,
            g12=sc[0]-sc[1] if len(sc) > 1 else 0,
            sp15=sc[0]-sc[4] if len(sc) > 4 else 99,
            tier=d.get("tier"), surface=d.get("surface"),
            dist=int(d.get("dist") or 0), field=int(d.get("field") or len(o)),
            day=int(rid[8:10]), baba=(d.get("baba") or "").strip(),
            venue=d.get("venue") or JRA_CODE.get(rid[4:6], ""),
            win=int(list(pay["単勝"].keys())[0])))
    return rows


def settle(sel, bet):
    if not sel:
        return None
    rets = [bet(r) for r in sel]
    s = len(rets)*100
    ret = sum(rets)
    hits = sum(1 for x in rets if x > 0)
    dv = [(x, r) for x, r in zip(rets, sel) if r["m"] <= "202603"]
    cf = [(x, r) for x, r in zip(rets, sel) if r["m"] > "202603"]
    dev = sum(x for x, _ in dv)/(len(dv)*100)*100 if dv else 0
    conf = sum(x for x, _ in cf)/(len(cf)*100)*100 if cf else 0
    mx = max(rets) if rets else 0
    excl = (ret-mx)/(s-100)*100 if s > 100 else 0
    ok = (dev >= 110 and conf >= 100 and len(sel) >= 40 and hits >= 5 and excl >= 95)
    return dict(n=len(sel), hits=hits, roi=ret/s*100, dev=dev, conf=conf, excl=excl, ok=ok)


def bet_umaren12(r):
    return float((r["pay"].get("馬連") or {}).get(key_of(r["order"][:2]), 0))


def bet_trio123(r):
    return float((r["pay"].get("三連複") or {}).get(key_of(r["order"][:3]), 0))


def bet_tan2(r):
    t2 = r["order"][1]
    return float((r["pay"].get("単勝") or {}).get(str(t2), 0)) if t2 == r["win"] else 0


def sweep(rows, name, base, bet, grids):
    """grids: {param_label: [(desc, extra_filter)]} の全組合せを走査"""
    print(f"\n■ {name}")
    results = []
    for combo in itertools.product(*grids):
        f = lambda r, combo=combo: base(r) and all(g[1](r) for g in combo)
        st = settle([r for r in rows if f(r)], bet)
        if not st:
            continue
        label = " × ".join(g[0] for g in combo)
        results.append((st["ok"], st["roi"], label, st))
    results.sort(key=lambda x: (-x[0], -x[1]))
    for ok, roi, label, st in results[:8]:
        mark = "✅" if ok else "  "
        print(f"  {mark} {label:42s} ROI{roi:6.1f}% n={st['n']:3d} hits{st['hits']:3d} "
              f"dev{st['dev']:6.1f}/conf{st['conf']:6.1f} 除外{st['excl']:6.1f}")
    best_ok = next((x for x in results if x[0]), None)
    return best_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--baseline", default=None)
    a = ap.parse_args()

    for path in ([a.baseline] if a.baseline else []) + [a.path]:
        rows = load(path)
        print(f"\n{'='*70}\n### {path} ({len(rows)}R)\n{'='*70}")
        g12s = sorted(r["g12"] for r in rows)
        qs = [g12s[int(len(g12s)*q)] for q in (0.5, 0.7, 0.8, 0.9)]
        print(f"g12分布: 中央値{qs[0]:.3f} p70={qs[1]:.3f} p80={qs[2]:.3f} p90={qs[3]:.3f}")

        founds = {}
        founds["芝馬連1600-1800"] = sweep(
            rows, "芝馬連1600-1800×自信(g12) [V3実績187.5%]",
            lambda r: (r["surface"] == "芝" and 1600 <= r["dist"] <= 1800
                       and not (r["tier"] or 0) >= 10 and len(r["order"]) >= 2),
            bet_umaren12,
            [[(f"g12>={th:.2f}", lambda r, th=th: r["g12"] >= th)
              for th in (0.2, 0.3, 0.4, qs[1], qs[2])]])

        founds["芝10頭以下馬連"] = sweep(
            rows, "芝×10頭以下×g12帯 馬連 [V3実績184.2%]",
            lambda r: (r["surface"] == "芝" and r["field"] <= 10
                       and not (r["tier"] or 0) >= 10 and len(r["order"]) >= 2),
            bet_umaren12,
            [[(f"g12∈[{lo:.2f},{hi:.2f})",
               lambda r, lo=lo, hi=hi: lo <= r["g12"] < hi)
              for lo, hi in ((0.2, 0.6), (0.1, 0.5), (qs[0], qs[2]), (0.15, 0.7))]])

        founds["上位平坦ダ馬連"] = sweep(
            rows, "上位平坦(spread15)×12頭以下×ダ×2日目+ 馬連 [V3実績174.8%]",
            lambda r: (r["surface"] == "ダ" and r["field"] <= 12 and r["day"] >= 2
                       and not (r["tier"] or 0) >= 10 and len(r["order"]) >= 2),
            bet_umaren12,
            [[(f"sp15<{th:.2f}", lambda r, th=th: r["sp15"] < th)
              for th in (0.8, 1.0, 1.5, 2.0)]])

        founds["芝三連複"] = sweep(
            rows, "芝×2勝以上×自信×良×16頭以下 三連複1-2-3位 [V3実績160.4%]",
            lambda r: (r["surface"] == "芝" and r["tier"] and 1 <= r["tier"] <= 5
                       and r["field"] <= 16 and r["baba"] == "良" and len(r["order"]) >= 3),
            bet_trio123,
            [[(f"g12>={th:.2f}", lambda r, th=th: r["g12"] >= th)
              for th in (0.1, 0.2, 0.3, qs[0])]])

        founds["未勝利2位"] = sweep(
            rows, "未勝利×g12×モデル2位5-10倍 単勝 [V3実績132.6%]",
            lambda r: ((r["tier"] or 0) >= 10 and len(r["order"]) >= 2
                       and 5.0 <= r["odds"].get(r["order"][1], 0) < 10.0
                       and r["baba"] == "良"),
            bet_tan2,
            [[(f"g12>={th:.2f}", lambda r, th=th: r["g12"] >= th)
              for th in (0.4, 0.6, 0.8, qs[1], qs[2])]])

        n_ok = sum(1 for v in founds.values() if v)
        print(f"\n### {path} 再確立: {n_ok}/{len(founds)}パターン")
        print("    エンジン切替の条件 = 主要パターンがここで再確立できること(RULES §V4-5)")


if __name__ == "__main__":
    main()
