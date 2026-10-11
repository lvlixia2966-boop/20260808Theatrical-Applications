"""语音合成（TTS）服务：统一入口，按配置与语言在引擎间分派。

高内聚：合成决策（选引擎、回退）收敛于此；音色注册表来自 core.voices。
低耦合：具体引擎在 tts_engines 包内实现，互不依赖；前端只需传音色 ID / 语言码。

按报价单 #8/#16，合成统一走豆包云 TTS；未配置凭据或失败时抛 RuntimeError，
由 api/tts.py 返回 503 明确报错（不做静默降级，避免错音色/错语言输出）。
"""
from app.config import settings
from app.core.voices import VOICE_MAP, is_known_voice, voices_for_lang, default_voice
from app.services.tts_engines import doubao

# 引擎链：豆包云 TTS（引擎约定保持可扩展，未来可按需追加引擎模块）
_ENGINE_CHAIN = [doubao]


def list_voices(lang_code: str | None = None) -> list[dict]:
    """返回音色列表；lang_code 非空时仅返回该语言的音色。"""
    if lang_code:
        return voices_for_lang(lang_code)
    return [dict(v) for v in VOICE_MAP.values()]


def resolve_voice(lang_code: str | None, voice_id: str = "") -> str:
    """解析最终使用的音色 ID：优先显式指定，否则取该语言默认音色。"""
    if voice_id and is_known_voice(voice_id):
        return voice_id
    if lang_code:
        return default_voice(lang_code)
    return default_voice("zh-CN")


def _lang_of_voice(voice_id: str) -> str:
    """由音色 ID 反查系统语言码；未知返回 zh-CN。"""
    v = VOICE_MAP.get(voice_id or "")
    return (v or {}).get("lang", "zh-CN")


def _engine_enabled(eng) -> bool:
    """该引擎是否参与本次分派：由凭据配置与 tts_engine 设置共同控制。"""
    if not doubao.is_configured():
        return False
    module_name = eng.__name__.rsplit(".", 1)[-1]
    return settings.tts_engine in ("auto", module_name)


async def synthesize(text: str, voice_id: str, rate: int = 0, lang_code: str | None = None) -> tuple[bytes, str]:
    """将文本合成为音频字节，返回 (bytes, mime)。

    豆包未配置或合成失败时抛 RuntimeError（调用方转为 503），不静默降级。
    lang_code 未传时由 voice_id 反推。
    """
    text = (text or "").strip()
    if not text:
        return (b"", doubao.MIME)
    lang = lang_code or _lang_of_voice(voice_id)

    for eng in _ENGINE_CHAIN:
        if not _engine_enabled(eng):
            continue
        if not eng.supports(lang):
            raise RuntimeError(f"豆包 TTS 不支持语言 {lang}（音色注册表未覆盖）")
        audio = await eng.synthesize(text, lang, rate, voice_id)
        if audio:
            return (audio, eng.MIME)

    raise RuntimeError("豆包 TTS 不可用：未配置 openspeech 凭据（doubao_speech_app_id / access_token）")


async def synthesize_sync(text: str, voice_id: str, rate: int = 0) -> bytes:
    """同步包装，供非异步调用场景使用。"""
    audio, _ = await synthesize(text, voice_id, rate)
    return audio
