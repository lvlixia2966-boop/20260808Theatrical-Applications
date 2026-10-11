"""FastAPI 应用入口：装配路由与静态资源托管。"""
import mimetypes
from contextlib import asynccontextmanager

# Windows 下 mimetypes 可能按注册表把 .js 判成 text/plain，
# ES Module 要求 JS MIME 严格正确，这里显式兜底注册。
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时建表。"""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "凉山伴游 · 纯伴游导览系统后端 API。"
        "游客端 / 小程序 / 三方平台一律经开放 API（/api/v1）接入内容，"
        "内容由管理后台（/api/admin）配置。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_heuristic_cache(request, call_next):
    """静态资源禁用启发式缓存：只允许带 ETag 的条件请求（304），
    避免浏览器长期复用过期/损坏的缓存条目（开发期改版即时生效）。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets") or path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-cache"
    return response

app.include_router(api_router)


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.app_name}


# 静态资源：游客端 H5（根路径）/ 管理后台（/admin）/ 上传素材（/uploads）
app.mount("/admin", StaticFiles(directory=settings.admin_static_dir, html=True), name="admin")
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
