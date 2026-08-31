# -*- coding: utf-8 -*-
"""
harvest_odds_combo.py ── 過去レースの「組合せ馬券オッズ」(複勝/ワイド/三連複…)を
                          netkeiba公開APIから収集して hist_odds/<race_id>.json に貯める

なぜ:
  3着内特化(複勝/ワイド/三連複)の期待値検証には、確率だけでなく「その時のオッズ」が要る。
  netkeiba の無料オッズAPI (race.netkeiba.com/api/api_get_jra_odds.html) は
  **過去レースでも最終(確定)オッズを返す**ことを実測(2023-2026で確認)。
  よって過去分は手作業なしで一括収集できる。

取れるもの (predict.fetch_jra の戻りそのまま):
  tan / fuku(下限) / umaren / wide / umatan / sanrenpuku / santan
  ※過去レースなので値は「最終オッズ」。事前オッズ(発走30分前など)ではない。
    事前オッズが要るレースは当日 jra_odds.fetch_official_combo() で取る。

使い方:
  python3 harvest_odds_combo.py --from-hist            # hist/にあってhist_oddsに無い分
  python3 harvest_odds_combo.py --from-hist --repair   # 既存でwide/三連複が欠けている分も
  python3 harvest_odds_combo.py --date 20260816        # その日のJRA全レース
  python3 harvest_odds_combo.py --start 20260101 --end 20260331
  python3 harvest_odds_combo.py --ids-file ids.txt     # race_id を1行1個
  python3 harvest_odds_combo.py 202601010801 202601010812
  オプション: --sleep 1.0 --limit N --out hist_odds --dry-run

安全:
  - 公開ページ/公開APIのみ。ログインしない。認証情報を扱わない。
  - 既定1秒間隔・単一スレッド。Ctrl-Cで中断しても既取得分は残る(1レース1ファイル)。
"""
import os, sys, json, time, argparse, datetime, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")
import predict as PR

OUT_DIR = "hist_odds"
HIST_DIR = "hist"
COMBO_KEYS = ("wide", "sanrenpuku")          # 3着内特化で必須の2券種
ALL_KEYS = ("tan", "fuku", "umaren", "wide", "umatan", "sanrenpuku", "santan")


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def has_combo(d, keys=COMBO_KEYS):
    return bool(d) and all(d.get(k) for k in keys)


def ids_from_hist(out_dir, repair=False, hist_dir=HIST_DIR):
    """hist/ にある race_id のうち、オッズ未取得(または組合せ欠け)のものを返す。"""
    if not os.path.isdir(hist_dir):
        return []
    ids = sorted(f[:-5] for f in os.listdir(hist_dir) if f.endswith(".json"))
    need = []
    for rid in ids:
        p = os.path.join(out_dir, rid + ".json")
        if not os.path.exists(p):
            need.append(rid)
        elif repair and not has_combo(_load(p)):
            need.append(rid)
    return need


