"""文创开放 API：商品只读 + 游客下单/支付（沙盒模拟）。

不打扰原则的接口面：商品查询永远被动（按 spot/area 关联返回），
没有任何主动推送型接口；下单用 visitor_id 标识，无需注册登录。
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content import Spot
from app.models.product import Order, Product

router = APIRouter()


class OrderItemIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=20)


class OrderIn(BaseModel):
    visitor_id: str = Field(min_length=6, max_length=64)
    items: list[OrderItemIn] = Field(min_length=1)


class PayIn(BaseModel):
    visitor_id: str
    channel: str = "wechat"  # wechat / alipay


def ser_product(row: Product) -> dict:
    return {
        "id": row.id, "name": row.name, "en_name": row.en_name,
        "price": row.price, "orig_price": row.orig_price, "desc": row.desc,
        "image_url": row.image_url, "stock": row.stock, "tags": row.tags,
        "scenic_area_id": row.scenic_area_id, "spot_ids": row.spot_ids,
    }


def ser_order(row: Order) -> dict:
    return {
        "id": row.id, "items": row.items, "total": row.total,
        "status": row.status, "channel": row.channel,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
    }


@router.get("/products")
def list_products(
    area_id: int | None = Query(None),
    spot_id: int | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """按上下文取商品：
    - ?spot_id=      → 点位精确关联 + 所属景区级商品（讲解页「手边好物」条）
    - ?area_id=      → 全域好物 + 该景区商品
    - 无参           → 全部在架（「更多好物」列表）
    """
    rows = (
        db.query(Product).filter(Product.status == 1)
        .order_by(Product.sort, Product.id).all()
    )
    if spot_id is not None:
        spot = db.get(Spot, spot_id)
        area_of_spot = spot.scenic_area_id if spot else None
        exact = [r for r in rows if spot_id in r.spot_ids]
        area_level = [
            r for r in rows
            if r.scenic_area_id and not r.spot_ids and r.scenic_area_id == area_of_spot
        ]
        rows = exact + area_level
    if area_id is not None:
        rows = [r for r in rows if r.scenic_area_id in (None, area_id)]
    if keyword:
        like = keyword.strip()
        rows = [r for r in rows if like in r.name or like in r.desc or like in "".join(r.tags)]
    return {"items": [ser_product(r) for r in rows]}


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if row is None or row.status != 1:
        raise HTTPException(404, "商品不存在或已下架")
    return ser_product(row)


@router.post("/orders")
def create_order(body: OrderIn, db: Session = Depends(get_db)):
    """创建订单：校验商品在架与库存，金额按服务端价格计算（不信任前端）。"""
    products = {
        p.id: p
        for p in db.query(Product).filter(Product.id.in_([i.product_id for i in body.items])).all()
    }
    items, total = [], 0.0
    for item in body.items:
        p = products.get(item.product_id)
        if p is None or p.status != 1:
            raise HTTPException(400, f"商品 #{item.product_id} 不存在或已下架")
        if p.stock < item.qty:
            raise HTTPException(400, f"「{p.name}」库存不足")
        items.append({"product_id": p.id, "name": p.name, "price": p.price, "qty": item.qty})
        total += p.price * item.qty
    order = Order(visitor_id=body.visitor_id, items=items, total=round(total, 2))
    db.add(order)
    db.commit()
    return ser_order(order)


@router.get("/orders")
def my_orders(vid: str = Query(min_length=6, max_length=64), db: Session = Depends(get_db)):
    rows = (
        db.query(Order).filter(Order.visitor_id == vid)
        .order_by(Order.id.desc()).limit(50).all()
    )
    return {"items": [ser_order(r) for r in rows]}


@router.get("/orders/{order_id}")
def get_order(order_id: int, vid: str = Query(min_length=6), db: Session = Depends(get_db)):
    row = db.get(Order, order_id)
    if row is None or row.visitor_id != vid:
        raise HTTPException(404, "订单不存在")
    return ser_order(row)


@router.post("/orders/{order_id}/pay")
def pay_order(order_id: int, body: PayIn, db: Session = Depends(get_db)):
    """沙盒支付：直接置为已支付并扣减库存。接入真实商户号时替换此实现。"""
    row = db.get(Order, order_id)
    if row is None or row.visitor_id != body.visitor_id:
        raise HTTPException(404, "订单不存在")
    if row.status != "pending":
        raise HTTPException(400, f"订单状态为 {row.status}，不可支付")
    for item in row.items:
        p = db.get(Product, item["product_id"])
        if p is not None:
            p.stock = max(0, p.stock - item["qty"])
    row.status = "paid"
    row.channel = body.channel
    row.paid_at = datetime.now(timezone.utc)
    db.commit()
    return ser_order(row)
