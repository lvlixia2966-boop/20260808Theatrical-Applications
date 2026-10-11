"""耳机模型：登记每副可出租的蓝牙耳机及其身份标识。"""
from sqlalchemy import String, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EarphoneStatus(str, Enum):
    AVAILABLE = "available"   # 可出租
    RENTED = "rented"         # 已出租/使用中
    OFFLINE = "offline"       # 下架/停用


class Earphone(Base):
    __tablename__ = "earphones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 唯一身份：二维码内容（扫码进入页面的 earphone_id）
    qr_code_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 蓝牙识别名（Web Bluetooth 扫描到的设备名）
    device_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 厂商自定义广播数据中的设备序列号（可选，强校验用）
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 厂商自定义广播数据的 Service UUID 前缀（可选）
    service_uuid: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    # 当前绑定的讲解节目标题（可选，用于展示）
    bound_program_title: Mapped[str] = mapped_column(String(128), nullable=False, default="")