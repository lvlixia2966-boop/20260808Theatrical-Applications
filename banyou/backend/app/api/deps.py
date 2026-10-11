"""API 依赖：数据库会话 + 管理员鉴权。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_payload, pwd_version
from app.database import get_db
from app.models.admin import AdminUser

_bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AdminUser:
    """校验 Bearer JWT 并返回管理员；游客端接口不挂此依赖。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_payload(credentials.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    admin = db.query(AdminUser).filter(AdminUser.username == payload.get("sub")).first()
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在")
    if payload.get("pwdv") != pwd_version(admin.password_hash):
        # 口令已变更（或改密前的旧签发），旧 token 一律作废
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    return admin
