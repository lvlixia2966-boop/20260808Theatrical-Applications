"""本地启动入口：cd banyou/backend && python run.py"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
