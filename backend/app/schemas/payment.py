"""支付相关模式：下单请求、订单展示与渠道信息。"""
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse


class PaymentItemIn(BaseModel):
    """商城商品条目（前端购物车快照）。"""
    id: str = Field(..., min_length=1, max_length=64, description="商品 ID")
    name: str = Field(..., min_length=1, max_length=128, description="商品名称")
    price_cents: int = Field(..., ge=0, description="单价（分）")
    qty: int = Field(1, ge=1, le=99, description="数量")


class PaymentOrderCreate(BaseModel):
    """创建支付单：商城购物车快照。"""
    channel: str = Field("wechat", pattern="^(paypal|wechat|alipay)$")
    items: list[PaymentItemIn] = Field(default_factory=list)


class PaymentOrderOut(BaseModel):
    order_no: str
    channel: str
    scene: str
    subject: str
    amount_cents: int
    currency: str
    status: str
    pay_url: str = ""
    gateway_order_id: str = ""
    paid_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaymentChannelOut(BaseModel):
    """对外渠道描述：前端据此渲染收银台选项。"""
    channel: str
    name: str
    mode: str  # sandbox / mock
    currency: str


class ChannelsData(BaseModel):
    channels: list[PaymentChannelOut]
    paypal_client_id: str = ""  # 沙盒 JS SDK 用；空表示走模拟收银台


class PaypalCaptureRequest(BaseModel):
    """PayPal 前端 approve 完成后回传 orderID 供服务端 capture。"""
    token: str = Field(..., min_length=1, max_length=128)


# 复用：支付单创建响应 = 订单信息 + 收银台跳转
class PaymentCreatedData(BaseModel):
    order: PaymentOrderOut


# OpenAPI 文档引用辅助（避免 ApiResponse 泛型悬空）
PaymentCreatedResponse = ApiResponse[PaymentCreatedData]
