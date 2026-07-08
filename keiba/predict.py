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
import sys, json, re, itertools, argparse, math
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

# ---------- 買い目: 二層構造 核(Sランク×上位A/B)＋上積み(期待値馬) ----------
def build_buylist(rows, odds, budget=10000, floor=2.5, unit=100,
                  ev_min=1.0, n_rel=6, force=None, two_axis=False,
                  core_ratio=0.6):
    """設計思想(7/8スパーキング反省):
       ① 軸=モデル最上位Sランク馬(decide_axis)。SをEV妙味で外さない。
       ② 【核】軸×上位A/B(pwin上位2頭) を単勝/馬連/ワイド/三連複で必ず押さえる
          =的中率重視。短オッズ本命はfloor未満でも可(核は当てにいく)。
       ③ 【上積み】期待値馬(軸と組んでEV高い穴)を三連複中心に薄く=配当重視。
          上積みだけは floor(250%) を厳守。
       core_ratio=核に回す予算割合。"""
    pw = {r["num"]: r["pwin"] / 100.0 for r in rows}
    rk = {r["num"]: r["rank"] for r in rows}
    tan = {int(k): v for k, v in odds.get("tan", {}).items() if v}
    um  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("umaren", {}).items() if v}
    wd  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("wide", {}).items() if v}
    tp  = {tuple(sorted(map(int, k.split("-")))): v for k, v in odds.get("sanrenpuku", {}).items() if v}
    order = sorted(pw, key=lambda h: -pw[h])
    dec = force or decide_axis(rows, two_axis=two_axis)
    axis = dec["axis"]; mode = dec["mode"]
    need = floor * budget

    def ceil_floor(o):   # floor担保の最小額
        return math.ceil(need / o / unit) * unit if o else unit

    # ---- BOX(S3頭)は従来通り ----
    if mode == "BOX":
        cands = []
        for h in axis:
            if h in tan: cands.append((pw[h]*tan[h], pw[h], tan[h], "単勝", "%d" % h))
        for i, j in itertools.combinations(axis, 2):
            k = tuple(sorted((i, j)))
            if k in um: cands.append((_um(pw,i,j)*um[k], _um(pw,i,j), um[k], "馬連", "%d-%d"%k))
            if k in wd: cands.append((_wide(pw,i,j)*wd[k], _wide(pw,i,j), wd[k], "ワイド", "%d-%d"%k))
        for c in itertools.combinations(sorted(axis), 3):
            if c in tp: cands.append((_p3(pw,*c)*tp[c], _p3(pw,*c), tp[c], "三連複", "%d-%d-%d"%c))
        cands = sorted([c for c in cands if c[0] >= ev_min], key=lambda c: -c[0])
        picks = [[k, l, o, ceil_floor(o), p, ev] for ev, p, o, k, l in cands]
        tot = sum(x[3] for x in picks)
        while tot > budget and picks: picks.pop(); tot = sum(x[3] for x in picks)
        picks.sort(key=lambda x: -x[4]); i = 0
        while tot + unit <= budget and picks:
            picks[i % min(3, len(picks))][3] += unit; tot += unit; i += 1
        picks.sort(key=lambda x: -x[5])
        return picks, tot, dec

    # ---- 1AXIS/2AXIS: 核＋上積み ----
    a = axis[0]
    non = [h for h in order if h not in axis]
    # 核相手=「モデルも市場も評価」する馬=ランクS/A/Bかつ単勝オッズが低い(人気)上位2頭。
    #   期待値馬(モデルだけ高評価の高オッズ穴)が核に紛れ込むのを防ぐ。
    core_pool = [h for h in non if rk.get(h) in ("S", "A", "B")] or non
    core_p = sorted(core_pool, key=lambda h: tan.get(h, 9999))[:2]
    # 期待値馬=核以外で 軸と組んだ時のEVが高い順(=市場に売られてる妙味馬)
    val_p = sorted([h for h in non if h not in core_p],
                   key=lambda h: -(pw[h]*tan.get(h, 0)))[:3]
    dec["core"] = core_p; dec["value"] = val_p

    core, value = [], []   # [kind,label,odds,prob,ev]
    def add(lst, kind, key, o, p):
        if o: lst.append([kind, key, o, p, p*o])
    # 【核】: 単勝a + (2頭軸なら両軸) 馬連/ワイド a×core + 三連複 a+core2
    for ax in axis:
        add(core, "単勝", "%d" % ax, tan.get(ax), pw[ax])
    for ax in axis:
        for c in core_p:
            k = tuple(sorted((ax, c)))
            add(core, "馬連", "%d-%d" % k, um.get(k), _um(pw, *k))
            add(core, "ワイド", "%d-%d" % k, wd.get(k), _wide(pw, *k))
    if len(core_p) >= 2 or (mode == "2AXIS"):
        base = sorted(set(list(axis) + core_p))
        for c in itertools.combinations(base, 3):
            if set(axis) & set(c) and c in tp:
                add(core, "三連複", "%d-%d-%d" % c, tp[c], _p3(pw, *c))
    # 【上積み】: 軸+核+期待値馬 の三連複、軸×期待値馬 の馬連/ワイド(EV降順)
    for v in val_p:
        k = tuple(sorted((a, v)))
        add(value, "馬連", "%d-%d" % k, um.get(k), _um(pw, *k))
        add(value, "ワイド", "%d-%d" % k, wd.get(k), _wide(pw, *k))
    bridge = sorted(set(list(axis) + core_p + val_p))
    for c in itertools.combinations(bridge, 3):
        if a in c and c in tp and not set(c) <= (set(axis) | set(core_p)):
            add(value, "三連複", "%d-%d-%d" % c, tp[c], _p3(pw, *c))

    # 重複除去
    def dedup(lst):
        seen = set(); out = []
        for x in lst:
            key = (x[0], x[1])
            if key not in seen: seen.add(key); out.append(x)
        return out
    core = dedup(core); value = dedup([v for v in value if (v[0], v[1]) not in
                                       {(c[0], c[1]) for c in core}])

    # ---- 配分 ----
    # 参照決着(軸1着→核①2着→核②3着)。この「買い目」で当たる核点を合算し floor(250%) を担保。
    #   複合(同一買い目の馬連＋ワイド＋単勝＋三連複)は一緒に当たるので合算でfloorを考える。
    ref = list(axis[:1]) + core_p[:2]
    refset = set(ref)
    def hits_ref(kind, label):
        ns = set(int(x) for x in label.split("-"))
        if kind == "単勝":  return ns <= refset and ns == set(axis[:1])
        if kind in ("馬連", "ワイド"): return ns <= refset and len(ns) == 2
        if kind == "三連複": return ns == refset
        return False
    core_budget = int(budget * core_ratio // unit) * unit
    picks = []
    hit_core = sorted([x for x in core if hits_ref(x[0], x[1])], key=lambda x: -x[2])
    miss_core = [x for x in core if not hits_ref(x[0], x[1])]
    if hit_core:
        # 先頭(最高オッズの当たり買い目)を floor 担保。以降は安全網としてprob重み配分。
        top = hit_core[0]
        st0 = min(ceil_floor(top[2]), core_budget)
        picks.append([top[0], top[1], top[2], st0, top[3], top[4]])
        rest = hit_core[1:] + miss_core
        rb = max(0, core_budget - st0); ws = sum(x[3] for x in rest) or 1
        for x in rest:
            st = max(unit, int(rb * x[3] / ws // unit) * unit)
            picks.append([x[0], x[1], x[2], st, x[3], x[4]])
    else:
        for x in core: picks.append([x[0], x[1], x[2], unit, x[3], x[4]])
    core_total = sum(x[3] for x in picks)
    # 参照決着での核・合算払戻(=複合で当たる合計)
    dec["core_ref"] = ref
    dec["core_return"] = sum(o*st for k, l, o, st, p, ev in picks if hits_ref(k, l))
    # 上積み(期待値馬): 残予算で EV降順・各点 floor(250%)厳守
    value = sorted([v for v in value if v[4] >= ev_min], key=lambda x: -x[4])
    tot = core_total
    for x in value:
        st = ceil_floor(x[2])
        if tot + st > budget: continue
        picks.append([x[0], x[1], x[2], st, x[3], x[4]]); tot += st
    # 余りは核の当たり買い目(合算floor)へ上乗せ
    picks.sort(key=lambda x: -x[4]); i = 0
    while tot + unit <= budget and picks:
        picks[i % min(3, len(picks))][3] += unit; tot += unit; i += 1
    dec["core_return"] = sum(o*st for k, l, o, st, p, ev in picks if hits_ref(k, l))
    picks.sort(key=lambda x: -x[5])
    return picks, tot, dec

# ---------- 出力(RULES.md準拠) ----------
def print_ranking(res):
    print("全頭ランキング  馬番 脚質  得点(WAvg)  PWin  ランク")
    for r in sorted(res["rows"], key=lambda x: -x["pwin"]):
        print("  %2d %-4s  %6.1f   %5.1f%%   %s" % (r["num"], r["style"], r["wavg"], r["pwin"], r["rank"]))
    print("  展開=%s / %s" % (res.get("drlbl", ""), res.get("case", "")))

def print_buylist(picks, total, dec, budget, floor):
    from collections import defaultdict
    core_horses = set(dec.get("axis", [])) | set(dec.get("core", []))
    print("\n買い目（%s／軸=%s 核相手=%s 期待値馬=%s）" % (
        dec["note"], ",".join(map(str, dec["axis"])),
        ",".join(map(str, dec.get("core", []))), ",".join(map(str, dec.get("value", [])))))
    print("  %-5s%-9s%8s%7s%9s%7s %s" % ("券種", "買い目", "オッズ", "金額", "払戻", "EV", "区分"))
    exp = 0.0; d = defaultdict(lambda: [0, 0])
    for kind, lbl, o, st, p, ev in picks:
        exp += st*p*o; d[kind][0] += st; d[kind][1] += 1
        nums = set(int(x) for x in lbl.split("-"))
        seg = "核" if nums <= core_horses else "上積"
        flag = "" if o*st >= floor*budget else "*"
        print("  %-5s%-9s%8.1f%7d%9.0f%6.0f%% %s%s" % (kind, lbl, o, st, o*st, ev*100, seg, flag))
    print("  ── 点数まとめ ──（*=単体floor未満だが複合で担保）")
    for k, (s, n) in d.items(): print("  %s %d点 %d円" % (k, n, s))
    # ── 買い目(複合)単位の合算floorチェック：同一買い目の馬連＋ワイド＋単勝＋三連複は一緒に当たる ──
    from collections import OrderedDict
    grp = OrderedDict()
    for kind, lbl, o, st, p, ev in picks:
        key = tuple(sorted(int(x) for x in lbl.split("-")))
        grp.setdefault(key, []).append((kind, o, st))
    print("  ── 買い目(複合)ごとの合算払戻＝250%%担保チェック ──")
    for key, items in grp.items():
        pay = sum(o*st for _, o, st in items)
        kinds = "+".join(k for k, _, _ in items)
        m = "○" if pay >= floor*budget else ("△" if pay >= floor*budget*0.8 else "・")
        print("   %s %-9s 合算払戻%7d円 (対予算%4.0f%%) [%s]" % (
            m, "-".join(map(str, key)), pay, pay/budget*100, kinds))
    if dec.get("core_return"):
        cr = dec["core_return"]; ref = dec.get("core_ref", [])
        print("  【核】想定決着 %s で複合合算払戻=%d円 (対予算%.0f%%)" % (
            "→".join(map(str, ref)), cr, cr/budget*100))
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
    ev2 = (order[1]["pwin"]/100.0) * tan.get(order[1]["num"], 0) if len(order) > 1 else 0
    exp = sum(st*p*o for _, _, o, st, p, _ in picks) / (total or 1)
    # GO: 核(Sランク軸)が機能し、想定決着の複合合算がfloor近辺以上、かつ portfolio EVプラス。
    core_ok = dec.get("core_return", 0) >= a.floor * a.budget * 0.9
    go = bool(picks and exp >= 1.2 and (core_ok or ev1 >= 1.5 or ev2 >= 1.8))
    print("\nEV裁定: %s（単勝EV1位=%.0f%% 2位=%.0f%% / 期待回収=%.0f%% / 核合算=%.0f%%）"
          % ("GO ●" if go else "見送り ○", ev1*100, ev2*100, exp*100,
             dec.get("core_return", 0)/a.budget*100))
    print_buylist(picks, total, dec, a.budget, a.floor)
    print_ipat(race, race_id, picks, total)

if __name__ == "__main__":
    main()
