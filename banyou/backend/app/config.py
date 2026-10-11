"""应用配置：集中管理环境变量，供各模块高内聚复用。

与主项目（川剧院导览系统）的 config.py 保持同一套约定：
pydantic-settings 读取 .env，缺省值直接可跑（SQLite，零外部依赖）。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "凉山伴游 · 纯伴游导览系统"
    app_env: str = "development"
    app_host: str = "127.0.0.1"  # 默认仅本机可访；对外部署时在 .env 显式改 0.0.0.0
    app_port: int = 8300
    debug: bool = True

    # 数据库：默认 SQLite，单文件随包部署；如需 MySQL 改为
    # mysql+pymysql://user:pwd@host:3306/banyou?charset=utf8mb4
    database_url: str = "sqlite:///./banyou.db"

    # JWT（管理后台鉴权）
    jwt_secret_key: str  # 必填（.env 提供），缺失即启动失败——不回退到公开默认值
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # 静态/上传
    upload_dir: str = "./uploads"
    static_dir: str = "../frontend"
    admin_static_dir: str = "../admin"

    # CORS
    cors_origins: list[str] = ["*"]

    # 伴游默认参数（后台「应用设置」可覆盖）
    default_arrival_radius: int = 50  # 到点触发半径（米）

    # ===== AI 伴游对话（可选）：配置 ARK_API_KEY 后自动升级豆包组织语言，
    # 知识内容仍只来自本地库（检索注入，防编造）；留空则纯规则引擎，离线可用 =====
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_llm_model: str = "doubao-seed-1-6-flash-250615"
    ark_timeout: float = 20.0

    # ===== 耳机语音沟通（可选）：配置后「说话 → ASR → 应答 → TTS 回耳机」全语音链，
    # 与主项目共用同一组凭据；留空时前端自动降级（浏览器识别 + 本机 TTS + 文字） =====
    doubao_speech_app_id: str = ""
    doubao_speech_access_token: str = ""
    doubao_asr_url: str = "wss://openspeech.bytedance.com/api/v3/asr/bigmodel"
    doubao_tts_http_url: str = "https://openspeech.bytedance.com/api/v1/tts"
    doubao_tts_default_voice: str = "zh_female_cancan_mars_bigtts"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
