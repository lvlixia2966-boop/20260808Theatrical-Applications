"""地理工具：距离 / 方位角（伴游引导的核心纯函数，前后端同款算法）。"""
import math


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两坐标球面距离（米）。"""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """从点到目标点的方位角（正北为 0，顺时针 0-360）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def format_distance(meters: float) -> str:
    """距离人性化输出。"""
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters / 1000:.1f}km"
