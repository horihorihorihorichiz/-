# -*- coding: utf-8 -*-
"""WIN5分析ツール（Ver.100）。
   数理: WIN5の払戻率は70%（全券種最悪）。勝者予測はα=0=市場と同等なので、
   選定でEV+は作れない。**キャリーオーバー週だけ**実効回収が跳ねる:
     実効期待回収 ≈ 0.70 × (1 + 繰越額 ÷ 当週売上)
   100%超の条件は「繰越額 > 0.30 × 当週売上」（式を解けばこれだけ）。

   ★2026-08-23 重大修正（外部調査報告で判明した設計欠陥）:
     旧既定 --sales 20e8 は**通常週**の売上規模。ところが繰越が発生した週は
     参加者が殺到して売上が3〜9倍に膨張する（希薄化）。実績:
        2018/12/28 繰越6.00億 → 売上34.99億（還元約97%）
        2020/07/26 繰越4.64億 → 売上31.57億（約85%）
        2025/01/26 繰越4.49億 → 売上52.67億（約79%）
        2026/02/15 繰越5.40億 → 売上62.68億（約79%）
        2011/09/11 繰越8.53億 → 売上28億（約104%）※2億上限時代・唯一の100%超
     つまり通常週の売上を当てはめると実効回収を1.5〜3倍に過大評価する。
     さらに繰越上限は6億円（2014年〜）なので、100%超に必要な「売上20億未満」は
     繰越週にはまず起こらない。**現行制度下で100%超は2014年以降ゼロ。**
     → 既定売上を繰越週の実績中央値45億に変更し、G4は原則「発火しない」のが正。

   usage: python3 win5.py [--budget 5000] [--sales 45e8] [--dry]
"""
import argparse, datetime, json, re, sys, urllib.request

import calc
import predict as PR
import harvest as HV

UA = {"User-Agent": "Mozilla/5.0"}


def fetch_win5():
    req = urllib.request.Request("https://race.netkeiba.com/top/win5.html", headers=UA)
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    rids = []
    for m in re.finditer(r"race_id=(\d{12})", h):
        if m.group(1) not in rids:
            rids.append(m.group(1))
    carry = 0
    m = re.search(r'CarryOver_Txt">([\d,]+)円', h)
    if m:
        carry = int(m.group(1).replace(",", ""))
    return rids[:5], carry


def probs_for(rid):
    """レースのブレンド勝率(市場×モデル)を返す {num: p}。オッズ未発売ならNone"""
    su = HV.FR.fetch_shutuba(rid, nar=False)
    race = HV.build_race_json(rid, su, datetime.date.today(), workers=4)
    res = calc.run(race)
    odds = PR.fetch_jra(rid)
    if not odds.get("tan"):
        return None, race
    return PR.blend_probs(res["rows"], odds["tan"]), race


def greedy_formation(P, budget, unit=100):
    """5レースの候補集合を、点数=Πk_i×100円が予算内で的中確率最大になるよう貪欲拡張"""
    sorted_h = [sorted(p, key=lambda h: -p[h]) for p in P]
    ks = [1]*5
    def cost(ks):
        c = unit
        for k in ks: c *= k
        return c
    def hitp(ks):
        v = 1.0
        for i, k in enumerate(ks):
            v *= sum(P[i][h] for h in sorted_h[i][:k])
        return v
    while True:
        best = None
        for i in range(5):
            if ks[i] >= min(4, len(sorted_h[i])):
                continue
            nk = ks[:]; nk[i] += 1
            if cost(nk) > budget:
                continue
            gain = (hitp(nk) - hitp(ks)) / (cost(nk) - cost(ks))
            if best is None or gain > best[0]:
                best = (gain, i)
        if best is None:
            break
        ks[best[1]] += 1
    return ks, hitp(ks), cost(ks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=5000)
    ap.add_argument("--sales", type=float, default=45e8,
                    help="当週売上の想定(円)。既定45億=繰越週の実績中央値(通常週6-7億とは別物)")
    ap.add_argument("--dry", action="store_true", help="対象と繰越だけ表示")
    a = ap.parse_args()

    rids, carry = fetch_win5()
    eff = 0.70 * (1 + carry/a.sales)
    print("=" * 60)
    print(f"WIN5  対象: {' '.join(rids)}")
    print(f"キャリーオーバー: {carry:,}円 → 実効期待回収 ≈ {eff*100:.0f}%"
          f"（想定売上{a.sales/1e8:.0f}億円）")
    print("=" * 60)
    if carry <= 0:
        print("裁定: 見送り ○（繰越なし=構造的に-30%。買う理由がない週）")
        return
    if a.dry:
        return

    P, names = [], []
    for rid in rids:
        p, race = probs_for(rid)
        if p is None:
            print(f"{rid}: オッズ未発売。発売後に再実行を。")
            return
        P.append(p)
        names.append(race.get("name", rid))
    ks, hp, c = greedy_formation(P, a.budget)
    print(f"\nフォーメーション（予算{a.budget}円・的中確率最大化）")
    for i, (rid, name) in enumerate(zip(rids, names)):
        top = sorted(P[i], key=lambda h: -P[i][h])[:ks[i]]
        s = " ".join(f"{h}({P[i][h]*100:.0f}%)" for h in top)
        print(f"  Leg{i+1} {name[:20]:20s}: {s}")
    print(f"  点数 {c//100}点 = {c:,}円 / 的中確率 {hp*100:.2f}% / "
          f"期待回収 ≈ {eff*100:.0f}%（選定edge=0の前提）")
    print("※購入・GOは人間。繰越が大きい週ほど価値が上がる。")


if __name__ == "__main__":
    main()
