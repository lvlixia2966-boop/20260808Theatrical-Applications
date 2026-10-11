"""Agent 伴游路由：会话创建 / 问答 / 历史 / 语音提问（报价单 #9/#12）。

高内聚：伴游问答的 HTTP 路由收敛在此；编排逻辑在 agent_service。
低耦合：路由只做鉴权（token）、参数装配与响应装配；无管理端依赖。
"""
import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.deps import DbDep
from app.models.agent import AgentMessage
from app.schemas import ApiResponse
from app.schemas.agent import (
    AgentChatReply,
    AgentChatRequest,
    AgentMessageOut,
    AgentSessionCreate,
    AgentSessionOut,
    AgentSourceOut,
    AgentVoiceReply,
)
from app.services.agent_service import agent_service
from app.services.doubao.asr_oneshot import decode_to_pcm16k, recognize
from app.services.usage_meter import record as record_usage

logger = logging.getLogger("agent")

router = APIRouter(prefix="/api/agent", tags=["Agent伴游"])

_VOICE_MAX_BYTES = 4 * 1024 * 1024   # 录音上传上限（约 4MB，覆盖 1 分钟 webm/opus）
_VOICE_MIN_PCM_BYTES = 9600          # 有效语音下限：0.3s @16kHz PCM16


def _sources_of(msg: AgentMessage) -> list[AgentSourceOut]:
    import json

    try:
        raw = json.loads(msg.sources_json or "[]")
    except Exception:  # noqa: BLE001
        raw = []
    return [AgentSourceOut(**item) for item in raw if isinstance(item, dict)]


@router.post("/sessions", response_model=ApiResponse[AgentSessionOut])
def create_session(payload: AgentSessionCreate, db: DbDep):
    """创建伴游会话：返回 token（前端持有，后续问答凭此）。"""
    row = agent_service.create_session(db, lang=payload.lang, node_code=payload.node_code)
    return ApiResponse(data=AgentSessionOut(token=row.token, lang=row.lang,
                                            node_code=row.node_code, created_at=row.created_at))


@router.post("/chat", response_model=ApiResponse[AgentChatReply])
async def chat(payload: AgentChatRequest, db: DbDep):
    """伴游问答：RAG 召回 → 豆包 LLM → 引用校验；LLM 不可用时降级为服务台引导话术。"""
    session = agent_service.get_session(db, payload.token)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    reply = await agent_service.chat(db, session, payload.text)
    return ApiResponse(data=AgentChatReply(
        text=reply.text,
        sources=[AgentSourceOut(**s) for s in reply.sources],
        degraded=reply.degraded,
    ))


@router.post("/voice", response_model=ApiResponse[AgentVoiceReply])
async def voice(db: DbDep, audio: UploadFile = File(...), token: str = Query(..., min_length=8, max_length=64)):
    """语音提问：录音整段上传 → 豆包单发 ASR 转文本 → 复用 chat 管线作答。

    浏览器端原生语音识别在场馆网络下不可用（依赖境外服务），故收音
    交由服务端转写；一次请求同时返回「识别原文 + 回答」，减少往返。
    """
    session = agent_service.get_session(db, token)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    raw = await audio.read()
    if len(raw) > _VOICE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="录音过长，请控制在 1 分钟内")
    try:
        pcm = decode_to_pcm16k(raw)
    except Exception:  # noqa: BLE001 - 浏览器编码差异导致解码失败时明确报错
        logger.warning("伴游语音解码失败（{} 字节）", len(raw))
        raise HTTPException(status_code=400, detail="录音格式无法解析，请重新按住话筒提问")
    if len(pcm) < _VOICE_MIN_PCM_BYTES:
        raise HTTPException(status_code=400, detail="没有听到声音，请靠近话筒重试")
    heard = recognize(pcm, uid=f"agent:{token[:8]}")
    record_usage("asr", round(len(pcm) / 32000, 2), session_ref=f"agent:{token[:16]}")
    if not heard:
        raise HTTPException(status_code=422, detail="没能识别出语音内容，请换个说法或直接打字提问")
    reply = await agent_service.chat(db, session, heard)
    return ApiResponse(data=AgentVoiceReply(
        heard=heard,
        text=reply.text,
        sources=[AgentSourceOut(**s) for s in reply.sources],
        degraded=reply.degraded,
    ))


@router.get("/history", response_model=ApiResponse[list[AgentMessageOut]])
def history(db: DbDep, token: str = Query(..., min_length=8, max_length=64),
            limit: int = Query(50, ge=1, le=200)):
    """会话历史（按时间正序），供前端刷新/回连时恢复对话。"""
    session = agent_service.get_session(db, token)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    rows = (
        db.query(AgentMessage)
        .filter(AgentMessage.session_id == session.id)
        .order_by(AgentMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return ApiResponse(data=[AgentMessageOut(
        id=r.id, role=r.role, content=r.content,
        sources=_sources_of(r), degraded=r.degraded, created_at=r.created_at,
    ) for r in rows])
