# -*- coding: utf-8 -*-
"""新潟芝1000m直線 専用システム（2021-2025の104レース・1718頭を実測して確定）。

   千直はJRA全体と別ゲーム。全体で効く「乖離単勝」は使わず、このコース専用の判定で買う。

   ■ 確定ルール（本線）
     外枠(7-8枠) × V3モデル1-3位 × 単勝5.0倍以下 の単勝
       → 勝率40.4%(市場implied 26.4%＝+14.0pt) / ROI 130.9% / 57点
          dev(2021-23)154.3% → conf(2024-25)108.3% / 最大的中除外124.6% / 5年全年プラス
   ■ 縁（小額のみ）
     同条件で5.0-8.0倍 → 109.2%
   ■ 採用しなかったもの（実測で否定）
     ・千直実績(コース巧者): 経験あり-0.6pt / 3着内実績あり-1.6pt・ROI52.4%
       → 市場が既に織り込み、むしろ過大評価。**買う理由にならない**
     ・6枠の追加: 単体では市場+2.3ptだがROI87.1%。本線に足すと130.9%→125.5%に薄まる
     ・内枠(1-3枠)×モデル1-3位: 勝率8.3%・市場-0.6pt・ROI53.6% = 死亡
     ・馬場状態: 良/稍/重/不で差ゼロ(全て±0.1pt以内)
     ・V3得点そのもの: モデル1位単勝は67.8%(市場との差0.0pt)＝順位だけ使い得点は使わない

   usage:
     python3 n1000_system.py              # 検証テーブルを再表示
     python3 n1000_system.py --live <rid> # 当日レースに適用(要 race_<rid>.json)
"""
import argparse, json, os, sys

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
import course

CORE_ODDS = 5.0      # 本線の上限オッズ
EDGE_ODDS = 8.0      # 縁の上限
CORE_ROI = 130.9
EDGE_ROI = 109.2


def judge(num, field, vrank, odds):
    """1頭ぶんの判定 -> (区分, 理由)。区分: 'core' / 'edge' / None"""
    w = course.jra_waku(num, field)
    if w < 7 or vrank is None or vrank > 3 or not odds:
        return None, ""
    if odds <= CORE_ODDS:
        return "core", f"{w}枠・モデル{vrank}位・{odds}倍"
    if odds <= EDGE_ODDS:
        return "edge", f"{w}枠・モデル{vrank}位・{odds}倍(5-8倍帯)"
    return None, ""


def pick(race_horses, field, order, tan):
    """レース全体 -> (本線list, 縁list, 全頭の判定内訳)"""
    vr = {n: i + 1 for i, n in enumerate(order)}
    core, edge, detail = [], [], []
    for n in [h["num"] for h in race_horses]:
        kind, why = judge(n, field, vr.get(n), tan.get(n))
        detail.append((n, course.jra_waku(n, field), vr.get(n), tan.get(n), kind))
        if kind == "core":
            core.append(n)
        elif kind == "edge":
            edge.append(n)
    return sorted(core), sorted(edge), detail


def main_live(rid):
    import calc, v2_live, predict as PR
    race = json.load(open(os.path.join(_DIR, f"race_{rid}.json"), encoding="utf-8"))
    r = calc.run(race)
    v2_live.rescore(race, r["rows"])
    rows = r["rows"]
    order = [x["num"] for x in rows]
    names = {h["num"]: h["name"] for h in race["horses"]}
    fld = race.get("field", len(rows))
    od = PR.fetch_jra(rid)
    tan = {int(k): v for k, v in od.get("tan", {}).items() if v}
    if race.get("surface") != "芝" or race.get("distance") != 1000 or rid[4:6] != "04":
        print(f"⚠ {rid} は新潟芝1000直ではない(surface={race.get('surface')} "
              f"dist={race.get('distance')} 場={rid[4:6]})。このシステムは適用外")
        return
    core, edge, detail = pick(race["horses"], fld, order, tan)
    print(f"# 新潟千直システム {rid} ({fld}頭)\n")
    print("| 馬番 | 馬名 | 枠 | モデル順位 | 単勝 | 判定 |")
    print("|---|---|---|---|---|---|")
    for n, w, v, o, kind in sorted(detail, key=lambda x: (x[2] or 99)):
        mark = {"core": "**◎本線**", "edge": "○縁"}.get(kind, "—")
        print(f"| {n} | {names.get(n,'')[:10]} | {w} | {v or '-'} | {o or '-'} | {mark} |")
    print()
    if core:
        print(f"**◎買い: 単勝 {core}**（外枠×モデル1-3位×5倍以下 = 5年ROI{CORE_ROI}%/57点・"
              f"勝率40.4%は市場見積り26.4%を+14.0pt上回る）")
        for n in core:
            print(f"  - {n} {names.get(n,'')}: 単勝{tan.get(n)}倍 → 1000円で{int(tan[n]*1000)}円")
    elif edge:
        print(f"○縁のみ: 単勝 {edge}（5-8倍帯=109.2%・小額 or 見送り）")
    else:
        print("**買い目なし** — 外枠×モデル1-3位×5倍以下の該当なし。千直は該当時だけ買う")
    print("\n※千直実績(コース巧者)は市場が織り込み済みで買う理由にならない(実測-1.6pt)。")
    print("※購入は人間。")


