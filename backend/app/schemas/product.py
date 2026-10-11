"""商品相关模式。"""
from pydantic import BaseModel, Field

CATEGORY_PATTERN = r"^(embroidery|accessory|lacquer|bamboo)$"


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    name_en: str = Field("", max_length=128)
    description: str = ""
    description_en: str = ""
    category: str = Field("accessory", pattern=CATEGORY_PATTERN)
    price_cents: int = Field(..., ge=0, description="售价（分）")
    orig_price_cents: int | None = Field(None, ge=0, description="划线原价（分）")
    image_url: str = Field("", max_length=255)
    badge: str = Field("", max_length=32)
    stock: int | None = Field(None, ge=0, description="库存；NULL=不限")
    sort: int = 0
    status: int = Field(1, ge=0, le=1)
    sku: str = Field("", max_length=32, description="留空自动生成 SHOP-xxx")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    name_en: str | None = Field(None, max_length=128)
    description: str | None = None
    description_en: str | None = None
    category: str | None = Field(None, pattern=CATEGORY_PATTERN)
    price_cents: int | None = Field(None, ge=0)
    orig_price_cents: int | None = Field(None, ge=0)
    image_url: str | None = Field(None, max_length=255)
    badge: str | None = Field(None, max_length=32)
    stock: int | None = Field(None, ge=0)
    sort: int | None = None
    status: int | None = Field(None, ge=0, le=1)


class ProductOut(ProductBase):
    id: int

    model_config = {"from_attributes": True}
