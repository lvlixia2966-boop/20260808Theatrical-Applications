"""商城路由：游客端商品列表 + 后台商品管理（后端化）。"""
import secrets
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import AdminDep, DbDep
from app.config import settings
from app.models import Product
from app.schemas import ApiResponse, ProductCreate, ProductOut, ProductUpdate
from app.services import product_service

shop_public = APIRouter(prefix="/api/shop", tags=["商城"])
shop_admin = APIRouter(prefix="/api/admin/products", tags=["商城-后台"])

ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


# —— 公开接口（游客端无需登录）——
@shop_public.get("/products", response_model=ApiResponse[list[ProductOut]])
def list_public_products(db: DbDep):
    """游客端：上架商品，按 sort 升序。"""
    return ApiResponse(data=product_service.list_public(db))


# —— 后台管理接口（需登录）——
@shop_admin.get("", response_model=ApiResponse[list[ProductOut]])
def list_all_products(db: DbDep, _: AdminDep):
    return ApiResponse(data=product_service.list_all(db))


@shop_admin.post("", response_model=ApiResponse[ProductOut])
def create_product(payload: ProductCreate, db: DbDep, _: AdminDep):
    return ApiResponse(data=product_service.create(db, payload))


@shop_admin.put("/{pid}", response_model=ApiResponse[ProductOut])
def update_product(pid: int, payload: ProductUpdate, db: DbDep, _: AdminDep):
    return ApiResponse(data=product_service.update(db, pid, payload))


@shop_admin.delete("/{pid}", response_model=ApiResponse[ProductOut])
def retire_product(pid: int, db: DbDep, _: AdminDep):
    """下架（软删，游客端立即不可见）。"""
    return ApiResponse(data=product_service.retire(db, pid))


@shop_admin.post("/{pid}/image", response_model=ApiResponse[ProductOut])
async def upload_product_image(pid: int, db: DbDep, _: AdminDep, file: UploadFile = File(...)):
    """上传商品图：5MB 内 jpg/png/webp，落盘 uploads/products/，返回更新后的商品。"""
    product = db.get(Product, pid)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="商品不存在")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMG_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="仅支持 jpg/png/webp 图片")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="图片不能超过 5MB")
    fname = f"{product.sku}-{secrets.token_hex(4)}{ext}"
    dest = Path(settings.upload_dir) / "products"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / fname).write_bytes(data)
    product.image_url = f"/uploads/products/{fname}"
    db.commit()
    db.refresh(product)
    return ApiResponse(data=ProductOut.model_validate(product))
