"""豆包用量计量：ASR/翻译/TTS/LLM 全链路埋点与月度预算（报价单 #16/#21）。

高内聚：计量口径（kind/unit/折算）与预算告警阈值收敛在此。
低耦合：record() 为尽力而为的落库（异常静默），调用方零负担；
       预算聚合由 admin_stats API 按月查询本模块提供的方法。
"""

import logging
from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.usage import UsageLog

logger = logging.getLogger("usage")

# 各 kind 的计量单位
UNIT = {"asr": "audio_seconds", "translate": "chars", "tts": "chars", "llm": "tokens"}


def record(kind: str, quantity: float, session_ref: str = "", meta: str = "") -> None:
    """记一笔用量（独立短会话，失败静默——计量绝不反噬业务链路）。"""
    if quantity <= 0:
        return
    try:
        db: Session = SessionLocal()
        try:
            db.add(UsageLog(kind=kind, quantity=quantity, unit=UNIT.get(kind, ""),
                            session_ref=session_ref, meta=meta[:255]))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("用量记录失败（%s）", kind)


def monthly_usage(month: str | None = None) -> dict[str, float]:
    """按月聚合用量：month 形如 2026-09，缺省当月。返回 {kind: 总量}。"""
    month = month or datetime.now().strftime("%Y-%m")
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(UsageLog.kind, sa_func.sum(UsageLog.quantity))
            .filter(sa_func.strftime("%Y-%m", UsageLog.created_at) == month)
            .group_by(UsageLog.kind)
            .all()
        ) if db.bind.dialect.name == "sqlite" else (
            db.query(UsageLog.kind, sa_func.sum(UsageLog.quantity))
            .filter(sa_func.date_format(UsageLog.created_at, "%Y-%m") == month)
            .group_by(UsageLog.kind)
            .all()
        )
        return {kind: float(total or 0) for kind, total in rows}
    finally:
        db.close()
