"""WebRTC 实时翻译音频网关：双端 PeerConnection 管理 + Opus↔PCM 转换 + 会话编排。

高内聚：信令处理、媒体轨道收发、ASR 喂入、字幕广播、peer 生命周期统一在此。
低耦合：ASR 走 asr_service 抽象、翻译/记录走 rtc_pipeline、持久化走模型层；
       与 live 域零 import 耦合（仅共享引擎与服务抽象，报价单 #15 独立网关）。

媒体流：
  上行（游客/工作人员麦克风）→ aiortc 解码 Opus → AudioResampler 转 PCM16/16kHz/单声道
    → AsrEngine.feed（线程池）→ 完整句 → rtc_pipeline.process_sentence
  下行（工作人员端听译文）→ 豆包流式 TTS PCM(24k) → 重采样 48k/20ms 帧
    → PcmSourceTrack → aiortc 编码 Opus → 工作人员耳机
"""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field

import av
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp
from aiortc.mediastreams import AudioStreamTrack
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.config import settings
from app.database import SessionLocal
from app.models.rtc import RtcLog, RtcSession
from app.schemas.rtc import (
    DIR_STAFF_TO_VISITOR,
    DIR_VISITOR_TO_STAFF,
    MSG_CAPTION,
    MSG_PING,
    MSG_SESSION_END,
    ROLE_STAFF,
    ROLE_VISITOR,
    SIG_ANSWER,
    SIG_ICE,
    SIG_OFFER,
    SIG_PTT,
)
from app.services import rtc_pipeline
from app.services.asr_service import AsrEngine, create_asr_engine

logger = logging.getLogger("rtc")

# PCM 帧参数
INGEST_RATE = 16000      # ASR 喂入采样率
OUTBOUND_RATE = 48000    # 下行播放采样率（浏览器 Opus 原生）
FRAME_SAMPLES = 960      # 48kHz 下 20ms 帧
USEC_PER_FRAME = 20000   # 20ms


class PcmSourceTrack(AudioStreamTrack):
    """工作人员端出站音频轨：内部队列接收译文 PCM，按 20ms 节奏产帧（48kHz mono s16）。"""

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)
        self._buf = b""
        self._pts = 0
        self._time_base = None
        self._started = time.monotonic()
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=OUTBOUND_RATE)

    async def push_pcm(self, pcm: bytes, src_rate: int = 24000) -> None:
        """接收一路 PCM（豆包流式 TTS 输出），重采样到 48kHz 后入队。"""
        if not pcm:
            return
        if src_rate != OUTBOUND_RATE:
            src = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
            src.sample_rate = src_rate
            src.planes[0].update(pcm)
            pcm = b"".join(_plane_bytes(f) for f in self._resampler.resample(src))
        try:
            self._queue.put_nowait(pcm)
        except asyncio.QueueFull:  # 播不动就丢最旧的，保实时
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(pcm)

    async def recv(self):
        # 等待攒够一帧（20ms = 960 samples = 1920 字节）；队列空闲时输出静音帧维持节奏
        while len(self._buf) < FRAME_SAMPLES * 2:
            if self._queue.empty():
                await asyncio.sleep(0.005)
                if self._queue.empty():
                    return self._make_frame(b"\x00" * (FRAME_SAMPLES * 2))
                continue
            self._buf += self._queue.get_nowait()
        data, self._buf = self._buf[: FRAME_SAMPLES * 2], self._buf[FRAME_SAMPLES * 2:]
        return self._make_frame(data)

    def _make_frame(self, data: bytes):
        frame = av.AudioFrame(format="s16", layout="mono", samples=FRAME_SAMPLES)
        frame.sample_rate = OUTBOUND_RATE
        frame.planes[0].update(data)
        frame.pts = self._pts
        if self._time_base is None:
            from fractions import Fraction

            self._time_base = Fraction(1, OUTBOUND_RATE)
        frame.time_base = self._time_base
        self._pts += FRAME_SAMPLES
        return frame


def _plane_bytes(frame: av.AudioFrame) -> bytes:
    """取音频帧的原始字节（s16 交错排布）。"""
    return frame.to_ndarray().tobytes()


@dataclass
class RtcPeer:
    """一端连接的运行时状态。"""

    role: str
    token: str
    session: RtcSession
    ws: WebSocket
    pc: RTCPeerConnection | None = None
    ingest_task: asyncio.Task | None = None
    outbound: PcmSourceTrack | None = None
    engine: AsrEngine | None = None
    ptt_on: bool = False
    online: bool = True


