# -*- coding: utf-8 -*-
"""
pick_races.py ── 指定日（既定=次の土日）の全レースから「買う価値のあるレース」を自動選定

netkeiba 公開のレース一覧(race_list_sub.html)を NAR+JRA 両方から取得し、
重賞>特別/OP>名前付き条件 の優先度で上位 N レース（既定10）を選ぶ。
選ばれた race_id は fetch_race.py にそのまま渡せる。

使い方:
  python pick_races.py                      # 次の土日を自動選定（各日 N=10）
  python pick_races.py 20260711             # 日付指定
  python pick_races.py 20260711 --n 8       # 本数指定
  python pick_races.py --tracks 川崎,福島   # 場を絞る
  python pick_races.py 20260711 --run       # 選定後そのまま各レースを fetch_race --run（軸重視・重い）

タイム指数は新聞から --tsi で貼れば精度UP（ログイン/認証情報は一切扱わない）。
"""
import sys, re, datetime, argparse, urllib.request, gzip, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    for i in range(4):
        try:
            r = urllib.request.urlopen(req, timeout=30)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", errors="replace")
        except Exception:
            if i == 3:
                return ""
            time.sleep(2 * (i + 1))

def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

# NAR 場コード（race_id の 5-6 桁目）
NAR_VENUE = {"30": "門別", "35": "盛岡", "36": "水沢", "42": "浦和", "43": "船橋",
             "44": "大井", "45": "川崎", "46": "金沢", "47": "笠松", "48": "名古屋",
             "50": "園田", "51": "姫路", "54": "高知", "55": "佐賀", "65": "帯広"}

# レース格付け → 選定優先度（大きいほど買う価値）
def grade_of(name, grade_icons):
    gs = [int(g) for g in grade_icons if g in ("1", "2", "3")]  # 0=非重賞スロットは無視
    if gs:
        gi = min(gs)  # 1=G1 2=G2 3=G3
        return {1: ("G1", 100), 2: ("G2", 95), 3: ("G3", 90)}[gi]
    n = name
    if re.search(r"(Jpn[123]|ダービー|記念|オークス|大賞典|グランプリ|皐月|菊花|天皇賞|有馬|宝塚|安田)", n):
        return "重賞", 88
    # オープン/リステッド: ステークス表記 or 末尾S or (L)/(OP)
    if re.search(r"(ステークス|[ぁ-んァ-ヶ一-龠ー]S(\b|$|\s|\())|\(L\)|\(OP\)|オープン|リステッド", n):
        return "OP/L", 62
    if "特別" in n:
        return "特別", 60
    if re.search(r"(未勝利|新馬|1勝クラス|2勝クラス|3勝クラス|メイクデビュー|サラ系一般|系一般)", n):
        return "条件", 10
    if re.search(r"(賞|カップ|杯|トロフィー|チャレンジ|プレミアム)", n):
        return "名物", 42   # 地方の特別＝名前付き条件
    if re.search(r"[ABC][123]", n):   # クラス表記のみ（C1/B2 等）
        return "地方条件", 22
    return "その他", 15

