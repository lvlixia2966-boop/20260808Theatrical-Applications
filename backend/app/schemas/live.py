"""场次直播相关 Schema：场次 CRUD 模型与 WebSocket 消息协议。

高内聚：场次直播的数据契约统一收敛在此模块。
低耦合：仅定义纯数据结构与协议常量，不依赖服务与路由实现。

WebSocket 协议（/api/live/ws/{session_code}?audio=0|1）：
  ── 服务端 → 观众（文本帧）──────────────────────
  {"type":"caption","seq":N,"text":"原文","translations":{"en":"..."},"ts":秒}
    最终字幕（识别+翻译完成）。
  {"type":"listeners","count":N}            在线人数变化
  {"type":"highlight","term":"变脸","text":"看点解说","translations":{"en":"..."},"ts":秒}
    绝技看点提示：ASR 命中术语自动触发（同术语 60s 冷却），
    前端以强调卡片展示后自动收起；不进入历史字幕缓存
  {"type":"session_end","title":"..."}      场次收播，客户端应提示并退出
  ── 服务端 → 观众（二进制帧，仅 audio=1）────────
  PCM16LE / 单声道 / 16kHz 原声块（现场收音转发，Web Audio 直接播放）
  ── 观众 → 服务端 ──────────────────────────────
  文本 {"type":"ping"}                       心跳保活
"""
from datetime import datetime

from pydantic import BaseModel, Field

# WebSocket 消息 type 常量（协议契约的唯一权威定义；只增不改）
MSG_CAPTION = "caption"
MSG_LISTENERS = "listeners"
MSG_HIGHLIGHT = "highlight"
MSG_SESSION_END = "session_end"
MSG_APPLAUD = "applaud"
MSG_PING = "ping"


class LiveShowCreate(BaseModel):
    """设置场次请求。"""

    title: str = Field(..., min_length=1, max_length=128, description="场次标题，如「折子戏专场」")
    host_name: str = Field("讲解员", max_length=64, description="讲解/演出人")
    start_at: datetime = Field(..., description="计划开始时间（本地时间），到点自动开播")
    duration_min: int = Field(60, ge=1, le=1440, description="场次时长（分钟），到点自动收播")
    target_langs: list[str] = Field(["en"], description="实时翻译目标语言码列表")


class LiveShowUpdate(BaseModel):
    """修改场次请求（仅未开播场次可改排期）。"""

    title: str | None = None
    host_name: str | None = None
    start_at: datetime | None = None
    duration_min: int | None = Field(None, ge=1, le=1440)
    target_langs: list[str] | None = None


class LiveShowOut(BaseModel):
    """场次信息（管理端与观众端共用，按需忽略字段）。"""

    id: int
    title: str
    host_name: str
    start_at: datetime
    duration_min: int
    target_langs: list[str]
    status: str = Field(description="scheduled=待开播 / live=直播中 / ended=已结束")
    session_code: str = Field(description="会场码（直播中的场次凭此接入 WS）")
    listeners: int = Field(0, description="当前在线收听人数（仅 live 有意义）")
    captions: int = Field(0, description="已产生的字幕条数")
    created_at: datetime | None = None


class BroadcastAudioIn(BaseModel):
    """管理端向直播中场次推流预录音频请求（临时通知 / 备用音源）。

    音频格式与直播原声通道一致：PCM16LE / 单声道 / 16kHz 的 base64 编码，
    由管理后台在浏览器本地转码后上传，推流期间现场收音让位。
    """

    pcm_b64: str = Field(..., min_length=8, description="PCM16LE/单声道/16kHz 的 base64 编码")
    notice: str | None = Field(None, max_length=500, description="随音频推送的字幕通知文案（可选）")
