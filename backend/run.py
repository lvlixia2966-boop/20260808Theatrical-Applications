"""本地启动入口：python run.py"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        reload_dirs=["./app"] if settings.debug else None,
    )