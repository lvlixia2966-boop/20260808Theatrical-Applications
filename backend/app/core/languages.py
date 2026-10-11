"""语言注册表：主流使用人群数靠前的语言，供翻译与语音播报复用。

高内聚：语言清单与元信息统一在此维护，避免散落各处。
低耦合：仅暴露纯数据，不依赖数据库或框架。
"""

# 按「母语 + 二语」大致使用人数从高到低排序。
# code 为 Google 翻译支持的 BCP-47 语言码；zh-CN 为系统源讲解语言。
LANGUAGES: list[dict] = [
    {"code": "zh-CN", "name_en": "Chinese (Simplified)", "name_native": "中文", "weight": 100},
    {"code": "en", "name_en": "English", "name_native": "English", "weight": 98},
    {"code": "hi", "name_en": "Hindi", "name_native": "हिन्दी", "weight": 90},
    {"code": "es", "name_en": "Spanish", "name_native": "Español", "weight": 85},
    {"code": "fr", "name_en": "French", "name_native": "Français", "weight": 77},
    {"code": "ar", "name_en": "Arabic", "name_native": "العربية", "weight": 75},
    {"code": "bn", "name_en": "Bengali", "name_native": "বাংলা", "weight": 70},
    {"code": "pt", "name_en": "Portuguese", "name_native": "Português", "weight": 68},
    {"code": "ru", "name_en": "Russian", "name_native": "Русский", "weight": 65},
    {"code": "ja", "name_en": "Japanese", "name_native": "日本語", "weight": 60},
    {"code": "de", "name_en": "German", "name_native": "Deutsch", "weight": 55},
    {"code": "id", "name_en": "Indonesian", "name_native": "Bahasa Indonesia", "weight": 50},
    {"code": "ur", "name_en": "Urdu", "name_native": "اردو", "weight": 48},
    {"code": "ko", "name_en": "Korean", "name_native": "한국어", "weight": 45},
    {"code": "it", "name_en": "Italian", "name_native": "Italiano", "weight": 42},
    {"code": "tr", "name_en": "Turkish", "name_native": "Türkçe", "weight": 40},
    {"code": "vi", "name_en": "Vietnamese", "name_native": "Tiếng Việt", "weight": 38},
    {"code": "th", "name_en": "Thai", "name_native": "ไทย", "weight": 35},
    {"code": "pl", "name_en": "Polish", "name_native": "Polski", "weight": 30},
    {"code": "nl", "name_en": "Dutch", "name_native": "Nederlands", "weight": 28},
    {"code": "uk", "name_en": "Ukrainian", "name_native": "Українська", "weight": 25},
    {"code": "ms", "name_en": "Malay", "name_native": "Bahasa Melayu", "weight": 22},
    {"code": "fa", "name_en": "Persian", "name_native": "فارسی", "weight": 20},
    {"code": "sw", "name_en": "Swahili", "name_native": "Kiswahili", "weight": 18},
]

# 系统讲解的源语言（原文均为中文讲解）
SOURCE_LANGUAGE: str = "zh-CN"

# 实时场景目标语言（报价单 #8/#16：12 种；zh 为源语言不计入）。
# 实时翻译（RTC）/ Agent 输出 / 豆包 TTS 音色注册表均以此为准；
# 录播导览母稿仍按人工翻译体系，上线前与院方冻结此清单。
REALTIME_TARGET_LANGS: list[str] = [
    "en", "ja", "ko", "es", "fr", "de", "ru", "hi", "th", "vi", "id", "ms",
]

# 语言码 -> 语言信息 的快速索引
LANGUAGE_MAP: dict[str, dict] = {item["code"]: item for item in LANGUAGES}


def is_supported(code: str) -> bool:
    """判断目标语言是否在支持清单内。"""
    return code in LANGUAGE_MAP


def native_name(code: str) -> str:
    """返回某语言码的本地名称，用于前端展示；未知则原样返回。"""
    item = LANGUAGE_MAP.get(code)
    return item["name_native"] if item else code