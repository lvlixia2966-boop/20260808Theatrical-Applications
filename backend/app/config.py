"""应用配置：集中管理环境变量，供各模块高内聚复用。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "川蜀大剧院语音导览系统"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # ===== 火山方舟 Ark（豆包大模型 / 翻译 / 视觉 / 向量，OpenAI 兼容 REST）=====
    ark_api_key: str = ""                                   # 火山方舟 API Key（Bearer）
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_llm_model: str = "doubao-seed-1-6-flash-250615"     # Agent / 翻译 / 编排（可换 ep-xxx 接入点）
    ark_vision_model: str = "doubao-seed-1-6-flash-250615"  # AI 旅拍视觉多模态
    ark_translate_model: str = ""                           # 空 = 复用 ark_llm_model
    ark_embedding_model: str = "doubao-embedding-large-text-250515"  # 知识库向量
    ark_image_model: str = ""                               # 可选：doubao-seedream 生图（旅拍增强）
    ark_timeout: float = 30.0

    # ===== 豆包语音（openspeech，独立鉴权体系：appid + access token）=====
    doubao_speech_app_id: str = ""
    doubao_speech_access_token: str = ""
    doubao_asr_url: str = "wss://openspeech.bytedance.com/api/v3/asr/bigmodel"
    doubao_asr_resource_id: str = "volc.bigasr.sauc.duration"
    doubao_tts_http_url: str = "https://openspeech.bytedance.com/api/v1/tts"
    doubao_tts_stream_url: str = "wss://openspeech.bytedance.com/api/v3/tts/unidirectional/stream"
    doubao_tts_resource_id: str = "volc.service_type.10029"
    doubao_tts_default_voice: str = "zh_female_cancan_mars_bigtts"  # 中文默认音色
    doubao_tts_voice_overrides: dict[str, str] = {}  # 语言码 -> 音色 ID 覆盖（音色表见 core/voices.py）

    # ===== 豆包用量与预算（报价单 #21）=====
    doubao_monthly_budget: float = 30000.0  # 每月预算（元），超 80% 在管理端告警

    # ===== WebRTC 实时翻译（报价单 #15）=====
    rtc_enabled: bool = True
    rtc_max_sessions: int = 8
    rtc_stun_urls: list[str] = []  # 局内网部署留空走 host 候选；跨网段再配 STUN
    rtc_audio_bitrate_kbps: int = 32
    rtc_peer_timeout_seconds: int = 60  # peer 掉线后允许同 token 重连复用会话的窗口

    # 数据库
    db_backend: str = "mysql"  # mysql / sqlite（sqlite 用于本地快速演示）
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "shuyin"

    # JWT
    jwt_secret_key: str = "please_change_me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # 静态/上传
    upload_dir: str = "./uploads"
    static_dir: str = "../frontend"
    admin_static_dir: str = "../admin"

    # CORS
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # 蓝牙校验
    bluetooth_verify_required: bool = True

    # 语音合成引擎：doubao（豆包云 TTS；未配置回退 mock 占位）/ mock
    tts_engine: str = "auto"

    # 会场收音直播：ASR 引擎 auto/doubao（豆包流式 ASR，未配置自动回退演示引擎）/ mock
    asr_engine: str = "auto"
    live_max_history: int = 300  # 每个场次缓存的近期字幕条数（观众中途加入补发用）
    # 收音采集：auto（优先服务器声卡线路输入，不可用回退演示采集）/ soundcard / mock
    live_capture: str = "auto"
    capture_device: str = ""  # 输入设备名或序号；空 = 系统默认输入（调音台接入的线路输入）
    live_tick_seconds: int = 10  # 场次调度器巡检间隔（秒）

    # 支付（沙盒演示模式）：PayPal 配置了 client_id/secret 时走真沙盒 REST，
    # 否则与微信/支付宝一样走本地模拟收银台（mock 网关）
    paypal_mode: str = "sandbox"  # sandbox / mock
    paypal_client_id: str = ""
    paypal_secret: str = ""

    @property
    def database_url(self) -> str:
        if self.db_backend == "sqlite":
            return f"sqlite:///{self.db_name}.db"
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()