"""PayPal 沙盒网关：REST v2（Checkout Orders），httpx 直调，无额外 SDK 依赖。

- mode=sandbox：调用 api-m.sandbox.paypal.com，需配置 client_id/secret；
- 凭证缺失时由工厂降级为 MockGateway，保证演示链路始终可用。
"""
import httpx

from app.config import settings
from app.models.payment import PaymentOrder
from app.services.payment.base import BaseGateway, GatewayResult, PaymentGatewayError

API_BASE = "https://api-m.sandbox.paypal.com"


class PaypalGateway(BaseGateway):
    channel = "paypal"
    mode = "sandbox"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    # ── OAuth ─────────────────────────────────────────────
    def _token(self) -> str:
        resp = httpx.post(
            f"{API_BASE}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            raise PaymentGatewayError(f"PayPal OAuth failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()["access_token"]

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"chuang-{id(self)}",
        }

    # ── 下单 ─────────────────────────────────────────────
    def create_payment(self, order: PaymentOrder, return_url: str) -> GatewayResult:
        amount_value = f"{order.amount_cents / 100:.2f}"
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": order.order_no,
                "description": order.subject[:127],
                "amount": {"currency_code": order.currency, "value": amount_value},
                "custom_id": order.order_no,
            }],
            "application_context": {
                "brand_name": "Sichuan Opera Theatre",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": return_url + ("&" if "?" in return_url else "?") + "cancelled=1",
            },
        }
        try:
            token = self._token()
            resp = httpx.post(
                f"{API_BASE}/v2/checkout/orders",
                json=payload, headers=self._headers(token), timeout=15,
            )
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"PayPal network error: {exc}") from exc
        if resp.status_code not in (200, 201):
            raise PaymentGatewayError(f"PayPal create order failed: {resp.status_code} {resp.text[:300]}")
        body = resp.json()
        approve_link = next(
            (l["href"] for l in body.get("links", []) if l.get("rel") == "approve"), ""
        )
        return GatewayResult(gateway_order_id=body.get("id", ""), pay_url=approve_link, raw=body)

    # ── 扣款（买家在 PayPal approve 后） ──────────────────
    def capture(self, order: PaymentOrder, token: str) -> dict:
        try:
            resp = httpx.post(
                f"{API_BASE}/v2/checkout/orders/{token}/capture",
                headers=self._headers(self._token()), timeout=15,
            )
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"PayPal network error: {exc}") from exc
        if resp.status_code not in (200, 201):
            raise PaymentGatewayError(f"PayPal capture failed: {resp.status_code} {resp.text[:300]}")
        body = resp.json()
        status = body.get("status", "")
        return {"status": "paid" if status == "COMPLETED" else "created", "raw": body}

    # ── 查单 ─────────────────────────────────────────────
    def query(self, order: PaymentOrder) -> dict:
        if not order.gateway_order_id:
            return {"status": order.status, "raw": {}}
        try:
            resp = httpx.get(
                f"{API_BASE}/v2/checkout/orders/{order.gateway_order_id}",
                headers=self._headers(self._token()), timeout=15,
            )
        except httpx.HTTPError as exc:
            raise PaymentGatewayError(f"PayPal network error: {exc}") from exc
        if resp.status_code != 200:
            return {"status": order.status, "raw": {}}
        body = resp.json()
        mapping = {"COMPLETED": "paid", "VOIDED": "failed"}
        return {"status": mapping.get(body.get("status", ""), "created"), "raw": body}


def paypal_configured() -> bool:
    """是否具备真实沙盒凭证（决定工厂是否降级 mock）。"""
    return bool(settings.paypal_client_id and settings.paypal_secret)
