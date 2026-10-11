"""场次直播枢纽：运行时会话管理 + 字幕生产线编排 + 原声/字幕广播。

高内聚：会话注册表、ASR→翻译→广播的编排流程、原声转发、历史字幕缓存统一在此模块。
低耦合：ASR 走 asr_service 引擎抽象、翻译复用 translation_service、
       采集由 show_scheduler 通过 CaptureWorker 喂入，网络收发只依赖
       starlette WebSocket 协议接口，路由层仅做参数装配。

字幕生产管线（无人值守，由调度器驱动）：
  采集器 PCM 块 → 原声广播（audio=1 的观众）
                → ASR 引擎（断句）→ 完整句 → 多目标语言翻译
                → caption（原文+译文+序号）→ 历史缓存 → 广播全部观众
"""

import asyncio
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from app.config import settings
from app.schemas.live import MSG_APPLAUD, MSG_CAPTION, MSG_HIGHLIGHT, MSG_LISTENERS, MSG_SESSION_END
from app.services import glossary_service as glossary
from app.services.asr_service import AsrEngine, create_asr_engine
from app.services.translation_service import translation_service

logger = logging.getLogger("live")

# 会场码字符集：去除易混淆的 0/O、1/I，便于观众口头转述与输入
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6

STATUS_LIVE = "live"
STATUS_ENDED = "ended"


@dataclass
class LiveSession:
    """一场场次直播的运行时状态（调度器开播时创建，收播时销毁）。"""

    session_id: str
    show_id: int
    title: str
    host_name: str
    target_langs: list[str]
    created_at: float = field(default_factory=time.time)
    status: str = STATUS_LIVE
    seq: int = 0  # 字幕递增序号
    history: deque = field(default_factory=lambda: deque(maxlen=settings.live_max_history))
    highlights_at: dict = field(default_factory=dict)  # 术语 -> 上次看点推送时间（冷却节流）
    applaud_count: int = 0   # 全场叫好累计数
    applaud_at: float = 0.0  # 上次叫好广播时间（0.8s 合并节流）
    engine: AsrEngine = field(default_factory=create_asr_engine)
    listeners: set = field(default_factory=set)  # 观众 WebSocket 集合
    audio_subscribers: set = field(default_factory=set)  # 订阅原声的观众子集（audio=1）
    broadcast_task: asyncio.Task | None = None  # 预录音频推流任务（推流期间现场收音让位）

    @property
    def listener_count(self) -> int:
        return len(self.listeners)


