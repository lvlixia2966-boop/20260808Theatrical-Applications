"""翻译与语音相关模式。"""
from pydantic import BaseModel, Field


class LanguageOut(BaseModel):
    code: str
    name_en: str
    name_native: str
    weight: int


class TranslateRequest(BaseModel):
    text: str = Field("", description="待翻译文本")
    target: str = Field(..., description="目标语言码，如 en / ja / fr")
    source: str = Field("zh-CN", description="源语言码，默认中文")


class TranslateOut(BaseModel):
    text: str
    target: str
    source: str


class VoiceOut(BaseModel):
    id: str
    lang: str
    name: str
    gender: str