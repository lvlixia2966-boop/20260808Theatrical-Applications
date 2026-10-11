"""RTC 翻译管线：两条链路的句子级处理与 TTS 音频合成。

高内聚：链路 A/B 的「翻译 → 记录 → 语音」编排收敛在此。
低耦合：只依赖 translate_pipeline / tts_stream / usage_meter 等服务抽象，
       由 rtc_gateway 持有连接与轨道并回调本模块；不 import live_hub。

链路 A（游客 → 工作人员）：ASR 句 → 翻译为工作人员语言 → 字幕广播+落库 → 流式 TTS 进工作人员耳机
链路 B（工作人员 → 游客）：ASR 句 → 翻译为游客语言 → 字幕广播+落库（报价单口径：仅显示，不合语音）
"""

import io
import logging
from typing import AsyncIterator

from app.services.translate_pipeline import translate_sentence
from app.services.usage_meter import record as record_usage

logger = logging.getLogger("rtc.pipeline")


async def tts_pcm_stream(text: str, lang: str) -> AsyncIterator[bytes]:
    """按语言把一句译文合成为 PCM16 音频块流（24000Hz 单声道）。

    优先豆包单向流式 TTS（低延迟）；凭据未配置或流式失败时静默结束
    （调用方已有纯字幕路径，不阻塞会话）。
    """
    from app.services.doubao import tts_stream, speech_configured

    if not speech_configured():
        return
    try:
        async for chunk in tts_stream.stream(text, lang):
            yield chunk
    except Exception:  # noqa: BLE001 - 流式失败不阻塞字幕链路
        logger.warning("流式 TTS 失败，本次仅字幕：%.30s…", text)


async def process_sentence(
    *,
    direction: str,
    source_text: str,
    visitor_lang: str,
    staff_lang: str,
    session_ref: str,
    emit_caption,           # async (direction, source, translated, seq) -> int/None
    tts_emit=None,          # async (pcm_stream, lang) -> None（仅链路 A，由网关注入）
) -> None:
    """处理一个 ASR 完整句：翻译 → 字幕广播+记录 → （链路 A）语音合成。"""
    target_lang = staff_lang if direction == "visitor->staff" else visitor_lang
    translated = await translate_sentence(source_text, target_lang)
    record_usage("translate", len(source_text), session_ref=session_ref)

    seq = await emit_caption(direction, source_text, translated)
    if seq is None:
        return

    # 链路 A：工作人员耳机听译文语音；链路 B：游客端仅显示字幕（报价单关键链路口径）
    if direction == "visitor->staff" and tts_emit is not None:
        record_usage("tts", len(translated), session_ref=session_ref)
        await tts_emit(tts_pcm_stream(translated, target_lang), target_lang)
