"""管理员模型：后台管理登录账号（报价单 #17 权限分级）。"""
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 角色常量：super=超级管理员（全部）/ ops=运营（统计/直播/会话）/ content=内容（知识库）
ROLE_SUPER = "super"
ROLE_OPS = "ops"
ROLE_CONTENT = "content"
ALL_ROLES = (ROLE_SUPER, ROLE_OPS, ROLE_CONTENT)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, default="管理员")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_SUPER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())