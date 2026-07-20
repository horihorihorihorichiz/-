# -*- coding: utf-8 -*-
"""大井(TCK)専用 買いパターン判定（7/20の19角度探索→メイン独立再現の確定分）。
   predict.py が venue==44(大井) のとき呼ぶ想定。JRA用 patterns.py とは別系統。

   実装済み確定パターン:
   - 本命: 三連複「1人気外し×モデル6位内」ながし (2年通算141.6%/207R)
   - 既知: 単勝15倍+×混戦g12<0.15 (183.6%)
   - 副(紙上): 降級×モデルTop3×前走6着以下×tier9+ 単勝 (172.8%)

   classify(order, tan, pops, g12, dist, tier, model6, demote_flags) -> [(name,desc,roi,verdict,note)]
     order: モデル順の馬番list / tan: {馬番:実オッズ} / pops: {馬番:人気}
     model6=order[:6]のset / demote_flags: {馬番:True}=降級かつ前走6着以下(histから事前算出)
"""


def classify(order, tan, pops, g12=None, dist=None, tier=None, demote_flags=None):
    out = []
    if not order:
        return out
    m1 = order[0]
    o1 = tan.get(m1, 0)
    top6 = set(order[:6])

    # --- 既知生存: 単勝15倍+×混戦 ---
    if o1 >= 15 and g12 is not None and g12 < 0.15:
        out.append(("大井 単勝15倍+×混戦", f"単勝 {m1}", 183.6, "◎買い推奨",
                    "2年183.6%/47R。市場が見捨てた深乖離×モデル僅差"))

    # --- 本命: 三連複 1人気外し×モデル6位内 ---
    if 2.5 <= o1 < 7.0 and g12 is not None and 0.15 <= g12 < 0.30:
        cand = sorted((n for n in tan if n != m1 and pops.get(n) in (2, 3, 4) and n in top6),
                      key=lambda n: pops.get(n, 99))
        if len(cand) >= 2:
            out.append(("大井 三連複 1人気外し×モデル6位内",
                        f"三連複 軸{m1} - 紐{cand}(市場2-4人気∩モデル6位内) ながし",
                        141.6, "◎買い推奨",
                        "2年141.6%/207R 全年+。対照:1人気入れると85.8%/モデル絞り無しで121.8%"))

    # --- 副(紙上): 降級×モデルTop3×前走大敗 単勝 ---
    if demote_flags and (tier or 0) >= 9:
        picks = [n for n in order[:3] if demote_flags.get(n)]
        for n in picks:
            out.append((f"大井 降級Top3×前走大敗 単勝",
                        f"単勝 {n}(降級・前走6着以下・モデルTop3)", 172.8, "○紙上検証枠",
                        "2年172.8%/65R。年別ばらつき大につき紙上優先"))
    out.sort(key=lambda x: -x[2])
    return out
