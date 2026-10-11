"""支付服务：订单创建、状态流转（文创商城）。

高内聚：金额计算、幂等确认全部收敛于此；
api 层只做请求解析与响应包装。
"""
import json
import secrets
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaymentOrder, PaymentStatus
from app.schemas.payment import PaymentOrderCreate
from app.services.payment import get_gateway
from app.services.payment.base import PaymentGatewayError


def _gen_order_no() -> str:
    return f"PO{datetime.now():%Y%m%d%H%M%S}{secrets.token_hex(2).upper()}"


def _validate_items(db: Session, items) -> None:
    """商城下单校验：商品须存在、上架、价格与库内一致（防前端篡改）；名称以库内为准。"""
    from app.models import Product
    for i in items:
        p = db.scalar(select(Product).where(Product.sku == i.id))
        if p is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"商品不存在或已下架：{i.id}")
        if p.status != 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"商品已下架：{p.name}")
        if i.price_cents != p.price_cents:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"商品价格已变更：{p.name}，请刷新购物车后重试",
            )
        i.name = p.name


def create_order(db: Session, payload: PaymentOrderCreate) -> PaymentOrder:
    """创建支付单并调网关下单；返回含收银台地址的订单。"""
    if not payload.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="购物车为空，无法结算")
    _validate_items(db, payload.items)
    amount_cents = sum(i.price_cents * i.qty for i in payload.items)
    if amount_cents <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="订单金额异常")
    subject = f"川剧文创 × {sum(i.qty for i in payload.items)} 件"
    items_json = json.dumps([i.model_dump() for i in payload.items], ensure_ascii=False)

    order = PaymentOrder(
        order_no=_gen_order_no(),
        channel=payload.channel,
        scene="mall",
        subject=subject,
        amount_cents=amount_cents,
        currency="CNY",
        status=PaymentStatus.CREATED,
        items_json=items_json,
        scene_ref="",
    )

    gateway = get_gateway(payload.channel)
    # PayPal approve 后回跳模拟收银台页，由页面引导完成 capture/查询
    return_url = f"/mock-cashier.html?order_no={order.order_no}"
    try:
        result = gateway.create_payment(order, return_url)
    except PaymentGatewayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"支付渠道异常：{exc}") from exc

    order.gateway_order_id = result.gateway_order_id
    order.pay_url = result.pay_url
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_no: str) -> PaymentOrder:
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.order_no == order_no))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


def mark_paid(db: Session, order: PaymentOrder, gateway_order_id: str = "") -> PaymentOrder:
    """幂等置为已支付。"""
    if order.status == PaymentStatus.PAID:
        return order
    order.status = PaymentStatus.PAID
    order.paid_at = datetime.now()
    if gateway_order_id:
        order.gateway_order_id = gateway_order_id
    db.commit()
    db.refresh(order)
    return order


def confirm_mock_payment(db: Session, order_no: str) -> PaymentOrder:
    """模拟收银台回调：仅模拟渠道订单允许，直接确认成功。"""
    order = get_order(db, order_no)
    if not order.channel or not order.gateway_order_id.startswith("MOCK-"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该订单非模拟渠道，无法模拟确认")
    return mark_paid(db, order)


def capture_paypal(db: Session, order_no: str, token: str) -> PaymentOrder:
    """PayPal 买家 approve 后服务端扣款。"""
    order = get_order(db, order_no)
    if order.channel != "paypal":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该订单非 PayPal 渠道")
    if order.status == PaymentStatus.PAID:
        return order
    from app.services.payment import get_gateway as _factory  # 局部引用避免循环依赖
    gateway = _factory("paypal")
    try:
        result = gateway.capture(order, token)
    except PaymentGatewayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"PayPal 扣款失败：{exc}") from exc
    if result.get("status") == "paid":
        return mark_paid(db, order, gateway_order_id=token)
    return order


def sync_order_status(db: Session, order: PaymentOrder) -> PaymentOrder:
    """查询时向网关同步一次状态（PayPal 回跳场景兜底）。"""
    if order.status != PaymentStatus.CREATED or order.gateway_order_id.startswith("MOCK-"):
        return order
    gateway = get_gateway(order.channel)
    try:
        remote = gateway.query(order)
    except PaymentGatewayError:
        return order  # 网关异常不阻塞本地查询
    if remote.get("status") == "paid":
        return mark_paid(db, order)
    return order
