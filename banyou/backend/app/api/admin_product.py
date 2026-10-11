"""管理后台：文创商品 CRUD + 订单管理。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.product import Order, Product

router = APIRouter(dependencies=[Depends(require_admin)])


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    en_name: str = ""
    price: float = 0.0
    orig_price: float = 0.0
    desc: str = ""
    image_url: str = ""
    stock: int = 99
    tags: list[str] = []
    scenic_area_id: int | None = None
    spot_ids: list[int] = []
    sort: int = 0
    status: int = 1


class OrderStatusIn(BaseModel):
    status: str  # paid / shipped / cancelled


def _apply(row: Product, body: ProductIn) -> None:
    for key, value in body.model_dump().items():
        if key == "tags":
            row.tags = value
        elif key == "spot_ids":
            row.spot_ids = value
        else:
            setattr(row, key, value)


@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    rows = db.query(Product).order_by(Product.sort, Product.id).all()
    return {"items": [
        {
            "id": p.id, "name": p.name, "en_name": p.en_name, "price": p.price,
            "orig_price": p.orig_price, "desc": p.desc, "image_url": p.image_url,
            "stock": p.stock, "tags": p.tags, "scenic_area_id": p.scenic_area_id,
            "spot_ids": p.spot_ids, "sort": p.sort, "status": p.status,
        }
        for p in rows
    ]}


@router.post("/products")
def create_product(body: ProductIn, db: Session = Depends(get_db)):
    row = Product()
    _apply(row, body)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/products/{product_id}")
def update_product(product_id: int, body: ProductIn, db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if row is None:
        raise HTTPException(404, "商品不存在")
    _apply(row, body)
    db.commit()
    return {"ok": True}


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    row = db.get(Product, product_id)
    if row is None:
        raise HTTPException(404, "商品不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/orders")
def list_orders(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Order).order_by(desc(Order.id))
    if status:
        query = query.filter(Order.status == status)
    rows = query.limit(200).all()
    return {"items": [
        {
            "id": o.id, "visitor_id": o.visitor_id, "items": o.items,
            "total": o.total, "status": o.status, "channel": o.channel,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in rows
    ]}


@router.put("/orders/{order_id}")
def update_order(order_id: int, body: OrderStatusIn, db: Session = Depends(get_db)):
    row = db.get(Order, order_id)
    if row is None:
        raise HTTPException(404, "订单不存在")
    if body.status not in ("paid", "shipped", "cancelled"):
        raise HTTPException(400, "非法状态")
    row.status = body.status
    db.commit()
    return {"ok": True}
