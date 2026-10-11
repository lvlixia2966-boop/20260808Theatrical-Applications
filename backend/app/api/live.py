"""场次直播路由：场次管理 REST + 观众订阅 WebSocket。

高内聚：本模块只做协议装配与连接生命周期管理，业务编排全部委托
       show_scheduler（状态机）与 live_hub（广播中枢）。
低耦合：不 import 具体 ASR 引擎/采集器；观众端经 live-listen.html 对接，
       管理端经 admin 后台对接，互不依赖。

REST：
  GET  /api/live/shows/now                 观众端：正在直播的场次
  POST /api/live/shows                     管理端：设置场次
  GET  /api/live/shows                     管理端：场次列表（可按状态过滤）
  PUT  /api/live/shows/{id}                管理端：修改未开播场次
  DELETE /api/live/shows/{id}              管理端：删除场次
  POST /api/live/shows/{id}/start          管理端：立即开播
  POST /api/live/shows/{id}/stop           管理端：立即收播
  POST /api/live/shows/{id}/broadcast      管理端：推流预录音频（临时通知/备用音源）
  POST /api/live/shows/{id}/broadcast/stop 管理端：停止推流
  GET  /api/live/shows/{code}/captions     观众端：近期字幕快照（断线补拉）

WS：/api/live/ws/{session_code}?audio=0|1  观众订阅（字幕文本帧 + 原声二进制帧）
"""
import base64
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import or_

from app.api.deps import AdminDep, DbDep
from app.core.languages import is_supported
from app.models import LiveShow
from app.schemas import ApiResponse, BroadcastAudioIn, LiveShowCreate, LiveShowOut, LiveShowUpdate
from app.schemas.live import MSG_APPLAUD, MSG_PING
from app.services import intro_service
from app.services.live_hub import live_hub
from app.services.show_scheduler import show_scheduler

logger = logging.getLogger("live")

router = APIRouter(prefix="/api/live", tags=["场次直播"])

STATUS_LIVE = "live"


# ── 观众端：正在直播的场次 ────────────────────────────────────────


@router.get("/intro")
def get_intro(lang: str = Query("zh", description="介绍语言码，如 zh/en/ja；未预置语言自动翻译")):
    """观众入场前的剧场介绍：返回该语言的介绍文案（前端再调 /api/tts/synthesize 播放）。"""
    lang, text = intro_service.get_intro_text(lang)
    return ApiResponse(data={"lang": lang, "text": text})


@router.get("/shows/now", response_model=ApiResponse[list[LiveShowOut]])
def shows_now(db: DbDep):
    """观众端首页：返回全部直播中的场次（进入播放页即收听）。"""
    shows = db.query(LiveShow).filter(LiveShow.status == STATUS_LIVE).all()
    return ApiResponse(data=[_show_out(db, s) for s in shows])


@router.get("/shows/{session_code}/captions")
def show_captions(session_code: str, limit: int = Query(50, ge=1, le=300)):
    """按会场码拉取近期字幕快照（观众端断线重连补拉）。"""
    session = live_hub.get(session_code)
    if session is None:
        return ApiResponse(code=404, message="会场不存在或已结束")
    return ApiResponse(data=live_hub.recent_captions(session, limit))


# ── 管理端：场次 CRUD ────────────────────────────────────────────


@router.post("/shows", response_model=ApiResponse[LiveShowOut])
def create_show(payload: LiveShowCreate, db: DbDep, _: AdminDep):
    """设置场次：到点由调度器自动开播收音并推送翻译字幕。"""
    show = LiveShow(
        title=payload.title,
        host_name=payload.host_name,
        start_at=payload.start_at,
        duration_min=payload.duration_min,
        target_langs=json.dumps(_clean_langs(payload.target_langs)),
        status="scheduled",
    )
    db.add(show)
    db.commit()
    db.refresh(show)
    return ApiResponse(message="场次已设置，将按排期自动开播", data=_show_out(db, show))


