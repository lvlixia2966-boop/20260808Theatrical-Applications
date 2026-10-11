"""耳机服务：登记、校验、扫码查询。"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bluetooth import verify_earphone_device
from app.models import Earphone
from app.schemas.earphone import EarphoneQueryRequest


def get_by_qr(db: Session, qr_code_id: str) -> Earphone:
    earphone = db.scalar(select(Earphone).where(Earphone.qr_code_id == qr_code_id))
    if not earphone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该耳机，请确认二维码")
    return earphone


def check_earphone(db: Session, qr_code_id: str, payload: EarphoneQueryRequest) -> dict:
    """扫码进入：校验耳机身份与蓝牙连接信息。"""
    earphone = get_by_qr(db, qr_code_id)
    if earphone.status == "offline":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该耳机已停用，请联系工作人员")

    ble = verify_earphone_device(
        earphone,
        reported_device_name=payload.device_name,
        reported_mfg_data=payload.serial_number or payload.mfg_data,
    )
    return {
        "earphone": earphone,
        "bluetooth": ble,
    }