class LiveHub:
    """场次直播会话注册表与广播中枢（进程内单例）。"""

    def __init__(self):
        self._sessions: dict[str, LiveSession] = {}

    # ── 会话生命周期 ────────────────────────────────────────────

    def create_session(
        self, show_id: int, title: str, host_name: str,
        target_langs: list[str], session_id: str | None = None,
    ) -> LiveSession:
        """开播：创建运行时会话（session_id 可指定以便服务重启后沿用会场码）。"""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session_id = session_id or self._new_code()
        session = LiveSession(
            session_id=session_id,
            show_id=show_id,
            title=title,
            host_name=host_name,
            target_langs=target_langs or ["en"],
        )
        self._sessions[session_id] = session
        logger.info("场次开播 %s「%s」目标语言=%s", session_id, title, session.target_langs)
        return session

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if code not in self._sessions:
                return code

    def get(self, session_id: str) -> LiveSession | None:
        return self._sessions.get((session_id or "").strip().upper())

    def get_by_show(self, show_id: int) -> LiveSession | None:
        for session in self._sessions.values():
            if session.show_id == show_id:
                return session
        return None

    def drop_session(self, session: LiveSession) -> None:
        """收播后从注册表移除（观众重连同会场码将得到 4403 已结束）。"""
        self._sessions.pop(session.session_id, None)

    async def end_session(self, session: LiveSession) -> None:
        """收播：广播结束通知、断开观众、移除注册。"""
        if session.status == STATUS_ENDED:
            return
        session.status = STATUS_ENDED
        await self.stop_broadcast(session)
        logger.info("场次收播 %s「%s」共 %s 条字幕", session.session_id, session.title, session.seq)
        await self._broadcast(session, {"type": MSG_SESSION_END, "title": session.title})
        for ws in list(session.listeners):
            try:
                await ws.close()
            except Exception:  # noqa: BLE001 - 关闭失败由各自循环兜底
                pass
        session.listeners.clear()
        session.audio_subscribers.clear()
        self.drop_session(session)

    # ── 观众连接注册 ────────────────────────────────────────────

    def add_listener(self, session: LiveSession, ws, want_audio: bool) -> None:
        session.listeners.add(ws)
        if want_audio:
            session.audio_subscribers.add(ws)
        asyncio.ensure_future(self._broadcast_listeners(session))

    def remove_listener(self, session: LiveSession, ws) -> None:
        session.listeners.discard(ws)
        session.audio_subscribers.discard(ws)
        if session.status == STATUS_LIVE:
            asyncio.ensure_future(self._broadcast_listeners(session))

    async def applaud(self, session: LiveSession) -> None:
        """观众叫好：全场累计并广播（0.8s 合并节流，连点只加密数不刷屏）。"""
        session.applaud_count += 1
        now = time.time()
        if now - session.applaud_at < 0.8:
            return
        session.applaud_at = now
        await self._broadcast(session, {"type": MSG_APPLAUD, "total": session.applaud_count})

    async def _broadcast_listeners(self, session: LiveSession) -> None:
        """在线人数变化通知全部观众。"""
        await self._broadcast(session, {"type": MSG_LISTENERS, "count": session.listener_count})

    async def _broadcast(self, session: LiveSession, message: dict) -> None:
        """向全部观众推送 JSON 文本；发送失败的连接即时剔除。"""
        dead = []
        for ws in list(session.listeners):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - 任何发送异常都视为连接失效
                dead.append(ws)
        for ws in dead:
            session.listeners.discard(ws)
            session.audio_subscribers.discard(ws)

    async def _broadcast_audio(self, session: LiveSession, pcm: bytes) -> None:
        """向订阅原声的观众转发 PCM 二进制帧；失败连接即时剔除。"""
        dead = []
        for ws in list(session.audio_subscribers):
            try:
                await ws.send_bytes(pcm)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            session.listeners.discard(ws)
            session.audio_subscribers.discard(ws)

    # ── 预录音频推流（管理端临时通知 / 备用音源）─────────────────

    BROADCAST_BLOCK_SAMPLES = 3200  # 每块 0.2s（16kHz × 0.2s）
    BROADCAST_BLOCK_INTERVAL = 0.2  # 实时速率节流（观众端按接收顺序排队播放）

    async def start_broadcast(self, session: LiveSession, pcm: bytes, notice: str | None = None) -> str:
        """向直播中场次推流一段预录音频（替代现场收音）。

        - 音频走原声通道（复用 audio=1 的观众订阅，观众端零改动）
        - 可选通知文案走字幕通道（进入翻译与历史缓存，中途加入观众可见）
        - 推流期间 process_audio 丢弃现场采集（避免声音重叠与误识别），推完自动恢复
        - 重复推流返回 conflict，需先停止当前推流
        """
        if session.status != STATUS_LIVE:
            return "not_live"
        if session.broadcast_task and not session.broadcast_task.done():
            return "conflict"
        if notice:
            await self._emit_caption(session, notice)
        session.broadcast_task = asyncio.ensure_future(self._run_broadcast(session, pcm))
        logger.info("预录音频推流开始（场次 %s，%.1fs）", session.session_id, len(pcm) / 32000)
        return "started"

    async def stop_broadcast(self, session: LiveSession) -> bool:
        """中止进行中的预录音频推流（现场收音即刻恢复）。"""
        task = session.broadcast_task
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - 取消后的清理异常不应外溢
            pass
        return True

    async def _run_broadcast(self, session: LiveSession, pcm: bytes) -> None:
        """按实时速率把预录 PCM 分块推给订阅原声的观众。"""
        try:
            step = self.BROADCAST_BLOCK_SAMPLES * 2  # PCM16 → 字节数
            for i in range(0, len(pcm), step):
                if session.status != STATUS_LIVE:
                    return
                await self._broadcast_audio(session, pcm[i:i + step])
                await asyncio.sleep(self.BROADCAST_BLOCK_INTERVAL)
        except asyncio.CancelledError:
            logger.info("预录音频推流被中止（场次 %s）", session.session_id)
            raise
        except Exception:  # noqa: BLE001 - 推流失败不应拖垮会话
            logger.exception("预录音频推流异常（场次 %s）", session.session_id)

    # ── 字幕生产管线 ────────────────────────────────────────────

    async def process_audio(self, session: LiveSession, pcm: bytes) -> None:
        """处理采集器一块 PCM：先转发原声，再识别断句、翻译、广播字幕。

        ASR 与翻译均为同步阻塞调用（本地推理 / 外部 HTTP），统一丢入线程池，
        避免长时间占用事件循环饿死其他场次与心跳。
        """
        if session.status != STATUS_LIVE or not pcm:
            return
        # 预录音频推流期间现场收音让位（观众只听推流音频，也不误识别）
        if session.broadcast_task and not session.broadcast_task.done():
            return
        # 原声转发与识别互不阻塞
        await self._broadcast_audio(session, pcm)
        try:
            result = await asyncio.to_thread(session.engine.feed, pcm, False)
        except Exception:  # noqa: BLE001 - 引擎异常不应中断收音链路
            logger.exception("ASR 识别异常（场次 %s）", session.session_id)
            return
        for sentence in result.finals:
            await self._emit_caption(session, sentence)

    async def _emit_caption(self, session: LiveSession, text: str) -> None:
        """把一句中文原文翻译成全部目标语言并广播为一条字幕。

        翻译优先级：经典唱段韵译（glossary）> 机翻 + 术语规范化（glossary）；
        术语库任何异常静默降级为纯机翻，绝不中断字幕管线。
        """
        translations = {}
        if session.target_langs:
            results = await asyncio.gather(
                *(asyncio.to_thread(self._translate_one, text, lang) for lang in session.target_langs)
            )
            translations = dict(zip(session.target_langs, results))

        session.seq += 1
        caption = {
            "type": MSG_CAPTION,
            "seq": session.seq,
            "text": text,
            "translations": translations,
            "ts": time.time(),
        }
        session.history.append(caption)
        await self._broadcast(session, caption)
        logger.debug("字幕 #%s [%s] %s", session.seq, session.session_id, text)

        # 绝技看点：ASR 句命中术语且冷却期满时推送（失败静默，不影响字幕）
        try:
            term = self._pick_highlight_term(session, text)
            if term:
                await self._emit_highlight(session, term)
        except Exception:  # noqa: BLE001 - 看点推送是增值功能，绝不反噬字幕链路
            logger.exception("看点推送失败（场次 %s）", session.session_id)

    @staticmethod
    def _translate_one(text: str, lang: str) -> str:
        """单句单语言翻译：委托共享管线（韵译优先 > 机翻 + 术语规范化）。"""
        from app.services.translate_pipeline import _translate_one_sync

        return _translate_one_sync(text, lang)

    def _pick_highlight_term(self, session: LiveSession, text: str) -> str | None:
        """选出应推送看点的术语：句中命中且过冷却期，取第一个。"""
        now = time.time()
        for term in glossary.match_terms(text):
            if term not in glossary.TERM_INFO:
                continue
            if now - session.highlights_at.get(term, 0.0) >= glossary.HIGHLIGHT_COOLDOWN:
                session.highlights_at[term] = now
                return term
        return None

    async def _emit_highlight(self, session: LiveSession, term: str) -> None:
        """广播看点提示：绝技解说卡片（不进历史缓存，过期看点无需补发）。"""
        info = glossary.TERM_INFO[term]
        message = {
            "type": MSG_HIGHLIGHT,
            "term": term,
            "text": info.get("zh", term),
            "translations": {lang: info[lang] for lang in session.target_langs if lang in info},
            "ts": time.time(),
        }
        await self._broadcast(session, message)
        logger.info("看点推送 [%s] %s", session.session_id, term)

    def recent_captions(self, session: LiveSession, limit: int | None = None) -> list[dict]:
        """返回最近字幕（观众中途加入时补发，避免错过上下文）。"""
        items = list(session.history)
        return items[-limit:] if limit else items


live_hub = LiveHub()
