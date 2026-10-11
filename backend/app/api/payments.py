"""支付路由：渠道查询、下单、状态查询、模拟确认与 PayPal 扣款。"""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep
from app.config import settings
from app.schemas import (
    ApiResponse,
    ChannelsData,
    PaymentChannelOut,
    PaymentCreatedData,
    PaymentOrderCreate,
    PaymentOrderOut,
    PaypalCaptureRequest,
)
from app.services import payment_service
from app.services.payment import list_channels, paypal_client_id_public
from app.services.payment.paypal_gateway import paypal_configured

router = APIRouter(prefix="/api/payments", tags=["支付"])


def _mock_cashier_enabled() -> bool:
    """模拟收银台开放条件：未配置真实网关（与 get_gateway 的降级逻辑一致）。"""
    return not (settings.paypal_mode == "sandbox" and paypal_configured())


@router.get("/channels", response_model=ApiResponse[ChannelsData])
def get_channels(db: DbDep):
    """可用支付渠道（mode=mock 表示沙盒演示模拟）。"""
    channels: list[PaymentChannelOut] = list_channels()
    return ApiResponse(data=ChannelsData(
        channels=channels, paypal_client_id=paypal_client_id_public(),
    ))


@router.post("/orders", response_model=ApiResponse[PaymentCreatedData])
def create_order(payload: PaymentOrderCreate, db: DbDep):
    """创建支付单（商城购物，items 为商品快照）。"""
    order = payment_service.create_order(db, payload)
    return ApiResponse(data=PaymentCreatedData(order=PaymentOrderOut.model_validate(order)))


@router.get("/orders/{order_no}", response_model=ApiResponse[PaymentOrderOut])
def get_order(order_no: str, db: DbDep):
    """查询订单状态（自动向真实网关同步一次）。"""
    order = payment_service.get_order(db, order_no)
    order = payment_service.sync_order_status(db, order)
    return ApiResponse(data=PaymentOrderOut.model_validate(order))


@router.post("/mock/{order_no}/confirm", response_model=ApiResponse[PaymentOrderOut])
def mock_confirm(order_no: str, db: DbDep):
    """沙盒演示：模拟收银台"支付成功"回调（仅模拟渠道订单；真实网关模式下线）。"""
    if not _mock_cashier_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="接口不存在")
    order = payment_service.confirm_mock_payment(db, order_no)
    return ApiResponse(data=PaymentOrderOut.model_validate(order))


@router.post("/orders/{order_no}/paypal-capture", response_model=ApiResponse[PaymentOrderOut])
def paypal_capture(order_no: str, payload: PaypalCaptureRequest, db: DbDep):
    """PayPal 沙盒：买家 approve 后服务端 capture。"""
    order = payment_service.capture_paypal(db, order_no, payload.token)
    return ApiResponse(data=PaymentOrderOut.model_validate(order))
