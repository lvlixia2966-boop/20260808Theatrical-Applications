"""数据库引擎与会话管理：统一提供 Session 依赖，供各 API/service 复用。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
    echo=settings.debug and settings.app_env == "development",
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 依赖：提供请求级数据库会话。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（create_all 只建新表不改旧表；后加列可用轻量 ALTER 兼容）。"""
    from app import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(bind=engine)