def main_table():
    res, mod = {}, {}
    for l in open(os.path.join(_DIR, "n1000_races.jsonl"), encoding="utf-8"):
        d = json.loads(l); res[d["rid"]] = d
    for l in open(os.path.join(_DIR, "n1000_model.jsonl"), encoding="utf-8"):
        d = json.loads(l); mod[d["rid"]] = d
    fp = os.path.join(_DIR, "n1000_feat.json")
    feat = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {}
    H = []
    for rid, r in res.items():
        m = mod.get(rid)
        if not m:
            continue
        vr = {x["num"]: i + 1 for i, x in enumerate(m["model"])}
        pf = feat.get(rid, {})
        for h in r["rows"]:
            if h["odds"] is None:
                continue
            f = pf.get(str(h["num"]), {})
            H.append(dict(date=r["date"], odds=h["odds"], win=1 if h["fin"] == "1" else 0,
                          waku=h["waku"], vr=vr.get(h["num"], 99),
                          pr=f.get("prior_runs", 0), pb=f.get("prior_best")))
    print(f"検証データ: {len(res)}R / 延べ{len(H)}頭 (2021-2025)\n")

    def ev(sel, lab):
        n = len(sel)
        if n < 20:
            return print(f"  {lab:<34} n={n}(少)")
        hit = [x for x in sel if x["win"]]
        tot = sum(x["odds"] * 100 for x in hit)
        mx = max((x["odds"] * 100 for x in hit), default=0)
        imp = sum(0.8 / x["odds"] for x in sel) / n
        dv = [x for x in sel if x["date"] < "20240101"]
        cf = [x for x in sel if x["date"] >= "20240101"]
        dr = 100 * sum(x["odds"] * 100 for x in dv if x["win"]) / (len(dv) * 100) if dv else 0
        cr = 100 * sum(x["odds"] * 100 for x in cf if x["win"]) / (len(cf) * 100) if cf else 0
        ex = 100 * (tot - mx) / ((n - 1) * 100) if n > 1 else 0
        print(f"  {lab:<34} n={n:4d} 的中{len(hit):3d} 勝率{100*len(hit)/n:5.1f}% "
              f"市場{100*imp:5.1f}% 差{100*len(hit)/n-100*imp:+5.1f}pt "
              f"ROI{100*tot/(n*100):6.1f}% dev{dr:6.1f} conf{cr:6.1f} 除外{ex:6.1f}")
    print("【本線】")
    ev([x for x in H if x["waku"] >= 7 and x["vr"] <= 3 and x["odds"] <= 5.0], "外7-8×モデル1-3位×5倍以下")
    print("【縁】")
    ev([x for x in H if x["waku"] >= 7 and x["vr"] <= 3 and 5.0 < x["odds"] <= 8.0], "同条件×5-8倍")
    print("【却下したもの】")
    ev([x for x in H if x["waku"] >= 7 and x["vr"] <= 3 and x["odds"] <= 5.0 and x["pr"] >= 1], "本線+千直経験あり")
    ev([x for x in H if x["waku"] >= 7 and x["vr"] <= 3 and x["odds"] <= 5.0
        and x["pb"] is not None and x["pb"] <= 3], "本線+千直3着内実績")
    ev([x for x in H if x["pb"] is not None and x["pb"] <= 3 and x["odds"] <= 10], "千直3着内実績×10倍以下(単独)")
    ev([x for x in H if 4 <= x["waku"] <= 6 and x["vr"] <= 3 and x["odds"] <= 5.0], "中4-6枠×モデル1-3位×5倍以下")
    ev([x for x in H if x["waku"] <= 3 and x["vr"] <= 3], "内1-3枠×モデル1-3位")
    ev([x for x in H if x["vr"] == 1], "モデル1位(全オッズ)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default=None)
    a = ap.parse_args()
    main_live(a.live) if a.live else main_table()
