"""应用设置服务：KV 读写 + 默认值兜底 + 公开白名单过滤。"""
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.settings import AppSetting

# 设置项默认值：后台「应用设置」页在此清单上展示与编辑
SETTING_DEFAULTS: dict[str, str] = {
    "app_display_name": "凉山伴游",
    "slogan": "口袋里的凉山向导 · 纯伴游模式",
    "announcement": "",
    "hero_banners": "[]",  # JSON: [{title, subtitle, image_url, link}]
    # 地图：瓦片源可在后台切换（高德/天地图/OSM），coord 声明瓦片坐标系以便前端做纠偏
    "map_tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "map_subdomains": "",  # 形如 "012"，配合 {s} 占位符
    "map_attribution": "&copy; OpenStreetMap contributors",
    "map_coord": "wgs84",  # wgs84 / gcj02（高德、天地图均为 gcj02）
    # 伴游参数
    "default_arrival_radius": str(app_settings.default_arrival_radius),
    "tts_auto_play": "1",  # 到点自动播讲解
    "tts_rate": "1.0",     # TTS 语速
    # 底部信息
    "service_tel": "",
    "footer_note": "凉山州文化和旅游 · 智慧导览",
}

# 开放 API 允许输出的设置键（不泄露内部项）
PUBLIC_KEYS = [
    "app_display_name", "slogan", "announcement", "hero_banners",
    "map_tile_url", "map_subdomains", "map_attribution", "map_coord",
    "default_arrival_radius", "tts_auto_play", "tts_rate",
    "service_tel", "footer_note",
]


def get_all(db: Session) -> dict[str, str]:
    """读取全部设置（默认值兜底）。"""
    merged = dict(SETTING_DEFAULTS)
    rows = db.query(AppSetting).all()
    for row in rows:
        merged[row.key] = row.value
    return merged


def update_many(db: Session, values: dict[str, str]) -> None:
    """仅更新已知键，忽略未知键，防止前端注入任意 KV。"""
    for key, value in values.items():
        if key not in SETTING_DEFAULTS:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
    db.commit()


def get_public(db: Session) -> dict[str, str]:
    """公开设置子集，供游客端 bootstrap。"""
    all_values = get_all(db)
    return {key: all_values.get(key, "") for key in PUBLIC_KEYS}
