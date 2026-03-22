"""
netkeiba.comからのレースデータ取得

使用方法:
  scraper = NetkeibaScraper()
  race = scraper.fetch_race("202506010811")  # レースID
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Optional

from ..core.models import (
    CourseInfo, HorseEntry, PaceScenario, RaceContext,
    RunningStyle, TrackCondition, TrackSurface,
)
from ..core.course_database import get_course


@dataclass
class RawHorseData:
    """スクレイピングで取得した生データ"""
    name: str = ""
    gate: int = 0
    post: int = 0
    jockey: str = ""
    weight: str = ""
    odds: float = 0.0
    running_style_label: str = ""
    speed_index: float = 0.0
    sire: str = ""
    bms: str = ""


class NetkeibaScraper:
    """netkeiba.comスクレイパー"""

    BASE_URL = "https://race.netkeiba.com"
    SHUTUBA_URL = "https://race.netkeiba.com/race/shutuba.html"
    RESULT_URL = "https://db.netkeiba.com/race/"

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last_request = 0.0

    def fetch_race_entries(self, race_id: str) -> Optional[RaceContext]:
        """出馬表からレース情報を取得"""
        url = f"{self.SHUTUBA_URL}?race_id={race_id}"
        html = self._fetch(url)
        if html is None:
            return None
        return self._parse_shutuba(html, race_id)

    def fetch_race_result(self, race_id: str) -> Optional[dict]:
        """レース結果を取得 (バックテスト用)"""
        url = f"{self.RESULT_URL}{race_id}"
        html = self._fetch(url)
        if html is None:
            return None
        return self._parse_result(html)

    def _fetch(self, url: str) -> Optional[str]:
        """HTTPリクエスト (レート制限付き)"""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; keiba-analysis/1.0)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._last_request = time.time()
                return resp.read().decode("euc-jp", errors="replace")
        except Exception as e:
            print(f"[ERROR] fetch failed: {url} - {e}")
            return None

    def _parse_shutuba(self, html: str, race_id: str) -> Optional[RaceContext]:
        """出馬表HTMLをパース"""
        # レース情報のパース
        venue = self._extract_venue(race_id)
        distance = self._extract_distance(html)
        surface = self._extract_surface(html)
        condition = self._extract_condition(html)
        course_type = self._extract_course_type(html)

        if distance == 0:
            return None

        course = get_course(venue, distance, surface, course_type)

        # 馬データのパース
        entries = self._extract_entries(html)
        if not entries:
            return None

        horse_entries = []
        for raw in entries:
            style = self._classify_running_style(raw.running_style_label)
            horse = HorseEntry(
                name=raw.name,
                gate_number=raw.gate,
                post_position=raw.post,
                running_style=style,
                speed_index=raw.speed_index,
                first_3f_speed=0.0,  # 別途取得が必要
                last_3f_speed=0.0,
                jockey_name=raw.jockey,
                sire_pace_aptitude=self._sire_pas(raw.sire),
                bms_pace_correction=self._bms_pas(raw.bms),
            )
            horse_entries.append(horse)

        track_cond = self._map_condition(condition)

        return RaceContext(
            course=course,
            entries=horse_entries,
            track_condition=track_cond,
            pace_scenario=PaceScenario.MIDDLE,  # 後で判定
            pace_confidence=0.5,
        )

    def _extract_venue(self, race_id: str) -> str:
        """レースIDから競馬場名を抽出"""
        venue_map = {
            "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
            "05": "東京", "06": "中山", "07": "中京", "08": "京都",
            "09": "阪神", "10": "小倉",
        }
        venue_code = race_id[4:6]
        return venue_map.get(venue_code, "不明")

    def _extract_distance(self, html: str) -> int:
        """HTMLから距離を抽出"""
        m = re.search(r'(\d{3,4})m', html)
        return int(m.group(1)) if m else 0

    def _extract_surface(self, html: str) -> str:
        if "ダ" in html[:5000]:
            return "ダート"
        return "芝"

    def _extract_condition(self, html: str) -> str:
        for cond in ["不良", "重", "稍重", "良"]:
            if cond in html[:5000]:
                return cond
        return "良"

    def _extract_course_type(self, html: str) -> str:
        if "外回り" in html[:5000] or "外" in html[:3000]:
            return "外回り"
        if "内回り" in html[:5000] or "内" in html[:3000]:
            return "内回り"
        return ""

    def _extract_entries(self, html: str) -> list[RawHorseData]:
        """出馬表から馬情報を抽出 (簡易版)"""
        entries = []
        # HorseListのテーブル行を探す
        rows = re.findall(
            r'<tr[^>]*class="HorseList"[^>]*>(.*?)</tr>',
            html, re.DOTALL
        )
        for row in rows:
            raw = RawHorseData()
            # 馬番
            m = re.search(r'<td[^>]*class="Umaban[^"]*"[^>]*>(\d+)</td>', row)
            if m:
                raw.post = int(m.group(1))
            # 枠番
            m = re.search(r'<td[^>]*class="Waku[^"]*"[^>]*>.*?(\d+)', row, re.DOTALL)
            if m:
                raw.gate = int(m.group(1))
            # 馬名
            m = re.search(r'class="HorseName"[^>]*>.*?<a[^>]*>([^<]+)</a>', row, re.DOTALL)
            if m:
                raw.name = m.group(1).strip()
            # 騎手
            m = re.search(r'class="Jockey"[^>]*>.*?<a[^>]*>([^<]+)</a>', row, re.DOTALL)
            if m:
                raw.jockey = m.group(1).strip()

            if raw.name:
                entries.append(raw)
        return entries

    def _classify_running_style(self, label: str) -> RunningStyle:
        """脚質ラベルをRunningStyleに変換"""
        if "逃" in label:
            return RunningStyle.NIGE
        if "先" in label:
            return RunningStyle.SENKO
        if "差" in label:
            return RunningStyle.SASHI
        if "追" in label:
            return RunningStyle.OIKOMI
        return RunningStyle.SASHI  # デフォルト

    def _map_condition(self, cond_str: str) -> TrackCondition:
        return {
            "良": TrackCondition.GOOD,
            "稍重": TrackCondition.SLIGHTLY_HEAVY,
            "重": TrackCondition.HEAVY,
            "不良": TrackCondition.BAD,
        }.get(cond_str, TrackCondition.GOOD)

    def _sire_pas(self, sire: str) -> float:
        """父系のペース適性スコア"""
        pas_table = {
            "ロードカナロア": 0.7, "ダイワメジャー": 0.8,
            "サクラバクシンオー": 0.6, "ステイゴールド": 0.6,
            "ドゥラメンテ": 0.5, "キングカメハメハ": 0.3,
            "ハービンジャー": 0.2, "エピファネイア": 0.2,
            "モーリス": 0.1, "キタサンブラック": 0.3,
            "ルーラーシップ": 0.1, "ディープインパクト": -0.5,
            "ハーツクライ": -0.4, "キズナ": -0.3,
            "スワーヴリチャード": -0.2, "サトノクラウン": -0.1,
            "ドレフォン": 0.4, "マインドユアビスケッツ": 0.3,
            "イスラボニータ": -0.1, "リオンディーズ": 0.0,
            "サトノダイヤモンド": -0.3, "シルバーステート": -0.2,
        }
        for key, val in pas_table.items():
            if key in sire:
                return val
        return 0.0

    def _bms_pas(self, bms: str) -> float:
        """母父系補正"""
        bms_table = {
            "ディープインパクト": -0.25, "キングカメハメハ": 0.15,
            "ステイゴールド": 0.15, "サンデーサイレンス": -0.15,
            "クロフネ": 0.10, "フジキセキ": -0.05,
        }
        for key, val in bms_table.items():
            if key in bms:
                return val
        return 0.0

    def _parse_result(self, html: str) -> Optional[dict]:
        """レース結果をパース (バックテスト用)"""
        # TODO: 実装
        return None
