"""认证路由：登录鉴权 + 失败限流（同一用户名 5 次失败/分钟，成功登录清零）。"""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep
from app.core.ratelimit import SlidingWindowLimiter
from app.schemas import ApiResponse, LoginRequest, LoginResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录失败限流：按用户名计数（docker-proxy 转发下源 IP 不可区分，见 ratelimit.py 说明）
_login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=60.0)


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(payload: LoginRequest, db: DbDep):
    if _login_limiter.blocked(payload.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="尝试过于频繁，请 1 分钟后再试",
        )
    try:
        result = auth_service.authenticate(db, payload.username, payload.password)
    except HTTPException:
        _login_limiter.record(payload.username)
        raise
    _login_limiter.reset(payload.username)
    return ApiResponse(data=LoginResponse(
        access_token=result.token, display_name=result.display_name, role=result.role,
    ))
