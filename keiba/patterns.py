# -*- coding: utf-8 -*-
"""買いパターンカタログ（pattern_mine.py のウォークフォワード統計に基づく）。
   レースごとに該当パターンを判定し「推奨/縁/見送り」と過去統計ROIを返す。
   基準: ROI≥105%=買い推奨 / 95-105%=プラス圏の縁(小額のみ) / <95%=見送り推奨"""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_stats():
    try:
        rows = json.load(open(os.path.join(_DIR, "pattern_stats.json"), encoding="utf-8"))
        return {r["pattern"]: r for r in rows}
    except Exception:
        return {}


STATS = _load_stats()
# 乖離の定義(7/19改定): 得点1位のオッズ≥7倍(人気順位不問)。2段階WF 108.0%/109.0% 通算108.3%
KAIRI_NOTE = "新定義(7倍+)WF 発見108.0%→確認109.0% 通算108.3%/236R"
KAIRI_ODDS = 7.0


def verdict_of(roi):
    if roi >= 105:
        return "◎買い推奨"
    if roi >= 95:
        return "△縁(小額のみ)"
    return "✕見送り推奨"


# 2段階採掘(pattern_lab.py 7/14)の生存者: 発見(202511-04)+確認(202605-07)両方プラスのみ
# 7/19再採掘(新定義7倍+ベース)。混戦は新定義下で確認99.5%とボーダーのため降格(縁扱い)
SURVIVORS = [
    dict(cond="上級(2勝+)", roi=144.8, dev="141.1%/93点", conf="154.4%/36点", n=129),
    dict(cond="ダ", roi=136.6, dev="139.4%/82点", conf="125.7%/21点", n=103),
    dict(cond="中距離", roi=123.0, dev="122.1%/87点", conf="126.2%/26点", n=113),
]


# ★ヒートスコア v2(7/25再測定・土台=7倍+×非未勝利×開催2日目以降 161R)
#   条件=上級/ダート/中距離(1301-1900)/11-17頭/モデル価値1.2+/メイン4場 の6つ。累積で単調上昇:
#   0個173.5%(161R) 3個204.7%(133R) 5個359.0%(49R・dev328/conf423・除外281%) 6個522.5%(16R)
#   ※6個はconf期の的中が無くn=16と薄いので「5個以上」を厚張りラインとして運用する
HEAT_LADDER = {0: (173.5, 161), 1: (175.7, 159), 2: (180.3, 155),
               3: (204.7, 133), 4: (208.9, 96), 5: (359.0, 49), 6: (522.5, 16)}
MAIN_VENUES = ("東京", "中山", "京都", "阪神")


def heat_of(order, tan, field, surface=None, dist=None, tier=None, p1=None, venue=None):
    """乖離発火レースの「熱さ」= 確認済み条件の重複数と実測ROI帯。
       返り値: (該当条件list, 個数, その個数以上のWF実測ROI, サンプル数)"""
    if not order or not tan or order[0] not in tan:
        return [], 0, 0, 0
    o1 = tan[order[0]]
    hits = []
    if tier and 6 <= tier <= 9:
        hits.append("上級")
    if surface == "ダ":
        hits.append("ダート")
    if dist and 1301 <= dist <= 1900:
        hits.append("中距離")
    if field and 11 <= field <= 17:
        hits.append(f"{field}頭")
    if p1 and p1 * o1 >= 1.2:
        hits.append(f"価値{p1*o1:.1f}")
    if venue in MAIN_VENUES:
        hits.append(f"メイン場({venue})")
    c = min(len(hits), 6)
    roi, n = HEAT_LADDER.get(c, (173.5, 161))
    return hits, len(hits), roi, n


# ★階級(7/26確定・実測でヒート数がSS/Sを分離することを確認)
#   実用コア×ヒート5+ = 453.0%/37R(dev434→conf484・除外352%)
#   最強帯(10倍+×上級)×ヒート4+ = 565.8%/24R(dev589→conf538・除外413%)
#   → SS は「パターンROI300%+ かつ ヒート4以上」で定義。1点1万円帯。
TIER_BUDGET = {"SS": 10000, "S": 5000, "A": 2000, "B": 1000, "C": 0}


