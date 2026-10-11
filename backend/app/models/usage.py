"""豆包用量计量模型：ASR/翻译/TTS/LLM 调用记录（报价单 #16 用量计量、#21 预算）。"""
from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageLog(Base):
    """一条用量记录：kind = asr(音频秒) / translate(字符) / tts(字符) / llm(token)。"""

    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # 来源场景引用：如 live:{session_id} / rtc:{session_id} / agent:{token}
    session_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    meta: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
