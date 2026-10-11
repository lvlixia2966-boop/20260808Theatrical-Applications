"""预约模型：用户通过扫码进入后，预约「文本/语音」讲解内容。"""
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReservationStatus(str):
    PENDING = "pending"        # 待确认
    CONFIRMED = "confirmed"    # 已确认
    COMPLETED = "completed"    # 已完成
    CANCELLED = "cancelled"    # 已取消


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联耳机（扫码身份）
    earphone_id: Mapped[int] = mapped_column(
        ForeignKey("earphones.id", ondelete="CASCADE"), index=True, nullable=False
    )
    qr_code_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 关联节目（被预约的讲解内容）
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    program_title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 预约的讲解类型：text / voice / full
    book_type: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # 预约备注（文本）与语音内容快照
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    customer_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())