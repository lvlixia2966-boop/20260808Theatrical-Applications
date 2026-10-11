"""实时翻译相关 Schema：REST 模型与 WebSocket 信令协议。

高内聚：RTC 域的数据契约统一收敛在此模块。
低耦合：仅定义纯数据结构与协议常量，不依赖服务与路由实现。

信令协议（/api/rtc/ws/{token}?role=visitor|staff，JSON 文本帧）：
  ── 客户端 → 服务端 ──────────────────────────────
  {"type":"offer","sdp":"..."}               WebRTC offer（客户端发起）
  {"type":"ice","candidate":{...}}           ICE 候选（candidate 为 RTCIceCandidateInit）
  {"type":"ptt","on":true}                   按住说话开/关（服务端据此开关出站收音）
  {"type":"ping"}                            心跳保活
  ── 服务端 → 客户端 ──────────────────────────────
  {"type":"answer","sdp":"..."}              WebRTC answer
  {"type":"ice","candidate":{...}}           ICE 候选
  {"type":"caption","seq":N,"direction":"visitor→staff","text":"原文","translated":"译文","ts":秒}
  {"type":"peer_state","state":"joined"|"left"|"ended","role":"..."}
  {"type":"session_end","code":"ABC234"}     会话结束，客户端应提示并退出
"""
from datetime import datetime

from pydantic import BaseModel, Field

# WebSocket 消息 type 常量（协议契约的唯一权威定义；只增不改）
SIG_OFFER = "offer"
SIG_ANSWER = "answer"
SIG_ICE = "ice"
SIG_PTT = "ptt"
MSG_CAPTION = "caption"
MSG_PEER_STATE = "peer_state"
MSG_SESSION_END = "session_end"
MSG_PING = "ping"

ROLE_VISITOR = "visitor"
ROLE_STAFF = "staff"

# 会话方向常量（链路 A/B，对齐报价单「关键链路」）
DIR_VISITOR_TO_STAFF = "visitor->staff"
DIR_STAFF_TO_VISITOR = "staff->visitor"


class RtcSessionCreate(BaseModel):
    """管理端创建双端翻译会话请求。"""

    title: str = Field("实时翻译会话", max_length=128)
    visitor_lang: str = Field("en", description="游客语言（12 目标语种之一）")
    staff_lang: str = Field("zh-CN", description="工作人员语言")
    retention_days: int = Field(30, ge=1, le=365, description="会话记录留存天数")


class RtcSessionOut(BaseModel):
    """会话信息（管理端列表与详情）。"""

    id: int
    code: str
    title: str
    visitor_lang: str
    staff_lang: str
    status: str
    retention_days: int
    visitor_url: str = Field("", description="游客端接入 URL（前端拼接域名后生成二维码）")
    staff_url: str = Field("", description="工作人员端接入 URL")
    log_count: int = Field(0, description="已产生记录条数")
    created_at: datetime | None = None


class TokenInfoOut(BaseModel):
    """token-info：扫码端换取会话上下文（角色、语言、状态）。"""

    code: str
    role: str
    title: str
    lang: str
    visitor_lang: str = Field("", description="游客侧语言（对端语言展示用）")
    staff_lang: str = Field("", description="工作人员侧语言（对端语言展示用）")
    session_status: str
    peer_online: bool = Field(False, description="对端是否在线")
