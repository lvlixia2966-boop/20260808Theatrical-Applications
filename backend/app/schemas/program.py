"""节目相关模式。"""
from datetime import datetime

from pydantic import BaseModel, Field


class ProgramBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    subtitle: str = Field("", max_length=255)
    content_type: str = Field("full", description="voice/text/full")
    audio_url: str = Field("", max_length=512)
    text_content: str = Field("", description="讲解正文")
    voice_content: str = Field("", description="语音讲解文本")
    narrator: str = Field("", max_length=64)
    venue: str = Field("", max_length=128)
    intro_zh: str | None = Field(None, description="一句话简介（中文）")
    intro_en: str | None = Field(None, description="一句话简介（英文）")
    duration_min: int = Field(0, ge=0)
    price: float = Field(0.0, ge=0)
    is_online: bool = True
    sort_order: int = 0


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    content_type: str | None = None
    audio_url: str | None = None
    text_content: str | None = None
    voice_content: str | None = None
    narrator: str | None = None
    venue: str | None = None
    intro_zh: str | None = None
    intro_en: str | None = None
    duration_min: int | None = None
    price: float | None = None
    is_online: bool | None = None
    sort_order: int | None = None


class ProgramOut(ProgramBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}