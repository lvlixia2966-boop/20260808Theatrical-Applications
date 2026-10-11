"""运营统计路由：豆包用量月度汇总 / 明细日志 / Agent 会话记录（报价单 #16/#18/#21）。

高内聚：运营视角的聚合查询收敛在此；计量口径在 usage_meter、记录在模型层。
低耦合：只读接口，不做写操作；ops/super 角色可访问（require_role 门禁）。
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.database import SessionLocal
from app.models import AdminUser
from app.models.agent import AgentMessage, AgentSession
from app.models.usage import UsageLog
from app.schemas import ApiResponse
from app.services.usage_meter import monthly_usage

logger = logging.getLogger("stats")

router = APIRouter(prefix="/api/admin", tags=["运营统计"])

OpsDep = Annotated[AdminUser, Depends(require_role("ops"))]

# kind → 展示名（中文），前端亦可自行覆盖
KIND_LABELS = {"asr": "语音识别", "translate": "翻译", "tts": "语音合成", "llm": "大模型"}


@router.get("/stats", response_model=ApiResponse[dict])
def stats(admin: OpsDep, month: str | None = Query(None, description="如 2026-09，缺省当月")):
    """月度用量汇总 + 业务量概览：ASR 秒数 / 翻译与 TTS 字符 / LLM token。"""
    usage = monthly_usage(month)
    db: Session = SessionLocal()
    try:
        return ApiResponse(data={
            "month": month,
            "usage": [
                {"kind": kind, "label": KIND_LABELS.get(kind, kind),
                 "quantity": round(quantity, 2), "unit": _unit_of(kind)}
                for kind, quantity in usage.items()
            ],
            "totals": {
                "agent_sessions": db.query(AgentSession).count(),
                "agent_messages": db.query(AgentMessage).count(),
                "agent_degraded": db.query(AgentMessage).filter(AgentMessage.degraded.is_(True)).count(),
            },
        })
    finally:
        db.close()


def _unit_of(kind: str) -> str:
    from app.services.usage_meter import UNIT

    return UNIT.get(kind, "")


@router.get("/usage-logs", response_model=ApiResponse[list[dict]])
def usage_logs(
    admin: OpsDep,
    kind: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """近期用量明细（倒序），供运营对账。"""
    db: Session = SessionLocal()
    try:
        query = db.query(UsageLog)
        if kind:
            query = query.filter(UsageLog.kind == kind)
        rows = query.order_by(UsageLog.id.desc()).limit(limit).all()
        return ApiResponse(data=[{
            "id": r.id, "kind": r.kind, "quantity": r.quantity, "unit": r.unit,
            "session_ref": r.session_ref, "meta": r.meta,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows])
    finally:
        db.close()


@router.get("/agent-sessions", response_model=ApiResponse[list[dict]])
def agent_sessions(admin: OpsDep, limit: int = Query(50, ge=1, le=200)):
    """Agent 伴游会话记录列表（消息数 / 降级次数 / 最近活跃），供运营回查。"""
    db: Session = SessionLocal()
    try:
        msg_count = (
            db.query(AgentMessage.session_id, sa_func.count(AgentMessage.id).label("n"))
            .group_by(AgentMessage.session_id)
            .subquery()
        )
        rows = (
            db.query(AgentSession, sa_func.coalesce(msg_count.c.n, 0))
            .outerjoin(msg_count, AgentSession.id == msg_count.c.session_id)
            .order_by(AgentSession.last_active_at.desc())
            .limit(limit)
            .all()
        )
        return ApiResponse(data=[{
            "id": s.id, "token": s.token[:8] + "…", "lang": s.lang, "node_code": s.node_code,
            "is_active": s.is_active, "messages": int(n),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
        } for s, n in rows])
    finally:
        db.close()
