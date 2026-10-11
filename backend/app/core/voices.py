"""豆包 TTS 音色注册表：为系统支持的每种语言挑选音色。

高内聚：音色清单与「系统语言 -> 豆包音色 ID」映射统一在此维护。
低耦合：仅暴露纯数据；接口函数（voices_for_lang/default_voice/is_known_voice）
       签名与旧版一致，/api/tts/voices 与 /api/tts/synthesize 契约不变。

⚠ 音色 ID 校准：zh-CN 两条为火山官方文档示例 ID；其余语言按控制台「音色管理」
  实测校准，或经 config.doubao_tts_voice_overrides（.env JSON）逐语言覆盖，
  无需改代码。未注册语言不走 TTS（合成接口明确 503），翻译字幕不受影响。
"""
from app.core.languages import LANGUAGES, REALTIME_TARGET_LANGS

# 豆包音色清单：id 为豆包音色 ID，lang 为系统语言码
VOICES: list[dict] = [
    # 中文（源语言）
    {"id": "zh_female_cancan_mars_bigtts", "lang": "zh-CN", "name": "灿灿 · 女声", "gender": "F"},
    {"id": "zh_male_beijingxiaoye_mars_bigtts", "lang": "zh-CN", "name": "京城小爷 · 男声", "gender": "M"},
    # 报价单 12 目标语言
    {"id": "en_female_amanda_mars_bigtts", "lang": "en", "name": "Amanda · English", "gender": "F"},
    {"id": "en_male_adam_mars_bigtts", "lang": "en", "name": "Adam · English", "gender": "M"},
    {"id": "ja_female_okonomi_mars_bigtts", "lang": "ja", "name": "おこのみ · 日本語", "gender": "F"},
    {"id": "ja_male_takumi_mars_bigtts", "lang": "ja", "name": "たくみ · 日本語", "gender": "M"},
    {"id": "ko_female_hailey_mars_bigtts", "lang": "ko", "name": "Hailey · 한국어", "gender": "F"},
    {"id": "es_female_sofia_mars_bigtts", "lang": "es", "name": "Sofía · Español", "gender": "F"},
    {"id": "fr_female_adele_mars_bigtts", "lang": "fr", "name": "Adèle · Français", "gender": "F"},
    {"id": "de_female_katja_mars_bigtts", "lang": "de", "name": "Katja · Deutsch", "gender": "F"},
    {"id": "ru_female_svetlana_mars_bigtts", "lang": "ru", "name": "Svetlana · Русский", "gender": "F"},
    {"id": "hi_female_kalyani_mars_bigtts", "lang": "hi", "name": "Kalyani · हिन्दी", "gender": "F"},
    {"id": "th_female_airoonjan_mars_bigtts", "lang": "th", "name": "Airoonjan · ไทย", "gender": "F"},
    {"id": "vi_female_hoaimy_mars_bigtts", "lang": "vi", "name": "Hoài My · Tiếng Việt", "gender": "F"},
    {"id": "id_female_gadis_mars_bigtts", "lang": "id", "name": "Gadis · Bahasa Indonesia", "gender": "F"},
    {"id": "ms_female_yasmin_mars_bigtts", "lang": "ms", "name": "Yasmin · Bahasa Melayu", "gender": "F"},
]

# 语言码 -> 该语言默认音色（用于自动选择）
DEFAULT_VOICE: dict[str, str] = {
    "zh-CN": "zh_female_cancan_mars_bigtts",
    "en": "en_female_amanda_mars_bigtts",
    "ja": "ja_female_okonomi_mars_bigtts",
    "ko": "ko_female_hailey_mars_bigtts",
    "es": "es_female_sofia_mars_bigtts",
    "fr": "fr_female_adele_mars_bigtts",
    "de": "de_female_katja_mars_bigtts",
    "ru": "ru_female_svetlana_mars_bigtts",
    "hi": "hi_female_kalyani_mars_bigtts",
    "th": "th_female_airoonjan_mars_bigtts",
    "vi": "vi_female_hoaimy_mars_bigtts",
    "id": "id_female_gadis_mars_bigtts",
    "ms": "ms_female_yasmin_mars_bigtts",
}

# 音色 ID -> 音色 的快速索引
VOICE_MAP: dict[str, dict] = {v["id"]: v for v in VOICES}


def _system_lang(code: str) -> str:
    """归一化语言码：locale 写法（en-US / zh-cn）归一为系统码（en / zh-CN）。"""
    code = (code or "").strip()
    if not code:
        return "zh-CN"
    if code in DEFAULT_VOICE:
        return code
    lowered = code.lower()
    for sys_code in DEFAULT_VOICE:
        if lowered == sys_code.lower():
            return sys_code
    # locale 前缀匹配（en-US -> en）
    prefix = lowered.split("-")[0]
    for sys_code in DEFAULT_VOICE:
        if sys_code.lower() == prefix or sys_code.lower().split("-")[0] == prefix:
            return sys_code
    return code


def voices_for_lang(lang_code: str) -> list[dict]:
    """返回某语言码对应的豆包音色列表，默认音色排在最前。"""
    sys_code = _system_lang(lang_code)
    voices = [v for v in VOICES if v["lang"] == sys_code]
    default = DEFAULT_VOICE.get(sys_code, "")
    voices.sort(key=lambda v: (v["id"] != default))
    return voices


def default_voice(lang_code: str) -> str:
    """返回某语言码的默认音色 ID；未注册语言返回空串（TTS 明确不支持）。"""
    return DEFAULT_VOICE.get(_system_lang(lang_code), "")


def is_known_voice(voice_id: str) -> bool:
    """判断音色 ID 是否在注册表内。"""
    return voice_id in VOICE_MAP


def realtime_langs() -> list[str]:
    """实时场景（RTC/Agent/TTS）支持的目标语言 = 注册表 ∩ 报价单 12 语种。"""
    return [lang for lang in REALTIME_TARGET_LANGS if lang in DEFAULT_VOICE] if LANGUAGES else []
