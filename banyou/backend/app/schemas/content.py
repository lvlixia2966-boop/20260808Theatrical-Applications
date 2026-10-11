"""内容 Pydantic 模型：请求体校验与响应序列化。"""
from typing import Any

from pydantic import BaseModel, Field


class RegionIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    sort: int = 0
    enabled: int = 1


class RegionOut(BaseModel):
    id: int
    code: str
    name: str
    sort: int
    enabled: int

    class Config:
        from_attributes = True


class ScenicAreaIn(BaseModel):
    region_id: int
    name: str = Field(min_length=1, max_length=128)
    en_name: str = ""
    city: str = ""
    level: str = ""
    address: str = ""
    tel: str = ""
    open_time: str = ""
    ticket_info: str = ""
    suggested_hours: float = 2.0
    short_intro: str = ""
    intro: str = ""
    lat: float = 0.0
    lng: float = 0.0
    cover_url: str = ""
    tags: list[str] = []
    rating: float = 4.5
    best_season: str = ""
    sort: int = 0
    status: int = 1


class SpotIn(BaseModel):
    scenic_area_id: int
    name: str = Field(min_length=1, max_length=128)
    en_name: str = ""
    category: str = "观景"
    lat: float = 0.0
    lng: float = 0.0
    radius: int = 50
    stay_minutes: int = 15
    narration: dict[str, str] = {}
    audio_url: str = ""
    image_url: str = ""
    tips: str = ""
    sort: int = 0
    status: int = 1


class TourRouteIn(BaseModel):
    scenic_area_id: int
    name: str = Field(min_length=1, max_length=128)
    theme: str = "休闲"
    intro: str = ""
    cover_url: str = ""
    duration_minutes: int = 120
    distance_km: float = 0.0
    difficulty: str = "轻松"
    mode: str = "步行"
    sort: int = 0
    status: int = 1


class RouteStopsIn(BaseModel):
    """重设路线点位顺序：按传入 spot_id 顺序生成 seq。"""

    spot_ids: list[int] = Field(min_length=1)


class Paged(BaseModel):
    total: int
    items: list[Any]
