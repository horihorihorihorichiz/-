# -*- coding: utf-8 -*-
"""
predict.py ── 競馬予想 司令塔スクリプト（Ver.99.27 エンジン + EV裁定 + 買い目 + i-PAT形式）

  「レースjson を渡すと、全頭ランキング → オッズ取得 → GO/NO-GO → 軸流し買い目 →
    i-PAT入力形式 まで一気に出す」ワンコマンド。

使い方:
  python predict.py race_xxx.json                 # 自動でオッズ取得(JRA/NAR)して全部出す
  python predict.py race_xxx.json --odds o.json   # オッズを手渡し(下記フォーマット)
  python predict.py race_xxx.json --budget 20000 --floor 3.0
  python predict.py race_xxx.json --axis 9        # 軸を手動指定(1頭軸流し)
  python predict.py race_xxx.json --box 4 9 12    # 3頭BOX指定

オッズ手渡しjson (--odds) のフォーマット:
  {
    "tan":  {"9":8.9, "4":7.2, ...},
    "umaren":       {"4-9":35.9, ...},        # 馬連  馬番は昇順ハイフン
    "wide":         {"4-9":10.8, ...},        # ワイド
    "sanrenpuku":   {"2-4-9":981.9, ...}      # 三連複 馬番は昇順
  }

★ JRAオッズAPIの型番(重要): type=1単勝 / 4馬連 / 5ワイド / 7三連複 / 8三連単。
  （8を三連複と取り違えると三連単オッズを使ってしまうので必ず7）。
"""
import sys, json, re, itertools, argparse
import calc

# ---------- オッズ取得 ----------
def _http(url):
    """proxy環境でも動くよう urllib→curl の順でフォールバック"""
    try:
        import urllib.request
        return urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        import subprocess
        return subprocess.check_output(["curl", "-s", url], timeout=25).decode("utf-8", "ignore")

def _f(x):
    try: return float(str(x).replace(",", ""))
    except: return None

def fetch_jra(race_id):
    """JRA JSON API。type=1単/4馬連/5ワイド/7三連複。返り値 dict(tan,umaren,wide,sanrenpuku)"""
    base = "https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=%s&type=%d&action=init"
    def grab(t):
        d = json.loads(_http(base % (race_id, t)))
        return d["data"]["odds"][str(t)]
    def pair_key(k):   # "0409" -> "4-9"
        a, b = int(k[:2]), int(k[2:4]); return "%d-%d" % tuple(sorted((a, b)))
    def trip_key(k):   # "020409" -> "2-4-9"
        n = sorted(int(k[i:i+2]) for i in range(0, 6, 2)); return "%d-%d-%d" % tuple(n)
    tan = {str(int(k)): _f(v[0]) for k, v in grab(1).items()}
    umaren = {pair_key(k): _f(v[0]) for k, v in grab(4).items()}
    wide = {pair_key(k): _f(v[0]) for k, v in grab(5).items()}
    trip = {trip_key(k): _f(v[0]) for k, v in grab(7).items()}
    return dict(tan=tan, umaren=umaren, wide=wide, sanrenpuku=trip)

def fetch_nar(race_id, field, axis=None):
    """NAR HTML。b1単/b4馬連/b5ワイド。組合せは昇順lexで並ぶのでzipで対応付け。
       三連複(b7)は軸(&jiku=)指定が要るので axis を渡した時だけ取得。"""
    base = "https://nar.netkeiba.com/odds/odds_get_form.html?type=%s&race_id=%s&housiki=c0"
    def odds_list(t, extra=""):
        h = _http((base % (t, race_id)) + extra)
        return [_f(x) for x in re.findall(r'class="[^"]*Odds[^"]*"[^>]*>([0-9.]+)', h)]
    nums = list(range(1, field + 1))
    tan = {}
    tl = odds_list("b1")
    for i, n in enumerate(nums):
        if i < len(tl): tan[str(n)] = tl[i]
    def pairs(t):
        ol = odds_list(t); d = {}; combos = list(itertools.combinations(nums, 2))
        for c, o in zip(combos, ol): d["%d-%d" % c] = o
        return d
    umaren = pairs("b4"); wide = pairs("b5")
    trip = {}
    if axis:  # 軸流し用: 各軸で b7&jiku= を引くと軸を含む三連複が全部並ぶ
        for jk in (axis if isinstance(axis, (list, tuple)) else [axis]):
            ol = odds_list("b7", "&jiku=%d" % jk)
            others = [n for n in nums if n != jk]
            combos = list(itertools.combinations(others, 2))
            for c, o in zip(combos, ol):
                key = "-".join(map(str, sorted((jk,) + c)))
                trip[key] = o
    return dict(tan=tan, umaren=umaren, wide=wide, sanrenpuku=trip)

