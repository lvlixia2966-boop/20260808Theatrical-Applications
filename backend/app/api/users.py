"""管理员账号路由：账号 CRUD 与角色分配（报价单 #17 权限分级，仅 super 可操作）。"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import require_role
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import AdminUser
from app.models.admin import ALL_ROLES
from app.schemas import ApiResponse

logger = logging.getLogger("users")

router = APIRouter(prefix="/api/admin/users", tags=["管理员账号"])

SuperDep = Annotated[AdminUser, Depends(require_role())]


class AdminUserCreate(BaseModel):
    """新建管理员请求。"""

    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field("", max_length=64)
    role: str = Field("ops", description="super / ops / content")


class AdminUserUpdate(BaseModel):
    """修改管理员请求（密码可空表示不改）。"""

    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


@router.get("", response_model=ApiResponse[list[dict]])
def list_users(admin: SuperDep):
    """账号列表（仅 super）。"""
    db = SessionLocal()
    try:
        rows = db.scalars(select(AdminUser).order_by(AdminUser.id)).all()
        return ApiResponse(data=[{
            "id": r.id, "username": r.username, "display_name": r.display_name,
            "role": r.role, "is_active": r.is_active,
        } for r in rows])
    finally:
        db.close()


@router.post("", response_model=ApiResponse[dict])
def create_user(payload: AdminUserCreate, admin: SuperDep):
    """新建管理员账号并分配角色（仅 super）。"""
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"角色须为 {'/'.join(ALL_ROLES)}")
    db = SessionLocal()
    try:
        if db.scalar(select(AdminUser).where(AdminUser.username == payload.username)):
            raise HTTPException(status_code=409, detail="用户名已存在")
        row = AdminUser(
            username=payload.username,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name or payload.username,
            role=payload.role,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ApiResponse(message="账号已创建", data={"id": row.id, "username": row.username, "role": row.role})
    finally:
        db.close()


@router.put("/{user_id}", response_model=ApiResponse[dict])
def update_user(user_id: int, payload: AdminUserUpdate, admin: SuperDep):
    """修改账号信息/角色/启停/密码（仅 super；不可停用自己）。"""
    db = SessionLocal()
    try:
        row = db.get(AdminUser, user_id)
        if row is None:
            raise HTTPException(status_code=404, detail="账号不存在")
        if row.id == admin.id and payload.is_active is False:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
        if payload.role is not None:
            if payload.role not in ALL_ROLES:
                raise HTTPException(status_code=400, detail=f"角色须为 {'/'.join(ALL_ROLES)}")
            if row.id == admin.id and payload.role != "super":
                raise HTTPException(status_code=400, detail="不能降低自己的角色")
            row.role = payload.role
        if payload.display_name is not None:
            row.display_name = payload.display_name
        if payload.is_active is not None:
            row.is_active = payload.is_active
        if payload.password:
            row.password_hash = hash_password(payload.password)
        db.commit()
        return ApiResponse(message="账号已更新", data={"id": row.id, "role": row.role, "is_active": row.is_active})
    finally:
        db.close()
