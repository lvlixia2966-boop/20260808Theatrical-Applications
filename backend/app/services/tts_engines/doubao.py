"""豆包 TTS 引擎：openspeech v1 HTTP 合成（整段返回 MP3）。

高内聚：仅负责豆包云 TTS 的请求构造与音频返回。
低耦合：遵循 tts_engines 模块级函数约定（supports / is_configured / synthesize / MIME），
       由 tts_service 引擎链分派；音色解析复用 doubao.tts_stream.resolve_voice。

凭据：openspeech 体系（doubao_speech_app_id + doubao_speech_access_token），
     与方舟（Ark）鉴权相互独立。
"""

import base64
import uuid

import httpx

from app.config import settings
from app.services.doubao.asr_stream import speech_configured
from app.services.doubao.tts_stream import resolve_voice

# 公共音色集群；接入点如有差异经配置覆盖
CLUSTER = "volcano_tts"

# 报价单 12 目标语言 + 中文源语言均已覆盖（音色注册表见 core/voices.py）
MIME = "audio/mpeg"


def is_configured() -> bool:
    """豆包语音凭据是否已配置（未配置时由链上 mock 兜底或直接 503）。"""
    return speech_configured()


def supports(lang_code: str) -> bool:
    """豆包音色注册表覆盖该语言即支持。"""
    from app.core.voices import default_voice

    return bool(default_voice(lang_code)) or lang_code == "zh-CN"


async def synthesize(text: str, lang_code: str, rate: int = 0, voice=None) -> bytes:
    """将文本合成为 MP3 音频字节。

    voice 参数语义沿用引擎链约定（参考人声条目），豆包场景改为显式音色 ID 覆盖。
    """
    text = (text or "").strip()
    if not text:
        return b""
    voice_id = resolve_voice(lang_code, voice if isinstance(voice, str) else "")
    body = {
        "app": {
            "appid": settings.doubao_speech_app_id,
            "token": "access_token",
            "cluster": CLUSTER,
        },
        "user": {"uid": "chuan-guide"},
        "audio": {
            "voice_type": voice_id,
            "encoding": "mp3",
            "speed_ratio": 1.0 + (rate or 0) / 100.0,
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
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(settings.doubao_tts_http_url, json=body, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"豆包 TTS HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
    if data.get("code") != 3000 or not data.get("data"):
        raise RuntimeError(f"豆包 TTS 失败: code={data.get('code')} message={data.get('message')}")
    return base64.b64decode(data["data"])