JRA_VENUES = set("札幌 函館 福島 新潟 東京 中山 中京 京都 阪神 小倉".split())

# ---------- 確率(Harville) ----------
def _um(pw, i, j):
    a, b = pw[i], pw[j]
    return a*b/(1-a) + b*a/(1-b)
def _wide(pw, i, j):
    hs = list(pw); t = 0.0
    for a, b, c in itertools.permutations(hs, 3):
        if i in (a, b, c) and j in (a, b, c):
            t += pw[a]*(pw[b]/(1-pw[a]))*(pw[c]/(1-pw[a]-pw[b]))
    return t
def _p3(pw, a, b, c):
    t = 0.0
    for x, y, z in itertools.permutations([a, b, c]):
        t += pw[x]*(pw[y]/(1-pw[x]))*(pw[z]/(1-pw[x]-pw[y]))
    return t

# ---------- 軸の決め方(7/5北九州記念の反省を反映) ----------
def decide_axis(rows, two_axis=False):
    """S頭数で軸形態を決める。★7/5北九州記念の反省=既定は1頭軸流し。
       S3頭以上 -> BOX
       S2頭    -> 既定は1位を単軸・2位を相手筆頭(1頭軸流し)。
                  ┗ 2頭軸は片方が飛ぶと全滅(=7/5で④凡走→8点全滅)なので自動では選ばない。
                    2頭軸にしたい時だけ two_axis=True(--two-axis)で明示。
       S1頭以下 -> 1位を単軸。"""
    order = sorted(rows, key=lambda r: -r["pwin"])
    S = [r["num"] for r in order if r["rank"] == "S"]
    top = order[0]["num"]
    if len(S) >= 3:
        return dict(mode="BOX", axis=S[:3], note="S3頭以上→BOX")
    if len(S) == 2 and two_axis:
        return dict(mode="2AXIS", axis=[order[0]["num"], order[1]["num"]],
                    note="S2頭・2頭軸流し(明示指定/片飛び全滅リスクあり)")
    return dict(mode="1AXIS", axis=[top],
                second=order[1]["num"] if len(order) > 1 else None,
                note=("S2頭→1位を単軸・2位を相手筆頭(片飛び全滅回避=7/5反省)"
                      if len(S) == 2 else "単軸1頭流し"))

