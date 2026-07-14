# -*- coding: utf-8 -*-
"""Ver.2統合チャンピオン(U2)の追加特徴量アグリゲータ。
   エージェント実験(exp_*)の勝ち特徴12個を本体(fit_v2/v2_live)へ供給する。
   ※exp_agari_contextはimport時にhist/から標準上がりテーブルを構築する(数秒)。"""
import exp_course_apt as CA
import exp_form_trajectory as FT
import exp_class_context as CC
import exp_agari_context as AG

UNION_FEATS = {
    # コース適性B
    "cond_perf": CA.FEATS["cond_perf"],
    "db_best": CA.FEATS["db_best"],
    "exact_dist_place": CA.FEATS["exact_dist_place"],
    "surf_switch": CA.FEATS["surf_switch"],
    "wet_apt": CA.FEATS["wet_apt"],
    # 上がり文脈A4
    "agari_dist_match": AG.agari_dist_match,
    "agari_mean3_rel": AG.agari_mean3_rel,
    "agari_close_q": AG.agari_close_q,
    # フォーム軌道C
    "fin_best2": FT.FEATS["fin_best2"],
    "layoff_lastfin": FT.FEATS["layoff_lastfin"],
    # クラス文脈C
    "classup_lastgood": CC.FEATS["classup_lastgood"],
    "field_chg": CC.FEATS["field_chg"],
}
ORDER = ["cond_perf", "db_best", "exact_dist_place", "surf_switch", "wet_apt",
         "agari_dist_match", "agari_mean3_rel", "agari_close_q",
         "fin_best2", "layoff_lastfin", "classup_lastgood", "field_chg"]


def extra_feats(h, race):
    return {k: UNION_FEATS[k](h, race, None) for k in ORDER}
