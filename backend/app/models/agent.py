"""Agent 伴游模型：问答会话与消息（报价单 #9/#12 会话记忆、#18 记录留存）。"""
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentSession(Base):
    """一次伴游问答会话：token 鉴权，lang 决定输出语言，node_code 提供扫码点位上下文。"""

    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    lang: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    node_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentMessage(Base):
    """问答消息：role=user/assistant，assistant 消息带引用来源 JSON 与降级标记。"""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("agent_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
