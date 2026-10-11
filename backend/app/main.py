"""FastAPI 应用入口：装配中间件、路由、调度器与静态资源托管。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.database import init_db
from app.services.show_scheduler import show_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时建表并拉起场次调度器，停止时收尾直播资源。"""
    init_db()
    show_scheduler.start()
    yield
    await show_scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    description="巴蜀语音导览系统后端 API：耳机管理 / 节目上下架 / 文本语音预约 / 场次直播",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.app_name}


# 托管静态资源：管理后台 / 前端扫码页 / 首页（根路径） / 设计版本验证页（redesign，一层深以保 ../assets 解析）
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/admin", StaticFiles(directory=settings.admin_static_dir, html=True), name="admin")
app.mount("/guide", StaticFiles(directory=settings.static_dir, html=True), name="guide")
app.mount("/designs", StaticFiles(directory=f"{settings.static_dir}/redesign", html=True), name="designs")
app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")