class RtcGateway:
    """RTC 会话注册表与信令/媒体中枢（进程内单例）。"""

    def __init__(self):
        # code -> {role: RtcPeer}
        self._rooms: dict[str, dict[str, RtcPeer]] = {}

    # ── 会话接入 ────────────────────────────────────────────────

    def resolve_session(self, db, token: str) -> RtcSession | None:
        """token 鉴权：游客/工作人员 token 统一定位会话。"""
        token = (token or "").strip()
        if not token:
            return None
        return (
            db.query(RtcSession)
            .filter((RtcSession.visitor_token == token) | (RtcSession.staff_token == token))
            .first()
        )

    def role_of(self, session: RtcSession, token: str) -> str:
        return ROLE_VISITOR if token == session.visitor_token else ROLE_STAFF

    async def serve_socket(self, ws: WebSocket, token: str) -> None:
        """信令主循环：鉴权 → 注册 → offer/answer 与 ICE 交换 → 断开清理。"""
        db = SessionLocal()
        try:
            session = self.resolve_session(db, token)
        finally:
            db.close()
        if session is None or session.status == "ended":
            await ws.close(code=4403)
            return
        if not settings.rtc_enabled or len(self._rooms) >= settings.rtc_max_sessions:
            await ws.close(code=4404)
            return

        role = self.role_of(session, token)
        peer = RtcPeer(role=role, token=token, session=session, ws=ws)
        room = self._rooms.setdefault(session.code, {})
        # 同 token 顶替旧连接（断线重连）
        old = room.get(role)
        if old is not None:
            await self._detach(old, notify=False)
        room[role] = peer

        await self._broadcast_peer_state(session, "joined", role)
        if all(r in room for r in (ROLE_VISITOR, ROLE_STAFF)) and session.status == "created":
            self._mark_active(session)
        try:
            await self._signaling_loop(peer)
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001 - 信令异常按断线处理
            logger.exception("RTC 信令异常（%s/%s）", session.code, role)
        finally:
            await self._detach(peer, notify=True)

    async def _signaling_loop(self, peer: RtcPeer) -> None:
        while True:
            message = await peer.ws.receive_json()
            mtype = message.get("type")
            if mtype == SIG_OFFER:
                await self._handle_offer(peer, message.get("sdp", ""))
            elif mtype == SIG_ICE:
                await self._handle_ice(peer, message.get("candidate"))
            elif mtype == SIG_PTT:
                await self._handle_ptt(peer, bool(message.get("on")))
            elif mtype == MSG_PING:
                await peer.ws.send_json({"type": MSG_PING, "ts": time.time()})

    # ── WebRTC 协商 ─────────────────────────────────────────────

    async def _handle_offer(self, peer: RtcPeer, sdp: str) -> None:
        pc = RTCPeerConnection(RTCConfiguration(iceServers=settings.rtc_stun_urls))
        peer.pc = pc
        peer.engine = create_asr_engine()  # 每端一路 ASR（会话级状态）
        if peer.role == ROLE_STAFF:
            peer.outbound = PcmSourceTrack()
            pc.addTrack(peer.outbound)

        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                peer.ingest_task = asyncio.ensure_future(self._ingest_loop(peer, track))

        # 说明：aiortc 的 setLocalDescription 完成时 ICE 收集已结束，
        # 服务器候选随 answer SDP 一次性下发；客户端 trickle 候选走 _handle_ice。
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await peer.ws.send_json({"type": SIG_ANSWER, "sdp": pc.localDescription.sdp})

    async def _handle_ice(self, peer: RtcPeer, candidate: dict | None) -> None:
        if peer.pc is None or not candidate:
            return
        try:
            # 浏览器候选 SDP 行形如 "candidate:udp ... typ host"，转 aiortc 候选对象
            sdp_line = (candidate.get("candidate") or "").removeprefix("candidate:")
            rtc_candidate = candidate_from_sdp(sdp_line)
            rtc_candidate.sdpMid = candidate.get("sdpMid")
            rtc_candidate.sdpMLineIndex = candidate.get("sdpMLineIndex")
            await peer.pc.addIceCandidate(rtc_candidate)
        except Exception as exc:  # noqa: BLE001 - 单条候选失败可忽略
            logger.debug("addIceCandidate 失败：%s", exc)

    async def _handle_ptt(self, peer: RtcPeer, on: bool) -> None:
        """按住说话：松开时强制断句收尾（吐出段内剩余），抑制抢话与回声。"""
        was_on = peer.ptt_on
        peer.ptt_on = on
        if was_on and not on and peer.engine is not None:
            result = await asyncio.to_thread(peer.engine.feed, b"", True)
            for sentence in result.finals:
                await self._on_final(peer, sentence)

    # ── 上行音频 → ASR ─────────────────────────────────────────

    async def _ingest_loop(self, peer: RtcPeer, track) -> None:
        """远端音频轨循环：Opus 帧 → PCM16k → 引擎喂入 → 完整句回调。"""
        resampler = av.AudioResampler(format="s16", layout="mono", rate=INGEST_RATE)
        audio_seconds = 0.0
        try:
            while True:
                frame = await track.recv()
                if not peer.ptt_on or peer.engine is None:
                    continue
                pcm = b"".join(_plane_bytes(f) for f in resampler.resample(frame))
                audio_seconds += len(pcm) / 2 / INGEST_RATE
                result = await asyncio.to_thread(peer.engine.feed, pcm, False)
                for sentence in result.finals:
                    await self._on_final(peer, sentence)
        except Exception:  # noqa: BLE001 - 轨道结束（断线）即退出循环
            pass
        finally:
            if audio_seconds > 0:
                from app.services.usage_meter import record as record_usage

                record_usage("asr", round(audio_seconds, 2), session_ref=f"rtc:{peer.session.code}")
            if peer.engine is not None:
                peer.engine.close()

    async def _on_final(self, peer: RtcPeer, text: str) -> None:
        """一个完整句产生：按角色路由方向并进入管线。"""
        text = (text or "").strip()
        if not text:
            return
        direction = DIR_VISITOR_TO_STAFF if peer.role == ROLE_VISITOR else DIR_STAFF_TO_VISITOR
        room = self._rooms.get(peer.session.code, {})

        async def emit_caption(d: str, source: str, translated: str) -> int | None:
            return await self._emit_caption(peer.session, room, d, source, translated)

        async def tts_emit(pcm_stream, lang: str):
            staff_peer = room.get(ROLE_STAFF)
            if staff_peer and staff_peer.outbound is not None:
                async for chunk in pcm_stream:
                    await staff_peer.outbound.push_pcm(chunk)

        try:
            await rtc_pipeline.process_sentence(
                direction=direction,
                source_text=text,
                visitor_lang=peer.session.visitor_lang,
                staff_lang=peer.session.staff_lang,
                session_ref=f"rtc:{peer.session.code}",
                emit_caption=emit_caption,
                tts_emit=tts_emit,
            )
        except Exception:  # noqa: BLE001 - 单句处理失败不中断会话
            logger.exception("RTC 句子处理异常（%s）", peer.session.code)

    # ── 字幕广播与记录 ──────────────────────────────────────────

    async def _emit_caption(
        self, session: RtcSession, room: dict, direction: str, source: str, translated: str
    ) -> int | None:
        """字幕双端广播 + RtcLog 落库；seq 取当前会话记录数（断线补拉按 id>after）。"""
        db = SessionLocal()
        try:
            row = RtcLog(session_id=session.id, direction=direction,
                         source_text=source, translated_text=translated)
            db.add(row)
            db.commit()
            db.refresh(row)
            payload = {
                "type": MSG_CAPTION,
                "seq": row.id,
                "direction": direction,
                "text": source,
                "translated": translated,
                "ts": time.time(),
            }
            for p in list(room.values()):
                await self._send_to(p, payload)
            return row.id
        except Exception:  # noqa: BLE001 - 记录失败仍推送字幕
            logger.exception("RTC 记录落库失败")
            return None
        finally:
            db.close()

    # ── 连接清理与会话状态 ──────────────────────────────────────

    async def _detach(self, peer: RtcPeer, notify: bool) -> None:
        peer.online = False
        room = self._rooms.get(peer.session.code)
        if room and room.get(peer.role) is peer:
            room.pop(peer.role, None)
            if not room:
                self._rooms.pop(peer.session.code, None)
        if peer.ingest_task:
            peer.ingest_task.cancel()
        if peer.pc:
            try:
                await peer.pc.close()
            except Exception:  # noqa: BLE001
                pass
        if peer.engine:
            peer.engine.close()
        if notify:
            await self._broadcast_peer_state(peer.session, "left", peer.role)

    async def _broadcast_peer_state(self, session: RtcSession, state: str, role: str) -> None:
        room = self._rooms.get(session.code, {})
        for p in list(room.values()):
            await self._send_to(p, {"type": "peer_state", "state": state, "role": role})

    async def _send_to(self, peer: RtcPeer, payload: dict) -> None:
        if not peer.online:
            return
        try:
            await peer.ws.send_json(payload)
        except Exception:  # noqa: BLE001 - 发送失败即视为掉线
            peer.online = False

    def _mark_active(self, session: RtcSession) -> None:
        from datetime import datetime

        db = SessionLocal()
        try:
            row = db.get(RtcSession, session.id)
            if row and row.status == "created":
                row.status = "active"
                row.started_at = datetime.now()
                db.commit()
                session.status = row.status
        finally:
            db.close()

    async def end_session(self, session: RtcSession) -> None:
        """管理端结束会话：广播 session_end、断开双端、落库状态。"""
        from datetime import datetime

        room = self._rooms.pop(session.code, None)
        for p in list((room or {}).values()):
            await self._send_to(p, {"type": MSG_SESSION_END, "code": session.code})
            try:
                await p.ws.close()
            except Exception:  # noqa: BLE001
                pass
            await self._detach(p, notify=False)
        db = SessionLocal()
        try:
            row = db.get(RtcSession, session.id)
            if row:
                row.status = "ended"
                row.ended_at = datetime.now()
                db.commit()
        finally:
            db.close()

    def peer_online(self, session: RtcSession, role: str) -> bool:
        peer = self._rooms.get(session.code, {}).get(role)
        return bool(peer and peer.online)

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(16)


rtc_gateway = RtcGateway()
