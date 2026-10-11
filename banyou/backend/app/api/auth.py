"""后台鉴权：登录 / 当前用户 / 修改密码。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import create_access_token, hash_password, pwd_version, verify_password
from app.database import get_db
from app.models.admin import AdminUser

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


# 登录失败限流：同一用户名 5 次失败/分钟，成功登录清零
_login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=60.0)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    username = body.username.strip()
    if _login_limiter.blocked(username):
        raise HTTPException(429, "尝试过于频繁，请 1 分钟后再试")
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None or not verify_password(body.password, admin.password_hash):
        _login_limiter.record(username)
        raise HTTPException(400, "用户名或密码错误")
    _login_limiter.reset(username)
    return {
        "token": create_access_token(admin.username, {"pwdv": pwd_version(admin.password_hash)}),
        "admin": {"id": admin.id, "username": admin.username, "display_name": admin.display_name},
    }


@router.get("/me")
def me(admin: AdminUser = Depends(require_admin)):
    return {"id": admin.id, "username": admin.username, "display_name": admin.display_name}


@router.put("/password")
def change_password(
    body: PasswordIn,
    admin: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, admin.password_hash):
        raise HTTPException(400, "原密码不正确")
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    admin.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
