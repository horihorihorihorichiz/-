# -*- coding: utf-8 -*-
"""デイボード: その日の対象場(既定=大井+JRA全場)を1枚のmdに集約するダッシュボード。
   - 各R: 発走/レース名/軸馬(モデル1位)+現在オッズ/狙い目ランク(S/A/B/C)/一言
   - S/A のレースは全頭ランキング(全列)を同ファイルに添付
   - 馬柱は初回のみ取得しキャッシュ(race_<rid>.json)。更新時はオッズ+馬体重のみ再取得=高速
   - 日付は常に実行時JST(引数省略時)。レース名・頭数をヘッダ表示(データ照合)

   usage: python3 day_board.py [YYYYMMDD] [--venue auto|大井|中央|場名,場名] [--rids id1,id2] [--fast]
     --venue auto(既定): 大井(開催日) + JRA全場(開催日)
     --fast: キャッシュ済みレースのみ(未取得の馬柱はスキップ)
   出力: board_<date>.md
"""
import argparse, datetime, json, os, sys

import pick_races as PK
import fetch_race as FR
import harvest as HV
import calc
import v2_live
import predict as PR
import oi_patterns
import patterns as JP
import course

JRA_VENUES = set("札幌 函館 福島 新潟 東京 中山 中京 京都 阪神 小倉".split())


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def load_or_fetch(rid, date, nar, fast=False):
    fn = f"race_{rid}.json"
    if os.path.exists(fn):
        d = json.load(open(fn, encoding="utf-8"))
        if d.get("race_id") == rid and d.get("horses"):
            return d
    if fast:
        return None
    su = FR.fetch_shutuba(rid, nar=nar)
    dd = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
    race = HV.build_race_json(rid, su, dd, workers=4)
    json.dump(race, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    return race


def refresh_weights(race, rid, nar):
    """出馬表1ページだけ再取得して馬体重を最新化"""
    try:
        su = FR.fetch_shutuba(rid, nar=nar)
        wmap = {h["num"]: (h.get("weight", 0), h.get("change", 0)) for h in su["horses"]}
        n = 0
        for h in race["horses"]:
            w, c = wmap.get(h["num"], (0, 0))
            if w:
                h["weight"], h["weight_change"] = w, c
                n += 1
        return n
    except Exception:
        return 0


def eval_race(it, date, nar, fast=False):
    rid = it["race_id"]
    out = dict(r=it.get("r"), time=it.get("time"), name=it.get("name", ""),
               dist=it.get("dist", ""), venue=it.get("venue", ""), rid=rid,
               rank="C", note="", rows=None)
    try:
        race = load_or_fetch(rid, date, nar, fast=fast)
        if race is None:
            out.update(rank="-", note="馬柱未取得(--fast)")
            return out
        refresh_weights(race, rid, nar)
        res = calc.run(race)
        v2_live.rescore(race, res["rows"])
        rows = res["rows"]
        order = [r["num"] for r in rows]
        names = {h["num"]: h["name"] for h in race["horses"]}
        g12 = (rows[0]["wavg"] - rows[1]["wavg"]) / 12.0 if len(rows) > 1 else 9
        od = PR.fetch_jra(rid) if not nar else PR.fetch_nar(rid, race.get("field", len(order)))
        tan = {int(k): v for k, v in od.get("tan", {}).items() if v}
        if not tan:
            out.update(rank="-", note="オッズ未発売")
            return out
        pops = {n: i + 1 for i, n in enumerate(sorted(tan, key=lambda h: tan[h]))}
        m1 = order[0]
        o1 = tan.get(m1, 0)
        p1 = rows[0].get("pwin", 0) / 100.0
        mval = p1 * o1
        out.update(axis=m1, axis_name=names.get(m1, ""), o1=o1, pop1=pops.get(m1, 0),
                   g12=round(g12, 3), mval=round(mval, 2), field=race.get("field"))
        # ---- パターン判定(場で分岐) ----
        if nar:
            fires = oi_patterns.classify(order, tan, pops, g12=g12,
                                         dist=race.get("distance"), tier=race.get("today_tier"))
        else:
            fires = JP.classify(order, tan, race.get("field", len(order)),
                                surface=race.get("surface"), dist=race.get("distance"),
                                tier=race.get("today_tier"), gap12=g12, p1=p1)
        buy = [f for f in fires if f[3].startswith("◎")]
        spread4 = rows[0]["wavg"] - rows[3]["wavg"] if len(rows) > 3 else 99
        # ヒートスコア(重複条件数): 乖離発火時のみ意味を持つ
        hn, hc, hroi, hsn = ([], 0, 0, 0)
        if not nar:
            hn, hc, hroi, hsn = JP.heat_of(order, tan, race.get("field", len(order)),
                                           surface=race.get("surface"), dist=race.get("distance"),
                                           tier=race.get("today_tier"), p1=p1)
        out.update(heat=hc, heat_hits=hn, heat_roi=hroi)
        if buy:
            best = max(buy, key=lambda f: f[2])
            out["rank"] = "S"
            heat_tag = (f" 🔥{hc}条件重複({'+'.join(hn)})={hc}個以上帯WF{hroi:.0f}%/{hsn}R"
                        if hc >= 3 else (f" 🔥{hc}条件" if hc else ""))
            out["note"] = f"発火: {best[0]} ROI{best[2]:.0f}%{heat_tag}"
            out["fire_desc"] = best[1] + (f" ／ 熱さ{hc}個: {'+'.join(hn)}" if hn else "")
        elif (o1 >= 12 and g12 < 0.20) or mval >= 1.6:
            why = []
            if o1 >= 12 and g12 < 0.20:
                why.append(f"深乖離{o1}倍×混戦寄り")
            if mval >= 1.6:
                why.append(f"モデル価値{mval:.1f}")
            out.update(rank="A", note="準発火: " + "・".join(why))
        elif nar and 2.5 <= o1 < 7.5 and 0.10 <= g12 < 0.35:
            out.update(rank="A", note="三連複1人気外しの近接帯(紐は発走前確認)")
        elif (not nar) and 5.5 <= o1 < 7.0:
            out.update(rank="A", note=f"乖離単勝の近接帯({o1}倍・7倍で発火)")
        elif g12 < 0.10 and spread4 <= 4.5:
            out.update(rank="B", note="混戦×モデル上位集中(BOX型・未検証の遊び枠)")
        else:
            out.update(rank="C", note="市場一致/歪みなし=見送り")
        # 未勝利・新馬: 検証済み発火(S)は残す(7/25採掘のモデル2位系)。A/Bの近接ヒューリスティックだけ無効化
        if "未勝利" in out.get("name", "") and out["rank"] in ("A", "B"):
            out.update(rank="C", note="未勝利=準発火ヒューリスティック対象外・ランキングのみ参考")
        # 新潟芝1000m直線: システム主軸×枠の専用合成(7/25 V3遡及5年104R・n1000_sysmine.py)
        #   ◎外枠(7-8枠)×モデル1-3位×5倍以下 = 133.2%/56点(dev154→conf112・除外後126.9%・5年全年+)
        #   対照: 内枠105.3% 中枠81.3% ／ 枠だけ(順位不問)108.4% ／ モデルだけ(枠不問)113.0%＝両方要る
        if (race.get("venue") == "新潟" or rid[4:6] == "04") and race.get("surface") == "芝" \
                and race.get("distance") == 1000:
            fld = race.get("field", len(order))
            vrank = {n: i + 1 for i, n in enumerate(order)}
            core = [n for n in tan if course.jra_waku(n, fld) >= 7
                    and vrank.get(n, 99) <= 3 and tan[n] <= 5.0]
            wide = [n for n in tan if course.jra_waku(n, fld) >= 7
                    and vrank.get(n, 99) <= 3 and 5.0 < tan[n] <= 8.0]
            if core:
                d = "・".join(f"{n}(モデル{vrank[n]}位/{tan[n]}倍/{course.jra_waku(n, fld)}枠)" for n in sorted(core))
                out.update(rank="S",
                           note=f"新潟1000直[システム×枠]: 外枠×モデル1-3位×5倍以下 → 単勝{sorted(core)} "
                                "(5年133.2%/56点・除外後127%・全年+)",
                           fire_desc=f"単勝 {sorted(core)} 各点。{d}。人気順位は不使用=システム主軸")
            elif wide:
                out.update(rank="A",
                           note=f"新潟1000直: 外枠×モデル1-3位だが5-8倍{sorted(wide)}=縁"
                                "(同条件8倍以下で109.2%・小額のみ)")
            else:
                out.update(rank="C",
                           note="新潟1000直: 外枠×モデル1-3位×低オッズの該当なし=見送り"
                                "(中枠81%・穴帯は全滅)")
        wmap = {h["num"]: h for h in race["horses"]}
        out["weights"] = any(h.get("weight") for h in race["horses"])
        out["rows"] = [dict(num=r["num"], name=names.get(r["num"], ""),
                            sty=r.get("paper_style", ""), sc=r["wavg"], pw=r["pwin"],
                            rk=r.get("rank", ""), odds=tan.get(r["num"]),
                            pop=pops.get(r["num"]),
                            wt=wmap.get(r["num"], {}).get("weight", 0) or 0,
                            wc=wmap.get(r["num"], {}).get("weight_change", 0) or 0)
                       for r in rows]
    except Exception as e:
        out.update(rank="-", note=f"エラー: {repr(e)[:50]}")
    return out


def gather_races(date, venue_arg):
    """対象レース列挙: [(it, nar)]"""
    targets = []
    if venue_arg == "auto":
        try:
            targets += [(it, True) for it in PK.fetch_list(date, nar=True)
                        if it.get("venue") == "大井" and "新馬" not in it.get("name", "")]
        except Exception:
            pass
        try:
            targets += [(it, False) for it in PK.fetch_list(date, nar=False)
                        if "障害" not in it.get("name", "") and "新馬" not in it.get("name", "")]
        except Exception:
            pass
    else:
        wants = set(venue_arg.split(","))
        if wants & {"中央", "JRA"}:
            targets += [(it, False) for it in PK.fetch_list(date, nar=False)
                        if "障害" not in it.get("name", "") and "新馬" not in it.get("name", "")]
            wants -= {"中央", "JRA"}
        if wants:
            for nar in (True, False):
                try:
                    targets += [(it, nar) for it in PK.fetch_list(date, nar=nar)
                                if it.get("venue") in wants]
                except Exception:
                    pass
    seen = set()
    uniq = []
    for it, nar in targets:
        if it["race_id"] in seen:
            continue
        seen.add(it["race_id"])
        uniq.append((it, nar))
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=None)
    ap.add_argument("--venue", default="auto")
    ap.add_argument("--rids", default=None)
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    date = a.date or jst_now().strftime("%Y%m%d")
    now = jst_now()

    targets = gather_races(date, a.venue)
    if a.rids:
        keep = set(a.rids.split(","))
        targets = [(it, nar) for it, nar in targets if it["race_id"] in keep]
    if not targets:
        print(f"{date} 対象開催なし")
        return
    targets.sort(key=lambda x: (x[0].get("time") or "99:99", x[0].get("venue", "")))

    results = []
    for it, nar in targets:
        print(f"[{it.get('venue')}{it.get('r')}R] 判定中...", file=sys.stderr, flush=True)
        results.append(eval_race(it, date, nar, fast=a.fast))

    RANK_ORD = {"S": 0, "A": 1, "B": 2, "C": 3, "-": 4}
    n_sa = sum(1 for o in results if o["rank"] in ("S", "A"))
    md = [f"# デイボード {date[:4]}/{date[4:6]}/{date[6:8]}",
          f"更新 {now.strftime('%H:%M')} JST ／ 対象{len(results)}R ／ "
          "狙い目: S=検証済パターン発火 A=準発火 B=混戦BOX型(未検証) C=見送り", "",
          "| 場 | R | 発走 | レース | 軸馬(モデル1位) | オッズ(人気) | g12 | 狙い目 | 判定 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for o in results:
        ax = f"{o.get('axis','-')} {o.get('axis_name','')[:8]}" if o.get("axis") else "-"
        oz = f"{o.get('o1','-')}倍({o.get('pop1','-')}人)" if o.get("o1") else "-"
        wt = "体重◎" if o.get("weights") else "体重未"
        md.append(f"| {o['venue']} | {o['r']} | {o['time']} | {o['name'][:10]}{o['dist']} | {ax} | {oz} | "
                  f"{o.get('g12','-')} | **{o['rank']}** | {o['note'][:38]} {wt} |")
    md.append("")
    hot = sorted([o for o in results if o["rank"] in ("S", "A") and o.get("rows")],
                 key=lambda x: (RANK_ORD[x["rank"]], x["time"]))
    for o in hot:
        md.append(f"## 【{o['rank']}】{o['venue']}{o['r']}R {o['time']} {o['name']}{o['dist']} ({o.get('field')}頭)")
        md.append(o["note"] + (f" ／ 買い方: {o.get('fire_desc','')}" if o.get("fire_desc") else ""))
        md.append("")
        md.append("| 馬番 | 馬名 | 脚質 | 得点 | PWin | ランク | 単勝(人気) | 馬体重 |")
        md.append("|---|---|---|---|---|---|---|---|")
        for r in o["rows"]:
            ws = f"{r['wt']}({r['wc']:+d})" if r["wt"] else "未"
            oz = f"{r['odds']}({r['pop']}人)" if r["odds"] else "-"
            md.append(f"| {r['num']} | {r['name'][:10]} | {r['sty']} | {r['sc']:.1f} | "
                      f"{r['pw']:.1f}% | {r['rk']} | {oz} | {ws} |")
        md.append("")
    md.append("※購入ボタンは人間。S以外は検証済みエッジではない。オッズは取得時点のもの。")
    fn = f"board_{date}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(md))
    print(f"WROTE {fn} ({len(results)}R / S+A={n_sa})")


if __name__ == "__main__":
    main()
