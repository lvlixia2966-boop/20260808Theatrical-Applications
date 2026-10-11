"""豆包语音单发识别：整段音频一次识别（Agent 语音问答等非流式场景）。

高内聚：压缩音频解码 → 开连接 → 分块喂音频 → 负序号收尾 → 等最终文本 → 关连接，
       全流程在此；调用方只需 decode_to_pcm16k(bytes) 与 recognize(pcm) -> str。
低耦合：复用 asr_stream 的连接与会话配置、protocol 的字节协议。
"""

import io
import logging
import time

import av

from app.services.doubao.asr_stream import DoubaoAsrConnection

logger = logging.getLogger("doubao.asr")

# 整段音频分块大小：0.1s @16kHz PCM16（3200 字节）
_CHUNK_BYTES = 3200
_FINAL_TIMEOUT = 10.0  # 等最终结果的超时（秒）


def decode_to_pcm16k(data: bytes) -> bytes:
    """把浏览器录音（webm/opus 或 mp4/aac）解码为 PCM16LE/单声道/16kHz。

    依 av（aiortc 附带依赖）重采样；解码失败抛异常由调用方降级处理。
    """
    container = av.open(io.BytesIO(data))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    out = bytearray()
    for frame in container.decode(audio=0):
        for rf in resampler.resample(frame):
            out += rf.to_ndarray().tobytes()
    return bytes(out)


def recognize(pcm: bytes, uid: str = "chuan-agent") -> str:
    """识别一整段 PCM16/16kHz/单声道音频，返回完整文本。失败返回空串。"""
    if not pcm:
        return ""
    conn = DoubaoAsrConnection(uid=uid)
    start = time.monotonic()
    try:
        offset = 0
        while offset + _CHUNK_BYTES < len(pcm):
            conn.send_audio(pcm[offset:offset + _CHUNK_BYTES], is_final=False)
            offset += _CHUNK_BYTES
        # 最后一块（含不足一块的剩余）以 is_final 收尾，等待最终结果
        return conn.send_audio(pcm[offset:], is_final=True).strip()
    except Exception:  # noqa: BLE001 - 识别失败由调用方降级处理
        logger.exception("豆包单发识别异常")
        return ""
    finally:
        conn.close()
        logger.debug("单发识别耗时 %dms / %.1fs 音频", int((time.monotonic() - start) * 1000), len(pcm) / 32000)
