"""实时翻译路由：信令 WebSocket + 双端 REST + 管理端会话/二维码（报价单 #14/#18）。

高内聚：RTC 域的 HTTP/WS 路由收敛在此；媒体与业务在 rtc_gateway / rtc_pipeline。
低耦合：路由只做鉴权、参数装配与响应装配；管理端操作走 AdminDep 权限。
"""
import logging
import secrets

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models.rtc import RtcLog, RtcSession
from app.api.deps import AdminDep
from app.schemas import ApiResponse
from app.schemas.rtc import (
    MSG_PING,
    ROLE_STAFF,
    ROLE_VISITOR,
    RtcSessionCreate,
    RtcSessionOut,
    TokenInfoOut,
)
from app.services.rtc_gateway import rtc_gateway

logger = logging.getLogger("rtc")

router = APIRouter(prefix="/api/rtc", tags=["实时翻译"])

# 会话码字符集：与 live 场次一致，去除易混淆字符
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

STATUS_ENDED = "ended"


# ── 扫码端 REST ─────────────────────────────────────────────────


@router.get("/token-info", response_model=ApiResponse[TokenInfoOut])
def token_info(token: str = Query(..., description="扫码 URL 携带的双端 token")):
    """扫码后换取会话上下文：角色、语言、会话状态、对端在线情况。"""
    db = SessionLocal()
    try:
        session = rtc_gateway.resolve_session(db, token)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在或已失效")
        role = rtc_gateway.role_of(session, token)
        return ApiResponse(data=TokenInfoOut(
            code=session.code,
            role=role,
            title=session.title,
            lang=session.visitor_lang if role == ROLE_VISITOR else session.staff_lang,
            visitor_lang=session.visitor_lang,
            staff_lang=session.staff_lang,
            session_status=session.status,
            peer_online=rtc_gateway.peer_online(session, ROLE_STAFF if role == ROLE_VISITOR else ROLE_VISITOR),
        ))
    finally:
        db.close()


@router.get("/captions/{token}", response_model=ApiResponse[list[dict]])
def captions(token: str, after: int = Query(0, ge=0, description="已收到的最大 seq，补拉其后记录")):
    """断线重连补拉字幕（按会话记录 id 递增），保留期内可回查。"""
    db = SessionLocal()
    try:
        session = rtc_gateway.resolve_session(db, token)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在或已失效")
        rows = (
            db.query(RtcLog)
            .filter(RtcLog.session_id == session.id, RtcLog.id > after)
            .order_by(RtcLog.id)
            .limit(200)
            .all()
        )
        return ApiResponse(data=[{
            "type": "caption",
            "seq": r.id,
            "direction": r.direction,
            "text": r.source_text,
            "translated": r.translated_text,
            "ts": r.created_at.timestamp() if r.created_at else 0,
        } for r in rows])
    finally:
        db.close()


# ── 信令 WebSocket ──────────────────────────────────────────────


@router.websocket("/ws/{token}")
async def rtc_ws(ws: WebSocket, token: str):
    """双端信令通道：鉴权后由网关接管 offer/answer、ICE、PTT 与字幕下行。"""
    await ws.accept()
    try:
        await rtc_gateway.serve_socket(ws, token)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - 网关内部已兜底，此处防任务泄漏
        logger.exception("RTC WebSocket 异常")


# ── 管理端（AdminDep）───────────────────────────────────────────


def _session_out(db, row: RtcSession) -> RtcSessionOut:
    log_count = db.query(RtcLog).filter(RtcLog.session_id == row.id).count()
    base = f"?view=rtc&token="
    return RtcSessionOut(
        id=row.id, code=row.code, title=row.title,
        visitor_lang=row.visitor_lang, staff_lang=row.staff_lang,
        status=row.status, retention_days=row.retention_days,
        visitor_url=f"index.html{base}{row.visitor_token}",
        staff_url=f"index.html?view=rtc&role=staff&token={row.staff_token}",
        log_count=log_count, created_at=row.created_at,
    )


@router.get("/sessions", response_model=ApiResponse[list[RtcSessionOut]])
def list_sessions(admin: AdminDep):
    """会话列表（管理端）。"""
    db = SessionLocal()
    try:
        rows = db.query(RtcSession).order_by(RtcSession.id.desc()).limit(100).all()
        return ApiResponse(data=[_session_out(db, r) for r in rows])
    finally:
        db.close()


@router.post("/sessions", response_model=ApiResponse[RtcSessionOut])
def create_session(payload: RtcSessionCreate, admin: AdminDep):
    """创建双端翻译会话，返回两端二维码 URL（前端渲染）。"""
    db = SessionLocal()
    try:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
            if not db.query(RtcSession).filter(RtcSession.code == code).first():
                break
        row = RtcSession(
            code=code,
            title=payload.title,
            visitor_lang=payload.visitor_lang,
            staff_lang=payload.staff_lang,
            visitor_token=rtc_gateway.new_token(),
            staff_token=rtc_gateway.new_token(),
            retention_days=payload.retention_days,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ApiResponse(data=_session_out(db, row))
    finally:
        db.close()


@router.post("/sessions/{session_id}/end", response_model=ApiResponse[dict])
async def end_session(session_id: int, admin: AdminDep):
    """结束会话：断开双端并广播 session_end。"""
    db = SessionLocal()
    try:
        row = db.get(RtcSession, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if row.status != STATUS_ENDED:
            await rtc_gateway.end_session(row)
        return ApiResponse(data={"id": row.id, "status": "ended"})
    finally:
        db.close()
