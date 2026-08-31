# -*- coding: utf-8 -*-
"""発見した「オッズ不使用ルール」を、理論的に成立しているか検証する。

   採掘は 2,780 セルを総当りしたので、そのままでは「たまたま当たったセル」を
   拾っただけかもしれない。以下の3つを潰して初めて“ロジック”と呼べる:

     A. 対照実験（これが本命）
        同じ246レースで「市場の1-2-3番人気」「ランダム3頭」の三連複も買う。
        モデルだけが儲かるなら、それはレース種別の性質ではなく**モデルの実力**。
        市場も儲かるなら、単にそのレース種別の三連複が過大配当なだけ。

     B. 分散の評価
        三連複の配当は裾が重い。ブートストラップでROIの95%区間を出し、
        下限が100%を割るなら「たまたま」の可能性を明示する。

     C. 多重検定
        モデルの並びだけをレース内でシャッフルした偽データで同じ採掘をかけ、
        「何もないはずのデータから何セル合格が出るか」を数える。

   usage: python3 rule_audit.py [wf_preds_v4bin2s.jsonl]
"""
import json, random, sys
from collections import defaultdict

from oddsfree_mine import JRA_CODE, key_of

MAIN4 = ("東京", "中山", "京都", "阪神")


def load(path):
    out = []
    for l in open(path, encoding="utf-8"):
        d = json.loads(l)
        pay = d.get("payout") or {}
        if not pay.get("単勝"):
            continue
        o = [int(x) for x in d["order"]]
        rid = d["rid"]
        odds = {int(k): float(v) for k, v in (d.get("odds") or {}).items() if v}
        out.append(dict(month=d["month"], rid=rid, order=o, trio=pay.get("三連複") or {},
                        tier=d.get("tier"), baba=(d.get("baba") or "").strip(),
                        day=int(rid[8:10]), odds=odds,
                        venue=d.get("venue") or JRA_CODE.get(rid[4:6], "")))
    return out


def in_rule(r):
    return (r["tier"] == 6 and r["venue"] in MAIN4
            and r["baba"] == "良" and r["day"] >= 2)


def ret_of(r, nums):
    return float(r["trio"].get(key_of(nums), 0))


def roi(vals):
    return sum(vals)/(len(vals)*100)*100 if vals else 0.0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "wf_preds_v4bin2s.jsonl"
    rows = [r for r in load(path) if in_rule(r)]
    print(f"対象: 1勝クラス×メイン4場×良×2日目+  {len(rows)}R  ({path})\n")

    # ── A. 対照実験 ──────────────────────────────────────────────
    rnd = random.Random(20260726)
    model, market, rand = [], [], []
    for r in rows:
        model.append(ret_of(r, r["order"][:3]))
        mk = sorted([n for n in r["order"] if n in r["odds"]], key=lambda n: r["odds"][n])
        market.append(ret_of(r, mk[:3]) if len(mk) >= 3 else 0.0)
        rand.append(ret_of(r, rnd.sample(r["order"], 3)))
    print("── A. 同じ246レースで買い方だけ変えた対照実験（三連複1点） ──")
    for name, v in (("モデル1-2-3位", model), ("市場1-2-3番人気", market), ("ランダム3頭", rand)):
        h = sum(1 for x in v if x > 0)
        print(f"  {name:14s} ROI {roi(v):6.1f}%  的中{h:3d}/{len(v)} ({h/len(v)*100:4.1f}%)"
              f"  平均配当{(sum(v)/h if h else 0):7.0f}円")
    print("  → モデルだけが100%を超えるなら、レース種別の性質ではなくモデルの実力。")

    # ── B. ブートストラップ ─────────────────────────────────────
    B = 10000
    rb = random.Random(1)
    boots = sorted(roi([model[rb.randrange(len(model))] for _ in model]) for _ in range(B))
    lo, hi = boots[int(B*0.025)], boots[int(B*0.975)]
    p_lose = sum(1 for x in boots if x < 100)/B
    print(f"\n── B. ブートストラップ({B}回・レース単位で復元抽出) ──")
    print(f"  ROI点推定 {roi(model):.1f}%  95%区間 [{lo:.1f}%, {hi:.1f}%]")
    print(f"  ROI<100%(負け)になる割合 {p_lose*100:.1f}%")
    print("  ※三連複は配当の裾が重く区間は必ず広い。下限が100%を割るなら断定はできない。")

    # ── C. 多重検定(帰無分布) ───────────────────────────────────
    print("\n── C. 多重検定: モデルの並びをレース内シャッフルした偽データ ──")
    allrows = load(path)
    real = [r for r in allrows if in_rule(r)]
    hits = []
    for t in range(200):
        rr = random.Random(1000+t)
        v = []
        for r in real:
            o = list(r["order"])
            rr.shuffle(o)
            v.append(ret_of(r, o[:3]))
        hits.append(roi(v))
    hits.sort()
    ge = sum(1 for x in hits if x >= roi(model))/len(hits)
    print(f"  偽データ200回の同条件ROI: 中央値{hits[100]:.1f}% / 95パーセンタイル{hits[189]:.1f}%")
    print(f"  実測{roi(model):.1f}%以上が偶然出た割合 = {ge*100:.1f}%"
          f"  → {'有意' if ge < 0.05 else '有意とは言えない'}(この条件を固定した場合)")
    print("  ※ただし条件自体を2,780セルから選んでいるので、条件選択込みの検定はDに示す。")

    if "--null-sweep" in sys.argv:
        null_sweep(path)


