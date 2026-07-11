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
    """JRA JSON API。1単/4馬連/5ワイド/6馬単/7三連複/8三連単。"""
    base = "https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=%s&type=%d&action=init"
    def grab(t):
        try:
            d = json.loads(_http(base % (race_id, t)))
            return d["data"]["odds"][str(t)]
        except Exception:
            return {}
    def us(k, n): return [int(k[i:i+2]) for i in range(0, 2*n, 2)]      # 分解
    tan = {str(int(k)): _f(v[0]) for k, v in grab(1).items()}
    umaren = {"%d-%d" % tuple(sorted(us(k, 2))): _f(v[0]) for k, v in grab(4).items()}
    wide   = {"%d-%d" % tuple(sorted(us(k, 2))): _f(v[0]) for k, v in grab(5).items()}
    umatan = {"%d>%d" % tuple(us(k, 2)): _f(v[0]) for k, v in grab(6).items()}     # 順序
    trip   = {"%d-%d-%d" % tuple(sorted(us(k, 3))): _f(v[0]) for k, v in grab(7).items()}
    santan = {">".join(map(str, us(k, 3))): _f(v[0]) for k, v in grab(8).items()}  # 順序
    return dict(tan=tan, umaren=umaren, wide=wide, umatan=umatan,
                sanrenpuku=trip, santan=santan)

def fetch_nar(race_id, field, axis=None):
    """NAR HTML。cart-item属性(例 _b8_c0_14_1_2=三連単⑭→①→②)から券種・組合せ・順序を確実に取得。
       b1単/b4馬連/b5ワイド/b6馬単/b7三連複/b8三連単。三連系(b7,b8)は&jiku=で軸1着固定。"""
    base = "https://nar.netkeiba.com/odds/odds_get_form.html?type=%s&race_id=%s&housiki=c0"
    prefix = [None]   # cart-item接頭辞(例 a4-45-12)を捕獲→ブックマークレット自動生成に使う
    def grab(t, extra=""):
        """cart-item から (combo_tuple, odds) を返す。comboは表示順(=着順)。"""
        h = _http((base % (t, race_id)) + extra)
        out = {}
        for pre, combo, od in re.findall(
                r'cart-item="([^"]+)_%s_c0_([0-9_]+)"[^>]*>\s*([0-9.,]+)' % t, h):
            v = _f(od)
            if v:
                out[tuple(int(x) for x in combo.split("_"))] = v
                prefix[0] = prefix[0] or pre
        return out
    # 単勝(b1)はcart-item無し。'複勝'手前のOddsセルを馬番順に拾う。
    h1 = _http(base % ("b1", race_id)).split("複勝")[0]
    tl = [_f(x) for x in re.findall(r'class="[^"]*Odds[^"]*"[^>]*>\s*([0-9]+\.[0-9])', h1)]
    tan = {str(i+1): tl[i] for i in range(min(field, len(tl))) if tl[i]}
    umaren = {"%d-%d" % tuple(sorted(k)): v for k, v in grab("b4").items()}
    wide   = {"%d-%d" % tuple(sorted(k)): v for k, v in grab("b5").items()}
    umatan = {"%d>%d" % k: v for k, v in grab("b6").items()}          # 馬単(順序)
    trip, santan = {}, {}
    if axis:
        for jk in (axis if isinstance(axis, (list, tuple)) else [axis]):
            for k, v in grab("b7", "&jiku=%d" % jk).items():
                trip["%d-%d-%d" % tuple(sorted(k))] = v
            for k, v in grab("b8", "&jiku=%d" % jk).items():
                santan[">".join(map(str, k))] = v                    # 三連単(軸1着固定)
    return dict(tan=tan, umaren=umaren, wide=wide, umatan=umatan,
                sanrenpuku=trip, santan=santan, _prefix=prefix[0])

JRA_VENUES = set("札幌 函館 福島 新潟 東京 中山 中京 京都 阪神 小倉".split())

# ---------- 自動購入: netkeibaカート投入ブックマークレット生成 ----------
BTYPE = {"単勝": "b1", "複勝": "b2", "馬連": "b4", "ワイド": "b5",
         "馬単": "b6", "三連複": "b7", "三連単": "b8"}
