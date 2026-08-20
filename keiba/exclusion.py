# -*- coding: utf-8 -*-
"""例外除外（選別）のライブ判定 — モデル非依存の純関数群（2026-08-20新設）。

   EXCLUSION_REPORT_20260818.md で確定した「レースを予想可能/例外に二分する」判定を、
   どのモデルがセッションを担当しても同じ結果になるようコード化する。
   閾値は MINE 4,440R（wf_preds_v3ext2.jsonl 〜202602）のみで決定した凍結値。
   以後の変更禁止（変更するなら新レポートと窓端の更新が必要）。

   指標（すべて発走前に入手できるもの。式は build_bsd16_ds.py と同一）:
     fav_p = 市場1番人気の implied 確率（単勝オッズ逆数を正規化した最大値）
     ent   = implied 確率分布のエントロピー（市場の割れ具合）
     sgap  = モデル1位と2位のスコア差（B-sd16レーンでは sgap16）

   判定:
     A: fav_p >= 0.341   … MINE上位40%分位（EXCLUSION_REPORT_20260818.md）
     B: ent   <= 1.904   … MINE下位40%分位（同上）
     C: sgap  >= 0.066   … MINE上位60%分位（同上・wf_preds_v3ext2の得点差で凍結。
                            B-sd16のsgap16に同値を流用してはいけない=参考表示のみ）
   選別（W12・ポートフォリオ分析の「+選別」）は A∧B のみを使う
   （PORTFOLIO_REPORT_20260820.md: 選別= fav_p>=0.341 & ent<=1.904）。

   usage: python3 exclusion.py   # selftest（オフライン）
"""
import math

# ── 凍結定数（出所: EXCLUSION_REPORT_20260818.md。MINEのみで決定・以後不変） ──
FAV_P_MIN = 0.341   # A: fav_p の MINE上位40%分位
ENT_MAX = 1.904     # B: ent の MINE下位40%分位
SGAP_MIN = 0.066    # C: sgap の MINE上位60%分位（wf_preds_v3ext2の得点差基準・参考）


# 2026-08-21 追加(監査B-4): 学習側 filtered_weights.py は `len(iv) < 6` のレースを
# 母集団から外している。ライブ側にガードが無いと、オッズAPIの部分パース失敗で
# 1-2頭しか取れなかったとき fav_p=1.0 / ent=0 となり **必ず A◯B◯** で
# 「最も堅い予想可能レース」として W12 が誤発火する（実測: judge({3:2.0}) → sel=True）。
MIN_RUNNERS = 6


def metrics(tan):
    """tan: {馬番: 単勝オッズ} → (fav_p, ent)。オッズ0/None/欠落は除外。
       式は build_bsd16_ds.py（bsd16_races.jsonl の fav_p/ent）と同一。
       オッズが MIN_RUNNERS 頭未満しか取れていない時は判定不能(None,None)。"""
    iv = {n: 1.0 / float(o) for n, o in (tan or {}).items() if o}
    tot = sum(iv.values())
    if not tot or len(iv) < MIN_RUNNERS:
        return None, None
    fav_p = max(iv.values()) / tot
    ent = -sum((x / tot) * math.log(x / tot) for x in iv.values())
    return fav_p, ent


def sgap_of(scores):
    """モデルスコア列 → 1位-2位の差（B-sd16スコアを渡せば sgap16）。"""
    if scores is None:
        return None
    ss = sorted(float(s) for s in scores)
    return (ss[-1] - ss[-2]) if len(ss) > 1 else None


def judge(tan, scores=None):
    """判定時点の単勝オッズ辞書 →
       dict(fav_p, ent, A, B, sel, sgap16)。sel = A∧B（=予想可能）。
       オッズが無ければ fav_p/ent/A/B/sel すべて None（判定不能）。"""
    fav_p, ent = metrics(tan)
    sg = sgap_of(scores)
    if fav_p is None:
        return dict(fav_p=None, ent=None, A=None, B=None, sel=None,
                    sgap16=(round(sg, 5) if sg is not None else None))
    A = fav_p >= FAV_P_MIN
    B = ent <= ENT_MAX
    return dict(fav_p=round(fav_p, 5), ent=round(ent, 5), A=A, B=B,
                sel=bool(A and B),
                sgap16=(round(sg, 5) if sg is not None else None))


def line(j):
    """対比表に出す1行。j は judge() の返り値（odds_src キーを足してもよい）。"""
    if not j or j.get("fav_p") is None:
        return "選別判定: 判定不能（オッズなし）"
    lab = "予想可能(A∧B)" if j["sel"] else "例外（買わない側）"
    sg = f"  sgap16={j['sgap16']:+.3f}" if j.get("sgap16") is not None else ""
    src = f"  [{j['odds_src']}]" if j.get("odds_src") else ""
    return (f"選別判定: {lab}  fav_p={j['fav_p']:.3f}{'◯' if j['A'] else '✕'}"
            f"(≥{FAV_P_MIN})  ent={j['ent']:.3f}{'◯' if j['B'] else '✕'}"
            f"(≤{ENT_MAX}){sg}{src}")


def selftest():
    """オフライン自己検査。異常は例外。戻り値は1行サマリ。"""
    # (a) 凍結定数（EXCLUSION_REPORT_20260818.md の値そのもの）
    assert (FAV_P_MIN, ENT_MAX, SGAP_MIN) == (0.341, 1.904, 0.066), "凍結値が書き換わった"
    # (b) metrics: 6頭均等(全2.0倍) → fav_p=1/6, ent=log6
    f, e = metrics({n: 2.0 for n in range(1, 7)})
    assert abs(f - 1 / 6) < 1e-12 and abs(e - math.log(6)) < 1e-12, "metricsの式が壊れた"
    # (c) 堅い1番人気（8頭・1.5倍+7頭20倍）→ A◯B◯=予想可能
    j = judge({1: 1.5, **{n: 20.0 for n in range(2, 9)}})
    assert j["sel"] and j["A"] and j["B"], f"堅いレースが例外扱い: {j}"
    # (c2) 2026-08-21追加(監査B-4): 頭数不足は判定不能。1頭だけのオッズで
    #      fav_p=1.0/ent=0 となり「最も堅い予想可能レース」に化けるのを防ぐ。
    for tan in ({3: 2.0}, {3: 2.0, 5: 4.0}, {n: 3.0 for n in range(1, 6)}):
        jj = judge(tan)
        assert jj["sel"] is None, f"頭数不足({len(tan)}頭)が判定不能でない: {jj}"
    assert judge({n: 3.0 for n in range(1, 7)})["sel"] is not None, "6頭が判定不能になった"
    # (d) 割れたレース(全頭5倍) → A✕B✕=例外
    j = judge({n: 5.0 for n in range(1, 9)})
    assert j["sel"] is False and not j["A"] and not j["B"], f"割れたレースが予想可能扱い: {j}"
    # (e) オッズなし → 判定不能（None）で例外にも予想可能にも倒さない
    j = judge({})
    assert j["sel"] is None and "判定不能" in line(j), "オッズ欠落の扱いが変わった"
    # (f) sgap16 = スコア1位-2位
    assert abs(sgap_of([0.5, 0.2, 0.9]) - 0.4) < 1e-12, "sgapの定義が壊れた"
    return ("選別判定6仕様OK（凍結値0.341/1.904/0.066・metrics式・A∧B判定・"
            "判定不能の扱い・頭数不足ガード・sgap定義）")


if __name__ == "__main__":
    print(selftest())