def null_sweep(path, trials=20):
    """D. 条件選択込みの多重検定。
       モデルの並びをレース内でシャッフル＝「モデルに実力が無い」偽世界を作り、
       **同じ2,780セルの総当り採掘を丸ごと**かける。偽世界で平均何セル合格するかが、
       採掘手続きそのものの偽陽性率。実測14件がそれを大きく上回らなければ、
       14件は「探した数だけ出ただけ」ということになる。"""
    import itertools
    import oddsfree_mine as OM

    rows = OM.load(path)
    print(f"\n── D. 条件選択込みの多重検定（{trials}回・全セル採掘をやり直す） ──")
    counts, best = [], []
    for t in range(trials):
        rr = random.Random(7000+t)
        cells = defaultdict(OM.Cell)
        for r in rows:
            o = list(r["order"])
            rr.shuffle(o)
            r2 = dict(r, order=o, waku1=r["waku1"], g12=r["g12"], spread15=r["spread15"])
            dev = r["month"] <= OM.DEV_MAX
            cs = sorted(OM.conds(r2))
            for bt, stake, ret in OM.bets(r2):
                for c in cs:
                    cells[(bt, c)].add(stake, ret, dev)
                for c1, c2 in itertools.combinations(cs, 2):
                    cells[(bt, f"{c1} × {c2}")].add(stake, ret, dev)
        ok = [c for c in cells.values()
              if c.n >= 40 and c.hits >= 5 and c.dev >= 110 and c.conf >= 100 and c.excl >= 95]
        counts.append(len(ok))
        best.append(max((c.roi for c in ok), default=0.0))
        print(f"  偽世界{t+1:2d}: 合格{len(ok):3d}件 / 最高ROI {best[-1]:6.1f}%", flush=True)
    counts.sort(); best.sort()
    mean = sum(counts)/len(counts)
    print(f"\n  偽世界の合格数: 平均{mean:.1f}件 中央値{counts[len(counts)//2]}件 "
          f"最大{counts[-1]}件")
    print(f"  偽世界の最高ROI: 中央値{best[len(best)//2]:.1f}% 最大{best[-1]:.1f}%")
    print(f"  実測: 合格14件 / 最高ROI 209.9%（本命ルールは164.8%）")
    print("  → 実測の合格数と最高ROIが偽世界の分布を明確に超えていれば、"
          "採掘手続きの偽陽性では説明できない。")


if __name__ == "__main__":
    main()