@router.get("/shows", response_model=ApiResponse[list[LiveShowOut]])
def list_shows(db: DbDep, _: AdminDep, status: str | None = Query(None)):
    """管理端场次列表（默认返回未结束的全部场次）。"""
    query = db.query(LiveShow)
    if status:
        query = query.filter(LiveShow.status == status)
    else:
        query = query.filter(or_(LiveShow.status == "scheduled", LiveShow.status == STATUS_LIVE))
    shows = query.order_by(LiveShow.start_at).all()
    return ApiResponse(data=[_show_out(db, s) for s in shows])


@router.get("/shows/next", response_model=ApiResponse)
def next_scheduled_show(db: DbDep):
    """最近一场待演场次（候场倒计时用）；无则 data=null。

    供前端情境引擎的「候场模式」轮询：距离 start_at 的倒计时驱动欢迎横幅。
    注意路由须先于 /shows/{show_id} 类路由声明。
    """
    show = (db.query(LiveShow)
            .filter(LiveShow.status == "scheduled")
            .order_by(LiveShow.start_at.asc())
            .first())
    return ApiResponse(data=_show_out(db, show) if show else None)


@router.put("/shows/{show_id}", response_model=ApiResponse[LiveShowOut])
def update_show(show_id: int, payload: LiveShowUpdate, db: DbDep, _: AdminDep):
    """修改场次（仅未开播场次可改；直播中/已结束不可改）。"""
    show = db.get(LiveShow, show_id)
    if show is None:
        return ApiResponse(code=404, message="场次不存在")
    if show.status != "scheduled":
        return ApiResponse(code=400, message="场次已开播，不可修改")
    if payload.title is not None:
        show.title = payload.title
    if payload.host_name is not None:
        show.host_name = payload.host_name
    if payload.start_at is not None:
        show.start_at = payload.start_at
    if payload.duration_min is not None:
        show.duration_min = payload.duration_min
    if payload.target_langs is not None:
        show.target_langs = json.dumps(_clean_langs(payload.target_langs))
    db.commit()
    db.refresh(show)
    return ApiResponse(message="场次已更新", data=_show_out(db, show))


@router.delete("/shows/{show_id}", response_model=ApiResponse)
async def delete_show(show_id: int, db: DbDep, _: AdminDep):
    """删除场次（直播中删除将先收播）。"""
    show = db.get(LiveShow, show_id)
    if show is None:
        return ApiResponse(code=404, message="场次不存在")
    if show.status == STATUS_LIVE:
        await show_scheduler.stop_now(show_id)
    db.delete(show)
    db.commit()
    return ApiResponse(message="场次已删除")


# ── 管理端：手动开播 / 收播 ──────────────────────────────────────


@router.post("/shows/{show_id}/start", response_model=ApiResponse[LiveShowOut])
async def start_show_now(show_id: int, db: DbDep, _: AdminDep):
    """立即开播（排期未到的 scheduled 场次）。"""
    show = await show_scheduler.start_now(show_id)
    if show is None:
        return ApiResponse(code=400, message="场次不存在或不可开播")
    return ApiResponse(message="场次已开播", data=_show_out(db, show))


@router.post("/shows/{show_id}/stop", response_model=ApiResponse[LiveShowOut])
async def stop_show_now(show_id: int, db: DbDep, _: AdminDep):
    """立即收播（直播中的场次）。"""
    show = await show_scheduler.stop_now(show_id)
    if show is None:
        return ApiResponse(code=400, message="场次不存在或不在直播中")
    return ApiResponse(message="场次已收播", data=_show_out(db, show))


# ── 管理端：预录音频推流（纯播放控制）────────────────────────────

MAX_BROADCAST_BYTES = 16 * 1024 * 1024  # ≈8.7 分钟（16kHz × 16bit）


