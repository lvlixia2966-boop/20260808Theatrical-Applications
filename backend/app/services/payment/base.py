"""支付网关抽象：统一各渠道的下单/查单/扣款接口。

低耦合：payment_service 只依赖 BaseGateway 接口与 GatewayResult 结构，
渠道实现（PayPal 沙盒 REST / 本地模拟）可独立替换。
"""
from dataclasses import dataclass, field

from app.models.payment import PaymentOrder


@dataclass
class GatewayResult:
    """网关下单结果。"""
    gateway_order_id: str = ""
    pay_url: str = ""          # 收银台跳转地址（模拟页或 PayPal approve link）
    raw: dict = field(default_factory=dict)


class PaymentGatewayError(Exception):
    """网关调用失败（网络/凭证/参数）。"""


class BaseGateway:
    """渠道网关接口。"""

    channel: str = "mock"
    mode: str = "mock"       # sandbox = 真实沙盒环境；mock = 本地模拟
    currency: str = "CNY"

    def create_payment(self, order: PaymentOrder, return_url: str) -> GatewayResult:
        raise NotImplementedError

    def capture(self, order: PaymentOrder, token: str) -> dict:
        """扣款/确认（PayPal 前端 approve 后调用；模拟渠道直接成功）。"""
        raise NotImplementedError

    def query(self, order: PaymentOrder) -> dict:
        """查询网关侧订单状态，返回 {status: created|paid|failed, raw}。"""
        raise NotImplementedError
