"""商品模型：文创旗舰店在售商品（商城后端化）。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="accessory")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orig_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    badge: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1 上架 / 0 下架
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
