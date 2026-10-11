"""数据库引擎与会话管理：统一提供 Session 依赖，供各 API/service 复用。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
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
    """建表 + 存量表轻量加列迁移（生产可用 alembic 替代）。

    create_all 只建新表不改旧表；此处对「后加的可空列」逐个 ALTER，
    列已存在时报错忽略，兼容 SQLite / MySQL。
    """
    from app import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(bind=engine)
    _migrations = (
        "ALTER TABLE programs ADD COLUMN intro_zh TEXT",
        "ALTER TABLE programs ADD COLUMN intro_en TEXT",
        "ALTER TABLE admin_users ADD COLUMN role VARCHAR(16) DEFAULT 'super'",
    )
    with engine.begin() as conn:
        for ddl in _migrations:
            try:
                conn.exec_driver_sql(ddl)
            except Exception:  # noqa: BLE001 - 列已存在等情形直接跳过
                pass