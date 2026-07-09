# -*- coding: utf-8 -*-
"""
fetch_race.py ── race_id だけから race_<id>.json を自動生成（データ入力の自動化）

netkeiba の公開ページのみ使用（プレミアム/ログイン不要）:
  - 出馬表  : nar.netkeiba.com/race/shutuba.html      (馬番/馬名/馬体重/斤量/馬場/距離/クラス)
  - 競走成績: db.netkeiba.com/horse/result/<horse_id>/ (過去9走: 着順/頭数/馬番/通過/上り/馬場/クラス/日付)

タイム指数(tsi)は netkeiba プレミアム限定なので既定 None（calc.py は None を許容）。
  --tsi tsi.txt で「馬番 t1 t2 …(新しい順)」を渡すと反映できる。

使い方:
  python fetch_race.py <race_id> [--tsi tsi.txt] [--baba 良|稍|重|不] [--out race_x.json]
  → race_<id>.json を書き出し、続けて実行するコマンドを表示

安全: 認証情報は一切扱わない。オッズ/買い目は predict.py 側で取得・判定。
"""
import sys, re, json, argparse, datetime, urllib.request, gzip, io, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def get(url, enc):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    for i in range(4):
        try:
            r = urllib.request.urlopen(req, timeout=30)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode(enc, errors="replace")
        except Exception as e:
            if i == 3:
                raise
            time.sleep(2 * (i + 1))

def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).replace("&nbsp;", " ").strip()

# ---- クラス → tier（小さいほど格上。SOP/RULES 準拠） ----
def class_to_tier(text):
    t = text
    if re.search(r"(Jpn1|G1|GⅠ|ＧⅠ)", t): return 1
    if re.search(r"(Jpn2|Jpn3|G2|G3|GⅡ|GⅢ|重賞)", t): return 2
    if re.search(r"(\(L\)|リステッド|オープン|ＯＰ|OP|Listed)", t): return 3
    if re.search(r"(A1|A2|Ａ1|Ａ2|3勝)", t): return 4
    if re.search(r"(B1|Ｂ1|2勝)", t): return 6
    if re.search(r"(B2|B3|Ｂ2|Ｂ3)", t): return 7
    if re.search(r"(C1|Ｃ1)", t): return 8
    if re.search(r"(C2|Ｃ2)", t): return 9
    if re.search(r"(C3|Ｃ3|新馬|未勝利|1勝)", t): return 10
    if re.search(r"(3歳|2歳)", t): return 9
    return 8  # 不明時はC1相当（中庸）

def dist_cat(d):
    return "S" if d <= 1400 else ("M" if d <= 1700 else "L")

def pace_label(pace_txt):
    # "39.7-41.1" → 前半/後半。前半速い=ハイ(H)、前半遅い=スロー(S)
    m = re.findall(r"[\d.]+", pace_txt or "")
    if len(m) < 2: return None
    a, b = float(m[0]), float(m[1])
    if a < b - 0.5: return "H"
    if a > b + 0.5: return "S"
    return "M"

def parse_dist_surface(txt):
    m = re.search(r"(芝|ダ|障)\s*(\d{3,4})", txt)
    if not m: return "ダ", 0
    return ("芝" if m.group(1) == "芝" else "ダ"), int(m.group(2))

# ---- 出馬表 ----
def fetch_shutuba(race_id, nar=True):
    host = "nar.netkeiba.com" if nar else "race.netkeiba.com"
    h = get(f"https://{host}/race/shutuba.html?race_id={race_id}", "utf-8")
    rn = re.search(r'<div class="RaceName"[^>]*>(.*?)</div>', h, re.S)
    race_name = strip(rn.group(1)) if rn else ""
    rd1 = re.search(r'RaceData01[^>]*>(.*?)</div>', h, re.S)
    d1 = strip(rd1.group(1)) if rd1 else ""
    rd2 = re.search(r'RaceData02[^>]*>(.*?)</div>', h, re.S)
    d2 = strip(rd2.group(1)) if rd2 else ""
    surface, distance = parse_dist_surface(d1)
    mb = re.search(r"馬場\s*:?\s*(良|稍|重|不)", d1)
    baba = {"良": "良", "稍": "稍", "重": "重", "不": "不"}.get(mb.group(1)) if mb else "良"
    tier = class_to_tier(race_name + " " + d2)
    mf = re.search(r"(\d+)頭", d2)
    field = int(mf.group(1)) if mf else 0
    mv = re.search(r"\d+回\s*(\S+?)\s*\d+日目", d2)
    venue = mv.group(1) if mv else ""

    horses = []
    for r in re.findall(r'<tr class="HorseList[^>]*>(.*?)</tr>', h, re.S):
        hid = re.findall(r"horse/(\d+)", r)
        if not hid: continue
        um = re.search(r'class="Umaban\d+"[^>]*>(\d+)<', r)
        if not um: continue  # 空テンプレ行を除外
        nm = re.search(r'HorseName.*?>\s*([^<]+?)\s*</a>', r, re.S)
        kin = re.search(r'class="Txt_C"[^>]*>\s*([\d.]+)\s*</td>', r)
        wt = re.search(r'class="Weight"[^>]*>(.*?)</td>', r, re.S)
        wtxt = strip(wt.group(1)) if wt else ""
        mw = re.search(r"(\d{3})\s*\(([-+]?\d+)\)", wtxt)
        weight = int(mw.group(1)) if mw else 0
        change = int(mw.group(2)) if mw else 0
        horses.append({
            "num": int(um.group(1)) if um else 0,
            "name": nm.group(1).strip() if nm else "",
            "horse_id": hid[0],
            "kin": float(kin.group(1)) if kin else 56.0,
            "weight": weight, "change": change,
        })
    if not field:
        field = len(horses)
    return {"race_name": race_name, "surface": surface, "distance": distance,
            "baba": baba, "tier": tier, "field": field, "venue": venue, "horses": horses}

