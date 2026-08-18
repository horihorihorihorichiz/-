# -*- coding: utf-8 -*-
"""place_real_result.json から報告書用のMarkdown表を吐く補助（数字の転記ミス防止）。

usage: python3 place_real_tables.py [--json place_real_result.json]
"""
import argparse, json

BET_JP = dict(fuku="複勝", wide="ワイド", trio="三連複", umaren="馬連")
SPLITS = ("MINE", "VALIDATE", "CONFIRM")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="place_real_result.json")
    a = ap.parse_args()
    D = json.load(open(a.json, encoding="utf-8"))

    for v, R in D.items():
        print("\n\n######## %s ########" % v)
        print("races=%d / α推定=%d(8頭以上) / 5-7頭=%d"
              % (R["n_races"], R["n_alpha_races"], R["n_small_field"]))

        print("\n### α_place fold表")
        print("| fold | 分割 | 学習R | α(実複勝オッズ) | α(単勝Harville) | α(両方入り) |")
        print("|---|---|---:|---|---|---|")
        for m, f in R["folds"].items():
            if f.get("skipped"):
                continue
            row = [m, f["split"], str(f["train"])]
            for nm in ("real", "hv", "both"):
                d = f[nm]
                row.append("%+.4f (%.4f, z%+.2f)" % (d["alpha"], d["se_alpha"], d["z_alpha"]))
            print("| " + " | ".join(row) + " |")
        for nm, jp in (("real", "実複勝オッズ"), ("hv", "単勝Harville"), ("both", "両市場入り")):
            d = R["alpha_%s" % nm]
            print("- %s: α>0 %d/%d fold・最長連続%d・最終fold %+.4f"
                  % (jp, d["pos"], d["n"], d["max_run"], d["last"]))
        print("- ヌル検査(%s): 実データ %+.4f / ヌル8本 平均%+.4f 最大%+.4f / 実データ以上 %d/8"
              % (R["null"]["fold"], R["null"]["real_alpha"], R["null"]["mean"],
                 R["null"]["max"], R["null"]["n_ge_real"]))

        print("\n### OOS対数損失(1頭あたり)")
        print("| 分割 | 市場側 | 頭数 | 市場のみ | +モデル | 改善 |")
        print("|---|---|---:|---|---|---|")
        for sp in SPLITS:
            for nm, jp in (("real", "実複勝"), ("hv", "Harville")):
                d = R["oos_logloss"].get("%s/%s" % (sp, nm))
                if d:
                    print("| %s | %s | %d | %.6f | %.6f | %+.6f |"
                          % (sp, jp, d["n"], d["market"], d["full"], d["gain"]))

        print("\n### 控除率（実オッズ実測）")
        print("| 券種 | Σ(1/odds) | 実測控除率 | EV=1に必要なエッジ |")
        print("|---|---:|---:|---:|")
        for k in ("fuku", "wide", "trio", "umaren"):
            d = R["takeout"][k]
            print("| %s | %.4f | %.1f%% | ×%.3f |"
                  % (BET_JP[k], d["mean_sum_inv_odds"], d["implied_takeout"] * 100,
                     1 + d["required_edge"]))
        if R.get("odds_ratio"):
            print("\n下限→実払戻の平均倍率(MINE期・的中組): "
                  + " / ".join("%s ×%.3f (n=%d)" % (BET_JP[k], d["mean"], d["n"])
                               for k, d in R["odds_ratio"].items()))

        print("\n### 券種別 成績（全ルール）")
        print("| 分割 | 券種 | 確率 | 較正 | オッズ | ルール | n | 的中 | ROI% | ROI(下限精算)% | 平均EV | 実測的中率 | モデル平均確率 | 市場implied |")
        print("|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for tag, d in R["bets"].items():
            sp, kind, src, cal, om, rule = tag.split("/")
            print("| %s | %s | %s | %s | %s | %s | %d | %d | %.1f | %.1f | %.2f | %s | %s | %s |"
                  % (sp, BET_JP[kind], src, cal, om, rule, d["n"], d["hits"], d["roi"],
                     d["roi_floor"], d["mean_ev"],
                     ("%.4f%%" % d["hit_rate"]),
                     ("%.6f" % d["mean_p"]) if d["mean_p"] else "-",
                     ("%.6f" % d["mean_imp"]) if d["mean_imp"] else "-"))

        print("\n### 合否")
        npass = sum(1 for x in R["verdict"].values() if x["pass_"])
        print("合格 %d / %d 組合せ" % (npass, len(R["verdict"])))
        best = sorted(R["verdict"].items(),
                      key=lambda kv: -min(kv[1]["val"][1], kv[1]["conf"][1]))[:8]
        print("\n| ルール | VAL n / ROI | CONF n / ROI | 判定 |")
        print("|---|---|---|---|")
        for k, x in best:
            print("| %s | %d / %.1f%% | %d / %.1f%% | %s |"
                  % (k, x["val"][0], x["val"][1], x["conf"][0], x["conf"][1],
                     "合格" if x["pass_"] else "不合格"))

        if R.get("kelly"):
            print("\n### ケリー（EV>=1の点を全部・1レースあたりの資金比率合計）")
            for k, d in R["kelly"].items():
                print("- %s : 平均 %.3f / 90%%点 %.3f (n=%dR)"
                      % (k, d["mean_total_f"], d["p90"], d["n"]))


if __name__ == "__main__":
    main()
