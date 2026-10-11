"""场次调度器：预设场次到点自动开播 / 到时自动收播，全程无人值守。

高内聚：场次状态机（scheduled → live → ended）、定时巡检、服务重启恢复、
       采集任务的启停统一收敛在此模块。
低耦合：排期数据来自 LiveShow 模型（DB），运行时会话委托 live_hub，
       采集委托 audio_capture.CaptureWorker，三者互不感知实现细节。

巡检规则（每 tick 秒执行一次）：
  - scheduled 且 start_at <= now            → 开播（若已超时超过收播宽限，直接标 ended）
  - live 且 now >= start_at + duration_min   → 收播
  - live 但内存无运行时会话（服务重启后）     → 未到收播时间则重建会话并续采，否则收播
手动控制：管理端可对 scheduled 场次立即开播（start_now）、对 live 场次立即收播（stop_now）。
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import LiveShow
from app.services.audio_capture import CaptureWorker
from app.services.live_hub import LiveHub, live_hub

logger = logging.getLogger("scheduler")

STATUS_SCHEDULED = "scheduled"
STATUS_LIVE = "live"
STATUS_ENDED = "ended"

# 迟到宽限：超过收播时间仍处 scheduled 的场次视为错过，直接结束（如停机错过整场）
_LATE_GRACE_MIN = 5


def _parse_langs(raw: str) -> list[str]:
    try:
        langs = json.loads(raw) if raw else []
        return langs if isinstance(langs, list) else ["en"]
    except (ValueError, TypeError):
        return ["en"]


class ShowScheduler:
    """场次状态机与巡检循环（进程内单例，随应用启停）。"""

    def __init__(self, hub: LiveHub = None):
        self._hub = hub or live_hub
        self._workers: dict[int, CaptureWorker] = {}  # show_id → 采集任务
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # ── 应用生命周期挂载 ────────────────────────────────────────

    def start(self) -> None:
        """应用 startup 时启动巡检循环。"""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("场次调度器已启动")

    async def stop(self) -> None:
        """应用 shutdown 时收尾：停巡检、停采集、断观众。"""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            self._task = None
        for show_id in list(self._workers):
            await self._teardown_worker(show_id)

    async def _run_loop(self) -> None:
        from app.config import settings

        tick = settings.live_tick_seconds
        while not self._stop_event.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - 单次巡检异常不应终止调度
                logger.exception("场次巡检异常")
            await asyncio.sleep(tick)

    # ── 状态机巡检 ──────────────────────────────────────────────

    async def tick(self) -> None:
        """单次巡检：驱动所有场次的状态迁移。"""
        db: Session = SessionLocal()
        try:
            now = datetime.now()
            shows = db.query(LiveShow).filter(
                LiveShow.status.in_([STATUS_SCHEDULED, STATUS_LIVE])
            ).all()
            for show in shows:
                end_at = show.start_at + timedelta(minutes=show.duration_min)
                if show.status == STATUS_SCHEDULED and now >= show.start_at:
                    if now >= end_at + timedelta(minutes=_LATE_GRACE_MIN):
                        # 停机错过整场：直接标记结束，不再开播
                        show.status = STATUS_ENDED
                        db.commit()
                        logger.info("场次 #%s「%s」已错过排期，标记结束", show.id, show.title)
                    else:
                        await self._start_show(db, show)
                elif show.status == STATUS_LIVE:
                    if now >= end_at:
                        await self._end_show(db, show)
                    elif self._hub.get_by_show(show.id) is None:
                        # 服务重启后恢复：重建运行时会话并续采（会场码沿用）
                        logger.info("场次 #%s「%s」检测到运行时缺失，恢复直播", show.id, show.title)
                        await self._start_show(db, show, reuse_code=True)
        finally:
            db.close()

    # ── 开播 / 收播 ─────────────────────────────────────────────

    async def _start_show(self, db: Session, show: LiveShow, reuse_code: bool = False) -> None:
        """开播：建运行时会话、启采集、落库状态与会场码。"""
        session = self._hub.create_session(
            show_id=show.id,
            title=show.title,
            host_name=show.host_name,
            target_langs=_parse_langs(show.target_langs),
            session_id=show.session_code if reuse_code and show.session_code else None,
        )
        worker = CaptureWorker(lambda pcm: self._hub.process_audio(session, pcm))
        try:
            worker.start()
        except Exception:  # noqa: BLE001 - 采集启动失败按场次收播处理
            logger.exception("场次 #%s 采集启动失败，收播处理", show.id)
            await self._hub.end_session(session)
            show.status = STATUS_ENDED
            db.commit()
            return
        self._workers[show.id] = worker
        show.status = STATUS_LIVE
        show.session_code = session.session_id
        db.commit()
        logger.info("场次 #%s「%s」已自动开播（会场码 %s）", show.id, show.title, session.session_id)

    async def _end_show(self, db: Session, show: LiveShow) -> None:
        """收播：停采集、通知观众、落库。"""
        await self._teardown_worker(show.id)
        session = self._hub.get_by_show(show.id)
        if session is not None:
            await self._hub.end_session(session)
        show.status = STATUS_ENDED
        db.commit()
        logger.info("场次 #%s「%s」已自动收播", show.id, show.title)

    async def _teardown_worker(self, show_id: int) -> None:
        """停止场次采集任务（采集器线程内 stop，事件循环安全）。"""
        worker = self._workers.pop(show_id, None)
        if worker is not None:
            await asyncio.to_thread(worker.stop)

    # ── 管理端手动控制 ──────────────────────────────────────────

    async def start_now(self, show_id: int) -> LiveShow | None:
        """立即开播（scheduled 场次提前开播，开始时间对齐当前时刻）。"""
        db: Session = SessionLocal()
        try:
            show = db.get(LiveShow, show_id)
            if show is None or show.status != STATUS_SCHEDULED:
                return None
            show.start_at = datetime.now()
            await self._start_show(db, show)
            db.refresh(show)
            return show
        finally:
            db.close()

    async def stop_now(self, show_id: int) -> LiveShow | None:
        """立即收播（live 场次提前结束）。"""
        db: Session = SessionLocal()
        try:
            show = db.get(LiveShow, show_id)
            if show is None or show.status != STATUS_LIVE:
                return None
            await self._end_show(db, show)
            db.refresh(show)
            return show
        finally:
            db.close()


show_scheduler = ShowScheduler()
