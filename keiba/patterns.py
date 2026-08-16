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
    dict(cond="上級(2勝+)※旧定義ラベル", roi=141.6, dev="148.9%/45点", conf="132.5%/36点", n=81),
    # 【降格8/2】ダ: 台帳2394R版で conf57.8%/32R(<100)=ゲート不通過 → △縁。dev175.1と乖離が大きく不安定
    dict(cond="ダ", roi=127.6, dev="175.1%/47点", conf="57.8%/32点", n=79, demoted=True),
    dict(cond="中距離", roi=256.8, dev="275.3%/17点", conf="234.3%/14点", n=31),
]


# ⚠7/27注記: HEAT_LADDERの絶対値は統一前データの実測。統一版では乖離ファミリー全体が
#   209.5%/111R(ベース)〜383.0%(中距離×1勝)に動いたが、ヒート数がROIを単調に押し上げる
#   構造は不変とみなし「順序・階級分け」にのみ使う。絶対値の再較正は次回データ拡張後。
# ★ヒートスコア v2(7/25再測定・土台=7倍+×非未勝利×開催2日目以降 161R)
#   条件=1勝クラス/ダート/中距離(1301-1900)/11-17頭/モデル価値1.2+/メイン4場 の6つ。累積で単調上昇:
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
        hits.append("1勝クラス")
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
#   最強帯(10倍+×1勝クラス)×ヒート4+ = 565.8%/24R(dev589→conf538・除外413%)
#   → SS は「パターンROI300%+ かつ ヒート4以上」で定義。1点1万円帯。
TIER_BUDGET = {"SS": 10000, "S": 5000, "A": 2000, "B": 1000, "C": 0}


