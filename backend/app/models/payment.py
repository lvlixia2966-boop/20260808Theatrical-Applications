"""支付订单模型：文创商城购买的收单单据。

高内聚：订单状态流转（created → paid/failed）与渠道细节全部收敛在本模块
与 app/services/payment 包内；业务方（商城）只依赖 payment_service。
"""
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentChannel(str):
    """支付渠道：PayPal 沙盒 + 微信支付/支付宝（演示模拟网关）。"""
    PAYPAL = "paypal"
    WECHAT = "wechat"
    ALIPAY = "alipay"


class PaymentScene(str):
    """支付场景：文创商城购物。"""
    MALL = "mall"


class PaymentStatus(str):
    CREATED = "created"    # 已创建待支付
    PAID = "paid"          # 支付成功
    FAILED = "failed"      # 支付失败/取消
    REFUNDED = "refunded"  # 已退款（预留）


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 对外订单号（幂等键，前端凭它查询状态与拉起收银台）
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="wechat")
    scene: Mapped[str] = mapped_column(String(20), nullable=False, default="mall")
    subject: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # 金额以最小货币单位存储（分），避免浮点误差
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created", index=True)
    # 商城商品快照 JSON（[{id,name,price_cents,qty}]）；租机场景存 {"qr_code_id": ...}
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 场景关联引用：租机 = 耳机二维码 ID；商城留空
    scene_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # 网关侧单号（PayPal order id 等）
    gateway_order_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 收银台跳转地址（模拟收银台 / PayPal approve link）
    pay_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
