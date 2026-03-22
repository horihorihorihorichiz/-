"""データモデル定義 - 競馬予想システム"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RunningStyle(Enum):
    NIGE = "逃げ"
    SENKO = "先行"
    SASHI = "差し"
    OIKOMI = "追込"


class PaceScenario(Enum):
    HIGH = "ハイペース"
    MIDDLE = "ミドルペース"
    SLOW = "スローペース"


class TrackCondition(Enum):
    GOOD = "良"
    SLIGHTLY_HEAVY = "稍重"
    HEAVY = "重"
    BAD = "不良"


class TrackSurface(Enum):
    TURF = "芝"
    DIRT = "ダート"


@dataclass
class CourseInfo:
    """コース情報"""
    venue: str               # 競馬場名 (東京, 中山, 阪神, 京都, 等)
    distance: int            # 距離 (m)
    surface: TrackSurface
    direction: str = "右"    # 右回り / 左回り
    course_type: str = ""    # 内回り / 外回り / ""
    straight_length: int = 0 # 最終直線長 (m)
    has_steep_hill: bool = False  # 急坂の有無
    corners: int = 4         # コーナー数
    first_corner_dist: int = 300  # スタートから1角までの距離 (m)

    @property
    def course_width_factor(self) -> float:
        """コース幅係数 (馬群密集度計算用)"""
        wide = {"東京", "新潟"}
        medium = {"阪神外", "中京"}
        narrow = {"小倉", "福島", "札幌", "函館"}
        key = self.venue + (self.course_type if "外" in self.course_type else "")
        if self.venue in wide or key in wide:
            return 1.4
        if key in medium or self.venue in {"中京"}:
            return 1.2
        if self.venue in narrow:
            return 0.9
        return 1.0

    @property
    def exhibition_impact(self) -> float:
        """展開影響度 (高いほど展開が結果に出やすい)"""
        if self.straight_length == 0:
            return 1.0
        base = 0.6 + (self.straight_length / 500) * 0.6
        return min(max(base, 0.5), 1.5)

    @property
    def lead_bias(self) -> float:
        """先行バイアス基礎値 (+なら先行有利, -なら差し有利)"""
        table = {
            "中山": 0.15, "小倉": 0.18, "福島": 0.12,
            "函館": 0.15, "札幌": 0.10,
            "東京": -0.05, "新潟": -0.10,
        }
        bias = table.get(self.venue, 0.0)
        if "外" in self.course_type:
            bias -= 0.03
        if "内" in self.course_type:
            bias += 0.10
        if self.surface == TrackSurface.DIRT:
            bias += 0.20
            if self.distance <= 1200:
                bias += 0.10
            elif self.distance >= 2000:
                bias -= 0.05
        return bias

    @property
    def straight_factor(self) -> float:
        """直線長補正 (σ調整用)"""
        if self.straight_length == 0:
            return 1.0
        return 0.85 + (self.straight_length / 500) * 0.30

    @property
    def inner_outer_coeff(self) -> float:
        """内外係数"""
        if self.corners <= 2:
            return 0.3
        if self.venue in {"中山", "福島", "小倉", "札幌", "函館"}:
            return 1.5
        if "内" in self.course_type:
            return 1.2
        if "外" in self.course_type or self.venue in {"東京"}:
            return 0.8
        return 1.0


@dataclass
class HorseEntry:
    """出走馬情報"""
    name: str
    gate_number: int         # 枠番 (1-8)
    post_position: int       # 馬番 (1-18)
    running_style: RunningStyle
    speed_index: float       # スピード指数
    first_3f_speed: float    # テン3Fスピード指数
    last_3f_speed: float     # 上がり3Fスピード指数

    # 過去走データ
    avg_position_index: float = 0.5  # 平均先行指数 (0=最前, 1=最後)
    avg_first_corner: float = 0.5    # 初角通過順平均 (正規化)
    first_3f_deviation: float = 0.0  # テン3F偏差 (メンバー平均との差)

    # 騎手情報
    jockey_name: str = ""
    jockey_lead_tendency: float = 0.5  # 騎手固有先行傾向 (0=前, 1=後)
    jockey_pace_high_rate: float = 0.0  # ハイペース時複勝率
    jockey_pace_mid_rate: float = 0.0
    jockey_pace_slow_rate: float = 0.0
    jockey_overall_rate: float = 0.0
    jockey_handling_skill: float = 1.0  # 捌き力 (1.0=平均)
    prev_jockey_tendency: float = 0.5   # 前走騎手の先行傾向
    jockey_changed: bool = False

    # 血統
    sire_pace_aptitude: float = 0.0  # 父系PAS (-1~+1)
    bms_pace_correction: float = 0.0 # 母父系補正

    # コンディション
    temperament_correction: float = 0.0  # 気性補正 (-0.15~+0.15)
    gate_miss_risk: float = 0.0          # 出遅れリスク (0~0.10)
    training_intensity: float = 0.0      # 調教強度スコア (-1.5~+3.0)
    weight_change: float = 0.0           # 馬体重変動 (kg, 前走比)

    # 前走情報
    prev_pace_scenario: Optional[PaceScenario] = None
    prev_tri: float = 0.0  # 前走のTRI相当値


@dataclass
class RaceContext:
    """レースコンテキスト"""
    course: CourseInfo
    entries: list[HorseEntry]
    track_condition: TrackCondition
    pace_scenario: PaceScenario
    pace_confidence: float = 0.7      # ペース予測確信度 (0-1)

    # ラップ情報 (予測値 or 実測値)
    estimated_first_3f: float = 0.0   # 推定前半3F
    baseline_first_3f: float = 0.0    # 基準前半3F (同条件過去平均)

    # トラックバイアス
    track_bias: float = 0.0           # TB値 (-2.0~+2.0, +は内有利)
    meeting_day: int = 1              # 開催何日目 (1~12)
    rain_forecast: float = 0.0        # 降水確率 (0~1)

    @property
    def num_runners(self) -> int:
        return len(self.entries)


@dataclass
class DevelopmentScore:
    """展開加点の結果"""
    horse_name: str
    total_score: float = 0.0

    # 内訳
    lap_depletion_score: float = 0.0     # ラップ消耗ベース
    position_fit_score: float = 0.0       # ポジション適合度
    track_bias_score: float = 0.0         # トラックバイアス
    ground_factor_score: float = 0.0      # 馬場補正
    course_score: float = 0.0             # コース特性
    bloodline_score: float = 0.0          # 血統ペース適性
    member_density_score: float = 0.0     # 馬群密集度
    jockey_score: float = 0.0             # 騎手展開適応
    condition_score: float = 0.0          # コンディション
    confidence_factor: float = 1.0        # 確信度係数
    ability_scaling: float = 1.0          # 能力差スケーリング

    def detail_str(self) -> str:
        parts = [
            f"  ラップ消耗: {self.lap_depletion_score:+.2f}",
            f"  ポジション適合: {self.position_fit_score:+.2f}",
            f"  トラックバイアス: {self.track_bias_score:+.2f}",
            f"  馬場補正: {self.ground_factor_score:+.2f}",
            f"  コース特性: {self.course_score:+.2f}",
            f"  血統適性: {self.bloodline_score:+.2f}",
            f"  馬群密集度: {self.member_density_score:+.2f}",
            f"  騎手適応: {self.jockey_score:+.2f}",
            f"  コンディション: {self.condition_score:+.2f}",
            f"  確信度: ×{self.confidence_factor:.2f}",
            f"  能力差スケール: ×{self.ability_scaling:.2f}",
        ]
        return "\n".join(parts)
