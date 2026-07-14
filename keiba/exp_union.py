# -*- coding: utf-8 -*-
"""統合ラウンド: 6ファミリーの勝ち特徴を合流させた最終候補。
   U1=全部盛り / U2=各ファミリー最強成分に絞った版 / U3=U2からL2強め"""
import exp_harness as H
import exp_course_apt as CA
import exp_form_trajectory as FT
import exp_class_context as CC
import exp_pace_context as PC
import exp_agari_context as AG

UNION = {
    # course_apt_B(最強): 条件一致成績・距離帯ベスト・ピッタリ距離複勝率・芝ダ替わり・道悪適性
    "course": ["cond_perf", "db_best", "exact_dist_place", "surf_switch", "wet_apt"],
    "agari":  ["agari_dist_match", "agari_mean3_rel", "agari_close_q"],
    "form":   ["fin_best2", "layoff_lastfin"],
    "class":  ["classup_lastgood", "field_chg"],
}
FNMAP = {}
FNMAP.update({k: CA.FEATS[k] for k in UNION["course"]})
FNMAP.update({k: FT.FEATS[k] for k in UNION["form"]})
FNMAP.update({k: CC.FEATS[k] for k in UNION["class"]})
FNMAP.update(dict(agari_dist_match=AG.agari_dist_match,
                  agari_mean3_rel=AG.agari_mean3_rel,
                  agari_close_q=AG.agari_close_q))

if __name__ == "__main__":
    ds = H.load_base()
    print(f"dataset: {len(ds)}R", flush=True)
    for name, fn in FNMAP.items():
        H.add_feature(ds, name, fn)
        print("feat +", name, flush=True)
    all_extra = [f for fam in UNION.values() for f in fam]
    r1 = H.run_experiment(ds, extra=all_extra, label="U1_全部盛り", l2=0.05)
    r2 = H.run_experiment(ds, extra=all_extra, label="U2_L2強め", l2=0.10)
    lean = ["cond_perf", "db_best", "exact_dist_place", "wet_apt",
            "agari_dist_match", "agari_mean3_rel", "fin_best2"]
    r3 = H.run_experiment(ds, extra=lean, label="U3_絞り込み", l2=0.05)
    print("\n==== summary ====")
    for r in (r1, r2, r3):
        print(f"{r['label']}: train={r['train']['capture5']:.1f} test={r['test']['capture5']:.1f} "
              f"全3頭={r['train']['all3']:.1f}/{r['test']['all3']:.1f} gate={r['gate']}")
    best = max((r1, r2, r3), key=lambda r: (r["gate"], r["test"]["capture5"] + r["train"]["capture5"]))
    import json
    json.dump(best, open("exp_union_best.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("best →", best["label"], "(exp_union_best.json)")
