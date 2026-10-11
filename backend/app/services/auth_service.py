"""认证服务：登录鉴权与令牌发放。"""
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, pwd_version, verify_password
from app.models import AdminUser


@dataclass
class AuthResult:
    """登录成功结果：token 与账号信息（供前端按角色装配界面）。"""

    token: str
    role: str
    display_name: str


def authenticate(db: Session, username: str, password: str) -> AuthResult:
    """校验管理员账号密码，返回 token 与角色。"""
    admin = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if not admin or not verify_password(password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    token = create_access_token(admin.id, {"role": admin.role, "pwdv": pwd_version(admin.password_hash)})
    return AuthResult(token=token, role=admin.role, display_name=admin.display_name)