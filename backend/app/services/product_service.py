"""商品服务：列表 / 增改 / 下架（商城后端化）。"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.schemas import ProductCreate, ProductUpdate

CATEGORIES = {"embroidery", "accessory", "lacquer", "bamboo"}


def list_public(db: Session) -> list[Product]:
    """游客端：仅上架商品，按 sort 升序。"""
    return list(
        db.scalars(select(Product).where(Product.status == 1).order_by(Product.sort, Product.id))
    )


def list_all(db: Session) -> list[Product]:
    """后台：全量（含下架）。"""
    return list(db.scalars(select(Product).order_by(Product.sort, Product.id)))


def create(db: Session, payload: ProductCreate) -> Product:
    data = payload.model_dump()
    if not data.get("sku"):
        seq = (db.scalar(select(Product.id).order_by(Product.id.desc()).limit(1)) or 0) + 1
        data["sku"] = f"SHOP-{seq:03d}"
    p = Product(**data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update(db: Session, pid: int, payload: ProductUpdate) -> Product:
    p = db.get(Product, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="商品不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


def retire(db: Session, pid: int) -> Product:
    """下架（软删，游客端立即不可见）。"""
    p = db.get(Product, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="商品不存在")
    p.status = 0
    db.commit()
    db.refresh(p)
    return p
