"""实时翻译会话模型：双端（游客/工作人员）WebRTC 会话与会话记录。

高内聚：RTC 会话（排期之外的即时会话）与字幕记录的持久化结构统一在此模块。
低耦合：运行时状态（PeerConnection、ASR 引擎）在 rtc_gateway 内存中，
       模型只保存会话配置、双端 token 与可留存的会话记录（报价单 #18）。
"""
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RtcSession(Base):
    __tablename__ = "rtc_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 6 位可读会话码（管理端/口头转述用）；实际鉴权靠双端 token
    code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="实时翻译会话")
    # 游客语言（12 目标语种之一）/ 工作人员语言（默认中文）
    visitor_lang: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    staff_lang: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    # 双端接入 token（唯一，二维码 URL 携带；WS 建立时校验）
    visitor_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    staff_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # created=待接入 / active=双端在线 / ended=已结束
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    # 会话记录留存天数（报价单 #18 可配置留存），到期由调度器清理
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RtcLog(Base):
    """会话记录：一句一档（方向、原文、译文），供管理端回查与留存到期清理。"""

    __tablename__ = "rtc_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("rtc_sessions.id"), nullable=False, index=True)
    # visitor→staff：游客说话；staff→visitor：工作人员说话
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
