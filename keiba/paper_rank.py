# -*- coding: utf-8 -*-
"""パターン・ルールブックの紙上運用（JRA専用・2026-07-29新設）。

   sim_rank.py で+48.2万/4ヶ月と出た「発火→ヒート→SS/S/A/B(改4)→配分」を、
   実弾を張らずに当日のライブオッズで記帳し、実払戻で精算して検証する。
   シミュとの差分＝実戦摩擦(オッズドリフト等)がここで測れる。

   usage:
     python3 paper_rank.py run [YYYYMMDD]   # 発走前のJRAレースを判定して記帳(何度でも・発走3分前で凍結)
     python3 paper_rank.py settle           # 結果が出たレースを精算
     python3 paper_rank.py stats            # 集計(判定ライン: 精算150Rで回収90%超→少額実弾検討)

   記録先: paper_rank_log.jsonl (1行=1レース)
   ※判定はライブと同一の patterns.classify/heat_of/tier_of。JRAのみ(台帳がJRA採掘のため)。
   ※購入・投票・GOは人間。これは記帳だけ。"""
import argparse, datetime, itertools, json, os, sys
import re

# 障害レース除外(2026-08-15 新潟JSすり抜け事故の再発防止): 「障害」表記だけでなく
# JS/ジャンプS等の重賞名もモデル対象外(平地専用)として弾く
JUMP_RE = re.compile(r"障害|ジャンプ|JS(?![a-z])")

import calc
import course
import v2_live
import predict as PR
import pick_races as PKR
import fetch_result as FRES
import day_board as DB
import patterns as JP

LOG = "paper_rank_log.jsonl"


def jst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def key_of(ns):
    return "-".join(str(x) for x in sorted(ns))


def load_log():
    if not os.path.exists(LOG):
        return []
    return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]


def save_log(rows):
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def fire_to_bets(name, order, odds, yen):
    """発火→具体的な買い目(100円単位)。sim_rank.settle_fireと同じ対応"""
    def r100(x):
        return max(int(x/100)*100, 100)
    if "馬連モデル1-2位" in name or "馬連1-2位" in name:
        return [dict(kind="馬連", sel=sorted(order[:2]), stake=r100(yen))]
    if "モデル2位" in name and "単勝" in name:
        return [dict(kind="単勝", sel=[order[1]], stake=r100(yen))]
    if "三連複軸ながし" in name:
        t1 = order[0]
        mtop = [n for n in sorted(odds, key=lambda h: odds[h]) if n != t1][:3]
        if len(mtop) < 3:
            return []
        combos = [sorted([t1, *p]) for p in itertools.combinations(mtop, 2)]
        per = r100(yen/len(combos))
        return [dict(kind="三連複", sel=c, stake=per) for c in combos]
    if "単勝" in name or "乖離" in name:
        return [dict(kind="単勝", sel=[order[0]], stake=r100(yen))]
    return []


def cmd_run(date):
    now = jst_now()
    logs = load_log()
    byrid = {r["race_id"]: r for r in logs}
    lst = [it for it in PKR.fetch_list(date, nar=False)
           if not JUMP_RE.search(it.get("name", ""))]
    print(f"[{date}] JRA {len(lst)}レースを紙上判定 ({now.strftime('%H:%M')} JST)", file=sys.stderr)
    n_new = n_upd = 0
    for it in lst:
        rid = it["race_id"]
        post = it.get("time") or "99:99"
        # 発走3分前で凍結。発走後のレースは記帳しない(オッズ汚染防止)
        if date == now.strftime("%Y%m%d") and post <= (now + datetime.timedelta(minutes=3)).strftime("%H:%M"):
            if rid not in byrid:
                continue
            if not byrid[rid].get("frozen"):
                byrid[rid]["frozen"] = True
            continue
        prev = byrid.get(rid)
        if prev and (prev.get("frozen") or prev.get("settled")):
            continue
        try:
            race = DB.load_or_fetch(rid, date, nar=False)
            DB.refresh_weights(race, rid, nar=False)
            res = calc.run(race)
            v2_live.rescore(race, res["rows"])
            rows = res["rows"]
            order = [r["num"] for r in rows]
            od = PR.fetch_jra(rid)
            tan = {int(k): v for k, v in od.get("tan", {}).items() if v}
            if not tan:
                continue
            g12 = (rows[0]["wavg"] - rows[1]["wavg"]) / 12.0 if len(rows) > 1 else 9
            sp15 = ((rows[0]["wavg"] - rows[4]["wavg"]) / 12.0) if len(rows) > 4 else None
            p1 = rows[0].get("pwin", 0) / 100.0
            fld = race.get("field", len(order))
            w2 = course.jra_waku(order[1], fld) if len(order) > 1 else None
            day_n = int(rid[8:10])
            fires = JP.classify(order, tan, fld, surface=race.get("surface"),
                                dist=race.get("distance"), tier=race.get("today_tier"),
                                gap12=g12, p1=p1, day=day_n,
                                venue=it.get("venue") or race.get("venue"),
                                spread15=sp15, waku2=w2, baba=race.get("baba"))
            buy = [f for f in fires if f[3].startswith("◎")]
            if not buy:
                byrid.pop(rid, None)     # 発火が消えたら記帳も取り下げ(凍結前のみ)
                continue
            hn, hc, _, _ = JP.heat_of(order, tan, fld, surface=race.get("surface"),
                                      dist=race.get("distance"), tier=race.get("today_tier"),
                                      p1=p1, venue=it.get("venue") or race.get("venue"))
            best = max(buy, key=lambda f: f[2])
            tier, yen, reason = JP.tier_of(best[2], hc, best[0], it.get("venue"))
            if yen <= 0:
                byrid.pop(rid, None)
                continue
            bets = fire_to_bets(best[0], order, tan, yen)
            if not bets:
                continue
            entry = dict(race_id=rid, date=date, venue=it.get("venue"), r=it.get("r"),
                         post=post, recorded=now.strftime("%m%d %H:%M"),
                         pattern=best[0], roi_claim=best[2], tier=tier, heat=hc,
                         bets=bets, odds_at_rec={str(k): v for k, v in
                                                 sorted(tan.items())[:0]} or None,
                         o1=tan.get(order[0]), baba=race.get("baba"),
                         frozen=False, settled=False)
            if prev:
                entry["recorded_first"] = prev.get("recorded_first", prev["recorded"])
                n_upd += 1
            else:
                entry["recorded_first"] = entry["recorded"]
                n_new += 1
            byrid[rid] = entry
            print(f"  📝 {it.get('venue')}{it.get('r')}R {post}発走 [{tier}/{yen:,}円] "
                  f"{best[0][:30]} 🔥{hc}", file=sys.stderr)
        except Exception as e:
            print(f"  {rid} 判定失敗: {e}", file=sys.stderr)
    keep = [r for r in logs if r["race_id"] not in byrid]
    save_log(keep + list(byrid.values()))
    print(f"記帳 新規{n_new} 更新{n_upd} / 総{len(byrid)}件 → {LOG}", file=sys.stderr)


