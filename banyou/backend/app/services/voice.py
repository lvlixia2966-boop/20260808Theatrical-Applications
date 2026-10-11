"""耳机语音沟通的语音链：豆包 ASR 单发识别 + 豆包 HTTP TTS（移植自主项目）。

配置（backend/.env，缺省未配置 → 前端自动降级浏览器语音/文字）：
  DOUBAO_SPEECH_APP_ID / DOUBAO_SPEECH_ACCESS_TOKEN
"""

import base64
import json
import logging
import time
import uuid

import httpx
import websocket
from websocket import WebSocketTimeoutException

from app.config import settings
from app.services import doubao_protocol as protocol

logger = logging.getLogger("doubao.voice")

_TTS_CLUSTER = "volcano_tts"
_CHUNK_BYTES = 3200        # 0.1s @16kHz PCM16
_FINAL_WAIT = 4.0          # 单发识别等待最终结果（秒）


def speech_configured() -> bool:
    return bool(settings.doubao_speech_app_id and settings.doubao_speech_access_token)


def asr_ready() -> bool:
    return speech_configured()


def tts_ready() -> bool:
    return speech_configured()


# ── ASR：整段音频一次识别 ─────────────────────────────────────────

def decode_to_pcm16k(data: bytes) -> bytes:
    """浏览器录音（webm/opus 等）→ PCM16LE/单声道/16kHz。需 av（随 aiortc 安装）。"""
    import io

    import av

    container = av.open(io.BytesIO(data))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    out = bytearray()
    for frame in container.decode(audio=0):
        for rf in resampler.resample(frame):
            out += rf.to_ndarray().tobytes()
    return bytes(out)


def asr_recognize(audio: bytes, uid: str = "banyou-companion") -> str:
    """识别一整段录音，返回文本；失败返回空串（调用方提示重试/改文字）。"""
    pcm = decode_to_pcm16k(audio)
    if not pcm:
        return ""
    ws = None
    accumulated = ""
    box = _Box()
    try:
        ws = websocket.create_connection(
            settings.doubao_asr_url,
            header=protocol.build_headers(),
            timeout=5.0,
        )
        ws.send_binary(protocol.full_client_request({
            "user": {"uid": uid},
            "audio": {"format": "pcm", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
            "request": {"model_name": "bigmodel", "enable_punc": True,
                        "enable_itn": False, "result_type": "full"},
        }))
        seq = 0
        offset = 0
        while offset < len(pcm):
            chunk = pcm[offset:offset + _CHUNK_BYTES]
            offset += _CHUNK_BYTES
            seq += 1
            is_final = offset >= len(pcm)
            ws.send_binary(protocol.audio_request(chunk, seq if not is_final else -seq))
            if not is_final:
                _drain(ws, 0, box)
                accumulated = box.text or accumulated
        _drain(ws, _FINAL_WAIT, box)
        accumulated = box.text or accumulated
        return accumulated.strip()
    except Exception:  # noqa: BLE001 - 失败由调用方降级
        logger.exception("豆包单发识别异常")
        return accumulated.strip()
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass


class _Box:
    """drain 过程中携带累积文本的小容器。"""

    def __init__(self) -> None:
        self.text = ""


def _extract_text(payload: dict) -> str:
    result = payload.get("result") or {}
    text = result.get("text") or ""
    if text:
        return text
    return "".join(u.get("text", "") for u in result.get("utterances") or [])


def _drain(ws: websocket.WebSocket, final_wait: float, box: _Box) -> None:
    try:
        ws.settimeout(final_wait if final_wait else 0.005)
    except Exception:  # noqa: BLE001
        return
    while True:
        try:
            frame = ws.recv()
        except WebSocketTimeoutException:
            return
        except Exception:  # noqa: BLE001
            return
        parsed = protocol.parse_response(frame if isinstance(frame, bytes) else frame.encode())
        if parsed["type"] == "json":
            box.text = _extract_text(parsed["payload"]) or box.text
            result = parsed["payload"].get("result") or {}
            if final_wait and (result.get("is_end") or parsed["payload"].get("is_final")):
                return
        elif parsed["type"] == "error":
            logger.warning("豆包 ASR 服务端错误：%s", parsed.get("message"))
            return


# ── TTS：HTTP 整段合成（返回 MP3，浏览器 Audio 播放自动走已连接耳机） ──

def tts_speak(text: str, lang_code: str = "zh-CN", rate: float = 1.0) -> bytes:
    text = (text or "").strip()
    if not text:
        return b""
    body = {
        "app": {
            "appid": settings.doubao_speech_app_id,
            "token": "access_token",
            "cluster": _TTS_CLUSTER,
        },
        "user": {"uid": "banyou-companion"},
        "audio": {
            "voice_type": settings.doubao_tts_default_voice,
            "encoding": "mp3",
            "speed_ratio": max(0.2, min(3.0, rate)),
        },
        "request": {
            "reqid": uuid.uuid4().hex,
            "text": text,
            "text_type": "plain",
            "operation": "query",
        },
    }
    headers = {
        "Authorization": f"Bearer; {settings.doubao_speech_access_token}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(settings.doubao_tts_http_url, json=body, headers=headers, timeout=30.0)
    if resp.status_code != 200:
        raise RuntimeError(f"豆包 TTS HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if data.get("code") != 3000 or not data.get("data"):
        raise RuntimeError(f"豆包 TTS 失败: code={data.get('code')} message={data.get('message')}")
    return base64.b64decode(data["data"])