def ids_from_dates(start, end):
    """日付範囲のJRAレース一覧(netkeiba公開のレース一覧)から race_id を集める。"""
    import pick_races as PKR
    d0 = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    d1 = datetime.date(int(end[:4]), int(end[4:6]), int(end[6:8]))
    out, d = [], d0
    while d <= d1:
        date = d.strftime("%Y%m%d")
        d += datetime.timedelta(days=1)
        try:
            lst = PKR.fetch_list(date, nar=False)
        except Exception as e:
            print("  [%s] 一覧取得失敗: %s" % (date, e), file=sys.stderr)
            continue
        got = [it["race_id"] for it in lst if str(it.get("race_id", ""))[4:6] in
               {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10"}]
        if got:
            print("  %s: %d レース" % (date, len(got)))
        out += got
        time.sleep(0.3)
    return sorted(set(out))


def harvest(ids, out_dir=OUT_DIR, sleep=1.0, repair=False, dry=False, keys=COMBO_KEYS):
    """race_id リストを順に取得して out_dir/<rid>.json に保存。返り値=集計dict。"""
    os.makedirs(out_dir, exist_ok=True)
    st = dict(total=len(ids), skip=0, ok=0, partial=0, fail=0, ng=0)
    t0 = time.time()
    for i, rid in enumerate(ids, 1):
        path = os.path.join(out_dir, rid + ".json")
        if os.path.exists(path):
            cur = _load(path)
            if has_combo(cur, keys) or not repair:
                st["skip"] += 1
                continue
        if dry:
            print("  [dry] would fetch %s" % rid)
            st["ok"] += 1
            continue
        try:
            o = PR.fetch_jra(rid)                     # fresh=False → 公式は叩かない
        except Exception as e:
            st["fail"] += 1
            print("  %s FAIL: %s" % (rid, e), file=sys.stderr)
            time.sleep(sleep)
            continue
        if o.get("ng_reason") and not o.get("tan"):
            st["ng"] += 1
            print("  %s NG: %s" % (rid, o["ng_reason"]), file=sys.stderr)
        elif has_combo(o, keys):
            st["ok"] += 1
        elif o.get("tan"):
            st["partial"] += 1
            print("  %s PARTIAL: %s" % (
                rid, {k: len(o.get(k) or {}) for k in ALL_KEYS}), file=sys.stderr)
        else:
            st["fail"] += 1
        if o.get("tan") or has_combo(o, keys):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(o, f, ensure_ascii=False)
            os.replace(tmp, path)
        if i % 25 == 0 or i == len(ids):
            el = time.time() - t0
            done = st["ok"] + st["partial"] + st["fail"] + st["ng"]
            rate = el / max(done, 1)
            print("  %d/%d  ok=%d partial=%d ng=%d fail=%d skip=%d  経過%.0f分 残%.0f分"
                  % (i, len(ids), st["ok"], st["partial"], st["ng"], st["fail"],
                     st["skip"], el / 60, rate * (len(ids) - i) / 60))
        time.sleep(sleep)
    return st


def main():
    ap = argparse.ArgumentParser(
        description="過去レースの組合せオッズ(ワイド/三連複ほか)を hist_odds/ に収集")
    ap.add_argument("race_ids", nargs="*", help="race_id を直接指定")
    ap.add_argument("--from-hist", action="store_true", help="hist/ の未取得分を対象")
    ap.add_argument("--repair", action="store_true",
                    help="既存ファイルでも wide/三連複 が欠けていれば取り直す")
    ap.add_argument("--date", help="YYYYMMDD 単日")
    ap.add_argument("--start", help="YYYYMMDD 範囲開始")
    ap.add_argument("--end", help="YYYYMMDD 範囲終了")
    ap.add_argument("--ids-file", help="race_id を1行1個書いたファイル")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--sleep", type=float, default=1.0, help="リクエスト間隔秒(既定1.0)")
    ap.add_argument("--limit", type=int, help="先頭N件だけ")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", action="store_true",
                    help="収集せず hist_odds/ の充足状況だけ集計する")
    a = ap.parse_args()

    if a.audit:
        files = sorted(f for f in os.listdir(a.out) if f.endswith(".json"))
        n = full = 0
        miss = {k: 0 for k in ALL_KEYS}
        for f in files:
            d = _load(os.path.join(a.out, f))
            if not d:
                continue
            n += 1
            for k in ALL_KEYS:
                if not d.get(k):
                    miss[k] += 1
            if has_combo(d):
                full += 1
        print("hist_odds/: %d ファイル / ワイド+三連複そろい %d (%.1f%%)"
              % (n, full, 100.0 * full / max(n, 1)))
        print("  券種別 欠損数: " + "  ".join("%s=%d" % (k, miss[k]) for k in ALL_KEYS))
        h = ids_from_hist(a.out, repair=False)
        print("  hist/ にあってオッズ未取得: %d" % len(h))
        print("  hist/ にあって組合せ欠け  : %d" % len(ids_from_hist(a.out, repair=True)))
        return

    ids = list(a.race_ids)
    if a.ids_file:
        with open(a.ids_file) as f:
            ids += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if a.date:
        ids += ids_from_dates(a.date, a.date)
    if a.start and a.end:
        ids += ids_from_dates(a.start, a.end)
    if a.from_hist:
        ids += ids_from_hist(a.out, repair=a.repair)
    ids = sorted(set(x for x in ids if len(str(x)) == 12))
    if a.limit:
        ids = ids[:a.limit]
    if not ids:
        ap.error("対象race_idが0件。--from-hist / --date / --start+--end / race_id を指定")
    print("■ 対象 %d レース (間隔%.1fs → 想定%.0f分)" % (len(ids), a.sleep,
                                                     len(ids) * (a.sleep + 3) / 60))
    st = harvest(ids, out_dir=a.out, sleep=a.sleep, repair=a.repair, dry=a.dry_run)
    print("■ 完了: %s" % st)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中断(取得済みは保存済み)", file=sys.stderr)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
