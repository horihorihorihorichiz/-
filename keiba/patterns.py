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


# ★ヒートスコア(7/25 heat_score.py・WF179発火Rで実測): 確認済み条件の重複数で単調にROIが上がる
#   1個以上163.8%(n176) 2個以上164.9%(n149) 3個以上210.7%(n113) 4個以上296.1%(n62) 5個以上645.3%(n19)
#   dev/conf両方で単調上昇を確認。1人気モデル売りは重複条件としては寄与-4.5ptのため除外済み。
HEAT_LADDER = {0: (161.0, 179), 1: (163.8, 176), 2: (164.9, 149),
               3: (210.7, 113), 4: (296.1, 62), 5: (645.3, 19)}


def heat_of(order, tan, field, surface=None, dist=None, tier=None, p1=None):
    """乖離発火レースの「熱さ」= 確認済み条件の重複数と実測ROI帯を返す。
       返り値: (該当条件list, 個数, その個数以上のWF実測ROI, サンプル数)"""
    if not order or not tan or order[0] not in tan:
        return [], 0, 0, 0
    o1 = tan[order[0]]
    hits = []
    if tier and tier >= 6:
        hits.append("上級")
    if surface == "ダ":
        hits.append("ダート")
    if dist and 1401 <= dist <= 1900:
        hits.append("中距離")
    if field and field >= 15:
        hits.append(f"多頭{field}")
    if p1 and p1 * o1 >= 1.6:
        hits.append(f"モデル価値{p1*o1:.1f}")
    if 10 <= o1 <= 30:
        hits.append(f"軸{o1}倍")
    c = min(len(hits), 5)
    roi, n = HEAT_LADDER.get(c, (161.0, 179))
    return hits, len(hits), roi, n


def classify(order, tan, field, surface=None, dist=None, tier=None, gap12=None, p1=None, day=None):
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
        # ★システム主軸フィルタ(7/20 20エージェント探索・両分割CONFIRMED): 乖離単勝の中の最上位シグナル
        mval = p1 * o1 if p1 else 0
        strong = []
        if mval >= 1.6:
            strong.append(f"モデル価値{mval:.1f}(WF186%)")
        if field and field >= 15:
            strong.append(f"多頭{field}頭(WF175%)")
        if strong:
            out.append(("◎◎乖離単勝×システム強化", f"単勝 {t1} [" + "・".join(strong) + "]",
                        185.9 if mval >= 1.6 else 175.4, "◎◎最優先買い",
                        "2年WF: モデル価値(確率×オッズ)1.6+=186%/多頭15+=175%。乖離単勝の中の最強フィルタ・厚張り候補"))
        # ★最強条件(7/19ユーザー発案の一致構造採掘): 1番人気をモデルが5位以下に酷評=群衆の錨が偽物
        vrank_all = {n: i+1 for i, n in enumerate(order)}
        fav = min(tan, key=lambda h: tan[h])
        if vrank_all.get(fav, 99) >= 5:
            out.append(("乖離単勝×1人気モデル売り", f"単勝 {t1} (1人気{fav}をモデル{vrank_all.get(fav)}位と酷評)",
                        216.7, "◎◎最強",
                        "WF 発見214.0%/53R→確認223.2%/22R 通算216.7%。厚張り候補"))
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
                        43.9, "✕見送り推奨",
                        "7/23採掘: 中距離でも条件級(1-2勝)は43.9%/56R。中距離の利益は上級戦由来"))
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
            m5 = set(sorted(tan, key=lambda h: tan[h])[:6]) - {t1}
            sys3 = [n for n in order if n != t1][:3]
            mixleg = list(dict.fromkeys([n for n in sys3 if n in m5]
                                        + [n for n in sorted(tan, key=lambda h: tan[h]) if n != t1][:2]))
            if len(mixleg) >= 3 and dist and 1401 <= dist <= 1900:
                import itertools as _it
                pts = sorted(tuple(sorted(p)) for p in _it.combinations(sorted(mixleg), 2))
                out.append(("◎◎三連複 混合紐(システム∩市場)×中距離",
                            f"三連複 {t1}軸 - {sorted(mixleg)} ながし({len(pts)}点)",
                            277.6, "◎◎最優先買い",
                            "紐=モデル2-4位のうち市場6人気内 ∪ 市場1-2人気。dev252.5%→conf325.8% "
                            "通算277.6%/105点・除外後188.4%・9ヶ月中6ヶ月+。純システム紐は89%で不採用"))
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
                            206.0, "◎買い推奨",
                            "7/25 bet_sweep: dev188.6%/258→conf231.7%/174 通算206.0%/432点・除外後172.9%。"
                            "3点版(191.5%)を全条件で上回るため6点を既定にする"))
        elif o1 < 10:
            out.append(("三連複ながし(軸オッズ不足)", f"軸{o1}倍<10倍 → ながしは見送り・単勝のみ",
                        76.0, "✕見送り推奨", "軸7-10倍のながしはWF76%=配当が3点をカバーできない"))
    else:
        add(f"単勝1位[{mrb}]", f"単勝 {t1}")
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
