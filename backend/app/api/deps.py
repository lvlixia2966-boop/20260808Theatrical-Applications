"""FastAPI 依赖：数据库会话、管理员认证、角色权限。"""
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token, pwd_version
from app.database import get_db
from app.models import AdminUser

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


def get_current_admin(
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AdminUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    admin = db.get(AdminUser, int(payload["sub"]))
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已禁用")
    if payload.get("pwdv") != pwd_version(admin.password_hash):
        # 口令已变更（或改密前的旧签发），旧 token 一律作废
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    return admin


AdminDep = Annotated[AdminUser, Depends(get_current_admin)]


def require_role(*roles: str) -> Callable[[AdminUser], AdminUser]:
    """角色门禁工厂：super 恒通过，其余角色须在白名单内（报价单 #17 权限分级）。

    用法：admin: Annotated[AdminUser, Depends(require_role("ops", "super"))]
    """
    allowed = set(roles) | {"super"}

    def _check(admin: AdminDep) -> AdminUser:
        if admin.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权执行此操作")
        return admin

    return _check