@router.post("/shows/{show_id}/broadcast", response_model=ApiResponse)
async def broadcast_audio(show_id: int, payload: BroadcastAudioIn, _: AdminDep):
    """向直播中场次推流预录音频（临时通知/备用音源）。

    推流期间现场收音让位（观众只听该音频、字幕不再误识别），
    推完自动恢复收音；可选通知文案随音频走字幕通道（含翻译）。
    """
    session = live_hub.get_by_show(show_id)
    if session is None:
        return ApiResponse(code=400, message="场次不在直播中")
    try:
        pcm = base64.b64decode(payload.pcm_b64, validate=True)
    except Exception:  # noqa: BLE001 - base64 非法统一按参数错误返回
        return ApiResponse(code=400, message="音频数据无效（需 PCM16 base64）")
    if len(pcm) < 3200:  # <0.1s
        return ApiResponse(code=400, message="音频内容过短")
    if len(pcm) > MAX_BROADCAST_BYTES:
        return ApiResponse(code=400, message="音频过长（超过约 8 分钟上限）")
    if len(pcm) % 2:  # 16bit 对齐
        pcm += b"\x00"
    result = await live_hub.start_broadcast(session, pcm, payload.notice)
    if result == "conflict":
        return ApiResponse(code=409, message="已有音频推流中，请先停止当前推流")
    if result != "started":
        return ApiResponse(code=400, message="场次不在直播中")
    return ApiResponse(message=f"推流已开始（约 {len(pcm) // 32000} 秒，推完自动恢复现场收音）")


@router.post("/shows/{show_id}/broadcast/stop", response_model=ApiResponse)
async def stop_broadcast_audio(show_id: int, _: AdminDep):
    """停止进行中的预录音频推流（现场收音即刻恢复）。"""
    session = live_hub.get_by_show(show_id)
    if session is None:
        return ApiResponse(code=400, message="场次不在直播中")
    stopped = await live_hub.stop_broadcast(session)
    return ApiResponse(message="推流已停止，现场收音已恢复" if stopped else "当前没有进行中的推流")


# ── 观众订阅 WebSocket ───────────────────────────────────────────


@router.websocket("/ws/{session_code}")
async def live_ws(ws: WebSocket, session_code: str, audio: int = 1):
    """观众订阅通道。

    文本下行：caption（原文+多语言译文）/ listeners / session_end
    二进制下行：PCM16/16k/mono 原声块（audio=1 时）
    上行：ping 心跳保活。
    连接即补发近期历史字幕，中途加入不缺上下文。
    """
    session = live_hub.get(session_code)
    if session is None:
        await ws.accept()
        await ws.close(code=4404, reason="会场不存在或已结束")
        return

    await ws.accept()
    live_hub.add_listener(session, ws, want_audio=bool(audio))
    logger.info("观众接入场次 %s（在线 %s 人，原声=%s）", session.session_id, session.listener_count, bool(audio))
    try:
        for caption in live_hub.recent_captions(session):
            await ws.send_json(caption)
        await ws.send_json({"type": "listeners", "count": session.listener_count})
        while True:
            message = await ws.receive_text()
            if MSG_PING in message:
                continue  # 心跳保活
            try:
                frame = json.loads(message)
            except ValueError:
                continue
            if frame.get("type") == MSG_APPLAUD:
                await live_hub.applaud(session)  # 全场叫好（节流广播）
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - 广播失败剔除由 hub 负责，此处兜底防泄漏
        logger.exception("观众连接异常（场次 %s）", session.session_id)
    finally:
        live_hub.remove_listener(session, ws)


# ── 工具 ────────────────────────────────────────────────────────


def _clean_langs(langs: list[str]) -> list[str]:
    """目标语言去重 + 过滤不支持的语言码；全无效时回退英文。"""
    cleaned = [lang for lang in dict.fromkeys(langs or []) if is_supported(lang)]
    return cleaned or ["en"]


def _show_out(db, show: LiveShow) -> LiveShowOut:
    """ORM → 响应模型（直播中的场次附加在线人数/字幕数）。"""
    listeners = captions = 0
    session = live_hub.get(show.session_code) if show.session_code else None
    if session is not None and session.show_id == show.id:
        listeners = session.listener_count
        captions = session.seq
    return LiveShowOut(
        id=show.id,
        title=show.title,
        host_name=show.host_name,
        start_at=show.start_at,
        duration_min=show.duration_min,
        target_langs=json.loads(show.target_langs) if show.target_langs else ["en"],
        status=show.status,
        session_code=show.session_code,
        listeners=listeners,
        captions=captions,
        created_at=show.created_at,
    )
