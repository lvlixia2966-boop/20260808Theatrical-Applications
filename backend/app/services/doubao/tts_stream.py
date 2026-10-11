"""豆包单向流式 TTS（unidirectional stream）：文本 → 增量 PCM，低延迟播放用。

高内聚：流式合成连接（建立/请求/收音频块/结束）收敛在此。
低耦合：调用方（RTC 管线）只面向 async 迭代 PCM 块；字节协议见 protocol.py。

音频格式约定：PCM16 单声道，采样率默认 24000（可配），由调用方按需重采样。
"""

import json
import logging
from typing import AsyncIterator

import websockets

from app.config import settings
from app.services.doubao import protocol
from app.services.doubao.asr_stream import speech_configured

logger = logging.getLogger("doubao.tts")


def resolve_voice(lang_code: str, voice: str = "") -> str:
    """解析豆包音色 ID：显式指定 > 语言覆盖配置 > 语言注册表 > 中文默认。"""
    if voice:
        return voice
    overrides = settings.doubao_tts_voice_overrides or {}
    if lang_code in overrides:
        return overrides[lang_code]
    from app.core.voices import default_voice

    return default_voice(lang_code) or settings.doubao_tts_default_voice


async def stream(text: str, lang_code: str = "zh-CN", voice: str = "", sample_rate: int = 24000) -> AsyncIterator[bytes]:
    """流式合成一段文本，按到达顺序产出 PCM 字节块。

    每次调用建立一条独立连接（合成请求即会话）；异常时静默结束（调用方有整段 TTS 兜底）。
    """
    if not speech_configured() or not (text or "").strip():
        return
    headers = protocol.build_headers()
    headers["X-Api-Resource-Id"] = settings.doubao_tts_resource_id
    request = {
        "user": {"uid": "chuan-guide"},
        "req_params": {
            "text": text.strip(),
            "speaker": resolve_voice(lang_code, voice),
            "audio_params": {"format": "pcm", "sample_rate": sample_rate, "speech_rate": 0},
            "addons": {"disable_markdown_filter": True},
        },
    }
    try:
        async with websockets.connect(
            settings.doubao_tts_stream_url, additional_headers=headers, open_timeout=5.0
        ) as ws:
            await ws.send(protocol.full_client_request(request))
            async for raw in ws:
                parsed = protocol.parse_response(raw)
                if parsed["type"] == "audio" and parsed.get("payload"):
                    yield parsed["payload"]
                    if parsed.get("last"):
                        break
                elif parsed["type"] == "error":
                    logger.warning("豆包流式 TTS 服务端错误：%s", parsed.get("message"))
                    return
                elif parsed["type"] == "json":
                    payload = parsed.get("payload") or {}
                    if isinstance(payload, dict) and payload.get("event") in ("finished", "fin"):
                        break
    except Exception as exc:  # noqa: BLE001 - 流式失败由调用方兜底（整段 TTS / 纯字幕）
        logger.warning("豆包流式 TTS 异常：%s", exc)


def request_preview(request: dict) -> str:
    """调试辅助：返回请求体 JSON（admin 联调用）。"""
    return json.dumps(request, ensure_ascii=False)
