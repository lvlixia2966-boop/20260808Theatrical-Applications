"""ORM 模型统一导出，确保 create_all 前全部注册。"""
from app.models.admin import AdminUser
from app.models.content import Region, ScenicArea, Spot, TourRoute, RouteStop
from app.models.product import Order, Product
from app.models.settings import AppSetting

__all__ = [
    "AdminUser", "Region", "ScenicArea", "Spot", "TourRoute", "RouteStop",
    "AppSetting", "Product", "Order",
]
