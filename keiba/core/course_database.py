"""コースデータベース - 主要コースの情報を定義"""

from .models import CourseInfo, TrackSurface


def get_course(venue: str, distance: int, surface: str = "芝",
               course_type: str = "") -> CourseInfo:
    """コース情報を取得"""
    surf = TrackSurface.TURF if surface == "芝" else TrackSurface.DIRT
    key = f"{venue}_{surface}_{distance}_{course_type}"

    if key in COURSE_DB:
        info = COURSE_DB[key]
        return CourseInfo(
            venue=venue, distance=distance, surface=surf,
            direction=info["direction"], course_type=course_type,
            straight_length=info["straight"],
            has_steep_hill=info.get("steep_hill", False),
            corners=info.get("corners", 4),
            first_corner_dist=info.get("first_corner", 300),
        )

    # 汎用フォールバック
    straight = _estimate_straight(venue, course_type)
    direction = _get_direction(venue)
    steep = venue in {"中山", "阪神"}
    corners = 2 if distance <= 1400 else 4
    return CourseInfo(
        venue=venue, distance=distance, surface=surf,
        direction=direction, course_type=course_type,
        straight_length=straight, has_steep_hill=steep,
        corners=corners, first_corner_dist=300,
    )


def _estimate_straight(venue: str, course_type: str) -> int:
    table = {
        "東京": 525, "中山": 310, "阪神": 474, "京都": 404,
        "中京": 412, "新潟": 659, "福島": 292, "小倉": 293,
        "札幌": 266, "函館": 262,
    }
    base = table.get(venue, 350)
    if "内" in course_type:
        base = int(base * 0.75)
    return base


def _get_direction(venue: str) -> str:
    left = {"東京", "中京", "新潟"}
    return "左" if venue in left else "右"


# 主要コースデータ
COURSE_DB = {
    # 東京
    "東京_芝_1400_": {"direction": "左", "straight": 525, "corners": 2, "first_corner": 540},
    "東京_芝_1600_": {"direction": "左", "straight": 525, "corners": 2, "first_corner": 450},
    "東京_芝_1800_": {"direction": "左", "straight": 525, "corners": 4, "first_corner": 350},
    "東京_芝_2000_": {"direction": "左", "straight": 525, "corners": 4, "first_corner": 350},
    "東京_芝_2400_": {"direction": "左", "straight": 525, "corners": 4, "first_corner": 350},
    "東京_ダート_1400_": {"direction": "左", "straight": 501, "corners": 2, "first_corner": 450},
    "東京_ダート_1600_": {"direction": "左", "straight": 501, "corners": 2, "first_corner": 480},
    "東京_ダート_2100_": {"direction": "左", "straight": 501, "corners": 4, "first_corner": 350},
    # 中山
    "中山_芝_1200_": {"direction": "右", "straight": 310, "steep_hill": True, "corners": 2, "first_corner": 200},
    "中山_芝_1600_": {"direction": "右", "straight": 310, "steep_hill": True, "corners": 4, "first_corner": 240},
    "中山_芝_1800_": {"direction": "右", "straight": 310, "steep_hill": True, "corners": 4, "first_corner": 250},
    "中山_芝_2000_": {"direction": "右", "straight": 310, "steep_hill": True, "corners": 4, "first_corner": 300},
    "中山_芝_2500_": {"direction": "右", "straight": 310, "steep_hill": True, "corners": 4, "first_corner": 350},
    "中山_ダート_1200_": {"direction": "右", "straight": 308, "steep_hill": True, "corners": 2, "first_corner": 200},
    "中山_ダート_1800_": {"direction": "右", "straight": 308, "steep_hill": True, "corners": 4, "first_corner": 250},
    # 阪神
    "阪神_芝_1400_内回り": {"direction": "右", "straight": 356, "steep_hill": True, "corners": 2, "first_corner": 300},
    "阪神_芝_1600_外回り": {"direction": "右", "straight": 474, "steep_hill": True, "corners": 2, "first_corner": 450},
    "阪神_芝_1800_外回り": {"direction": "右", "straight": 474, "steep_hill": True, "corners": 4, "first_corner": 300},
    "阪神_芝_2000_内回り": {"direction": "右", "straight": 356, "steep_hill": True, "corners": 4, "first_corner": 300},
    "阪神_芝_2200_外回り": {"direction": "右", "straight": 474, "steep_hill": True, "corners": 4, "first_corner": 350},
    "阪神_ダート_1400_": {"direction": "右", "straight": 352, "steep_hill": True, "corners": 2, "first_corner": 300},
    "阪神_ダート_1800_": {"direction": "右", "straight": 352, "steep_hill": True, "corners": 4, "first_corner": 300},
    # 京都
    "京都_芝_1600_外回り": {"direction": "右", "straight": 404, "corners": 2, "first_corner": 450},
    "京都_芝_1800_外回り": {"direction": "右", "straight": 404, "corners": 4, "first_corner": 300},
    "京都_芝_2000_内回り": {"direction": "右", "straight": 328, "corners": 4, "first_corner": 300},
    "京都_芝_2400_外回り": {"direction": "右", "straight": 404, "corners": 4, "first_corner": 350},
    "京都_芝_3000_外回り": {"direction": "右", "straight": 404, "corners": 4, "first_corner": 400},
    # 中京
    "中京_芝_1200_": {"direction": "左", "straight": 412, "corners": 2, "first_corner": 350},
    "中京_芝_1600_": {"direction": "左", "straight": 412, "corners": 4, "first_corner": 300},
    "中京_芝_2000_": {"direction": "左", "straight": 412, "corners": 4, "first_corner": 300},
    "中京_ダート_1800_": {"direction": "左", "straight": 410, "corners": 4, "first_corner": 300},
    # 新潟
    "新潟_芝_1000_": {"direction": "左", "straight": 659, "corners": 0, "first_corner": 1000},
    "新潟_芝_1600_外回り": {"direction": "左", "straight": 659, "corners": 2, "first_corner": 500},
    "新潟_芝_2000_外回り": {"direction": "左", "straight": 659, "corners": 4, "first_corner": 350},
    # 小回り
    "小倉_芝_1200_": {"direction": "右", "straight": 293, "corners": 2, "first_corner": 250},
    "小倉_芝_1800_": {"direction": "右", "straight": 293, "corners": 4, "first_corner": 300},
    "小倉_芝_2000_": {"direction": "右", "straight": 293, "corners": 4, "first_corner": 300},
    "福島_芝_1200_": {"direction": "右", "straight": 292, "corners": 2, "first_corner": 250},
    "福島_芝_1800_": {"direction": "右", "straight": 292, "corners": 4, "first_corner": 300},
    "福島_芝_2000_": {"direction": "右", "straight": 292, "corners": 4, "first_corner": 300},
    "札幌_芝_1200_": {"direction": "右", "straight": 266, "corners": 2, "first_corner": 250},
    "札幌_芝_1800_": {"direction": "右", "straight": 266, "corners": 4, "first_corner": 300},
    "函館_芝_1200_": {"direction": "右", "straight": 262, "corners": 2, "first_corner": 250},
    "函館_芝_2000_": {"direction": "右", "straight": 262, "corners": 4, "first_corner": 300},
}
