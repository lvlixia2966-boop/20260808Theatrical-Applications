"""豆包大模型流式语音识别（bigmodel ASR）连接管理。

高内聚：单条 WS 连接的生命周期（建立/喂音频/拉取结果/轮换/关闭）收敛在此。
低耦合：asr_service.DoubaoAsrEngine 只面向「send_audio + poll_text」语义，
       不感知二进制协议（见 protocol.py）。

与 live_hub feed 轮询模型的适配：
  feed 节奏由调用方驱动（200ms 块），本类每次 send_audio 后非阻塞拉取
  最新识别结果并返回「当前段累积文本」，由 AsrEngine 基类按句末标点断句。
  连接断开时静默标记，下次 send_audio 自动重建（失败重试由轮询节奏天然承担）。
"""

import json
import logging
import time

from websocket import WebSocket, WebSocketTimeoutException, create_connection

from app.config import settings
from app.services.doubao import protocol

logger = logging.getLogger("doubao.asr")

# 连接轮换阈值：超时或空闲过久主动重建，避免长连接被服务端静默掐断
MAX_CONNECTION_SECONDS = 300.0
RECV_DRAIN_TIMEOUT = 0.005  # 非阻塞拉取（每次 feed 最多等 5ms）


def speech_configured() -> bool:
    """豆包语音凭据是否已配置（appid + access token）。"""
    return bool(settings.doubao_speech_app_id and settings.doubao_speech_access_token)


class DoubaoAsrConnection:
    """一条大模型流式 ASR 连接（对应一个识别会话，不可跨会话共享）。"""

    def __init__(self, uid: str = "chuan-guide"):
        self._uid = uid
        self._ws: WebSocket | None = None
        self._seq = 0
        self._accumulated = ""  # 当前段累积文本（豆包自带标点）
        self._connected_at = 0.0
        self._stale = False

    # ── 连接管理 ────────────────────────────────────────────────

    def _ensure_connection(self) -> bool:
        if self._ws is not None and not self._stale:
            return True
        self._close_quietly()
        try:
            self._ws = create_connection(
                settings.doubao_asr_url,
                header=protocol.build_headers(),
                timeout=5.0,
            )
            # 首包：会话配置（PCM16 16kHz 单声道 + 开启标点）
            self._ws.send_binary(protocol.full_client_request({
                "user": {"uid": self._uid},
                "audio": {"format": "pcm", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
                "request": {
                    "model_name": "bigmodel",
                    "enable_punc": True,
                    "enable_itn": False,
                    "result_type": "full",
                },
            }))
            self._seq = 0
            self._accumulated = ""
            self._connected_at = time.monotonic()
            self._stale = False
            return True
        except Exception as exc:  # noqa: BLE001 - 连接失败交由调用方按轮询节奏重试
            logger.warning("豆包 ASR 连接失败：%s", exc)
            self._ws = None
            return False

    def _needs_rotation(self) -> bool:
        return (time.monotonic() - self._connected_at) > MAX_CONNECTION_SECONDS

    # ── 音频收发 ────────────────────────────────────────────────

    def send_audio(self, pcm: bytes, is_final: bool) -> str:
        """发送一块音频并返回当前段累积文本（非阻塞拉取最新结果）。

        is_final=True 时以负序号收尾并等待最终结果（短暂阻塞）。
        """
        if not self._ensure_connection():
            return self._accumulated
        if self._needs_rotation():
            logger.info("豆包 ASR 连接轮换（超过 %.0fs）", MAX_CONNECTION_SECONDS)
            self.reset()
            if not self._ensure_connection():
                return self._accumulated

        self._seq += 1
        seq = self._seq if not is_final else -self._seq
        try:
            self._ws.send_binary(protocol.audio_request(pcm, seq))
        except Exception as exc:  # noqa: BLE001 - 发送失败标记重连，本块结果返回累积值
            logger.warning("豆包 ASR 发送失败：%s", exc)
            self._stale = True
            return self._accumulated

        if is_final:
            self._drain(final_wait=2.0)
            text = self._accumulated
            self.reset()
            return text
        self._drain(final_wait=0)
        return self._accumulated

    def _drain(self, final_wait: float) -> None:
        """非阻塞拉取服务端结果，更新累积文本；final_wait>0 时阻塞等待收尾。"""
        if self._ws is None:
            return
        try:
            self._ws.settimeout(RECV_DRAIN_TIMEOUT if not final_wait else final_wait)
        except Exception:  # noqa: BLE001
            return
        while True:
            try:
                frame = self._ws.recv()
            except WebSocketTimeoutException:
                return
            except Exception as exc:  # noqa: BLE001 - 连接异常标记重连
                logger.warning("豆包 ASR 接收异常：%s", exc)
                self._stale = True
                return
            parsed = protocol.parse_response(frame if isinstance(frame, bytes) else frame.encode())
            if parsed["type"] == "json":
                self._accumulated = self._extract_text(parsed["payload"]) or self._accumulated
                if final_wait and self._is_final_payload(parsed["payload"]):
                    return
            elif parsed["type"] == "error":
                logger.warning("豆包 ASR 服务端错误：%s", parsed.get("message"))
                self._stale = True
                return

    @staticmethod
    def _extract_text(payload: dict) -> str:
        """从响应 JSON 提取累积文本（兼容 result.text 与 utterances 两种形态）。"""
        result = payload.get("result") or {}
        text = result.get("text") or ""
        if text:
            return text
        utterances = result.get("utterances") or []
        return "".join(u.get("text", "") for u in utterances)

    @staticmethod
    def _is_final_payload(payload: dict) -> bool:
        result = payload.get("result") or {}
        return bool(result.get("is_end") or payload.get("is_final"))

    # ── 生命周期 ────────────────────────────────────────────────

    def reset(self) -> None:
        """重置段状态并关闭连接（下次 send_audio 自动重建）。"""
        self._close_quietly()
        self._accumulated = ""
        self._seq = 0

    def close(self) -> None:
        self._close_quietly()

    def _close_quietly(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