def fetch_list(date, nar):
    host = "nar.netkeiba.com" if nar else "race.netkeiba.com"
    h = get(f"https://{host}/top/race_list_sub.html?kaisai_date={date}")
    if not h:
        return []
    # 場ヘッダごとに分割して venue を拾う
    out = []
    # dt(見出し) と dd(レース群) が交互。単純化: 各Itemの直前ヘッダを引く
    # 場名は RaceList_DataTitle。Item を順に読み、直近の title を venue にする。
    tokens = re.split(r'(<p class="RaceList_DataTitle">.*?</p>)', h, flags=re.S)
    venue = ""
    for tk in tokens:
        mt = re.match(r'<p class="RaceList_DataTitle">(.*?)</p>', tk, re.S)
        if mt:
            t = strip(mt.group(1))
            mv = re.search(r"(?:\d+回)?\s*([^\d\s]+?)\s*(?:\d+日目)?$", t)
            venue = mv.group(1) if mv else t
            continue
        for it in re.findall(r'<li class="RaceList_DataItem[^"]*">(.*?)</li>', tk, re.S):
            rid = re.search(r"race_id=(\d+)", it)
            if not rid:
                continue
            num = re.search(r"Race_Num.*?>\s*(\d+)R", it, re.S)
            nm = re.search(r"ItemTitle[^>]*>(.*?)</", it, re.S)
            gi = re.findall(r"Icon_GradeType(\d+)", it)
            dist = re.search(r"([芝ダ])\s*(\d{3,4})m", it)
            tm = re.search(r"Itemtime[^>]*>(.*?)</", it, re.S) or re.search(r">(\d\d:\d\d)<", it)
            name = strip(nm.group(1)) if nm else ""
            glabel, gscore = grade_of(name, gi)
            ven = venue or NAR_VENUE.get(rid.group(1)[4:6], "")
            out.append({
                "race_id": rid.group(1), "venue": ven,
                "r": int(num.group(1)) if num else 0,
                "name": name, "grade": glabel, "score": gscore,
                "dist": dist.group(0) if dist else "",
                "time": strip(tm.group(1)) if tm else "",
                "kind": "NAR" if nar else "JRA",
            })
    return out

def weekend_dates():
    today = datetime.date.today()
    sat = today + datetime.timedelta((5 - today.weekday()) % 7)
    sun = sat + datetime.timedelta(1)
    # 当日が土日ならその日から
    if today.weekday() == 5:
        sat = today
    if today.weekday() == 6:
        sat, sun = today, today
    return sorted({sat, sun})

def select(races, n, tracks):
    races = [r for r in races if r["venue"] != "帯広"]  # ばんえいは calc.py 対象外
    if tracks:
        races = [r for r in races if any(t in r["venue"] for t in tracks)]
    # 条件戦(平場)は既定で除外して「特別/重賞/名物」を優先
    named = [r for r in races if r["score"] >= 40]
    pool = named if named else races
    pool.sort(key=lambda r: (-r["score"], r["time"] or "99:99"))
    return pool[:n]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", help="YYYYMMDD（省略時=次の土日）")
    ap.add_argument("--n", type=int, default=10, help="1日あたり選ぶ本数（既定10）")
    ap.add_argument("--tracks", help="場を絞る（カンマ区切り 例: 川崎,福島）")
    ap.add_argument("--run", action="store_true", help="選定後 各レースを fetch_race --run で回す")
    ap.add_argument("--budget", type=int, default=10000)
    ap.add_argument("--mobile", action="store_true", help="スマホ投票用表示も出す")
    args = ap.parse_args()

    dates = [args.date] if args.date else [d.strftime("%Y%m%d") for d in weekend_dates()]
    tracks = [t.strip() for t in args.tracks.split(",")] if args.tracks else None

    picked_all = []
    for date in dates:
        races = fetch_list(date, nar=True) + fetch_list(date, nar=False)
        sel = select(races, args.n, tracks)
        picked_all += sel
        dd = datetime.datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d (%a)")
        print(f"\n==== {dd}  選定 {len(sel)}レース / 全{len(races)}レース ====")
        print(" 発走  場  R  グレード  レース名                 距離        race_id")
        print(" " + "-" * 74)
        for r in sel:
            print(f" {r['time']:>5} {r['venue']:<3}{r['r']:>2}R {r['grade']:<5} "
                  f"{r['name'][:22]:<22} {r['dist']:<9} {r['race_id']}")

    print(f"\n合計 {len(picked_all)}レース選定。各レースの予想:")
    print("  python fetch_race.py <race_id> --run --budget", args.budget)
    print("  ※タイム指数を新聞から貼れる時: python fetch_race.py <race_id> --tsi tsi.txt --run")

    if args.run:
        import subprocess, os
        for r in picked_all:
            print("\n" + "=" * 70)
            print(f"▼ {r['venue']}{r['r']}R {r['name']} ({r['race_id']})")
            cmd = ["python", "fetch_race.py", r["race_id"], "--run", "--budget", str(args.budget)]
            if args.mobile:
                cmd.append("--mobile")
            subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    main()
