# -*- coding: utf-8 -*-
"""豆包化改造·连通性自检工具（报价单 #23 部署交付项）。

在 backend 目录下运行（自动加载 .env）：
    python tools\\check_connectivity.py

逐项验证：
  1. 数据库连通（SQLAlchemy select 1）
  2. 方舟 LLM（chat 一次极短请求）
  3. 方舟向量（embed 一条文本，知识库 RAG 依赖）
  4. 豆包流式 TTS（合成一句短文本，确认有 PCM 产出）
  5. 豆包流式 ASR（喂 1 秒正弦波 PCM，确认链路握手与返回）
  6. WebRTC 依赖（aiortc 可导入 + rtc_enabled）

输出逐项 PASS/FAIL 与耗时；任何 FAIL 退出码为 1，可直接用于部署后 CI 式自检。
服务器容器内亦可运行：docker exec chuan-guide python tools/check_connectivity.py
"""
import asyncio
import math
import struct
import sys
import time
import traceback

sys.path.insert(0, ".")

CHECKS = []


def check(name: str):
    """注册一项自检的装饰器。"""

    def deco(fn):
        CHECKS.append((name, fn))
        return fn

    return deco


def pcm_sine(seconds: float = 1.0, freq: int = 440, rate: int = 16000) -> bytes:
    """生成一段 PCM16/单声道/16kHz 正弦波，供 ASR 链路测试。"""
    frames = int(seconds * rate)
    return b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(frames)
    )


@check("数据库连通")
def check_db() -> str:
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return "OK"
    finally:
        db.close()


@check("方舟 LLM（Agent/翻译/编排）")
async def check_ark_llm() -> str:
    from app.services.doubao.ark_client import ark_client

    if not ark_client.is_configured():
        return "SKIP：未配置 ARK_API_KEY"
    text = await ark_client.chat([{"role": "user", "content": "回复OK两个字"}], temperature=0)
    return f"回复：{text[:20]}"


@check("方舟向量（知识库 RAG）")
async def check_ark_embed() -> str:
    from app.services.doubao.ark_client import ark_client

    if not ark_client.is_configured():
        return "SKIP：未配置 ARK_API_KEY"
    vec = (await ark_client.embed(["连通性自检"]))[0]
    return f"维度 {len(vec)}"


@check("豆包流式 TTS")
async def check_doubao_tts() -> str:
    from app.services.doubao.asr_stream import speech_configured
    from app.services.doubao import tts_stream

    if not speech_configured():
        return "SKIP：未配置豆包语音凭据"
    total = 0
    async for chunk in tts_stream.stream("您好，欢迎来到川蜀大剧院。", "zh-CN"):
        total += len(chunk)
        if total > 9600:  # 0.2s @24kHz PCM16 即可证明链路通
            break
    if total == 0:
        raise RuntimeError("未收到任何音频块")
    return f"收到 PCM {total} 字节"


@check("豆包流式 ASR")
async def check_doubao_asr() -> str:
    from app.services.doubao import asr_oneshot
    from app.services.doubao.asr_stream import speech_configured

    if not speech_configured():
        return "SKIP：未配置豆包语音凭据"
    # 正弦波非人声，识别结果通常为空；能走完协议握手并拿到最终事件即算通过
    asr_oneshot.recognize(pcm_sine(1.0))
    return "链路握手/收尾正常"


@check("WebRTC 依赖（aiortc）")
def check_rtc() -> str:
    from app.config import settings

    import aiortc  # noqa: F401

    return f"rtc_enabled={settings.rtc_enabled}, 最大并发 {settings.rtc_max_sessions}"


async def main() -> int:
    print("=" * 56)
    print("豆包化改造 · 连通性自检")
    print("=" * 56)
    failed = 0
    for name, fn in CHECKS:
        start = time.monotonic()
        try:
            result = fn() if not asyncio.iscoroutinefunction(fn) else await fn()
            status = "PASS" if not result.startswith("SKIP") else "SKIP"
        except Exception as exc:  # noqa: BLE001 - 自检要捕获全部异常并报告
            result = f"{exc.__class__.__name__}: {exc}"
            status = "FAIL"
            failed += 1
            traceback.print_exc(limit=1)
        print(f"[{status}] {name}（{time.monotonic() - start:.1f}s）→ {result}")
    print("=" * 56)
    print("结论：全部通过" if failed == 0 else f"结论：{failed} 项失败，请检查凭据与网络")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
