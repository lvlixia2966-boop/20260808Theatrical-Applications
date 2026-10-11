"""文创商品与订单模型：纯伴游的「不打扰」售卖——
商品可全局销售，也可挂到景区/点位，游客在讲解页按需看到，伴游过程零打扰。"""
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.content import dump_json, load_json


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    """文创商品：scenic_area_id 为空表示全域好物；spot_ids 为关联讲解点位。"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    en_name: Mapped[str] = mapped_column(String(128), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)          # 元
    orig_price: Mapped[float] = mapped_column(Float, default=0.0)     # 划线价，0 = 不展示
    desc: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(255), default="")
    stock: Mapped[int] = mapped_column(Integer, default=99)
    tags_raw: Mapped[str] = mapped_column("tags", Text, default="[]")
    scenic_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenic_areas.id"), nullable=True, index=True)
    spot_ids_raw: Mapped[str] = mapped_column("spot_ids", Text, default="[]")  # JSON 数组
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)           # 1 上架 / 0 下架
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    @property
    def tags(self) -> list[str]:
        return load_json(self.tags_raw, [])

    @tags.setter
    def tags(self, value: list[str]) -> None:
        self.tags_raw = dump_json(value or [])

    @property
    def spot_ids(self) -> list[int]:
        return load_json(self.spot_ids_raw, [])

    @spot_ids.setter
    def spot_ids(self, value: list[int]) -> None:
        self.spot_ids_raw = dump_json(value or [])


class Order(Base):
    """游客订单：无账号体系，visitor_id 由游客端生成并本地持久化。"""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    items_raw: Mapped[str] = mapped_column("items", Text, default="[]")  # [{product_id,name,price,qty}]
    total: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending 待支付 / paid 已支付 / shipped 已发货 / cancelled 已取消
    channel: Mapped[str] = mapped_column(String(16), default="")      # wechat / alipay
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def items(self) -> list[dict[str, Any]]:
        return load_json(self.items_raw, [])

    @items.setter
    def items(self, value: list[dict[str, Any]]) -> None:
        self.items_raw = dump_json(value or [])
