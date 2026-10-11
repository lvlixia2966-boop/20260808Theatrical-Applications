"""Agent 伴游 Schema：会话创建 / 问答 / 历史（报价单 #9/#12）。

高内聚：伴游问答的数据契约统一收敛在此模块。
低耦合：仅定义纯数据结构，不依赖服务与路由实现。
"""
from datetime import datetime

from pydantic import BaseModel, Field


class AgentSessionCreate(BaseModel):
    """创建伴游会话请求（游客端进入伴游页时调用）。"""

    lang: str = Field("zh-CN", min_length=2, max_length=16, description="问答输出语言码")
    node_code: str = Field("", max_length=32, description="扫码进入时的知识节点码（点位上下文）")


class AgentSourceOut(BaseModel):
    """回答引用来源。"""

    n: int = Field(..., description="引用编号，对应回答中的 [n]")
    title: str
    node: str
    unit_id: int


class AgentMessageOut(BaseModel):
    """会话历史消息。"""

    id: int
    role: str = Field(..., description="user / assistant")
    content: str
    sources: list[AgentSourceOut] = Field(default_factory=list)
    degraded: bool = False
    created_at: datetime | None = None


class AgentSessionOut(BaseModel):
    """伴游会话信息（token 由前端持有，后续问答凭此鉴权）。"""

    token: str
    lang: str
    node_code: str
    created_at: datetime | None = None


class AgentChatRequest(BaseModel):
    """伴游问答请求。"""

    token: str = Field(..., min_length=8, max_length=64)
    text: str = Field(..., min_length=1, max_length=500, description="游客提问（已由前端 ASR 或手输）")


class AgentChatReply(BaseModel):
    """伴游问答回复。"""

    text: str
    sources: list[AgentSourceOut] = Field(default_factory=list)
    degraded: bool = Field(False, description="True=LLM 不可用时的降级话术（引导人工服务台）")


class AgentVoiceReply(AgentChatReply):
    """语音问答回复：额外带回识别出的提问文本（前端展示「您问的是…」）。"""

    heard: str = Field("", description="豆包单发 ASR 识别出的提问原文")
