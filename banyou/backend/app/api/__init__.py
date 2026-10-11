"""路由装配：开放 API（/api/v1）+ 管理后台 API（/api/admin）。"""
from fastapi import APIRouter

from app.api import admin_content, admin_product, admin_settings, auth, companion, content, product

api_router = APIRouter()
api_router.include_router(content.router, prefix="/api/v1", tags=["开放API"])
api_router.include_router(product.router, prefix="/api/v1", tags=["开放API-文创"])
api_router.include_router(companion.router, prefix="/api/v1", tags=["开放API-AI伴游"])
api_router.include_router(auth.router, prefix="/api/admin", tags=["后台-鉴权"])
api_router.include_router(admin_content.router, prefix="/api/admin", tags=["后台-内容"])
api_router.include_router(admin_product.router, prefix="/api/admin", tags=["后台-文创"])
api_router.include_router(admin_settings.router, prefix="/api/admin", tags=["后台-设置"])