def tier_of(best_roi, heat_count):
    """買い階級を返す。best_roi=最上位パターンのWF実測ROI, heat_count=重複条件数"""
    if best_roi is None:
        return "C", 0, ""
    if best_roi >= 300 and heat_count >= 4:
        return "SS", TIER_BUDGET["SS"], "最強帯×ヒート4+ (実測453-566%帯)"
    if best_roi >= 300:
        return "S", TIER_BUDGET["S"], "高ROI帯だがヒート3以下"
    if best_roi >= 200 and heat_count >= 4:
        return "S", TIER_BUDGET["S"], "ROI200%+×ヒート4+"
    if best_roi >= 160:
        return "A", TIER_BUDGET["A"], "検証済みだが中位ROI"
    if best_roi >= 105:
        return "B", TIER_BUDGET["B"], "薄エッジ・小額のみ"
    return "C", 0, "見送り"


def classify(order, tan, field, surface=None, dist=None, tier=None, gap12=None, p1=None,
             day=None, venue=None, spread15=None, waku2=None, baba=None):
    """order=V3得点順の馬番リスト, tan={num:単勝オッズ}, field=頭数。
       返り値: [(パターン名, 買い目説明, ROI, 判定, note)]"""
    out = []
    if not order or not tan:
        return out
    t1 = order[0]
    mr = (sorted(tan, key=lambda h: tan[h]).index(t1) + 1) if t1 in tan else 99
    mrb = "1人気" if mr == 1 else ("2-3人気" if mr <= 3 else "4人気以下")
    fs = "小頭数" if field <= 12 else "多頭数"

    def add(key, desc, note=""):
        s = STATS.get(key)
        if not s:
            return
        roi = s["roi"]
        out.append((key, desc, roi, verdict_of(roi), note))

    o1 = tan.get(t1, 0)
    # ★未勝利・新馬専用(7/25 20エージェント採掘・懐疑2票の独立再現でCONFIRMED)
    #   構造: 1位は序列正だが得点過大(単勝67.8%)。自信レース(g12大)ほど市場が1位に過剰集中し2位中穴が売れ残る
    if tier is not None and tier >= 10 and gap12 is not None and len(order) >= 2:
        t2 = order[1]
        o2 = tan.get(t2, 0)
        if gap12 >= 0.6 and 5.0 <= o2 < 10.0:
            out.append(("◎未勝利・新馬 モデル2位中穴単勝", f"単勝 {t2} (モデル2位{o2}倍)",
                        132.6, "◎買い推奨",
                        "dev143.5%/52→conf120.2%/46 通算132.6%/98R hits20・最大的中除外124.4%。1位は買わない"))
        elif 0.6 <= gap12 < 0.95 and o2:
            out.append(("◎未勝利・新馬 モデル2位単勝(g12帯)", f"単勝 {t2} (モデル2位{o2}倍)",
                        126.0, "◎買い推奨",
                        "dev135.3%/73→conf114.8%/61 通算126.0%/134R・除外後117.7%。帯感度は0.85-1.0まで両側+"))
        if surface == "芝" and tan:
            fav = min(tan, key=lambda h: tan[h])
            vr = {n: i+1 for i, n in enumerate(order)}.get(fav, 99)
            if vr in (2, 3):
                out.append(("○未勝利・新馬芝 1人気(モデル2-3位)単勝", f"単勝 {fav} ({tan[fav]}倍1人気)",
                            108.4, "○小額のみ",
                            "108.4%/107R 勝率39%の堅実型・除外後104.3%。薄エッジにつき小額。ダートは70%で対象外"))
    fire = o1 >= KAIRI_ODDS or (o1 >= 6.0 and p1 and p1*o1 >= 1.0)  # 第2条件(7/19): 6倍+×モデル価値1.0+ WF108.1%
    # 7/21層別: 未勝利・新馬(tier10)の乖離単勝はWF46.5%/31Rで死亡 → 発火抑止
    if fire and tier is not None and tier >= 10:
        out.append(("乖離単勝[新馬・未勝利]", f"単勝 {t1} は買わない", 46.5, "✕見送り推奨",
                    "未勝利の乖離単勝はWF46.5%/31R。軽キャリア馬は市場(調教・血統)が正しい"))
        fire = False
    # ★開催初日カット(7/25 14体採掘→自前再現): 初日の乖離単勝は48.9%/18R(的中1)・2日目以降は173.5%/161R
    #   (dev174.4/conf172.0とほぼ同値=時期偏りなし)。馬場情報が読めない初日は市場も自分も当てにならない
    if fire and day == 1:
        out.append(("乖離単勝[開催初日]", f"単勝 {t1} は買わない(開催初日)", 48.9, "✕見送り推奨",
                    "初日の乖離単勝は2年48.9%/18R(的中1)。2日目以降だけで173.5%/161R・dev/conf同値"))
        fire = False
    if fire:
        add("乖離単勝(1位が4人気以下)", f"単勝 {t1}", KAIRI_NOTE)
        # ★最強帯(7/25): 1位オッズ10倍+ × 上級(2勝-OP、未勝利除く) = 412.2%/37R
        if tier and 6 <= tier <= 9 and o1 >= 10.0:
            out.append(("◎◎◎乖離単勝×10倍+×上級", f"単勝 {t1} ({o1}倍・上級)",
                        412.2, "◎◎◎最優先・厚張り",
                        "dev405.7%/23→conf422.9%/14 通算412.2%/37R hits8・最大的中除外310.3%。"
                        "10倍未満の上級は素通し帯。現行最強の単一フィルタ"))
        # ★18頭は死亡確定(7/25 16体採掘→自前再現): 18頭のみ 0的中/23R・0.0%。11-17頭に限ると201.5%/143R
        if field and field >= 18:
            out.append(("⚠乖離単勝[18頭立て]", f"単勝 {t1} は買わない(18頭)", 0.0, "✕見送り推奨",
                        "18頭立ての乖離単勝は2年0的中/23R。11-17頭に絞ると201.5%/143R(dev198.6/conf207.1)"))
        # ★実用コア(7/25): 7倍+ × 11-17頭 × 上級 × 開催2日目以降 = 332.4%/63R
        #   最強帯(10倍+×上級412%/37R)より試行数が7割多く、除外後271.9%と頑健
        if (surface == "芝" and dist and 1800 <= dist <= 1999):
            out.append(("⚠乖離単勝[芝1800-1999]", f"単勝 {t1} は買わない(芝1800-1999)", 0.0,
                        "✕見送り推奨",
                        "芝1800-1999の乖離単勝は2年0的中/19R。主戦場からこの1セルを除くだけで214.9%→234.8%"))
        elif tier and 6 <= tier <= 9 and field and 11 <= field <= 17 and day and day >= 2:
            out.append(("◎◎◎乖離単勝×11-17頭×上級×2日目+", f"単勝 {t1} (実用コア)",
                        332.4, "◎◎◎最優先・厚張り",
                        "dev319.3%/42→conf358.6%/21 通算332.4%/63R hits15・除外後271.9%。"
                        "18頭除外(0/23)と初日除外が独立に効く"))
        # ★メイン4場(東京/中山/京都/阪神)は上級乖離が特に強い: 366.1%/41R vs ローカル185.3%/32R
        if venue in ("東京", "中山", "京都", "阪神") and tier and 6 <= tier <= 9 and day and day >= 2:
            out.append(("◎◎乖離単勝×メイン4場×上級×2日目+", f"単勝 {t1} ({venue})",
                        366.1, "◎◎最優先買い",
                        "dev403.6%/25→conf307.5%/16 通算366.1%/41R hits9・除外後273.2%。"
                        "ローカル場の同条件は185.3%＝メイン場の方が乖離が効く"))
        # ★システム主軸フィルタ: モデル価値は上級で完全単調(1.0=250%/1.5=337%/1.6=401%/2.0=548%)
        mval = p1 * o1 if p1 else 0
        strong = []
        if mval >= 1.6:
            strong.append(f"モデル価値{mval:.1f}(上級WF401%)")
        if field and 11 <= field <= 17:
            strong.append(f"{field}頭(11-17帯WF201%)")
        if strong:
            out.append(("◎◎乖離単勝×システム強化", f"単勝 {t1} [" + "・".join(strong) + "]",
                        185.9 if mval >= 1.6 else 175.4, "◎◎最優先買い",
                        "2年WF: モデル価値(確率×オッズ)1.6+=186%/多頭15+=175%。乖離単勝の中の最強フィルタ・厚張り候補"))
        # ★最強条件(7/19ユーザー発案の一致構造採掘): 1番人気をモデルが5位以下に酷評=群衆の錨が偽物
        vrank_all = {n: i+1 for i, n in enumerate(order)}
        fav = min(tan, key=lambda h: tan[h])
        if vrank_all.get(fav, 99) >= 5:
            out.append(("乖離単勝×1人気モデル売り", f"単勝 {t1} (1人気{fav}をモデル{vrank_all.get(fav)}位と酷評)",
                        157.8, "◎買い推奨",
                        "7/25監査で再計測: 通算157.8%/49R dev157.4→conf158.2・除外後128.5%。"
                        "旧表記216.7%は未勝利込みの古い定義。ヒート重複条件としての寄与は-4.5ptで算入外"))
        # 条件付き強化版(2段階採掘の生存者)
        hits = []
        if tier and tier >= 6:
            hits.append(SURVIVORS[0])
        if surface == "ダ":
            hits.append(SURVIVORS[1])
        if dist and 1401 <= dist <= 1900 and not (tier and tier < 6):
            hits.append(SURVIVORS[2])  # 7/23層別: 中距離の利益は上級由来。条件級は43.9%につき抑止
        
        # ★7/23 条件マップ採掘(mine_cond.py・53条件dev/conf): 中距離×上級の重複が最強帯
        if tier and 6 <= tier <= 9 and dist and 1301 <= dist <= 1900:
            out.append(("◎◎乖離単勝×中距離×上級", f"単勝 {t1} [中距離(1301-1900)×上級=重複最強帯]",
                        331.6, "◎◎最優先買い",
                        "dev338.1%/32→conf320.5%/19 通算331.6%/51R hits12・除外後256.6%。"
                        "※1401-1900に絞ると357.6%/37R・さらにモデル価値1.30+で427.6%/29R(n薄)"))
        # 逆に 中距離×条件クラス は43.9%/56Rの死亡帯(7/23) → 単独の中距離該当でも警告
        if dist and 1401 <= dist <= 1900 and tier and tier < 6:
            out.append(("⚠乖離単勝[中距離×条件級]", f"単勝 {t1} は弱い帯",
                        34.7, "✕見送り推奨",
                        "7/25監査: 中距離でも条件級(1-2勝)は34.7%/45R(dev53.8→conf0.0)。利益は上級戦由来"))
        for s2 in hits:
            out.append((f"乖離単勝×{s2['cond']}", f"単勝 {t1} (強化条件該当)",
                        s2["roi"], "◎買い推奨",
                        f"発見{s2['dev']}→確認{s2['conf']} 通算{s2['n']}点"))
        # 三連複ながし(7/25 leg_sysvspop.py で紐構成を総当たり比較・全て2分割実測)
        #  ・純システム紐(モデル2-4位/2-5位)は全条件で人気紐に完敗(53-89%)=採用しない
        #  ・既定は市場1-4人気6点(軸10-30倍で206.0%/432点 dev189→conf232 除外173%)
        #  ・中距離だけは「システムで選び市場が認めた馬」の混合紐が上(277.6%/105点 除外188%)
        if 10 <= o1 <= 30 and (not dist or dist <= 1900):
            mtop = [n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:3]
            mtop4 = [n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:4]
            m5 = set([n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:5])
            sys3 = [n for n in order if n != t1][:3]
            mixleg = list(dict.fromkeys([n for n in sys3 if n in m5]
                                        + [n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:2]))
            if len(mixleg) >= 3 and dist and 1401 <= dist <= 1900:
                import itertools as _it
                pts = sorted(tuple(sorted(p)) for p in _it.combinations(sorted(mixleg), 2))
                out.append(("◎◎三連複 混合紐(システム∩市場)×中距離",
                            f"三連複 {t1}軸 - {sorted(mixleg)} ながし({len(pts)}点)",
                            260.3, "◎◎最優先買い",
                            "紐=モデル2-4位のうち市場5人気内 ∪ 市場1-2人気。dev238.6%→conf300.8% "
                            "通算260.3%/112点・除外後176.5%。純システム紐(モデル2-4位のみ)は89%で不採用"))
            if len(mtop) >= 3:
                m5 = set(order[:5])
                agree3 = all(p in m5 for p in mtop)
                konsen = gap12 is not None and gap12 < 0.15
                marks = ["紐一致◎(過去271%/18R)" if agree3 else "紐にモデル圏外あり"]
                if konsen:
                    marks.append("混戦◎(1-2位差薄/過去193%)")
                if agree3 and konsen:
                    marks.append("重複=最強帯(過去361%/11R)")
                out.append(("三連複軸ながし×軸10-30倍",
                            f"三連複 {t1}軸 - {sorted(mtop)} ながし(3点)",
                            166.1, "◎買い推奨",
                            "2年WF 発見108.5%/59R→確認307.8%/24R／" + "・".join(marks)))
            if len(mtop4) >= 4:
                out.append(("◎三連複 紐=市場1-4人気(6点)",
                            f"三連複 {t1}軸 - {sorted(mtop4)} ながし(6点)",
                            215.7, "◎買い推奨",
                            "7/25監査(現行発火条件で再計測): dev174.0→conf280.0 通算215.7%/366点・除外後176.7%。"
                            "3点版(207.6%・dev94.7で不安定)より6点が安定"))
        elif o1 < 10:
            out.append(("三連複ながし(軸オッズ不足)", f"軸{o1}倍<10倍 → ながしは見送り・単勝のみ",
                        76.0, "✕見送り推奨", "軸7-10倍のながしはWF76%=配当が3点をカバーできない"))
    else:
        add(f"単勝1位[{mrb}]", f"単勝 {t1}")
    # ★芝の攻略(7/25 自前精査): 芝の馬連1-2位は全体104.0%/689点で死んでいるが、
    #   **芝1600-1800m × 自信(g12>=0.3)** に絞ると 187.5%/104点(dev187.6/conf187.3=完全一致)。
    #   月ジャックナイフ9通りで147-206%と一度も崩れず、除外後164.4%。距離窓の外は全滅
    #   (1800-2400=90.4% / 1000-1400=28.5%)。同条件のダートは29.7%＝芝限定の現象。
    #   券種も馬連だけ(ワイド105% 三連複83% 単勝94%)＝「実力上位2頭の1-2着」を獲る形。
    if (surface == "芝" and dist and 1600 <= dist <= 1800 and gap12 is not None and gap12 >= 0.3
            and not (tier and tier >= 10) and len(order) >= 2):
        mm = "-".join(map(str, sorted(order[:2])))
        strong2 = gap12 >= 0.4
        main2 = venue in MAIN_VENUES and day and day >= 2
        roi2 = 224.2 if main2 else (210.5 if strong2 else 187.5)
        tags = []
        if strong2:
            tags.append("自信厚(g12≥0.4→210.5%/82点)")
        if main2:
            tags.append("メイン場×2日目+(224.2%/71点)")
        out.append(("◎◎芝 馬連モデル1-2位×1600-1800×自信", f"馬連 {mm}",
                    roi2, "◎◎最優先買い",
                    "基本形 187.5%/104点(dev187.6/conf187.3・除外後164.4・月JK147-206%)"
                    + ("／" + "・".join(tags) if tags else "")
                    + "。芝全体は104%＝距離と自信が揃った時だけ。ダート同条件は29.7%で厳禁"))
    # ===== 非乖離レースの攻略(7/25 未開拓2000R採掘・全て自前再現一致) =====
    # 【二層構造】ダート=穴を単勝で獲る(乖離単勝) / 芝=モデル上位の堅い決着を馬連・三連複で獲る
    if len(order) >= 2 and not (tier and tier >= 10):
        mm = "-".join(map(str, sorted(order[:2])))
        # ★芝×少頭数(10頭以下)の馬連: ダートの同条件は32.2%で死亡=芝限定
        if surface == "芝" and field and field <= 10:
            if gap12 is not None and 0.2 <= gap12 < 0.6:
                out.append(("◎◎芝×10頭以下×中確信 馬連1-2位", f"馬連 {mm}",
                            184.2, "◎◎最優先買い",
                            "dev144.6→conf249.3 通算184.2%/74点・除外後151.5%。"
                            "g12は山型で0.6以上(確信しすぎ)は49%に落ちる。ダ同条件は32.2%"))
            elif tier and 1 <= tier <= 5:
                out.append(("◎芝×10頭以下×条件級 馬連1-2位", f"馬連 {mm}",
                            165.9, "◎買い推奨",
                            "dev148.2→conf203.1 通算165.9%/90点・除外後138.9%。"
                            "『中距離×条件級は死亡』の逆＝少頭数芝では条件級が主戦場"))
        # ★芝×条件級×自信×良 の三連複1-2-3位: 純システム紐の唯一の生存領域(ダは53.1%)
        #  ※測定条件は【良馬場限定】。道悪では未検証につき発火させない(7/26修正)
        if (surface == "芝" and tier and 1 <= tier <= 5 and gap12 is not None and gap12 >= 0.2
                and field and field <= 16 and len(order) >= 3 and baba == "良"):
            out.append(("◎芝×条件級×自信 三連複モデル1-2-3位",
                        f"三連複 {'-'.join(map(str, sorted(order[:3])))}",
                        160.4, "◎買い推奨",
                        "dev142.0→conf197.1 通算160.4%/168点・除外後133.1%(良馬場限定)。"
                        "ダートの同条件は53.1%＝『システム紐は死亡』の唯一の例外領域"))
        # ★得点形状: 上位が平坦(1位-5位の得点差が小さい)×少頭数 の馬連
        #   spread15 = (得点1位 - 得点5位) を12スケールで割った生値
        #  ★7/26 芝ダ分割で判明: この馬連は【ダート限定】。芝は最大的中除外88.6%で1発依存
        if (spread15 is not None and spread15 < 1.0 and field and field <= 12
                and day and day >= 2):
            tight = spread15 < 0.8
            if surface == "ダ":
                out.append(("◎上位平坦×12頭以下×ダ 馬連1-2位", f"馬連 {mm} (1-5位差{spread15:.2f})",
                            210.5 if tight else 174.8, "◎買い推奨",
                            ("ダ×差<0.8: dev200.0→conf220.0 通算210.5%/44点・除外154.9%" if tight else
                             "ダ×差<1.0: dev215.2→conf147.5 通算174.8%/67点・除外138.0%")
                            + "。尖ったレースは78.9%。芝の同条件は除外後88.6%で不採用"))
            else:
                out.append(("△上位平坦×12頭以下[芝]", f"馬連 {mm} は見送り(芝)", 88.6, "✕見送り推奨",
                            "芝の上位平坦馬連は通算130.1%だが最大的中除外88.6%＝高配当1本依存。"
                            "同パターンはダート限定(174.8%・除外138.0%)で採用"))
        # ★外枠のモデル2位(市場が枠で嫌う馬をモデルが拾う): 内枠の同条件は83.2%で死亡
        # ⚠2026-07-26判明: これはV3に枠特徴が無いことによる順位バグを拾っていた
        #   （V3では外枠2位27.2% > モデル1位24.4%＝順位が逆転していた）。
        #   V4では枠を学習して逆転が消えた(1位25.4% > 外枠2位22.0%)ので、V4では発火させない。
        if (os.environ.get("KEIBA_ENGINE", "").lower() != "v4"
                and field and 13 <= field <= 16 and day and day >= 3 and waku2 and waku2 >= 7):
            fav2 = sorted(tan, key=lambda h: tan[h])[1] if len(tan) > 1 else None
            t2 = order[1]
            if fav2 != t2:
                out.append(("◎◎外枠モデル2位×13-16頭×3日目+ 単勝", f"単勝 {t2} (モデル2位・{waku2}枠)",
                            186.4, "◎◎最優先買い",
                            "dev216.4→conf148.3 通算186.4%/200点 的中63(31.5%)・除外後170.5%。"
                            "内枠(1-3枠)の同条件は83.2%で死亡／市場2番人気だと77.6%＝織込済みで妙味消滅"))
    add(f"複勝1位[{mrb}]", f"複勝 {t1}")
    if len(order) >= 2:
        add(f"ワイド1-2位[{mrb}]", f"ワイド {'-'.join(map(str, sorted(order[:2])))}")
        add(f"馬連1-2位[{mrb}]", f"馬連 {'-'.join(map(str, sorted(order[:2])))}")
    if len(order) >= 5:
        add(f"三連複BOX上位5[{fs}]", f"三連複BOX {sorted(order[:5])} (10点)")
        add(f"三連複軸1位ながし2-5位[{fs}]", f"三連複 {t1}軸-{sorted(order[1:5])} (6点)")
    out.sort(key=lambda x: -x[2])
    return out


def print_patterns(order, tan, field, surface=None, dist=None, tier=None, gap12=None, p1=None):
    pats = classify(order, tan, field, surface=surface, dist=dist, tier=tier, gap12=gap12, p1=p1)
    if not pats:
        return
    print("\n🎯 パターン判定（ウォークフォワード実測ROI・未来を知らない状態での過去統計）")
    for name, desc, roi, verd, note in pats:
        line = f"  {verd} {name}: {desc}  [過去ROI {roi:.1f}%]"
        if note:
            line += f" ※{note}"
        print(line)
    best = pats[0]
    if best[2] >= 95:
        print(f"  → 本線: {best[1]}（{best[0]} / 過去ROI {best[2]:.1f}%）")
    else:
        print("  → 全パターンがROI95%未満＝このレースは統計的に見送りが正解")