def make_bookmarklets(picks, race_id, prefix, budget):
    """買い目リストから netkeiba カート自動投入JSを生成。
       A=選択(オッズ画面) / B=金額セット(投票画面, NDIsam)。購入ボタンは押さない。"""
    items = []   # (btype, nums, yen)
    for kind, lbl, o, stake, p, ev in picks:
        bt = BTYPE.get(kind)
        if not bt: continue
        nums = "_".join(lbl.replace(">", "-").split("-"))   # 順序付きはそのまま連結
        items.append((bt, nums, int(stake)))
    sel = ",".join('["%s","%s"]' % (b, n) for b, n, _ in items)
    amt = ",".join('["%s","%s",%d]' % (b, n, y) for b, n, y in items)
    total = sum(y for _, _, y in items)
    js_a = ('javascript:(function(){var P="%s",R="%s",G="bet_"+R;var B=[%s];'
            'if(typeof update_cart_checkbox!=="function"){alert("netkeibaのオッズ画面で実行");return;}'
            'function add(i){if(i>=B.length){alert("%d点選択完了。画面下の購入ボタンから投票画面へ。");return;}'
            'var id=P+"_"+B[i][0]+"_c0_"+B[i][1];try{update_cart_checkbox(G,id,1,"",true);}catch(e){}'
            'setTimeout(function(){add(i+1)},120);}add(0);})();'
            % (prefix, race_id, sel, len(items)))
    js_b = ('javascript:(function(){var P="%s",R="%s",D="bet_"+R;'
            'if(typeof NDIsam!=="function"){alert("投票(金額入力)画面で実行");return;}'
            'var B=[%s];var nd=new NDIsam();var t=Date.now();'
            'for(var i=0;i<B.length;i++){var bid=P+"_"+B[i][0]+"_c0_"+B[i][1];'
            'nd.replace(D,R+"_k"+i+"_"+t,{bet_id:bid,bet_money:B[i][2]*100});}'
            'alert("%d点・合計%d円をセット。再読込→金額確認→購入は必ず自分で。");})();'
            % (prefix, race_id, amt, len(items), total))
    return js_a, js_b, total, len(items)

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
def _umt(pw, i, j):     # 馬単 P(i→j)  順序付き
    return pw[i] * pw[j] / (1 - pw[i])
def _st(pw, i, j, k):   # 三連単 P(i→j→k) 順序付き
    return pw[i] * (pw[j]/(1-pw[i])) * (pw[k]/(1-pw[i]-pw[j]))