def tier_of(best_roi, heat_count, name=None, venue=None):
    """買い階級を返す。best_roi=最上位パターンのWF実測ROI, heat_count=重複条件数,
       name=パターン名(ヒートを適用するか判定。None=乖離扱い=後方互換)。

       ★7/27 sim_rank.py 2200R再生シミュで改定(全構成比較で「改4」採用):
         旧規則(SS=ヒート4+/ROI300単独S)は S階級が赤字・SSにヒート4の赤字帯(84%/19R)混入。
         新規則: 損益+101.7万/投下82.1万(ROI223.9%)・全階級黒字・最大DD-8.1万・
                 dev220.4%/conf228.1%・ブートストラップ2000回でP(損失)=0%。
       - SS(1万円) = 乖離系 ROI300%+ × ヒート5以上(実測322.9%/34R。ヒート4は84%で除外)
       - S (5千円) = 乖離系 ROI200-300 × ヒート4以上(システム強化圏。実測331.5%/13R)
       - A (2千円) = ROI160%+(乖離のROI300+×ヒート4もここへ退避)
       - B (千円)  = ROI105%+
       - 非乖離パターン(馬連系等)はヒートの意味が無いためROIのみで判定"""
    if best_roi is None:
        return "C", 0, ""
    kairi = name is None or ("乖離" in name or "未勝利・新馬 モデル2位" in name)
    # ★中山の乖離単勝系は場だけ死んでいる(7/29 sim場別分解: 中山23R ROI18.9% vs 他場155R 287.3%・
    #   dev/conf両期マイナス)。n=23<40で全抑止の証拠基準に届かないため、B(千円)へ自動降格して
    #   少額でデータ収集を継続する(未勝利道悪の降格と同じ流儀)。芝馬連も中山0/14だが降格対象は乖離のみ。
    if venue == "中山" and kairi and "未勝利" not in (name or ""):
        if best_roi >= 105:
            return "B", TIER_BUDGET["B"], "⚠中山の乖離は18.9%/23R(他場287%)→B降格・データ収集継続"
        return "C", 0, "見送り"
    if kairi:
        # ★8/15 SS再定義(ss_mine.py・台帳2394R): 旧「300%+×ヒート5」は台帳刷新後に主張300%超が
        #   消滅して永久に発火しない死文となったため、事前指定6セルから採掘し直した。
        #   新SS=主張230%+×ヒート4+ → 窓内参考値237.6%/42R・null p=0.000。※採掘窓内の数字であり実測ではない
        #   (ANALYSIS_20260816.md)。実測=2026-08-16凍結後の紙上成績のみ。
        if best_roi >= 230 and heat_count >= 4:
            return "SS", TIER_BUDGET["SS"], "乖離230%+×ヒート4+ [参考値237.6%/42R窓内・実測は凍結後紙上のみ]"
        if 200 <= best_roi < 230 and heat_count >= 4:
            return "S", TIER_BUDGET["S"], "乖離200-230×ヒート4+"
    if best_roi >= 160:
        note = "検証済み中位ROI" if kairi else "非乖離系(ヒート不適用)"
        return "A", TIER_BUDGET["A"], note
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
        # ★馬場層別(7/26 baba_impact.py実測): 良158.9%/64R に対し 稍75.8%/24R・重不100%/10R
        #   ＝道悪計83.0%/34R。軽キャリア馬は道悪適性が過去走から読めず市場も自分も精度が落ちる
        #   → 道悪の日は「◎買い推奨」から「△縁(小額のみ)」へ自動降格する
        wet = baba in ("稍", "重", "不")
        mv, mnote = (("△縁(小額のみ・道悪)",
                      "⚠道悪実測83.0%/34R(良は158.9%/64R)=妙味薄。買うなら半額以下")
                     if wet else ("◎買い推奨", ""))
        # ★7/27統一データ版: 閾値g12>=0.40に移動(0.34-0.44が台地・旧0.6)。138.8%/66R
        #   (dev122.2/conf154.4/除外126.8)。旧第2変種(g12帯126.0%)は本則に統合し廃止。
        if gap12 >= 0.40 and 5.0 <= o2 < 10.0:
            out.append(("◎未勝利・新馬 モデル2位中穴単勝", f"単勝 {t2} (モデル2位{o2}倍)",
                        148.4, mv,
                        "★8/2台帳2394R版: 148.4%/50R hits10 (dev178.8/conf134.1=両側通過)。旧主張138.8。"
                        "1位は買わない" + ("。" + mnote if mnote else "")))
        # 【引退7/27】未勝利芝1人気(モデル2-3位)単勝(旧108.4%): 統一データ版で95.9%＝死亡。発火停止。
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
        # ★最強帯(7/25): 1位オッズ10倍+ × 1勝クラス(tier6。※JRAのtierは{3,4,5,6,10}のみ) = 412.2%/37R
        if tier and 6 <= tier <= 9 and o1 >= 10.0:
            out.append(("◎◎◎乖離単勝×10倍+×1勝クラス", f"単勝 {t1} ({o1}倍・1勝クラス)",
                        162.4, "◎◎最優先買い",
                        "★8/2台帳2394R版: 162.4%/37R hits4 (dev170.5/conf151.9)。旧主張366.4は"
                        "特徴量再構築で剥落=Aバンドへ。n37<40につき次回拡張で再判定"))
        # ★18頭は死亡確定(7/25 16体採掘→自前再現): 18頭のみ 0的中/23R・0.0%。11-17頭に限ると201.5%/143R
        if field and field >= 18:
            out.append(("⚠乖離単勝[18頭立て]", f"単勝 {t1} は買わない(18頭)", 0.0, "✕見送り推奨",
                        "18頭立ての乖離単勝は2年0的中/23R。11-17頭に絞ると201.5%/143R(dev198.6/conf207.1)"))
        # ★実用コア(7/25): 7倍+ × 11-17頭 × 1勝クラス × 開催2日目以降 = 332.4%/63R
        #   最強帯(10倍+×1勝クラス412%/37R)より試行数が7割多く、除外後271.9%と頑健
        if (surface == "芝" and dist and 1800 <= dist <= 1999):
            out.append(("⚠乖離単勝[芝1800-1999]", f"単勝 {t1} は買わない(芝1800-1999)", 0.0,
                        "✕見送り推奨",
                        "芝1800-1999の乖離単勝は2年0的中/19R。主戦場からこの1セルを除くだけで214.9%→234.8%"))
        elif tier and 6 <= tier <= 9 and field and 11 <= field <= 17 and day and day >= 2:
            out.append(("◎◎◎乖離単勝×11-17頭×1勝クラス×2日目+", f"単勝 {t1} (実用コア)",
                        204.8, "◎◎◎最優先・厚張り",
                        "★8/2台帳2394R版: 204.8%/56R hits11 (dev203.0/conf207.4=両側通過・全ゲート合格)。"
                        "旧主張286.4。18頭除外・初日除外は継続"))
        # ★メイン4場(東京/中山/京都/阪神)は1勝クラス乖離が特に強い: 366.1%/41R vs ローカル185.3%/32R
        if venue in ("東京", "中山", "京都", "阪神") and tier and 6 <= tier <= 9 and day and day >= 2:
            # 【降格8/2】台帳2394R版: conf79.4%/18R(<100)=ゲート不通過 → △縁
            out.append(("乖離単勝×メイン4場×1勝クラス×2日目+", f"単勝 {t1} ({venue})",
                        160.9, "△縁(小額のみ)",
                        "【降格8/2】台帳2394R版160.9%/46R (dev213.2→conf79.4=conf側崩れ)。"
                        "旧主張304.8。confが100を回復するまで◎から外す"))
        # ★システム主軸フィルタ: モデル価値は1勝クラスで完全単調(1.0=250%/1.5=337%/1.6=401%/2.0=548%)
        mval = p1 * o1 if p1 else 0
        strong = []
        if mval >= 1.6:
            strong.append(f"モデル価値{mval:.1f}(1勝クラスWF401%)")
        if field and 11 <= field <= 17:
            strong.append(f"{field}頭(11-17帯WF201%)")
        if strong:
            # 【8/2台帳2394R版】mval1.6+変種は102.2%/65R(dev161.9→conf62.3)=ゲート不通過→△縁。
            #   11-17頭変種は129.5%/104R(dev104.0/conf175.7)=devが110を僅かに割るがn104・全期間129.5で
            #   Bバンド継続(実測どおりB=薄票なら妥当)。
            if mval >= 1.6:
                out.append(("乖離単勝×システム強化[mval1.6]", f"単勝 {t1} [" + "・".join(strong) + "]",
                            102.2, "△縁(小額のみ)",
                            "【降格8/2】mval1.6+は台帳2394R版102.2%/65R(conf62.3)。旧主張247.0は剥落"))
            else:
                out.append(("◎◎乖離単勝×システム強化", f"単勝 {t1} [" + "・".join(strong) + "]",
                            129.5, "◎◎最優先買い",
                            "★8/2台帳2394R版: 11-17頭変種129.5%/104R hits17(dev104.0/conf175.7)。"
                            "旧主張137.9→129.5。Bバンド(薄票)で継続"))
        # ★最強条件(7/19ユーザー発案の一致構造採掘): 1番人気をモデルが5位以下に酷評=群衆の錨が偽物
        vrank_all = {n: i+1 for i, n in enumerate(order)}
        fav = min(tan, key=lambda h: tan[h])
        if vrank_all.get(fav, 99) >= 5:
            out.append(("乖離単勝×1人気モデル売り", f"単勝 {t1} (1人気{fav}をモデル{vrank_all.get(fav)}位と酷評)",
                        98.3, "△縁(小額のみ)",
                        "【降格8/2】台帳2394R版98.3%/35R(dev38.4→conf169.4=不安定)。旧主張157.8。"
                        "全期間<105につき◎から外す"))
        # 条件付き強化版(2段階採掘の生存者)
        hits = []
        if tier and tier >= 6:
            hits.append(SURVIVORS[0])
        if surface == "ダ":
            hits.append(SURVIVORS[1])
        if dist and 1401 <= dist <= 1900 and not (tier and tier < 6):
            hits.append(SURVIVORS[2])  # 7/23層別: 中距離の利益は1勝クラス由来。2勝以上は43.9%につき抑止
        
        # ★7/23 条件マップ採掘(mine_cond.py・53条件dev/conf): 中距離×1勝クラスの重複が最強帯
        if tier and 6 <= tier <= 9 and dist and 1301 <= dist <= 1900:
            out.append(("◎◎乖離単勝×中距離×1勝クラス", f"単勝 {t1} [中距離(1301-1900)×1勝クラス=重複最強帯]",
                        233.5, "◎◎最優先買い",
                        "★8/2台帳2394R版: 233.5%/46R hits10 (dev291.3/conf175.7=両側通過・全ゲート合格)。"
                        "旧主張383.0は特徴量再構築で剥落=Sバンドへ。重複帯としては引き続き最強級"))
        # 逆に 中距離×条件クラス は43.9%/56Rの死亡帯(7/23) → 単独の中距離該当でも警告
        if dist and 1401 <= dist <= 1900 and tier and tier < 6:
            out.append(("⚠乖離単勝[中距離×2勝以上]", f"単勝 {t1} は弱い帯",
                        34.7, "✕見送り推奨",
                        "7/25監査: 中距離でも2勝以上(tier3-5)は34.7%/45R(dev53.8→conf0.0)。利益は1勝クラス戦由来"))
        for s2 in hits:
            # 【8/2】demoted=True(ゲート不通過)は△縁として出す(◎から外す)
            v2 = "△縁(小額のみ)" if s2.get("demoted") else "◎買い推奨"
            out.append((f"乖離単勝×{s2['cond']}", f"単勝 {t1} (強化条件該当)",
                        s2["roi"], v2,
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
            # 【降格7/27】混合紐×中距離: 統一データ版149.3%/44点(dev175.8/conf116.3)だが
            #   最大的中除外87.4%<95でゲート不通過→△縁(小額のみ)に降格。
            if len(mixleg) >= 3 and dist and 1401 <= dist <= 1900:
                import itertools as _it
                pts = sorted(tuple(sorted(p)) for p in _it.combinations(sorted(mixleg), 2))
                out.append(("△三連複 混合紐(システム∩市場)×中距離",
                            f"三連複 {t1}軸 - {sorted(mixleg)} ながし({len(pts)}点)",
                            149.3, "△縁(小額のみ)",
                            "★7/27統一データ版: 149.3%/44点(dev175.8/conf116.3・除外87.4=1発依存)。"
                            "(旧260.3%) ゲート不通過につき小額のみ"))
            if len(mtop) >= 3:
                m5 = set(order[:5])
                agree3 = all(p in m5 for p in mtop)
                konsen = gap12 is not None and gap12 < 0.15
                marks = ["紐一致◎(過去271%/18R)" if agree3 else "紐にモデル圏外あり"]
                if konsen:
                    marks.append("混戦◎(1-2位差薄/過去193%)")
                if agree3 and konsen:
                    marks.append("重複=最強帯(過去361%/11R)")
                # 【降格8/2】台帳2394R版: dev67.6%/36R(<110)=ゲート不通過 → △縁
                out.append(("三連複軸ながし×軸10-30倍",
                            f"三連複 {t1}軸 - {sorted(mtop)} ながし(3点)",
                            167.4, "△縁(小額のみ)",
                            "【降格8/2】台帳2394R版167.4%/59R (dev67.6→conf323.6=前半崩壊・期間偏り)。"
                            "ゲート不通過につき小額のみ／" + "・".join(marks)))
            # 【降格7/27】三連複6点(旧215.7%): 統一データ版125.7%/438点・dev60.7=前半崩壊。
            #   ゲート不通過→△縁に降格(conf208.9は後半のみの偏り)。
            if len(mtop4) >= 4:
                out.append(("△三連複 紐=市場1-4人気(6点)",
                            f"三連複 {t1}軸 - {sorted(mtop4)} ながし(6点)",
                            125.7, "△縁(小額のみ)",
                            "★7/27統一データ版: 125.7%(dev60.7/conf208.9)＝期間偏りが強くゲート不通過。"
                            "(旧215.7%) 単勝を主・こちらは小額のみ"))
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
    # ★7/27統一データ版で再採掘: 閾値はg12>=0.34に移動(旧0.3)・165.9%/70R(dev167.4/conf164.4/除外131.0)。
    #   旧変種(g12>=0.4→210.5 / メイン場→224.2)は統一版で再確立できず廃止(g12>=0.44はconf43.1で死亡)。
    if (surface == "芝" and dist and 1600 <= dist <= 1800 and gap12 is not None and gap12 >= 0.34
            and not (tier and tier >= 10) and len(order) >= 2):
        mm = "-".join(map(str, sorted(order[:2])))
        out.append(("◎◎芝 馬連モデル1-2位×1600-1800×自信", f"馬連 {mm}",
                    142.6, "◎◎最優先買い",
                    "★8/2台帳2394R版: 142.6%/61R hits9 (dev127.6/conf150.5=両側通過)。旧主張165.9。"
                    "ダート同条件は厳禁のまま"
                    + ("。⚠稍重は旧データでdev214→conf49と不安定＝稍の日は半額" if baba == "稍" else "")))
    # ===== 非乖離レースの攻略(7/25 未開拓2000R採掘・全て自前再現一致) =====
    # 【二層構造】ダート=穴を単勝で獲る(乖離単勝) / 芝=モデル上位の堅い決着を馬連・三連複で獲る
    if len(order) >= 2 and not (tier and tier >= 10):
        mm = "-".join(map(str, sorted(order[:2])))
        # 【引退7/27】芝×10頭以下の馬連(旧184.2%/165.9%):
        #   統一データ版で再確立できず(最良122.3%・dev101.9<110)。旧V3の低情報時代の癖を
        #   突いていたパターンと判断し発火停止。データが増えたら remine_g12.py で再挑戦可。
        # 【引退7/27】芝×2勝以上×自信×良の三連複(旧160.4%):
        #   統一データ版でdev71.5と崩壊(conf293は分散)。ゲート不通過につき発火停止。
        # 【引退7/27】上位平坦×12頭以下×ダの馬連(旧174.8/210.5%):
        #   統一データ版でdev53.3と完全崩壊。得点分布が変わりspread15の意味も変質した。発火停止。
        # ★外枠のモデル2位(市場が枠で嫌う馬をモデルが拾う): 内枠の同条件は83.2%で死亡
        # ⚠2026-07-26判明: これはV3に枠特徴が無いことによる順位バグを拾っていた
        #   （V3では外枠2位27.2% > モデル1位24.4%＝順位が逆転していた）。
        #   V4では枠を学習して逆転が消えた(1位25.4% > 外枠2位22.0%)ので、V4では発火させない。
        if (os.environ.get("KEIBA_ENGINE", "").lower() not in ("v4", "v5")
                and field and 13 <= field <= 16 and day and day >= 3 and waku2 and waku2 >= 7):
            fav2 = sorted(tan, key=lambda h: tan[h])[1] if len(tan) > 1 else None
            t2 = order[1]
            if fav2 != t2:
                out.append(("△外枠モデル2位×13-16頭×3日目+ 単勝", f"単勝 {t2} (モデル2位・{waku2}枠)",
                            130.4, "△縁(小額のみ)",
                            "★7/27統一データ版: 130.4%/207R(dev162.9→conf92.0)＝conf<100でゲート不通過。"
                            "(旧186.4%はV3枠バグ+旧データの産物) 参考表示のみ・買うなら小額"))
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
