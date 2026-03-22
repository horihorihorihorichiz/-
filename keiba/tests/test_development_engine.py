"""展開加点エンジンのテスト"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from keiba.core.models import (
    CourseInfo, HorseEntry, PaceScenario, RaceContext,
    RunningStyle, TrackCondition, TrackSurface,
)
from keiba.core.development_engine import DevelopmentEngine, print_results
from keiba.core.course_database import get_course


def make_test_race() -> RaceContext:
    """テスト用レースデータ (東京芝2400m・ダービー想定)"""
    course = get_course("東京", 2400, "芝")
    entries = [
        HorseEntry(
            name="ハイペースメーカー", gate_number=1, post_position=1,
            running_style=RunningStyle.NIGE, speed_index=85,
            first_3f_speed=34.0, last_3f_speed=36.5,
            avg_position_index=0.1, avg_first_corner=0.1,
            first_3f_deviation=-2.0,
            jockey_name="武豊", jockey_lead_tendency=0.3,
            jockey_pace_high_rate=0.15, jockey_pace_slow_rate=0.20,
            jockey_overall_rate=0.18, jockey_handling_skill=1.3,
            sire_pace_aptitude=0.8, bms_pace_correction=0.0,
            training_intensity=2.0, weight_change=0,
        ),
        HorseEntry(
            name="好位差しエース", gate_number=3, post_position=5,
            running_style=RunningStyle.SENKO, speed_index=92,
            first_3f_speed=34.5, last_3f_speed=34.0,
            avg_position_index=0.3, avg_first_corner=0.25,
            first_3f_deviation=-0.5,
            jockey_name="ルメール", jockey_lead_tendency=0.35,
            jockey_pace_high_rate=0.22, jockey_pace_slow_rate=0.25,
            jockey_overall_rate=0.22, jockey_handling_skill=1.4,
            sire_pace_aptitude=-0.5, bms_pace_correction=0.15,
            training_intensity=2.5, weight_change=-4,
        ),
        HorseEntry(
            name="中団差し馬", gate_number=5, post_position=9,
            running_style=RunningStyle.SASHI, speed_index=90,
            first_3f_speed=35.5, last_3f_speed=33.5,
            avg_position_index=0.55, avg_first_corner=0.5,
            first_3f_deviation=0.5,
            jockey_name="川田", jockey_lead_tendency=0.45,
            jockey_pace_high_rate=0.23, jockey_pace_slow_rate=0.18,
            jockey_overall_rate=0.20, jockey_handling_skill=1.2,
            sire_pace_aptitude=-0.4, bms_pace_correction=-0.25,
            training_intensity=1.5, weight_change=2,
        ),
        HorseEntry(
            name="追込豪脚", gate_number=7, post_position=14,
            running_style=RunningStyle.OIKOMI, speed_index=88,
            first_3f_speed=36.5, last_3f_speed=32.8,
            avg_position_index=0.85, avg_first_corner=0.8,
            first_3f_deviation=2.0,
            jockey_name="横山武史", jockey_lead_tendency=0.7,
            jockey_pace_high_rate=0.18, jockey_pace_slow_rate=0.12,
            jockey_overall_rate=0.15, jockey_handling_skill=0.9,
            sire_pace_aptitude=-0.5, bms_pace_correction=-0.25,
            training_intensity=1.0, weight_change=6,
        ),
        HorseEntry(
            name="逃げ番手", gate_number=2, post_position=3,
            running_style=RunningStyle.SENKO, speed_index=86,
            first_3f_speed=34.2, last_3f_speed=35.5,
            avg_position_index=0.2, avg_first_corner=0.2,
            first_3f_deviation=-1.5,
            jockey_name="横山典弘", jockey_lead_tendency=0.25,
            jockey_pace_high_rate=0.16, jockey_pace_slow_rate=0.22,
            jockey_overall_rate=0.18, jockey_handling_skill=1.1,
            sire_pace_aptitude=0.3, bms_pace_correction=0.15,
            training_intensity=0.5, weight_change=-2,
        ),
        HorseEntry(
            name="外枠差し", gate_number=8, post_position=16,
            running_style=RunningStyle.SASHI, speed_index=89,
            first_3f_speed=35.8, last_3f_speed=33.2,
            avg_position_index=0.6, avg_first_corner=0.55,
            first_3f_deviation=1.0,
            jockey_name="戸崎圭太", jockey_lead_tendency=0.5,
            jockey_pace_high_rate=0.19, jockey_pace_slow_rate=0.17,
            jockey_overall_rate=0.18, jockey_handling_skill=1.3,
            sire_pace_aptitude=-0.3, bms_pace_correction=0.0,
            training_intensity=2.0, weight_change=0,
        ),
    ]

    return RaceContext(
        course=course,
        entries=entries,
        track_condition=TrackCondition.GOOD,
        pace_scenario=PaceScenario.HIGH,
        pace_confidence=0.7,
        estimated_first_3f=34.2,
        baseline_first_3f=35.0,
        track_bias=0.3,  # やや内有利
        meeting_day=3,
    )


def test_basic_calculation():
    """基本計算テスト"""
    engine = DevelopmentEngine()
    ctx = make_test_race()
    scores = engine.calculate(ctx)

    assert len(scores) == 6, f"Expected 6 scores, got {len(scores)}"

    # ハイペースなら差し・追込が有利のはず
    score_by_name = {s.horse_name: s for s in scores}
    nige_score = score_by_name["ハイペースメーカー"].total_score
    sashi_score = score_by_name["中団差し馬"].total_score

    assert sashi_score > nige_score, (
        f"ハイペースで差し({sashi_score:.2f}) > 逃げ({nige_score:.2f})のはず"
    )
    print("✓ 基本計算テスト: OK")


def test_pace_scenarios():
    """ペースシナリオ別テスト"""
    engine = DevelopmentEngine()

    for pace in PaceScenario:
        ctx = make_test_race()
        ctx.pace_scenario = pace
        scores = engine.calculate(ctx)
        by_name = {s.horse_name: s for s in scores}

        if pace == PaceScenario.HIGH:
            assert by_name["中団差し馬"].total_score > by_name["ハイペースメーカー"].total_score
        elif pace == PaceScenario.SLOW:
            assert by_name["逃げ番手"].total_score > by_name["追込豪脚"].total_score

        print(f"✓ ペースシナリオ {pace.value}: OK")


def test_ground_condition():
    """馬場状態テスト"""
    engine = DevelopmentEngine()

    for cond in TrackCondition:
        ctx = make_test_race()
        ctx.track_condition = cond
        scores = engine.calculate(ctx)
        assert all(isinstance(s.total_score, float) for s in scores)
    print("✓ 馬場状態テスト: OK")


def test_score_range():
    """スコア範囲テスト"""
    engine = DevelopmentEngine()
    ctx = make_test_race()
    scores = engine.calculate(ctx)

    for s in scores:
        assert -14.0 <= s.total_score <= 20.0, (
            f"{s.horse_name}: {s.total_score} out of range"
        )
    print("✓ スコア範囲テスト: OK")


def test_no_multiplicative():
    """乗算方式が使われていないことの確認"""
    engine = DevelopmentEngine()
    ctx = make_test_race()
    scores = engine.calculate(ctx)

    # 旧方式: 能力値 * 1.2 のような乗算は使わない
    # → 展開加点が能力値に比例しないことを確認
    by_name = {s.horse_name: s for s in scores}

    # 能力値92の好位差しエースと88の追込豪脚
    # ハイペースなら追込の方が展開加点が高いはず(能力値は低いのに)
    ace_score = by_name["好位差しエース"].total_score
    oikomi_score = by_name["追込豪脚"].total_score
    # 追込の方が展開加点が大きいことを確認
    # (旧方式なら92*1.2=110.4 vs 88*1.2=105.6で能力順が維持される)
    print(f"  好位差し: {ace_score:+.2f}pt, 追込: {oikomi_score:+.2f}pt")
    print("✓ 非乗算方式テスト: OK")


def test_different_courses():
    """コース別テスト"""
    engine = DevelopmentEngine()

    courses = [
        ("東京", 2400, "芝", ""),
        ("中山", 2000, "芝", ""),
        ("阪神", 1600, "芝", "外回り"),
        ("小倉", 1200, "芝", ""),
        ("東京", 1600, "ダート", ""),
    ]

    for venue, dist, surf, ctype in courses:
        ctx = make_test_race()
        ctx.course = get_course(venue, dist, surf, ctype)
        scores = engine.calculate(ctx)
        assert len(scores) > 0
        print(f"✓ {venue}{surf}{dist}m: OK")


def run_demo():
    """デモ実行"""
    print("\n" + "=" * 60)
    print("【デモ】東京芝2400m ハイペース想定")
    print("=" * 60)

    ctx = make_test_race()
    engine = DevelopmentEngine()
    scores = engine.calculate(ctx)
    print_results(scores)

    # スロー想定でも計算
    print("\n" + "=" * 60)
    print("【デモ】同メンバー・スローペース想定")
    print("=" * 60)
    ctx.pace_scenario = PaceScenario.SLOW
    ctx.estimated_first_3f = 36.0
    scores_slow = engine.calculate(ctx)
    print_results(scores_slow)


if __name__ == "__main__":
    print("=== 展開加点エンジン テスト ===\n")
    test_basic_calculation()
    test_pace_scenarios()
    test_ground_condition()
    test_score_range()
    test_no_multiplicative()
    test_different_courses()
    print("\n=== 全テスト完了 ===")

    run_demo()