def _nums(label):       # "8>3>4" / "3-4-8" どちらも [8,3,4]/[3,4,8]
    return [int(x) for x in re.split(r"[>-]", label)]

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
def build_buylist(rows, odds, budget=10000, floor=2.0, unit=100,
                  ev_min=1.0, n_rel=6, force=None, two_axis=False,
                  core_ratio=0.6, simple=True):
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
    ut  = {tuple(map(int, k.split(">"))): v for k, v in odds.get("umatan", {}).items() if v}   # 馬単(順)
    st  = {tuple(map(int, k.split(">"))): v for k, v in odds.get("santan", {}).items() if v}    # 三連単(順)
    order = sorted(pw, key=lambda h: -pw[h])
    dec = force or decide_axis(rows, two_axis=two_axis)
    axis = dec["axis"]; mode = dec["mode"]
    need = floor * budget

    def ceil_floor(o):   # floor担保の最小額
        return math.ceil(need / o / unit) * unit if o else unit

    # ---- BOX(S3頭): S3頭のBOX ＋ 妙味の相手(次点4頭)も含めてEV+floorで詰める ----
    if mode == "BOX":
        order_all = sorted(pw, key=lambda h: -pw[h])
        relays = [h for h in order_all if h not in axis][:4]   # 妙味相手候補
        pool = list(axis) + relays
        cands = []
        for h in axis:
            if h in tan: cands.append((pw[h]*tan[h], pw[h], tan[h], "単勝", "%d" % h))
        for i, j in itertools.combinations(pool, 2):
            if not (set((i, j)) & set(axis)): continue     # 軸を1頭は含む
            k = tuple(sorted((i, j)))
            if k in um: cands.append((_um(pw,i,j)*um[k], _um(pw,i,j), um[k], "馬連", "%d-%d"%k))
            if k in wd: cands.append((_wide(pw,i,j)*wd[k], _wide(pw,i,j), wd[k], "ワイド", "%d-%d"%k))
        for c in itertools.combinations(sorted(pool), 3):
            if len(set(c) & set(axis)) < 2: continue        # 軸を2頭は含む三連複
            if c in tp: cands.append((_p3(pw,*c)*tp[c], _p3(pw,*c), tp[c], "三連複", "%d-%d-%d"%c))
        cands = sorted([c for c in cands if c[0] >= ev_min], key=lambda c: -c[0])
        picks = []; tot = 0
        for ev, p, o, k, l in cands:
            st = ceil_floor(o)
            if tot + st > budget: continue
            picks.append([k, l, o, st, p, ev]); tot += st
        # 余りは高prob点へ(1点あたり予算の40%まで=1点集中を防ぐ)
        cap = max(unit, int(budget * 0.4 // unit) * unit)
        picks.sort(key=lambda x: -x[4]); i = 0
        guard = 0
        while tot + unit <= budget and picks and guard < 1000:
            guard += 1
            idx = i % min(3, len(picks))
            if picks[idx][3] + unit <= cap:
                picks[idx][3] += unit; tot += unit
            i += 1
        dec["core_ref"] = list(axis[:3]); dec["core_return"] = 0
        picks.sort(key=lambda x: -x[5])
        return picks, tot, dec

    # ---- 1AXIS/2AXIS: 相手を決めて「馬連＋ワイド＋三連複」のハシゴを必ず揃える ----
    #   (7/9修正: 三連複に入る馬が馬連/ワイドに居ない“歯抜け”を禁止。相手＝システム順位ベース)
    a = axis[0]
    non = [h for h in order if h not in axis]
    # 相手選定: ①人気の明確な本命(S/A/B or 単勝≤3.5)は必ず ②残りはモデルpwin順 ③S/A/Bは全員入れる
    core_pool = [h for h in non if rk.get(h) in ("S", "A", "B") or tan.get(h, 99) <= 3.5]
    core_p = sorted(core_pool, key=lambda h: tan.get(h, 9999))[:2]
    partners = list(core_p)
    for h in non:                                  # システム順位で補充(最大5頭)
        if h not in partners and len(partners) < 5:
            partners.append(h)
    for h in non:                                  # S/A/Bは5頭を超えても必ず入れる
        if rk.get(h) in ("S", "A", "B") and h not in partners:
            partners.append(h)
    # 表示・想定決着用: 相手はモデルpwin順で持つ
    partners = sorted(partners, key=lambda h: -pw[h])
    dec["core"] = core_p; dec["value"] = [h for h in partners if h not in core_p]

    head = (rk.get(a) == "S") and (tan.get(a, 99) <= 5.0 or pw[a] >= 0.25)
    picks = []; tot = 0
    def push(kind, label, o, p, stake):
        nonlocal tot
        stake = int(stake // unit) * unit
        if not o or stake < unit or tot + stake > budget: return False
        picks.append([kind, label, o, stake, p, p*o]); tot += stake
        return True

    # ===== 保証層(シナリオベース・最低ライン floor倍) =====
    # 原理: 馬連的中⇒同じ買い目のワイドも必ず的中。だから
    #   ・ワイドを「単独でfloor倍」に置けば『軸と相手が両方馬券内』の全シナリオをfloor倍保証(最安のカバー)
    #   ・ワイドが高すぎる人気相手は「馬連単独floor倍」に格下げ(ワンツーのみカバー・安い)
    #   ・floor倍に届かないトークン買いは廃止(当たっても回収が合わない買い方をしない)
    # カバー優先度 = 的中確率/円(≒EV効率) → システム上位×期待値が自然に両立
    base_cap = budget * 0.75
    covered = {}   # h -> 'full'(ワイド=両方馬券内) / 'pair'(馬連=ワンツーのみ)
    base_spent = 0
    def cover(h, cap_each):
        """相手hをfloor倍で担保。安い方(通常は馬連<ワイド)を優先しつつ、
           ワイドが cap_each 内ならfullカバー(両方馬券内シナリオまで保証)を選ぶ。"""
        nonlocal base_spent
        k = tuple(sorted((a, h)))
        wo, uo = wd.get(k), um.get(k)
        cw = ceil_floor(wo) if wo else None
        cu = ceil_floor(uo) if uo else None
        if cw and cw <= cap_each and base_spent + cw <= base_cap:
            if push("ワイド", "%d-%d" % k, wo, _wide(pw, *k), cw):
                covered[h] = "full"; base_spent += cw; return True
        if cu and cu <= cap_each and base_spent + cu <= base_cap:
            if push("馬連", "%d-%d" % k, uo, _um(pw, *k), cu):
                covered[h] = "pair"; base_spent += cu; return True
        return False
    # PhaseA: 核(人気本命S/A/B or ≤3.5倍)は必須カバー(1本かぶりを切らない)。1頭あたり上限30%。
    for h in core_p:
        cover(h, budget * 0.30)
    # PhaseB: 残る相手を効率(的中確率/円)順にカバー。1頭あたり上限22%。
    rest = [h for h in partners if h not in covered]
    def eff(h):
        k = tuple(sorted((a, h)))
        best = 0
        if wd.get(k): best = max(best, _wide(pw, *k) / ceil_floor(wd[k]))
        if um.get(k): best = max(best, _um(pw, *k) / ceil_floor(um[k]))
        return best
    for h in sorted(rest, key=lambda x: -eff(x)):
        cover(h, budget * 0.22)
    dec["coverage"] = dict(covered)
    # 単勝軸: 「軸1着・2着が相手外」のシナリオ用。floor額が予算15%以内の時だけ(トークン禁止)
    if tan.get(a) and ceil_floor(tan[a]) <= budget * 0.15:
        push("単勝", "%d" % a, tan[a], pw[a], ceil_floor(tan[a]))

    # ===== EVブースト層(残予算・各点floor倍厳守) =====
    if simple:
        # 【シンプルモード(既定)】三連複は「軸ながし・均一額」1グループだけ=ながし1回で入力可。
        #   均一額でもfloor倍を満たすオッズの組合せのみ採用(トークン禁止は維持)。
        remain = budget - tot
        combos = []
        for c in itertools.combinations(sorted(partners), 2):
            k = tuple(sorted((a,) + c))
            if k in tp and _p3(pw, *k) * tp[k] >= ev_min:
                combos.append((k, tp[k], _p3(pw, *k)))
        best = None   # (期待値合計, 均一額, 採用組)
        for u in (unit, unit*2, unit*3, unit*5):
            ok = [(k, o, p) for k, o, p in combos if o * u >= need]
            ok.sort(key=lambda x: -x[2]*x[1])
            n_max = min(len(ok), int(remain // u))
            if n_max <= 0: continue
            sel = ok[:n_max]
            evsum = sum(p*o for _, o, p in sel) * u
            if best is None or evsum > best[0]:
                best = (evsum, u, sel)
        if best:
            _, u, sel = best
            for k, o, p in sorted(sel):
                push("三連複", "%d-%d-%d" % k, o, p, u)
            dec["nagashi"] = (u, [k for k, _, _ in sel])
    else:
        # 【フルモード(--full)】三連複個別＋三連単/馬単の1着固定までEV降順で詰める
        boost = []
        for c in itertools.combinations(sorted(partners), 2):
            k = tuple(sorted((a,) + c))
            if k in tp:
                p = _p3(pw, *k)
                boost.append((p * tp[k], "三連複", "%d-%d-%d" % k, tp[k], p))
        if head:
            for x, y in itertools.permutations(partners[:4], 2):
                if (a, x, y) in st:
                    p = _st(pw, a, x, y)
                    boost.append((p * st[(a, x, y)], "三連単", "%d>%d>%d" % (a, x, y), st[(a, x, y)], p))
            for h in partners:
                if (a, h) in ut:
                    p = _umt(pw, a, h)
                    boost.append((p * ut[(a, h)], "馬単", "%d>%d" % (a, h), ut[(a, h)], p))
        for h in partners:
            if covered.get(h) == "full":
                k = tuple(sorted((a, h)))
                if um.get(k):
                    p = _um(pw, *k)
                    boost.append((p * um[k], "馬連", "%d-%d" % k, um[k], p))
        seen = {(x[0], x[1]) for x in picks}
        boost = [b for b in boost if b[0] >= ev_min and (b[1], b[2]) not in seen]
        boost.sort(key=lambda x: -x[0])
        cap1 = budget * 0.15
        for ev, kind, lbl, o, p in boost:
            c = ceil_floor(o)
            if c > cap1: continue
            push(kind, lbl, o, p, c)

    # 余り: 保証層ワイド/馬連(システム上位順)へ上乗せ=シナリオ回収がfloor倍を超えて伸びる
    prio = [x for x in picks if x[0] in ("ワイド", "馬連")]
    prio.sort(key=lambda x: -x[4])
    i = 0
    while tot + unit <= budget and prio:
        prio[i % min(3, len(prio))][3] += unit; tot += unit; i += 1

    # 想定決着(軸→相手1→相手2)の複合合算
    ref = [a] + partners[:2]
    refset = set(ref)
    def hits_ref(kind, label):
        seq = _nums(label); ns = set(seq)
        if kind == "単勝":  return seq == [ref[0]]
        if kind in ("馬連", "ワイド"): return ns <= refset and len(ns) == 2
        if kind == "馬単":  return seq == ref[:2]
        if kind == "三連複": return ns == refset
        if kind == "三連単": return seq == ref
        return False
    dec["core_ref"] = ref
    dec["core_return"] = sum(o*s for k2, l2, o, s, p2, e2 in picks if hits_ref(k2, l2))
    picks.sort(key=lambda x: -x[5])
    return picks, tot, dec

# ---------- 出力(RULES.md準拠) ----------
def print_ranking(res, tan=None):
    """全頭ランキング。RULES§1: 馬番・馬名・脚質・得点(WAvg)・PWin・ランク・単勝オッズ(人気) 全列必須・全頭省略禁止"""
    ninki = {}
    if tan:
        for i, (n, o) in enumerate(sorted(tan.items(), key=lambda kv: kv[1]), 1):
            ninki[n] = i
    print("全頭ランキング（全%d頭）" % len(res["rows"]))
    print("  馬番 馬名             脚質  得点(WAvg)   PWin  ランク  単勝(人気)")
    for r in sorted(res["rows"], key=lambda x: -x["pwin"]):
        od = ("%6.1f (%d人気)" % (tan[r["num"]], ninki[r["num"]])
              if tan and r["num"] in tan else "    --")
        print("  %2d  %-16s %-4s %7.1f  %6.1f%%   %s   %s" % (
            r["num"], r.get("name", "")[:8], r["style"], r["wavg"], r["pwin"], r["rank"], od))
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
        nums = set(_nums(lbl))
        seg = "核" if nums <= core_horses else "上積"
        flag = "" if o*st >= floor*budget else "*"
        print("  %-5s%-9s%8.1f%7d%9.0f%6.0f%% %s%s" % (kind, lbl, o, st, o*st, ev*100, seg, flag))
    print("  ── 点数まとめ ──（*=単体floor未満だが複合で担保）")
    for k, (s, n) in d.items(): print("  %s %d点 %d円" % (k, n, s))
    # ── 買い目(複合)単位の合算floorチェック：同一買い目の馬連＋ワイド＋単勝＋三連複は一緒に当たる ──
    from collections import OrderedDict
    grp = OrderedDict()
    for kind, lbl, o, st, p, ev in picks:
        key = tuple(sorted(_nums(lbl)))
        grp.setdefault(key, []).append((kind, o, st))
    print("  ── 買い目(複合)ごとの合算払戻＝最低%.0f%%チェック ──" % (floor*100))
    for key, items in grp.items():
        pay = sum(o*st for _, o, st in items)
        kinds = "+".join(k for k, _, _ in items)
        m = "○" if pay >= floor*budget else ("△" if pay >= floor*budget*0.8 else "・")
        print("   %s %-9s 合算払戻%7d円 (対予算%4.0f%%) [%s]" % (
            m, "-".join(map(str, key)), pay, pay/budget*100, kinds))
    # ── シナリオ別保証(軸×相手が馬券内になった時の最低回収) ──
    cov = dec.get("coverage")
    if cov:
        ax = dec["axis"][0]
        print("  ── シナリオ保証（軸%dと相手が馬券内の時の最低回収）──" % ax)
        wide_st = {tuple(sorted(_nums(l))): (o, s) for k2, l, o, s, p, e in picks if k2 == "ワイド"}
        um_st   = {tuple(sorted(_nums(l))): (o, s) for k2, l, o, s, p, e in picks if k2 == "馬連"}
        for h, mode_c in cov.items():
            k = tuple(sorted((ax, h)))
            if mode_c == "full":
                o, s = wide_st.get(k, (0, 0))
                extra = um_st.get(k)
                w_ret = o * s
                u_ret = w_ret + (extra[0]*extra[1] if extra else 0)
                print("   相手%2d [full] 両方馬券内=%6d円(%.0f%%) / ワンツー=%6d円(%.0f%%)"
                      % (h, w_ret, w_ret/budget*100, u_ret, u_ret/budget*100))
            else:
                o, s = um_st.get(k, (0, 0))
                print("   相手%2d [pair] ワンツーのみ=%6d円(%.0f%%)（両方馬券内どまりは対象外）"
                      % (h, o*s, o*s/budget*100))
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

def print_mobile(race, race_id, picks, total, is_jra):
    """スマホ投票用のコンパクト表示。券種ごとにまとめ、馬番昇順。
       地方=SPAT4 / JRA=IPAT のアプリに親指入力しやすい最短形。購入は人間。"""
    site = "IPAT(JRA)" if is_jra else "SPAT4(地方)"
    order = ["単勝", "複勝", "馬連", "馬単", "ワイド", "三連複", "三連単"]
    by = {}
    for kind, lbl, o, st, p, ev in picks:
        by.setdefault(kind, []).append((lbl, int(st), o))
    print("\n📱[スマホ投票] %s / %s" % (race.get("name", ""), site))
    print("  各行: 買い目=金額（現在オッズ→的中時払戻）。%s アプリに上から入力→確認→購入は自分で。" % site)
    for kind in order:
        if kind not in by: continue
        rows = sorted(by[kind], key=lambda x: [int(n) for n in re.split(r"[>-]", x[0])])
        print("─ %s ─" % kind)
        for lbl, st, o in rows:
            print("  %s = %d円 （%.1f倍 → %s円）" % (lbl, st, o, f"{int(st * o):,}"))
    print("─────────  計 %d円 / %d点" % (total, len(picks)))
    print("  ※オッズは取得時点。発走直前に変わるので最終確認は画面で。")
    _print_nagashi_plan(by, order)

def _amt_str(parts):
    """parts=[(表示ラベル, 金額)] → 均一なら『各N円』、バラなら個別表記"""
    amt = {st for _, st in parts}
    if len(amt) == 1:
        return "各%s円" % f"{parts[0][1]:,}"
    return " ".join("%s=%s円" % (lb, f"{st:,}") for lb, st in parts)

def _find_core(rows):
    """全買い目が『核セット∪外1頭』で表せる核(2-3頭)を探す（S軍団+相手の型）"""
    import itertools as _it
    horses = sorted({n for ns, _ in rows for n in ns})
    for k in (3, 2):
        best = None
        for core in _it.combinations(horses, k):
            cs = set(core)
            if not all(len(set(ns) - cs) <= 1 for ns, _ in rows):
                continue
            axes = {}
            for ns, _ in rows:
                out = set(ns) - cs
                if out:
                    axes[sorted(out)[0]] = axes.get(sorted(out)[0], 0) + 1
            inside = sum(1 for ns, _ in rows if set(ns) <= cs)
            # 軸の数が少なく・各軸の点数がまとまる核ほど読みやすい
            score = (-len(axes), sum(v * v for v in axes.values()), inside)
            if best is None or score > best[0]:
                best = (score, cs)
        if best:
            return best[1]
    return None

def _print_nagashi_plan(by, order):
    """🎯入力プラン: アプリの「ながし/BOX」入力手順(軸→相手→金額)にまとめ直す。買い目自体は同一。"""
    print("\n🎯[入力プラン(ながし形式)] アプリの流し/BOX画面でこの通り選ぶだけ")
    for kind in order:
        if kind not in by: continue
        rows = [(sorted(_nums(lbl)), int(st)) for lbl, st, o in by[kind]]
        if kind in ("単勝", "複勝"):
            for ns, st in rows:
                print("  【%s】 %d = %s円" % (kind, ns[0], f"{st:,}"))
            continue
        common = set(rows[0][0])
        for ns, _ in rows[1:]:
            common &= set(ns)
        if common:
            # 型A: 全買い目に共通の軸がいる → 王道の軸ながし
            axis = sorted(common)[0] if len(common) == 1 else None
            if len(common) == 2 and kind == "三連複":
                ax = sorted(common)
                parts = [(str(sorted(set(ns) - common)[0]), st) for ns, st in
                         sorted(rows, key=lambda x: sorted(set(x[0]) - common))]
                print("  【三連複 軸2頭ながし】 軸 %d-%d → 相手 %s（%d点） %s"
                      % (ax[0], ax[1], ",".join(lb for lb, _ in parts), len(parts), _amt_str(parts)))
                continue
            if axis is not None:
                grp = sorted(rows, key=lambda x: sorted(set(x[0]) - {axis}))
                if kind == "三連複":
                    parts = [("%d-%d" % tuple(sorted(set(ns) - {axis})), st) for ns, st in grp]
                    aite = sorted({n for ns, _ in grp for n in ns if n != axis})
                    print("  【三連複 軸1頭ながし】 軸 %d → 相手 %s から下記ペア（%d点） %s"
                          % (axis, ",".join(map(str, aite)), len(parts), _amt_str(parts)))
                else:
                    parts = [(str(next(n for n in ns if n != axis)), st) for ns, st in grp]
                    print("  【%s ながし】 軸 %d → 相手 %s（%d点） %s"
                          % (kind, axis, ",".join(lb for lb, _ in parts), len(parts), _amt_str(parts)))
                continue
        core = _find_core(rows)
        if core:
            # 型B: 核(S軍団)が相手枠。核内BOX + 外の馬ごとに核へながし
            cs = sorted(core)
            inside = sorted([r for r in rows if set(r[0]) <= core])
            outside = {}
            for ns, st in rows:
                out = set(ns) - core
                if out:
                    outside.setdefault(sorted(out)[0], []).append((ns, st))
            print("  ◆%s: 相手枠＝%s の型" % (kind, "-".join(map(str, cs))))
            for ns, st in inside:
                print("    【%s BOX内】 %s = %s円" % (kind, "-".join(map(str, ns)), f"{st:,}"))
            for ax in sorted(outside):
                grp = sorted(outside[ax], key=lambda x: sorted(set(x[0]) - {ax}))
                if kind == "三連複":
                    parts = [("%d-%d" % tuple(sorted(set(ns) - {ax})), st) for ns, st in grp]
                    lbl = "軸 %d → 相手 %s" % (ax, "-".join(map(str, cs)))
                else:
                    parts = [(str(next(n for n in ns if n != ax)), st) for ns, st in grp]
                    lbl = "軸 %d → 相手 %s" % (ax, ",".join(lb for lb, _ in parts))
                print("    【%s ながし】 %s（%d点） %s" % (kind, lbl, len(parts), _amt_str(parts)))
            continue
        # 型C: フォールバック（最頻出軸で貪欲）
        remain = rows[:]
        while remain:
            freq = {}
            for ns, st in remain:
                for n in ns:
                    freq[n] = freq.get(n, 0) + 1
            axis = max(freq, key=lambda n: freq[n])
            grp = sorted([r for r in remain if axis in r[0]], key=lambda x: sorted(set(x[0]) - {axis}))
            remain = [r for r in remain if axis not in r[0]]
            if kind == "三連複":
                parts = [("%d-%d" % tuple(sorted(set(ns) - {axis})), st) for ns, st in grp]
                print("  【三連複 軸1頭ながし】 軸 %d → ペア %s（%d点） %s"
                      % (axis, " / ".join(lb for lb, _ in parts), len(parts), _amt_str(parts)))
            else:
                parts = [(str(next(n for n in ns if n != axis)), st) for ns, st in grp]
                print("  【%s ながし】 軸 %d → 相手 %s（%d点） %s"
                      % (kind, axis, ",".join(lb for lb, _ in parts), len(parts), _amt_str(parts)))
    print("  ※ネット投票はnetkeibaの公式IPAT/SPAT4連携で（ID登録は自分の手で・GOも自分）。")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("race_json")
    ap.add_argument("--race-id", default=None)
    ap.add_argument("--odds", default=None, help="手渡しオッズjson")
    ap.add_argument("--budget", type=int, default=10000)
    ap.add_argument("--floor", type=float, default=2.0)
    ap.add_argument("--unit", type=int, default=100)
    ap.add_argument("--axis", type=int, nargs="+", default=None, help="軸を手動指定")
    ap.add_argument("--box", type=int, nargs="+", default=None, help="3頭BOX指定")
    ap.add_argument("--two-axis", action="store_true", help="S2頭を2頭軸流しにする(既定は1頭軸流し)")
    ap.add_argument("--no-odds", action="store_true", help="ランキングだけ出す")
    ap.add_argument("--full", action="store_true",
                    help="フルモード(三連複個別+三連単/馬単)。既定はシンプル(保証層+三連複ながし均一)")
    ap.add_argument("--cart", action="store_true",
                    help="netkeibaカート自動投入ブックマークレットを生成(bookmarklets_<race_id>.txt)")
    ap.add_argument("--bets", action="store_true",
                    help="自動投票ツール(IPATVoter等)向けの bets_<race_id>.json を出力")
    ap.add_argument("--mobile", action="store_true",
                    help="スマホ投票用のコンパクト買い目表示(SPAT4/IPATアプリ入力向け)")
    ap.add_argument("--cap", type=int, default=10000,
                    help="自動投入のハードキャップ(円)。買い目合計がこれを超えると生成拒否")
    a = ap.parse_args()

    race = json.load(open(a.race_json, encoding="utf-8"))
    res = calc.run(race)
    print("=" * 60)
    print(race.get("name", a.race_json), " 馬場:", race.get("baba", "?"))
    print("=" * 60)
    if a.no_odds:
        print_ranking(res)
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
            print_ranking(res)
            print("\n[オッズ自動取得に失敗:%s] --odds でオッズjsonを渡してください。" % e)
            return
    else:
        print_ranking(res)
        print("\n[race_id不明] jsonに \"race_id\" を入れるか --race-id / --odds を指定してください。")
        return
    # ランキングは単勝オッズ(人気)列込みで出す（RULES§1）
    print_ranking(res, tan={int(k): v for k, v in odds.get("tan", {}).items() if v})

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
                                      two_axis=a.two_axis, simple=not a.full)
    # GO/NO-GO(単勝EVで簡易裁定)
    order = sorted(res["rows"], key=lambda r: -r["pwin"])
    tan = {int(k): v for k, v in odds.get("tan", {}).items() if v}
    ev1 = (order[0]["pwin"]/100.0) * tan.get(order[0]["num"], 0)
    ev2 = (order[1]["pwin"]/100.0) * tan.get(order[1]["num"], 0) if len(order) > 1 else 0
    exp = sum(st*p*o for _, _, o, st, p, _ in picks) / (total or 1)
    # GO: 核(Sランク軸)が機能し、想定決着の複合合算がfloor近辺以上、かつ portfolio EVプラス。
    core_ok = dec.get("core_return", 0) >= a.floor * a.budget * 0.9
    # BOX(S3頭混戦)は核returnを持たないので、BOX全体の期待回収がfloor以上ならGO扱い
    box_ok = dec.get("mode") == "BOX" and exp >= a.floor
    go = bool(picks and exp >= 1.2 and (core_ok or box_ok or ev1 >= 1.5 or ev2 >= 1.8))
    print("\nEV裁定: %s（単勝EV1位=%.0f%% 2位=%.0f%% / 期待回収=%.0f%% / 核合算=%.0f%%）"
          % ("GO ●" if go else "見送り ○", ev1*100, ev2*100, exp*100,
             dec.get("core_return", 0)/a.budget*100))
    print_buylist(picks, total, dec, a.budget, a.floor)
    print_ipat(race, race_id, picks, total)
    if a.mobile:
        print_mobile(race, race_id, picks, total, is_jra=(venue in JRA_VENUES))

    # 自動購入(カート投入まで): --cart でブックマークレット生成。購入ボタンは人間。
    if a.cart:
        prefix = odds.get("_prefix")
        if not prefix:
            print("\n[--cart] cart-item接頭辞が取れませんでした(JRA/オッズ手渡しは非対応)。")
        elif not go:
            print("\n[--cart] EV裁定が見送りのため生成しません(GOのみ自動投入)。")
        elif total > a.cap:
            print("\n[--cart] 合計%d円がハードキャップ%d円を超過。生成しません。" % (total, a.cap))
        else:
            js_a, js_b, tt, n = make_bookmarklets(picks, race_id, prefix, a.budget)
            fn = "bookmarklets_%s.txt" % race_id
            with open(fn, "w", encoding="utf-8") as f:
                f.write("%s %d点 合計%d円 (cap %d円)\n" % (race.get("name", ""), n, tt, a.cap))
                f.write("オッズ画面: https://nar.netkeiba.com/odds/index.html?race_id=%s\n\n" % race_id)
                f.write("A) オッズ画面で実行=%d点選択:\n%s\n\n" % (n, js_a))
                f.write("B) 投票(金額)画面で実行=金額セット:\n%s\n\n" % js_b)
                f.write("※最後の購入(投票確定)は必ず人間が押す。\n")
            print("\n[--cart] %s を生成(%d点/%d円)。A→Bの順にブラウザで実行。購入は手動。" % (fn, n, tt))

    # 自動投票ツール(IPATVoter/Selenium等)向け機械可読フォーマット
    if a.bets:
        if not go:
            print("\n[--bets] EV裁定が見送りのため出力しません(GOのみ)。")
        elif total > a.cap:
            print("\n[--bets] 合計%d円がハードキャップ%d円を超過。出力しません。" % (total, a.cap))
        else:
            ENG = {"単勝": "TANSYO", "複勝": "FUKUSYO", "馬連": "UMAREN", "ワイド": "WIDE",
                   "馬単": "UMATAN", "三連複": "SANRENPUKU", "三連単": "SANRENTAN"}
            items = []
            for kind, lbl, o, stake, p, ev in picks:
                nums = _nums(lbl)   # 馬単/三連単は着順、他は昇順
                items.append(dict(type=ENG.get(kind, kind), kind=kind,
                                  numbers=nums, amount=int(stake),
                                  odds_at_build=o, ev=round(ev, 3)))
            out = dict(race_id=str(race_id), race_name=race.get("name", ""),
                       venue=race.get("venue", ""), baba=race.get("baba", ""),
                       budget=a.budget, total=total, n_bets=len(items),
                       hard_cap=a.cap, verdict="GO",
                       generated_note="購入確定は人間が確認してから。オッズ急変時は再生成。",
                       bets=items)
            fn = "bets_%s.json" % race_id
            json.dump(out, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print("\n[--bets] %s を出力(%d点/%d円)。IPATVoter系ツールの入力に。" % (fn, len(items), total))

if __name__ == "__main__":
    main()
