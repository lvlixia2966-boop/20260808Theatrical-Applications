"""豆包 openspeech 二进制 WebSocket 协议：帧头构造/解析、鉴权头、gzip 编解码。

高内聚：全部字节布局细节（版本位、消息类型、序列化/压缩位、payload 长度）收敛于此，
其它模块只面向「构造请求 / 解析响应」的语义层。
低耦合：纯函数、无 IO、无状态；asr_stream / tts_stream 均只依赖本模块。

协议要点（大模型流式语音识别 / 单向流式 TTS 通用）：
  - 帧头固定 4 字节：
      byte0 = (protocol_version << 4) | header_size        # 0x11
      byte1 = (message_type << 4) | message_type_flags     # 类型与标志（含序列号语义）
      byte2 = (serialization << 4) | compression           # json=0b0001 / gzip=0b0001
      byte3 = reserved                                     # 0x00
  - 帧头后可跟 4 字节 payload 长度（大端）+ payload
  - 音频帧带正序号、最后一包用负序号（flags 区分）
"""

import gzip
import json
import struct

# ===== 协议常量 =====
PROTOCOL_VERSION = 0b0001
HEADER_SIZE = 0b0001

# 客户端消息类型
FULL_CLIENT_REQUEST = 0b0001   # 首包：会话配置（JSON payload）
AUDIO_ONLY_REQUEST = 0b0010    # 音频帧（payload 为裸音频，可带序号）

# 服务端消息类型
FULL_SERVER_RESPONSE = 0b1001  # 完整 JSON 响应
AUDIO_SERVER_RESPONSE = 0b1011  # 音频块（TTS 流式返回）
ERROR_RESPONSE = 0b1111        # 错误响应

# 序列化 / 压缩方式
SERIALIZATION_JSON = 0b0001
SERIALIZATION_NONE = 0b0000
COMPRESSION_GZIP = 0b0001
COMPRESSION_NONE = 0b0000

# 音频帧 flags：带正序号 / 带负序号（最后一包）
FLAG_POS_SEQ = 0b0001
FLAG_NEG_SEQ = 0b0011  # 负序号 + 结束语义（部分文档亦称 last-no-sequence，此处按带序号收尾）

_JSON = "json"


def build_headers() -> dict[str, str]:
    """openspeech WebSocket 握手鉴权头（appid + access token 双凭据）。"""
    from app.config import settings

    token = settings.doubao_speech_access_token
    return {
        "X-Api-App-Key": settings.doubao_speech_app_id,
        "X-Api-Access-Key": token,
        # 官方样例格式为「Bearer; <token>」（带分号），照抄以保证兼容
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
    """构造首包（会话配置 JSON，gzip 压缩）。"""
    payload = gzip.compress(json.dumps(config).encode("utf-8"))
    return _header(FULL_CLIENT_REQUEST, 0b0000, SERIALIZATION_JSON, COMPRESSION_GZIP) + \
        struct.pack(">I", len(payload)) + payload


def audio_request(pcm: bytes, seq: int) -> bytes:
    """构造音频帧：seq > 0 为普通帧，seq < 0 为最后一包。payload 不压缩。"""
    flags = FLAG_POS_SEQ if seq > 0 else FLAG_NEG_SEQ
    return _header(AUDIO_ONLY_REQUEST, flags, SERIALIZATION_NONE, COMPRESSION_NONE) + \
        struct.pack(">i", seq) + pcm


def parse_response(frame: bytes) -> dict:
    """解析一帧服务端响应。

    返回 {"type": "json"|"audio"|"error", "payload": ...}：
      - json  -> payload 为 dict（识别结果 / 事件确认）
      - audio -> payload 为音频字节
      - error -> payload 为错误码 int 与错误消息 dict/str
    未知类型按无有效载荷忽略（返回 {"type": "none"}），保持前向兼容。
    """
    if len(frame) < 4:
        return {"type": "none"}
    message_type = frame[1] >> 4
    flags = frame[1] & 0x0F
    serialization = frame[2] >> 4
    compression = frame[2] & 0x0F

    offset = 4
    # 序列号语义：flags 带序号时先读 4 字节 int32
    if message_type == AUDIO_ONLY_REQUEST and flags in (FLAG_POS_SEQ, 0b0010, FLAG_NEG_SEQ):
        offset += 4

    payload: bytes = b""
    if len(frame) > offset + 4 and message_type not in (AUDIO_ONLY_REQUEST,):
        # JSON / 音频响应帧带 payload 长度前缀
        (size,) = struct.unpack(">I", frame[offset:offset + 4])
        offset += 4
        payload = frame[offset:offset + size]
    elif len(frame) > offset and message_type in (AUDIO_ONLY_REQUEST,):
        payload = frame[offset:]

    if message_type == ERROR_RESPONSE:
        detail: object
        try:
            detail = json.loads(_maybe_gunzip(payload, compression))
        except Exception:  # noqa: BLE001 - 错误消息解析失败时原样透传
            detail = payload.decode("utf-8", errors="replace")
        return {"type": "error", "code": flags, "message": detail}

    if message_type == AUDIO_SERVER_RESPONSE:
        return {"type": "audio", "payload": _maybe_gunzip(payload, compression), "last": bool(flags & 0b0010)}

    if message_type in (FULL_SERVER_RESPONSE,):
        data = _maybe_gunzip(payload, compression)
        try:
            parsed = json.loads(data)
        except Exception:  # noqa: BLE001
            parsed = {"raw": data.decode("utf-8", errors="replace")}
        if serialization != SERIALIZATION_JSON and _JSON not in str(serialization):
            pass
        return {"type": "json", "payload": parsed}

    return {"type": "none"}


def _maybe_gunzip(payload: bytes, compression: int) -> bytes:
    if compression == COMPRESSION_GZIP and payload[:2] == b"\x1f\x8b":
        return gzip.decompress(payload)
    return payload
