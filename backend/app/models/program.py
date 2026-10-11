"""节目模型：语音讲解内容，支持上下架与文本/语音两种形态。"""
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 内容类型：voice（语音讲解）/ text（文字讲解）/ full（文本+语音）
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # 讲解正文（文本内容）
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 讲解人/场馆
    narrator: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    venue: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 一句话简介（中英双语；其余语言由前端/接口按 请求语言→en→zh 回退）
    intro_zh: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    intro_en: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[float] = mapped_column(nullable=False, default=0.0)
    # 上下架状态
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())