# ---------- 買い目(軸流し形式, floor担保, 上位厚く) ----------
def build_buylist(rows, odds, budget=10000, floor=2.5, unit=100,
                  ev_min=1.0, n_rel=6, force=None, two_axis=False):
    pw = {r["num"]: r["pwin"] / 100.0 for r in rows}
    tan = {int(k): v for k, v in odds.get("tan", {}).items() if v}
    um  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("umaren", {}).items() if v}
    wd  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("wide", {}).items() if v}
    tp  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("sanrenpuku", {}).items() if v}
    order = sorted(pw, key=lambda h: -pw[h])
    dec = force or decide_axis(rows, two_axis=two_axis)
    axis = dec["axis"]; mode = dec["mode"]
    rel = [h for h in order if h not in axis][:n_rel]      # 相手(モデル上位)
    need = floor * budget
    cands = []  # (ev, prob, odds, 券種, label)
    # 単勝(軸のみ)
    for h in axis:
        if h in tan:
            p = pw[h]; cands.append((p*tan[h], p, tan[h], "単勝", "%d" % h))
    if mode == "BOX":
        for i, j in itertools.combinations(axis, 2):
            k = tuple(sorted((i, j)))
            if k in um: p = _um(pw, i, j); cands.append((p*um[k], p, um[k], "馬連", "%d-%d" % k))
            if k in wd: p = _wide(pw, i, j); cands.append((p*wd[k], p, wd[k], "ワイド", "%d-%d" % k))
        for c in itertools.combinations(sorted(axis), 3):
            if c in tp: p = _p3(pw, *c); cands.append((p*tp[c], p, tp[c], "三連複", "%d-%d-%d" % c))
    else:  # 1AXIS / 2AXIS 軸流し
        # 馬連・ワイド: 軸 × (相手 ∪ もう片方の軸)
        partners = rel + [a for a in axis]
        for a in axis:
            for r in partners:
                if r == a: continue
                k = tuple(sorted((a, r)))
                if k in um and ("馬連", k) not in [(c[3], tuple(sorted(map(int, c[4].split("-"))))) for c in cands]:
                    p = _um(pw, *k); cands.append((p*um[k], p, um[k], "馬連", "%d-%d" % k))
                if k in wd and ("ワイド", k) not in [(c[3], tuple(sorted(map(int, c[4].split("-"))))) for c in cands]:
                    p = _wide(pw, *k); cands.append((p*wd[k], p, wd[k], "ワイド", "%d-%d" % k))
        # 三連複: 軸(全頭)を含む × 相手2頭
        seen = set()
        for c in itertools.combinations(sorted(set(axis) | set(rel) | ({dec.get("second")} - {None})), 3):
            if not set(axis).issubset(c) if mode == "2AXIS" else not (set(axis) & set(c)):
                continue
            if c in tp and c not in seen:
                seen.add(c); p = _p3(pw, *c); cands.append((p*tp[c], p, tp[c], "三連複", "%d-%d-%d" % c))
    # EVプラスのみ・EV降順
    cands = [c for c in cands if c[0] >= ev_min]
    cands.sort(key=lambda c: -c[0])
    # floor最小額(unit切上げ)
    picks = []
    for ev, p, o, kind, lbl in cands:
        st = -(-int(need / o) // unit) * unit
        if st <= 0: st = unit
        picks.append([kind, lbl, o, st, p, ev])
    total = sum(x[3] for x in picks)
    while total > budget and picks:
        picks.pop(); total = sum(x[3] for x in picks)     # EV最低から落とす
    # 余りは高確率(=システム上位)から上乗せ=厚く
    picks.sort(key=lambda x: -x[4])
    i = 0
    while total + unit <= budget and picks:
        picks[i % min(3, len(picks))][3] += unit; total += unit; i += 1
    picks.sort(key=lambda x: -x[5])
    return picks, total, dec

# ---------- 出力(RULES.md準拠) ----------
def print_ranking(res):
    print("全頭ランキング  馬番 脚質  得点(WAvg)  PWin  ランク")
    for r in sorted(res["rows"], key=lambda x: -x["pwin"]):
        print("  %2d %-4s  %6.1f   %5.1f%%   %s" % (r["num"], r["style"], r["wavg"], r["pwin"], r["rank"]))
    print("  展開=%s / %s" % (res.get("drlbl", ""), res.get("case", "")))

def print_buylist(picks, total, dec, budget, floor):
    from collections import defaultdict
    print("\n買い目（%s／軸=%s）" % (dec["note"], ",".join(map(str, dec["axis"]))))
    print("  %-5s%-9s%8s%7s%9s%7s" % ("券種", "買い目", "オッズ", "金額", "払戻", "EV"))
    exp = 0.0; d = defaultdict(lambda: [0, 0])
    for kind, lbl, o, st, p, ev in picks:
        exp += st*p*o; d[kind][0] += st; d[kind][1] += 1
        flag = "" if o*st >= floor*budget else " ★floor割れ"
        print("  %-5s%-9s%8.1f%7d%9.0f%6.0f%%%s" % (kind, lbl, o, st, o*st, ev*100, flag))
    print("  ── 点数まとめ ──")
    for k, (s, n) in d.items(): print("  %s %d点 %d円" % (k, n, s))
    print("  合計 %d点 / %d円 / 期待回収 %.0f%%" % (len(picks), total, exp/total*100 if total else 0))

def print_ipat(race, race_id, picks, total):
    print("\n[i-PAT入力フォーマット]")
    print("レース: %s (race_id %s)" % (race.get("name", ""), race_id))
    print("通常投票 / 単位=100円")
    for kind, lbl, o, st, p, ev in picks:
        print("%-6s %-10s %d円" % (kind, lbl, st))
    print("------------------------------")
    print("合計 %d円 / 全%d点" % (total, len(picks)))
    print("※確認画面で必ず停止。購入(投票)ボタンは人間が押す。")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("race_json")
    ap.add_argument("--race-id", default=None)
    ap.add_argument("--odds", default=None, help="手渡しオッズjson")
    ap.add_argument("--budget", type=int, default=10000)
    ap.add_argument("--floor", type=float, default=2.5)
    ap.add_argument("--unit", type=int, default=100)
    ap.add_argument("--axis", type=int, nargs="+", default=None, help="軸を手動指定")
    ap.add_argument("--box", type=int, nargs="+", default=None, help="3頭BOX指定")
    ap.add_argument("--two-axis", action="store_true", help="S2頭を2頭軸流しにする(既定は1頭軸流し)")
    ap.add_argument("--no-odds", action="store_true", help="ランキングだけ出す")
    a = ap.parse_args()

    race = json.load(open(a.race_json, encoding="utf-8"))
    res = calc.run(race)
    print("=" * 60)
    print(race.get("name", a.race_json), " 馬場:", race.get("baba", "?"))
    print("=" * 60)
    print_ranking(res)
    if a.no_odds:
        return

    # race_id: 明示 > jsonの race_id > 推定不可なら中断
    race_id = a.race_id or race.get("race_id")
    venue = race.get("venue", "")
    if a.odds:
        odds = json.load(open(a.odds, encoding="utf-8"))
    elif race_id:
        try:
            odds = (fetch_jra(race_id) if venue in JRA_VENUES
                    else fetch_nar(race_id, race.get("field", 16),
                                   axis=(a.box or a.axis or [sorted(res["rows"], key=lambda r:-r["pwin"])[0]["num"]])))
        except Exception as e:
            print("\n[オッズ自動取得に失敗:%s] --odds でオッズjsonを渡してください。" % e)
            return
    else:
        print("\n[race_id不明] jsonに \"race_id\" を入れるか --race-id / --odds を指定してください。")
        return

    # 軸の手動上書き
    force = None
    if a.box:
        force = dict(mode="BOX", axis=a.box, note="手動BOX")
    elif a.axis:
        order = sorted(res["rows"], key=lambda r: -r["pwin"])
        force = dict(mode="1AXIS", axis=a.axis,
                     second=next((r["num"] for r in order if r["num"] not in a.axis), None),
                     note="手動1頭軸流し")

    picks, total, dec = build_buylist(res["rows"], odds, budget=a.budget,
                                      floor=a.floor, unit=a.unit, force=force,
                                      two_axis=a.two_axis)
    # GO/NO-GO(単勝EVで簡易裁定)
    order = sorted(res["rows"], key=lambda r: -r["pwin"])
    tan = {int(k): v for k, v in odds.get("tan", {}).items() if v}
    ev1 = (order[0]["pwin"]/100.0) * tan.get(order[0]["num"], 0)
    exp = sum(st*p*o for _, _, o, st, p, _ in picks) / (total or 1)
    go = ev1 >= 1.5 and exp >= 1.3 and picks
    print("\nEV裁定: %s（単勝EV1位=%.0f%% / 期待回収=%.0f%%）"
          % ("GO ●" if go else "見送り ○", ev1*100, exp*100))
    print_buylist(picks, total, dec, a.budget, a.floor)
    print_ipat(race, race_id, picks, total)

if __name__ == "__main__":
    main()
