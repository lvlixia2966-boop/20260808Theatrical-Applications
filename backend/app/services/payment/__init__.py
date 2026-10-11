"""支付渠道工厂：按渠道返回网关实例，凭证缺失自动降级模拟。"""
from app.config import settings
from app.schemas.payment import PaymentChannelOut
from app.services.payment.base import BaseGateway
from app.services.payment.mock_gateway import MockGateway
from app.services.payment.paypal_gateway import PaypalGateway, paypal_configured

# 渠道展示信息（前端收银台渲染用）
CHANNEL_META: dict[str, dict] = {
    "paypal": {"name": "PayPal", "currency": "CNY"},
    "wechat": {"name": "微信支付", "currency": "CNY"},
    "alipay": {"name": "支付宝", "currency": "CNY"},
}


def get_gateway(channel: str) -> BaseGateway:
    if channel == "paypal" and settings.paypal_mode == "sandbox" and paypal_configured():
        return PaypalGateway(settings.paypal_client_id, settings.paypal_secret)
    if channel not in CHANNEL_META:
        raise ValueError(f"unsupported channel: {channel}")
    return MockGateway(channel, CHANNEL_META[channel]["currency"])


def list_channels() -> list[PaymentChannelOut]:
    items = []
    for channel, meta in CHANNEL_META.items():
        mode = "sandbox" if channel == "paypal" and paypal_configured() else "mock"
        items.append(PaymentChannelOut(
            channel=channel, name=meta["name"], mode=mode, currency=meta["currency"],
        ))
    return items


def paypal_client_id_public() -> str:
    """前端 JS SDK 用的沙盒 client id（未配置返回空，前端走模拟收银台）。"""
    return settings.paypal_client_id if settings.paypal_mode == "sandbox" else ""
