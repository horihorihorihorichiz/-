"""
新・展開加点エンジン (Development Scoring Engine)

21名の予想家エージェントの議論結果を統合した多角的展開加点システム。
従来の「脚質×1.2倍」を廃止し、9つの評価軸による加減算方式を採用。

評価軸:
  1. ラップ消耗度 (LDI + RII → TRI)
  2. ポジション適合度 (EPI → ガウス適合)
  3. トラックバイアス
  4. 馬場状態補正
  5. コース特性
  6. 血統ペース適性
  7. 馬群密集度
  8. 騎手展開適応
  9. コンディション
  + 確信度係数 / 能力差スケーリング
"""

from __future__ import annotations

import math
import statistics
from typing import Optional

from .models import (
    CourseInfo, DevelopmentScore, HorseEntry, PaceScenario,
    RaceContext, RunningStyle, TrackCondition,
)


class DevelopmentEngine:
    """展開加点エンジン"""

    def calculate(self, ctx: RaceContext) -> list[DevelopmentScore]:
        """全出走馬の展開加点を計算"""
        # Step 0: 各馬の想定ポジション (EPI) を算出
        epis = self._calc_all_epi(ctx)

        # Step 1: TRI (総合展開インパクト) を算出
        tri = self._calc_tri(ctx)

        # Step 2: ペース増幅係数 (FPI) を算出
        paf = self._calc_pace_amplification(ctx)

        # Step 3: メンバー均一度を算出
        ability_scaling = self._calc_member_uniformity(ctx)

        results = []
        for i, horse in enumerate(ctx.entries):
            score = DevelopmentScore(horse_name=horse.name)
            norm_epi = epis[i]

            # 1. ラップ消耗ベーススコア
            score.lap_depletion_score = self._calc_lap_depletion(
                tri, norm_epi, ctx.num_runners
            )

            # 2. ポジション適合度
            score.position_fit_score = self._calc_position_fit(
                norm_epi, ctx.pace_scenario, ctx.course
            )

            # 3. トラックバイアス
            score.track_bias_score = self._calc_track_bias(
                horse, norm_epi, ctx
            )

            # 4. 馬場補正
            score.ground_factor_score = self._calc_ground_factor(
                horse, ctx.track_condition, ctx.pace_scenario
            )

            # 5. コース特性
            score.course_score = self._calc_course_score(
                horse, norm_epi, ctx.course, ctx.pace_scenario
            )

            # 6. 血統ペース適性
            score.bloodline_score = self._calc_bloodline(
                horse, ctx.pace_scenario, ctx.course
            )

            # 7. 馬群密集度
            score.member_density_score = self._calc_density(
                horse, ctx, paf
            )

            # 8. 騎手展開適応
            score.jockey_score = self._calc_jockey(horse, ctx.pace_scenario)

            # 9. コンディション
            score.condition_score = self._calc_condition(horse)

            # 確信度係数
            score.confidence_factor = max(0.3, ctx.pace_confidence)

            # 能力差スケーリング
            score.ability_scaling = ability_scaling

            # 合算
            raw = (
                score.lap_depletion_score
                + score.position_fit_score
                + score.track_bias_score
                + score.ground_factor_score
                + score.course_score
                + score.bloodline_score
                + score.member_density_score
                + score.jockey_score
                + score.condition_score
            )

            # 確信度と能力差スケーリングを適用
            scaled = raw * score.confidence_factor * score.ability_scaling

            # クリッピング (-14 ~ +20)
            score.total_score = max(-14.0, min(20.0, scaled))

            results.append(score)

        return results

    # ─── EPI (想定ポジション) ───

    def _calc_all_epi(self, ctx: RaceContext) -> list[float]:
        """全馬のEPI (正規化: 0=最前, 1=最後方) を算出"""
        raw_epis = []
        n = ctx.num_runners
        course_form_coeff = self._course_form_coeff(ctx.course)

        for horse in ctx.entries:
            gate_norm = (horse.post_position - 1) / max(n - 1, 1)
            raw = (
                0.35 * horse.avg_position_index
                + 0.25 * horse.avg_first_corner
                + 0.15 * self._normalize_3f_deviation(horse.first_3f_deviation)
                + 0.15 * horse.jockey_lead_tendency
                + 0.10 * gate_norm * course_form_coeff
            )
            # 気性補正 + 出遅れリスク
            raw += horse.temperament_correction + horse.gate_miss_risk

            # 乗り替わり補正
            if horse.jockey_changed:
                raw += (horse.jockey_lead_tendency - horse.prev_jockey_tendency) * 0.5

            raw_epis.append(raw)

        # メンバー内で正規化 (0~1)
        min_epi = min(raw_epis)
        max_epi = max(raw_epis)
        span = max_epi - min_epi if max_epi != min_epi else 1.0
        return [(e - min_epi) / span for e in raw_epis]

    def _course_form_coeff(self, course: CourseInfo) -> float:
        """コース形態による枠順影響係数"""
        base = 300
        dist = course.first_corner_dist
        return 1.0 + (base - dist) / base * 0.5

    def _normalize_3f_deviation(self, dev: float) -> float:
        """テン3F偏差を0~1に正規化 (マイナス=前に行く力=0寄り)"""
        return max(0.0, min(1.0, 0.5 + dev * 0.1))

    # ─── TRI (総合展開インパクト) ───

    def _calc_tri(self, ctx: RaceContext) -> float:
        """TRI = w1 * 補正LDI + w2 * RII"""
        ldi = self._calc_ldi(ctx)
        rii = self._calc_rii(ctx)
        corrected_ldi = ldi * ctx.course.straight_factor
        w1, w2 = self._distance_weights(ctx.course.distance)
        return w1 * corrected_ldi + w2 * rii

    def _calc_ldi(self, ctx: RaceContext) -> float:
        """ラップ消耗指数 (Lap Depletion Index)"""
        if ctx.baseline_first_3f == 0:
            return 0.0
        return (ctx.baseline_first_3f - ctx.estimated_first_3f) / ctx.baseline_first_3f * 100

    def _calc_rii(self, ctx: RaceContext) -> float:
        """競争強度指数 (Race Intensity Index)"""
        leaders = sorted(ctx.entries, key=lambda h: h.avg_position_index)[:3]
        if len(leaders) < 2:
            return 0.0
        speeds = [h.first_3f_speed for h in leaders]
        max_diff = max(speeds) - min(speeds)
        if max_diff == 0:
            return 10.0
        return min(10.0, len(leaders) * (1.0 / max(max_diff, 0.1)))

    def _distance_weights(self, distance: int) -> tuple[float, float]:
        """距離別の肉体的/精神的消耗の重み"""
        if distance <= 1400:
            return 0.70, 0.30
        elif distance <= 1600:
            return 0.60, 0.40
        elif distance <= 2200:
            return 0.50, 0.50
        else:
            return 0.40, 0.60

    # ─── 1. ラップ消耗ベーススコア ───

    def _calc_lap_depletion(self, tri: float, norm_epi: float,
                            num_runners: int) -> float:
        """TRIベースの加減算スコア"""
        position_impact = (2 * norm_epi) - 1  # -1 (最前) ~ +1 (最後方)
        return tri * position_impact * 0.1  # スケーリング

    # ─── 2. ポジション適合度 ───

    def _calc_position_fit(self, norm_epi: float,
                           pace: PaceScenario,
                           course: CourseInfo) -> float:
        """ガウス関数によるポジション適合度"""
        params = {
            PaceScenario.HIGH: (0.65, 15.0, 0.20),
            PaceScenario.MIDDLE: (0.35, 8.0, 0.30),
            PaceScenario.SLOW: (0.20, 12.0, 0.22),
        }
        optimal, max_bonus, sigma_base = params[pace]
        sigma = sigma_base * course.straight_factor
        fit = math.exp(-((norm_epi - optimal) ** 2) / (2 * sigma ** 2))
        return max_bonus * fit - max_bonus * 0.3  # 基準点をオフセット

    # ─── 3. トラックバイアス ───

    def _calc_track_bias(self, horse: HorseEntry, norm_epi: float,
                         ctx: RaceContext) -> float:
        """TB値 × 位置取り × 枠順のバイアススコア"""
        tb = ctx.track_bias
        if tb == 0:
            return 0.0

        # 位置取りファクター (前方内目ほど+1, 後方外目ほど-1)
        pos_factor = 1.0 - 2.0 * norm_epi  # +1(前) ~ -1(後)

        # 枠順ファクター
        n = ctx.num_runners
        gate_norm = (horse.post_position - 1) / max(n - 1, 1)
        gate_factor = 1.0 - 2.0 * gate_norm  # +1(内) ~ -1(外)

        return tb * (pos_factor * 0.5 + gate_factor * 0.5) * 2.0

    # ─── 4. 馬場補正 ───

    def _calc_ground_factor(self, horse: HorseEntry,
                            condition: TrackCondition,
                            pace: PaceScenario) -> float:
        """馬場状態による展開影響の増幅"""
        gf = {
            TrackCondition.GOOD: 1.0,
            TrackCondition.SLIGHTLY_HEAVY: 1.2,
            TrackCondition.HEAVY: 1.5,
            TrackCondition.BAD: 1.8,
        }[condition]

        # 基本展開効果テーブル (統計派提案)
        style = horse.running_style
        table = {
            PaceScenario.HIGH: {
                RunningStyle.NIGE: -6.0, RunningStyle.SENKO: -3.0,
                RunningStyle.SASHI: 4.0, RunningStyle.OIKOMI: 5.5,
            },
            PaceScenario.MIDDLE: {
                RunningStyle.NIGE: 1.0, RunningStyle.SENKO: 1.5,
                RunningStyle.SASHI: 0.5, RunningStyle.OIKOMI: -1.5,
            },
            PaceScenario.SLOW: {
                RunningStyle.NIGE: 5.0, RunningStyle.SENKO: 3.5,
                RunningStyle.SASHI: -2.5, RunningStyle.OIKOMI: -5.0,
            },
        }
        base_effect = table[pace][style]

        # 重馬場以上で追込は減衰
        if style == RunningStyle.OIKOMI:
            if condition == TrackCondition.HEAVY:
                gf *= 0.6
            elif condition == TrackCondition.BAD:
                gf *= 0.4

        # 馬場で増幅した効果を返す (ただしbaseの方向は維持)
        return base_effect * (gf - 1.0)  # 良馬場なら0、重馬場なら補正分

    # ─── 5. コース特性 ───

    def _calc_course_score(self, horse: HorseEntry, norm_epi: float,
                           course: CourseInfo,
                           pace: PaceScenario) -> float:
        """コース形態による補正"""
        score = 0.0

        # 先行バイアス
        lb = course.lead_bias
        if norm_epi < 0.4:  # 先行寄り
            score += lb * 5.0
        else:  # 差し寄り
            score -= lb * 5.0

        # 坂補正
        if course.has_steep_hill and pace == PaceScenario.HIGH:
            score += (norm_epi - 0.5) * 2.0  # 後方ほど有利

        # コーナー数補正 (多コーナーで好位内目有利)
        if course.corners >= 4 and norm_epi < 0.4:
            score += 1.0

        # 展開影響度でスケーリング
        score *= course.exhibition_impact

        return max(-5.0, min(5.0, score))

    # ─── 6. 血統ペース適性 ───

    def _calc_bloodline(self, horse: HorseEntry,
                        pace: PaceScenario,
                        course: CourseInfo) -> float:
        """血統のペース適性スコア"""
        pas = horse.sire_pace_aptitude + horse.bms_pace_correction

        # ペース相性計算
        if pace == PaceScenario.HIGH:
            pc = 0.5 + pas * 0.5
        elif pace == PaceScenario.SLOW:
            pc = 0.5 - pas * 0.5
        else:  # MIDDLE
            pc = 0.5 + (1.0 - abs(pas)) * 0.3

        # コース×血統補正
        cbc = 1.0
        if course.venue in {"東京", "新潟"}:
            if pas < -0.3:
                cbc = 1.15
            elif pas > 0.3:
                cbc = 0.95
        elif course.venue in {"中山", "小倉", "福島", "函館", "札幌"}:
            if pas > 0.3:
                cbc = 1.10
            elif pas < -0.3:
                cbc = 0.90

        return (pc - 0.5) * cbc * 6.0  # -3 ~ +3 程度

    # ─── 7. 馬群密集度 ───

    def _calc_density(self, horse: HorseEntry,
                      ctx: RaceContext,
                      paf: float) -> float:
        """馬群の厚さによる進路難易度"""
        n = ctx.num_runners
        if n <= 8:
            return 0.0  # 少頭数は影響小

        # 脚質分布の密集度
        style_counts = {s: 0 for s in RunningStyle}
        for h in ctx.entries:
            style_counts[h.running_style] += 1

        ideal_ratios = {
            RunningStyle.NIGE: 0.15, RunningStyle.SENKO: 0.30,
            RunningStyle.SASHI: 0.35, RunningStyle.OIKOMI: 0.20,
        }
        my_style = horse.running_style
        actual_ratio = style_counts[my_style] / n
        ideal = ideal_ratios[my_style]
        density = actual_ratio / ideal if ideal > 0 else 1.0

        # コース幅で割る
        pd = density / ctx.course.course_width_factor

        # 枠順補正 (差し追込の場合)
        if my_style in {RunningStyle.SASHI, RunningStyle.OIKOMI}:
            gate_third = n / 3
            if horse.post_position <= gate_third:
                pd *= 1.15  # 内枠差し → 包まれリスク
            elif horse.post_position > n - gate_third:
                pd *= 0.90  # 外枠差し → スムーズ

            # 騎手の捌き力で補正
            if horse.jockey_handling_skill > 1.2:
                pd *= 0.80
            elif horse.jockey_handling_skill < 0.8:
                pd *= 1.20

        # スコア化
        if pd < 0.8:
            return 1.5  # 空いてるボーナス
        elif pd > 1.6:
            return -3.0  # 非常に窮屈
        elif pd > 1.2:
            return -1.5  # やや窮屈
        return 0.0

    # ─── 8. 騎手展開適応 ───

    def _calc_jockey(self, horse: HorseEntry,
                     pace: PaceScenario) -> float:
        """騎手のペース別適応スコア (JPAS)"""
        if horse.jockey_overall_rate == 0:
            return 0.0

        pace_rate = {
            PaceScenario.HIGH: horse.jockey_pace_high_rate,
            PaceScenario.MIDDLE: horse.jockey_pace_mid_rate,
            PaceScenario.SLOW: horse.jockey_pace_slow_rate,
        }[pace]

        overall = horse.jockey_overall_rate
        if overall == 0:
            return 0.0

        jpas = (pace_rate - overall) / overall * 10
        return max(-3.0, min(3.0, jpas))

    # ─── 9. コンディション ───

    def _calc_condition(self, horse: HorseEntry) -> float:
        """調教+馬体重のコンディション補正"""
        # 調教補正
        tis = horse.training_intensity
        train_coeff = tis / 15.0  # -0.1 ~ +0.2

        # 馬体重補正
        wc = horse.weight_change
        if abs(wc) <= 4:
            weight_factor = 0.0
        elif 6 <= wc <= 10:
            weight_factor = -0.05
        elif wc > 10:
            weight_factor = -0.10
        elif -10 <= wc <= -6:
            weight_factor = 0.03
        else:  # < -10
            weight_factor = -0.08

        # 脚質別追加補正
        if horse.running_style in {RunningStyle.NIGE, RunningStyle.SENKO} and wc > 6:
            weight_factor *= 1.5
        elif horse.running_style == RunningStyle.OIKOMI and wc < -10:
            weight_factor *= 1.3

        return (train_coeff + weight_factor) * 10.0

    # ─── ペース増幅係数 ───

    def _calc_pace_amplification(self, ctx: RaceContext) -> float:
        """FPI (逃げ馬圧力指数) ベースのペース増幅係数"""
        leaders = [h for h in ctx.entries
                   if h.running_style == RunningStyle.NIGE]

        if not leaders:
            return 0.7  # 逃げ馬不在 → 超スローリスク

        avg_field_speed = statistics.mean(h.first_3f_speed for h in ctx.entries)
        if avg_field_speed == 0:
            return 1.0

        fpi = sum(h.first_3f_speed for h in leaders) / avg_field_speed

        # 逃げ馬競合度
        if len(leaders) >= 2:
            speeds = [h.first_3f_speed for h in leaders]
            max_diff = max(speeds) - min(speeds)
            competition = max(0, min(1, 1 - max_diff / 10))
        else:
            competition = 0

        return fpi * (1 + 0.5 * competition)

    # ─── メンバー均一度 ───

    def _calc_member_uniformity(self, ctx: RaceContext) -> float:
        """能力拮抗度による展開加点のスケーリング"""
        if len(ctx.entries) < 2:
            return 1.0
        speeds = [h.speed_index for h in ctx.entries]
        sigma = statistics.stdev(speeds) if len(speeds) > 1 else 0
        return 1.0 / (1.0 + sigma / 5.0)


def analyze_race(ctx: RaceContext) -> list[DevelopmentScore]:
    """レースを分析して展開加点を返す (便利関数)"""
    engine = DevelopmentEngine()
    return engine.calculate(ctx)


def print_results(scores: list[DevelopmentScore]) -> None:
    """結果を見やすく表示"""
    sorted_scores = sorted(scores, key=lambda s: s.total_score, reverse=True)
    print("=" * 60)
    print("【展開加点ランキング】")
    print("=" * 60)
    for rank, s in enumerate(sorted_scores, 1):
        bar = "█" * max(0, int(s.total_score + 14))
        print(f"{rank:2d}. {s.horse_name:<10s}  {s.total_score:+6.2f}pt  {bar}")
    print()
    print("【詳細内訳 (上位3頭)】")
    print("-" * 60)
    for s in sorted_scores[:3]:
        print(f"\n■ {s.horse_name} ({s.total_score:+.2f}pt)")
        print(s.detail_str())
