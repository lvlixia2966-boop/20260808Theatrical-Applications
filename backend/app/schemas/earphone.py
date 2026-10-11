"""耳机相关模式。"""
from pydantic import BaseModel, Field


class EarphoneBase(BaseModel):
    qr_code_id: str = Field(..., min_length=1, max_length=64, description="二维码唯一标识")
    name: str = Field("", max_length=128)
    device_name: str = Field("", max_length=128, description="蓝牙设备名")
    serial_number: str = Field("", max_length=128, description="厂商数据序列号(可选)")
    service_uuid: str = Field("", max_length=64)
    status: str = Field("available", description="available/rented/offline")
    bound_program_title: str = Field("", max_length=128)


class EarphoneCreate(EarphoneBase):
    pass


class EarphoneUpdate(BaseModel):
    name: str | None = None
    device_name: str | None = None
    serial_number: str | None = None
    service_uuid: str | None = None
    status: str | None = None
    bound_program_title: str | None = None


class EarphoneOut(EarphoneBase):
    id: int

    model_config = {"from_attributes": True}


class EarphoneQueryRequest(BaseModel):
    """扫码进入后，前端上报蓝牙扫描结果用于校验。"""
    device_name: str | None = None
    mfg_data: str | None = None
    serial_number: str | None = None