# ---- 競走成績（過去走） ----
def fetch_horse_results(horse_id, race_date, today_surface, today_dist, max_races=9):
    h = get(f"https://db.netkeiba.com/horse/result/{horse_id}/", "euc-jp")
    m = re.search(r'<table[^>]*db_h_race_results[^>]*>(.*?)</table>', h, re.S)
    if not m:
        return []
    tbl = m.group(1)
    heads = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", x)) for x in re.findall(r'<th[^>]*>(.*?)</th>', tbl, re.S)]
    def idx(name):
        for i, hd in enumerate(heads):
            if hd.startswith(name):
                return i
        return -1
    I = {k: idx(k) for k in ["日付", "開催", "天気", "頭数", "馬番", "着順", "斤量", "距離", "馬場", "レース名", "通過", "ペース", "上り", "馬体重"]}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S)
    out = []
    for r in rows[1:]:
        tds = [strip(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
        if len(tds) < len(heads):
            continue
        def g(k):
            return tds[I[k]] if I[k] >= 0 and I[k] < len(tds) else ""
        ds = g("日付")
        dm = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", ds)
        if not dm:
            continue
        pdate = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        days = (race_date - pdate).days
        if days < 0:
            continue  # 未来（当日より後）は除外
        fin = re.match(r"\d+", g("着順"))
        if not fin:
            continue  # 中止/取消
        surf, dist = parse_dist_surface(g("距離"))
        field = int(re.match(r"\d+", g("頭数")).group()) if re.match(r"\d+", g("頭数")) else 0
        um = int(re.match(r"\d+", g("馬番")).group()) if re.match(r"\d+", g("馬番")) else 0
        corners = re.findall(r"\d+", g("通過"))
        c4 = int(corners[-1]) if corners else 0
        ag = re.search(r"[\d.]+", g("上り"))
        agari = float(ag.group()) if ag else 40.0
        baba = next((b for b in ["良", "稍", "重", "不"] if b in g("馬場")), "良")
        tier = class_to_tier(g("レース名"))
        out.append({
            "surface": surf, "dist": dist, "finish": int(fin.group()), "field": field,
            "umaban": um, "corner4": c4, "agari": agari, "vg": 2, "tier": tier,
            "days": days, "pace": pace_label(g("ペース")), "baba_idx": None, "tsi": None,
            "_baba": baba, "_venue": g("開催"),
        })
        if len(out) >= max_races:
            break
    return out

# ---- 脚質・csi・off の導出 ----
def derive_style(races):
    rs = races[:4] if races else []
    ratios = [r["corner4"] / r["field"] for r in rs if r["field"]]
    if not ratios:
        return "差"
    a = sum(ratios) / len(ratios)
    if a <= 0.18: return "逃"
    if a <= 0.38: return "先"
    if a <= 0.62: return "差"
    return "追"

def derive_csi(races, venue, today_dist):
    # コース（開催場）×同距離帯の実績を重視（SOP: 同コース同距離で勝ち=特級）
    dc = dist_cat(today_dist)
    course = [r for r in races if r.get("_venue") == venue and dist_cat(r["dist"]) == dc]
    same = [r for r in races if dist_cat(r["dist"]) == dc]  # 距離帯のみ一致
    cwins = sum(1 for r in course if r["finish"] == 1)
    cplace = sum(1 for r in course if r["finish"] <= 3)
    wins = sum(1 for r in same if r["finish"] == 1)
    places = sum(1 for r in same if r["finish"] <= 2)
    if cwins >= 1 or wins >= 2: return 5           # 同コース勝ち / 同距離帯2勝＝特級
    if cplace >= 2 or wins >= 1 or places >= 2: return 2.5
    return 0

def derive_off(races):
    return [r["finish"] for r in races if r.get("_baba") in ("稍", "重", "不")]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("race_id")
    ap.add_argument("--tsi", help="馬番ごとのタイム指数ファイル（'num t1 t2 ...'新しい順）")
    ap.add_argument("--from-netkeiba", dest="from_netkeiba",
                    help="別ツールの <race_id>_all.json からタイム指数(近5走)を反映")
    ap.add_argument("--baba", help="馬場を上書き（良/稍/重/不）")
    ap.add_argument("--jra", action="store_true", help="JRAレース（既定はNAR）")
    ap.add_argument("--out")
    ap.add_argument("--run", action="store_true", help="生成後そのまま predict.py を実行")
    ap.add_argument("--budget", type=int, help="--run時の予算をpredictへ渡す")
    ap.add_argument("--mobile", action="store_true", help="--run時 スマホ投票用表示もpredictに出させる")
    args = ap.parse_args()

    rid = args.race_id
    nar = not args.jra
    # NAR race_id = YYYY場MMDDRR → 日付
    race_date = None
    if nar and len(rid) == 12:
        try:
            race_date = datetime.date(int(rid[:4]), int(rid[6:8]), int(rid[8:10]))
        except ValueError:
            race_date = None
    if race_date is None:
        race_date = datetime.date.today()

    print(f"[1/3] 出馬表取得 race_id={rid} ...", file=sys.stderr)
    su = fetch_shutuba(rid, nar=nar)
    baba = args.baba or su["baba"]
    print(f"      {su['race_name']} / {su['surface']}{su['distance']}m / 馬場{baba} / {su['field']}頭 / tier{su['tier']}", file=sys.stderr)

    def _num(v):
        s = str(v).strip()
        return float(s) if s and s.lstrip("-").replace(".", "", 1).isdigit() else None

    tsi_map = {}
    if args.tsi:
        for line in open(args.tsi, encoding="utf-8"):
            p = line.split()
            if p and p[0].isdigit():
                tsi_map[int(p[0])] = [_num(x) for x in p[1:]]
    if args.from_netkeiba:
        # 別ツール（netkeiba_run.py）の統合JSON: time_index[].r1..r5.index（新しい順）を反映
        data = json.load(open(args.from_netkeiba, encoding="utf-8"))
        applied = 0
        for e in data.get("time_index", []):
            um = _num(e.get("umaban"))
            if um is None:
                continue
            idxs = []
            for k in ("r1", "r2", "r3", "r4", "r5"):
                v = e.get(k)
                idxs.append(_num(v.get("index")) if isinstance(v, dict) else None)
            if any(x is not None for x in idxs):
                tsi_map[int(um)] = idxs
                applied += 1
        print(f"      --from-netkeiba: {applied}頭にタイム指数を反映", file=sys.stderr)

    horses = []
    for i, hs in enumerate(su["horses"]):
        print(f"[2/3] 馬柱取得 {hs['num']:>2} {hs['name']} ...", file=sys.stderr)
        races = fetch_horse_results(hs["horse_id"], race_date, su["surface"], su["distance"])
        # tsi 反映
        tl = tsi_map.get(hs["num"], [])
        for j, r in enumerate(races):
            if j < len(tl):
                r["tsi"] = tl[j]
        off = derive_off(races)
        csi = derive_csi(races, su["venue"], su["distance"])
        for r in races:
            r.pop("_baba", None)
            r.pop("_venue", None)
        horses.append({
            "num": hs["num"], "name": hs["name"],
            "paper_style": derive_style(races),
            "kinryo": hs["kin"], "weight": hs["weight"], "weight_change": hs["change"],
            "boost": 0,
            "last_race_days": races[0]["days"] if races else 30,
            "csi": csi,
            "offtrack_finishes": off,
            "races": races,
        })

    race = {
        "name": f"{su['race_name']} {su['surface']}{su['distance']}",
        "venue": rid[4:6] if nar else "",
        "surface": su["surface"], "distance": su["distance"], "field": su["field"],
        "baba": baba, "today_vg": 2, "dist_cat": dist_cat(su["distance"]),
        "dsi_haiten": 5, "today_tier": su["tier"], "nsi_haiten": 20,
        "race_id": rid, "horses": horses,
    }
    out = args.out or f"race_{rid}.json"
    json.dump(race, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[3/3] 書き出し: {out}", file=sys.stderr)
    n_tsi = sum(1 for hh in horses for r in hh["races"] if r["tsi"] is not None)
    print(f"\n★ {out} 生成完了（{len(horses)}頭）。タイム指数反映: {n_tsi}走"
          + ("（未指定=プレミアム限定のため None。--tsi か --from-netkeiba で反映可）"
             if not args.tsi and not args.from_netkeiba else ""), file=sys.stderr)
    cmd = ["python", "predict.py", out, "--race-id", rid]
    if args.budget:
        cmd += ["--budget", str(args.budget)]
    if args.mobile:
        cmd.append("--mobile")
    print(f"\n次のコマンド:\n  {' '.join(cmd)}\n", file=sys.stderr)

    if args.run:
        import subprocess, os
        print("=" * 60, file=sys.stderr)
        subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    main()
