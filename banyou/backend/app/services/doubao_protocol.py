"""豆包 openspeech 二进制 WebSocket 协议（移植自主项目，原样保留）。

帧头构造/解析、鉴权头、gzip 编解码；大模型流式语音识别 / TTS 通用。
纯函数、无 IO、无状态。
"""

import gzip
import json
import struct

PROTOCOL_VERSION = 0b0001
HEADER_SIZE = 0b0001

FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST = 0b0010
FULL_SERVER_RESPONSE = 0b1001
AUDIO_SERVER_RESPONSE = 0b1011
ERROR_RESPONSE = 0b1111

SERIALIZATION_JSON = 0b0001
SERIALIZATION_NONE = 0b0000
COMPRESSION_GZIP = 0b0001
COMPRESSION_NONE = 0b0000

FLAG_POS_SEQ = 0b0001
FLAG_NEG_SEQ = 0b0011


def build_headers() -> dict[str, str]:
    """openspeech WebSocket 握手鉴权头（appid + access token 双凭据）。"""
    from app.config import settings

    token = settings.doubao_speech_access_token
    return {
        "X-Api-App-Key": settings.doubao_speech_app_id,
        "X-Api-Access-Key": token,
        "Authorization": f"Bearer; {token}",
    }


def _header(message_type: int, flags: int, serialization: int, compression: int) -> bytes:
    return bytes([
        (PROTOCOL_VERSION << 4) | HEADER_SIZE,
        (message_type << 4) | flags,
        (serialization << 4) | compression,
        0x00,
    ])


def full_client_request(config: dict) -> bytes:
    payload = gzip.compress(json.dumps(config).encode("utf-8"))
    return _header(FULL_CLIENT_REQUEST, 0b0000, SERIALIZATION_JSON, COMPRESSION_GZIP) + \
        struct.pack(">I", len(payload)) + payload


def audio_request(pcm: bytes, seq: int) -> bytes:
    flags = FLAG_POS_SEQ if seq > 0 else FLAG_NEG_SEQ
    return _header(AUDIO_ONLY_REQUEST, flags, SERIALIZATION_NONE, COMPRESSION_NONE) + \
        struct.pack(">i", seq) + pcm


def parse_response(frame: bytes) -> dict:
    if len(frame) < 4:
        return {"type": "none"}
    message_type = frame[1] >> 4
    flags = frame[1] & 0x0F
    serialization = frame[2] >> 4
    compression = frame[2] & 0x0F

    offset = 4
    if message_type == AUDIO_ONLY_REQUEST and flags in (FLAG_POS_SEQ, 0b0010, FLAG_NEG_SEQ):
        offset += 4

    payload: bytes = b""
    if len(frame) > offset + 4 and message_type not in (AUDIO_ONLY_REQUEST,):
        (size,) = struct.unpack(">I", frame[offset:offset + 4])
        offset += 4
        payload = frame[offset:offset + size]
    elif len(frame) > offset and message_type in (AUDIO_ONLY_REQUEST,):
        payload = frame[offset:]

    if message_type == ERROR_RESPONSE:
        try:
            detail = json.loads(_maybe_gunzip(payload, compression))
        except Exception:  # noqa: BLE001
            detail = payload.decode("utf-8", errors="replace")
        return {"type": "error", "code": flags, "message": detail}

    if message_type == AUDIO_SERVER_RESPONSE:
        return {"type": "audio", "payload": _maybe_gunzip(payload, compression), "last": bool(flags & 0b0010)}

    if message_type == FULL_SERVER_RESPONSE:
        data = _maybe_gunzip(payload, compression)
        try:
            parsed = json.loads(data)
        except Exception:  # noqa: BLE001
            parsed = {"raw": data.decode("utf-8", errors="replace")}
        return {"type": "json", "payload": parsed}

    return {"type": "none"}


def _maybe_gunzip(payload: bytes, compression: int) -> bytes:
    if compression == COMPRESSION_GZIP and payload[:2] == b"\x1f\x8b":
        return gzip.decompress(payload)
    return payload
