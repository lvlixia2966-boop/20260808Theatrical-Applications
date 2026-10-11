"""内容模型：区域 / 景区 / 点位 / 伴游路线 / 路线点位。

纯伴游模式的内容骨架：所有游客端可见内容都由后台配置，经开放 API 输出。
"""
import json
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def load_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


class Region(Base):
    """区域（如：凉山彝族自治州）；景区挂在区域下，便于后续扩川内其他州市。"""

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[int] = mapped_column(Integer, default=1)  # 1 上线 / 0 下线

    areas: Mapped[list["ScenicArea"]] = relationship(back_populates="region")


class ScenicArea(Base):
    """景区：伴游内容的一级组织单元。"""

    __tablename__ = "scenic_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    en_name: Mapped[str] = mapped_column(String(128), default="")
    city: Mapped[str] = mapped_column(String(64), default="")      # 县市，如 西昌市 / 盐源县
    level: Mapped[str] = mapped_column(String(16), default="")     # 5A / 4A / 世界遗产…
    address: Mapped[str] = mapped_column(String(255), default="")
    tel: Mapped[str] = mapped_column(String(32), default="")
    open_time: Mapped[str] = mapped_column(String(128), default="")
    ticket_info: Mapped[str] = mapped_column(String(255), default="")
    suggested_hours: Mapped[float] = mapped_column(Float, default=2.0)
    short_intro: Mapped[str] = mapped_column(String(255), default="")
    intro: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    cover_url: Mapped[str] = mapped_column(String(255), default="")
    tags_raw: Mapped[str] = mapped_column("tags", Text, default="[]")   # JSON 数组
    rating: Mapped[float] = mapped_column(Float, default=4.5)
    best_season: Mapped[str] = mapped_column(String(64), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)

    region: Mapped[Region] = relationship(back_populates="areas")
    spots: Mapped[list["Spot"]] = relationship(
        back_populates="area", cascade="all, delete-orphan", order_by="Spot.sort"
    )
    routes: Mapped[list["TourRoute"]] = relationship(
        back_populates="area", cascade="all, delete-orphan", order_by="TourRoute.sort"
    )

    @property
    def tags(self) -> list[str]:
        return load_json(self.tags_raw, [])

    @tags.setter
    def tags(self, value: list[str]) -> None:
        self.tags_raw = dump_json(value or [])


class Spot(Base):
    """点位：景区内的讲解点，含坐标、到点触发半径与多语言讲解稿。"""

    __tablename__ = "spots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    en_name: Mapped[str] = mapped_column(String(128), default="")
    category: Mapped[str] = mapped_column(String(32), default="观景")  # 观景/文化/宗教/地质/红色/体验…
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    radius: Mapped[int] = mapped_column(Integer, default=50)       # 到点触发半径（米）
    stay_minutes: Mapped[int] = mapped_column(Integer, default=15)  # 建议停留
    narration_raw: Mapped[str] = mapped_column("narration", Text, default="{}")  # {"zh": "...", "en": "..."}
    audio_url: Mapped[str] = mapped_column(String(255), default="")  # 人工录音优先；空则前端 TTS
    image_url: Mapped[str] = mapped_column(String(255), default="")
    tips: Mapped[str] = mapped_column(String(255), default="")       # 游览贴士
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)

    area: Mapped[ScenicArea] = relationship(back_populates="spots")

    @property
    def narration(self) -> dict[str, str]:
        return load_json(self.narration_raw, {})

    @narration.setter
    def narration(self, value: dict[str, str]) -> None:
        self.narration_raw = dump_json(value or {})


class TourRoute(Base):
    """伴游路线：点位有序串联，游客端「开始伴游」即按此顺序引导。"""

    __tablename__ = "tour_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenic_area_id: Mapped[int] = mapped_column(ForeignKey("scenic_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    theme: Mapped[str] = mapped_column(String(32), default="休闲")   # 休闲/人文/亲子/研学/红色/徒步…
    intro: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(String(255), default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[str] = mapped_column(String(16), default="轻松")  # 轻松/中等/进阶
    mode: Mapped[str] = mapped_column(String(16), default="步行")        # 步行/车行+步行/索道+徒步
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)

    area: Mapped[ScenicArea] = relationship(back_populates="routes")
    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.seq"
    )


class RouteStop(Base):
    """路线-点位关联：seq 即伴游顺序（从 1 开始）。"""

    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("tour_routes.id"), index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("spots.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=1)

    route: Mapped[TourRoute] = relationship(back_populates="stops")
    spot: Mapped[Spot] = relationship()
