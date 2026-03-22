#!/usr/bin/env python3
"""
競馬展開加点分析 - メインスクリプト

使い方:
  # テストデータでデモ実行
  python -m keiba.run_analysis --demo

  # レースID指定 (netkeiba)
  python -m keiba.run_analysis --race 202506010811

  # 手動入力モード
  python -m keiba.run_analysis --manual
"""

import argparse
import json
import sys

from keiba.core.models import (
    HorseEntry, PaceScenario, RaceContext,
    RunningStyle, TrackCondition,
)
from keiba.core.development_engine import DevelopmentEngine, print_results
from keiba.core.course_database import get_course


def run_demo():
    """デモデータで実行"""
    from keiba.tests.test_development_engine import make_test_race, run_demo as demo
    demo()


def run_manual():
    """対話形式で入力して分析"""
    print("=== 手動入力モード ===\n")

    venue = input("競馬場 (東京/中山/阪神/京都/中京/新潟/小倉/福島/札幌/函館): ").strip()
    distance = int(input("距離 (m): ").strip())
    surface = input("芝/ダート: ").strip()
    course_type = input("コースタイプ (内回り/外回り/空欄): ").strip()
    condition = input("馬場状態 (良/稍重/重/不良): ").strip()
    pace_input = input("展開予想 (H=ハイ/M=ミドル/S=スロー): ").strip().upper()
    confidence = float(input("ペース確信度 (0.0〜1.0): ").strip() or "0.7")

    pace_map = {"H": PaceScenario.HIGH, "M": PaceScenario.MIDDLE, "S": PaceScenario.SLOW}
    pace = pace_map.get(pace_input, PaceScenario.MIDDLE)

    cond_map = {
        "良": TrackCondition.GOOD, "稍重": TrackCondition.SLIGHTLY_HEAVY,
        "重": TrackCondition.HEAVY, "不良": TrackCondition.BAD,
    }
    track_cond = cond_map.get(condition, TrackCondition.GOOD)

    course = get_course(venue, distance, surface, course_type)

    est_3f = float(input("推定前半3F (秒, 0で省略): ").strip() or "0")
    base_3f = float(input("基準前半3F (秒, 0で省略): ").strip() or "0")
    tb = float(input("トラックバイアス (-2.0〜+2.0, 0=フラット): ").strip() or "0")

    entries = []
    print("\n--- 出走馬入力 (空行で終了) ---")
    while True:
        name = input(f"\n馬{len(entries)+1} 名前 (空で終了): ").strip()
        if not name:
            break

        gate = int(input("  枠番 (1-8): ").strip())
        post = int(input("  馬番: ").strip())
        style_in = input("  脚質 (逃/先/差/追): ").strip()
        speed = float(input("  スピード指数: ").strip() or "80")
        f3f = float(input("  テン3F (秒): ").strip() or "35.0")
        l3f = float(input("  上がり3F (秒): ").strip() or "34.5")

        style_map = {
            "逃": RunningStyle.NIGE, "先": RunningStyle.SENKO,
            "差": RunningStyle.SASHI, "追": RunningStyle.OIKOMI,
        }
        style = style_map.get(style_in, RunningStyle.SASHI)

        avg_pos = {"逃": 0.1, "先": 0.3, "差": 0.6, "追": 0.85}.get(style_in, 0.5)

        horse = HorseEntry(
            name=name, gate_number=gate, post_position=post,
            running_style=style, speed_index=speed,
            first_3f_speed=f3f, last_3f_speed=l3f,
            avg_position_index=avg_pos, avg_first_corner=avg_pos,
        )
        entries.append(horse)

    if len(entries) < 2:
        print("最低2頭必要です")
        return

    ctx = RaceContext(
        course=course, entries=entries,
        track_condition=track_cond, pace_scenario=pace,
        pace_confidence=confidence,
        estimated_first_3f=est_3f, baseline_first_3f=base_3f,
        track_bias=tb,
    )

    engine = DevelopmentEngine()
    scores = engine.calculate(ctx)
    print_results(scores)


def run_race(race_id: str):
    """netkeiba レースIDから分析"""
    from keiba.scrapers.netkeiba import NetkeibaScraper

    print(f"レースID: {race_id} を取得中...")
    scraper = NetkeibaScraper()
    ctx = scraper.fetch_race_entries(race_id)

    if ctx is None:
        print("レースデータの取得に失敗しました")
        return

    print(f"取得完了: {ctx.course.venue} {ctx.course.surface.value}"
          f"{ctx.course.distance}m {ctx.track_condition.value}")
    print(f"出走頭数: {ctx.num_runners}頭")

    # ペースシナリオを判定
    pace_input = input("\n展開予想 (H=ハイ/M=ミドル/S=スロー) [M]: ").strip().upper()
    pace_map = {"H": PaceScenario.HIGH, "M": PaceScenario.MIDDLE, "S": PaceScenario.SLOW}
    ctx.pace_scenario = pace_map.get(pace_input, PaceScenario.MIDDLE)
    ctx.pace_confidence = float(input("ペース確信度 (0.0〜1.0) [0.7]: ").strip() or "0.7")

    engine = DevelopmentEngine()
    scores = engine.calculate(ctx)
    print_results(scores)


def main():
    parser = argparse.ArgumentParser(description="競馬展開加点分析")
    parser.add_argument("--demo", action="store_true", help="デモデータで実行")
    parser.add_argument("--manual", action="store_true", help="手動入力モード")
    parser.add_argument("--race", type=str, help="レースID (netkeiba形式)")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.manual:
        run_manual()
    elif args.race:
        run_race(args.race)
    else:
        parser.print_help()
        print("\n例: python -m keiba.run_analysis --demo")


if __name__ == "__main__":
    main()
