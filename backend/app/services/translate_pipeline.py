"""共享翻译管线：单句「韵译优先 > 豆包机翻 + 术语规范化」的统一编排。

高内聚：翻译优先级策略收敛于此（对应报价单 #16 的「术语表」环节）。
低耦合：live_hub 与 rtc_pipeline 共同调用，消除重复；glossary 异常一律静默降级，
       绝不中断字幕/译文管线。
"""

import asyncio

from app.services import glossary_service as glossary
from app.services.translation_service import translation_service


def _translate_one_sync(text: str, lang: str) -> str:
    """单句单语言翻译（同步）：唱段韵译短路 > 豆包机翻 + 术语规范化。"""
    try:
        poetic = glossary.lookup_lyric(text, lang)
        if poetic:
            return poetic
    except Exception:  # noqa: BLE001 - 术语库异常降级纯机翻
        pass
    translated = translation_service.translate(text, lang)
    try:
        return glossary.apply_terms(text, lang, translated)
    except Exception:  # noqa: BLE001
        return translated


async def translate_sentence(text: str, lang: str) -> str:
    """异步包装：在线程池执行阻塞翻译，不占用事件循环。"""
    return await asyncio.to_thread(_translate_one_sync, text, lang)
