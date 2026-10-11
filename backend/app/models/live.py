"""场次模型：预设的直播场次，由调度器到点自动开播/收播。

高内聚：直播场次（排期）的持久化结构统一在此模块。
低耦合：运行时状态（ASR 引擎、听众连接）在 live_hub 内存中，
       模型只保存排期与开播后生成的会场码。
"""
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LiveShow(Base):
    __tablename__ = "live_shows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    # 讲解/演出人（收音对象），供观众端展示
    host_name: Mapped[str] = mapped_column(String(64), nullable=False, default="讲解员")
    # 计划开始时间（本地时间）：到点由调度器自动开播
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 场次时长（分钟）：到点自动收播
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # 实时翻译目标语言（JSON 数组字符串，如 ["en","ja"]）
    target_langs: Mapped[str] = mapped_column(String(255), nullable=False, default='["en"]')
    # scheduled=待开播 / live=直播中 / ended=已结束
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    # 开播后生成的会场码（观众 WS 凭此接入；沿用至场次结束）
    session_code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