def cmd_settle():
    logs = load_log()
    n = 0
    for r in logs:
        if r.get("settled"):
            continue
        try:
            res = FRES.get_result(r["race_id"])
        except Exception:
            continue
        pay = res.get("payout") or {}
        if not pay.get("単勝"):
            continue
        win = int(list(pay["単勝"].keys())[0])
        ret = 0.0
        for b in r["bets"]:
            if b["kind"] == "単勝":
                if b["sel"][0] == win:
                    ret += float(pay["単勝"].get(str(win), 0))/100.0 * b["stake"]
            elif b["kind"] == "馬連":
                ret += float((pay.get("馬連") or {}).get(key_of(b["sel"]), 0))/100.0 * b["stake"]
            elif b["kind"] == "三連複":
                ret += float((pay.get("三連複") or {}).get(key_of(b["sel"]), 0))/100.0 * b["stake"]
        r["settled"] = True
        r["ret"] = round(ret)
        r["stake_total"] = sum(b["stake"] for b in r["bets"])
        n += 1
        mark = "🎯" if ret > 0 else "…"
        print(f"  {mark} {r['venue']}{r['r']}R [{r['tier']}] {r['pattern'][:24]} "
              f"投{r['stake_total']:,} → 戻{r['ret']:,}", file=sys.stderr)
    save_log(logs)
    print(f"精算 {n}件", file=sys.stderr)


def cmd_stats():
    logs = [r for r in load_log() if r.get("settled")]
    if not logs:
        print("精算済みレコードなし")
        return
    st = sum(r["stake_total"] for r in logs)
    rt = sum(r["ret"] for r in logs)
    h = sum(1 for r in logs if r["ret"] > 0)
    print(f"紙上運用(パターン・ルールブック/JRA): {len(logs)}R精算")
    print(f"  的中{h} ({h/len(logs)*100:.0f}%) / 投下{st:,}円 → 回収{rt:,}円 "
          f"(ROI {rt/max(st,1)*100:.1f}%) / 損益 {rt-st:+,}円")
    from collections import defaultdict
    byt = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for r in logs:
        a = byt[r["tier"]]
        a[0] += 1
        a[1] += r["ret"] > 0
        a[2] += r["stake_total"]
        a[3] += r["ret"]
    for t in ("SS", "S", "A", "B"):
        if t in byt:
            n_, h_, s_, r_ = byt[t]
            print(f"  {t}: {n_}R 的中{h_} ROI {r_/max(s_,1)*100:.0f}% 損益{r_-s_:+,.0f}円")
    print(f"  参考: シミュ(WF2200R)はROI223.9%・的中17%。")
    print(f"  判定ライン(RULES): 精算150Rで回収90%超→少額実弾を検討 / 70%未満→設計に戻る")
    print(f"  進捗: {len(logs)}/150R")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("run")
    p1.add_argument("date", nargs="?", default=None)
    sub.add_parser("settle")
    sub.add_parser("stats")
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a.date or jst_now().strftime("%Y%m%d"))
    elif a.cmd == "settle":
        cmd_settle()
    else:
        cmd_stats()


if __name__ == "__main__":
    main()
