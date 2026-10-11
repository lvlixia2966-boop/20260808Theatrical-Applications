"""预约相关模式。"""
from datetime import datetime

from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    earphone_id: int
    qr_code_id: str = Field("", max_length=64)
    program_id: int | None = None
    program_title: str = Field("", max_length=128)
    book_type: str = Field("full", description="text/voice/full")
    scheduled_at: datetime | None = None
    text_content: str = Field("")
    voice_content: str = Field("")
    customer_name: str = Field("", max_length=64)
    contact: str = Field("", max_length=64)


class ReservationUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    customer_name: str | None = None
    contact: str | None = None


class ReservationOut(BaseModel):
    id: int
    earphone_id: int
    qr_code_id: str
    program_id: int | None
    program_title: str
    book_type: str
    scheduled_at: datetime | None
    status: str
    text_content: str
    voice_content: str
    customer_name: str
    contact: str
    created_at: datetime | None

    model_config = {"from_attributes": True}