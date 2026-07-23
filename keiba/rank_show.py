# -*- coding: utf-8 -*-
"""race_<rid>.json から全頭ランキング(得点/PWin/ランク/馬体重)mdを生成。
   usage: python3 rank_show.py <rid> [表示名]"""
import json, sys
import calc, v2_live


def make(rid, title=None):
    title = title or rid
    d = json.load(open(f"race_{rid}.json"))
    res = calc.run(d); v2_live.rescore(d, res["rows"])
    rows = res["rows"]
    hm = {h["num"]: h for h in d["horses"]}
    nm = {h["num"]: h["name"] for h in d["horses"]}
    g12 = (rows[0]["wavg"] - rows[1]["wavg"]) / 12 if len(rows) > 1 else 0
    anyw = any(hm[r["num"]].get("weight") for r in rows)
    out = [f"# {title} 全頭ランキング",
           f"(surface={d.get('surface')} {d.get('distance')}m / today_vg={d.get('today_vg')} / g12={g12:.3f} / 馬体重={'発表済' if anyw else '未発表'})", "",
           "| 馬番 | 馬名 | 脚質 | 得点 | PWin | ランク | 馬体重 |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        n = r["num"]; h = hm.get(n, {}); wt = h.get("weight") or 0; ch = h.get("weight_change")
        ws = ("%d(%+d)" % (wt, ch)) if wt else "未発表"
        out.append("| %d | %s | %s | %.1f | %.1f%% | %s | %s |" %
                   (n, nm.get(n, "")[:10], r.get("paper_style", ""), r["wavg"], r["pwin"], r.get("rank", ""), ws))
    fn = f"rank_{rid}.md"
    open(fn, "w").write("\n".join(out))
    return fn


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 rank_show.py <rid> [表示名]")
    print("WROTE " + make(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
