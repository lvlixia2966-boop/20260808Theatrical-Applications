"""模拟收单网关：微信支付/支付宝/PayPal 降级共用的沙盒演示实现。

不发起任何真实扣款：生成网关单号与本地模拟收银台地址，
由收银台页面的"模拟支付成功"按钮回调 /api/payments/mock/{order_no}/confirm 完成闭环。
"""
import secrets
from urllib.parse import urlencode

from app.models.payment import PaymentOrder
from app.services.payment.base import BaseGateway, GatewayResult


class MockGateway(BaseGateway):
    """本地模拟网关。mode=mock，仅用于演示与联调。"""

    def __init__(self, channel: str, currency: str = "CNY"):
        self.channel = channel
        self.currency = currency

    def create_payment(self, order: PaymentOrder, return_url: str) -> GatewayResult:
        gateway_order_id = f"MOCK-{self.channel.upper()}-{secrets.token_hex(6).upper()}"
        pay_url = "/mock-cashier.html?" + urlencode({
            "order_no": order.order_no,
            "channel": self.channel,
            "subject": order.subject,
            "amount": f"{order.amount_cents / 100:.2f}",
            "currency": order.currency,
        })
        return GatewayResult(gateway_order_id=gateway_order_id, pay_url=pay_url,
                             raw={"mode": "mock"})

    def capture(self, order: PaymentOrder, token: str) -> dict:
        # 模拟渠道无独立 capture 动作，确认由 confirm 回调完成
        return {"status": "paid", "raw": {"mode": "mock", "token": token}}

    def query(self, order: PaymentOrder) -> dict:
        # 状态以本地库为准，网关侧仅回显
        return {"status": order.status, "raw": {"mode": "mock"}}
