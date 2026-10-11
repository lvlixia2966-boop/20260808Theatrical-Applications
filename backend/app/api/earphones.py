"""耳机路由：后台管理 + 前端扫码查询/校验。"""
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminDep, DbDep
from app.models import Earphone
from app.schemas import (
    ApiResponse,
    EarphoneCreate,
    EarphoneOut,
    EarphoneQueryRequest,
    EarphoneUpdate,
    PageResult,
)
from app.services import earphone_service

router = APIRouter(prefix="/api/earphones", tags=["耳机"])


@router.get("", response_model=ApiResponse[PageResult[EarphoneOut]])
def list_earphones(
    db: DbDep,
    _: AdminDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Earphone).order_by(Earphone.id.desc())
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.post("", response_model=ApiResponse[EarphoneOut])
def create_earphone(payload: EarphoneCreate, db: DbDep, _: AdminDep):
    earphone = Earphone(**payload.model_dump())
    db.add(earphone)
    db.commit()
    db.refresh(earphone)
    return ApiResponse(message="新增成功", data=earphone)


@router.put("/{earphone_id}", response_model=ApiResponse[EarphoneOut])
def update_earphone(earphone_id: int, payload: EarphoneUpdate, db: DbDep, _: AdminDep):
    earphone = db.get(Earphone, earphone_id)
    if not earphone:
        return ApiResponse(code=404, message="耳机不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(earphone, key, value)
    db.commit()
    db.refresh(earphone)
    return ApiResponse(message="更新成功", data=earphone)


@router.delete("/{earphone_id}", response_model=ApiResponse)
def delete_earphone(earphone_id: int, db: DbDep, _: AdminDep):
    earphone = db.get(Earphone, earphone_id)
    if not earphone:
        return ApiResponse(code=404, message="耳机不存在")
    db.delete(earphone)
    db.commit()
    return ApiResponse(message="删除成功")


@router.get("/{qr_code_id}/check", response_model=ApiResponse)
def check_by_qr(
    qr_code_id: str,
    db: DbDep,
    device_name: str = "",
    serial_number: str = "",
):
    """前端扫码进入：校验耳机身份与蓝牙连接信息。"""
    req = EarphoneQueryRequest(device_name=device_name, serial_number=serial_number)
    data = earphone_service.check_earphone(db, qr_code_id, req)
    return ApiResponse(data={
        "earphone": EarphoneOut.model_validate(data["earphone"]).model_dump(),
        "bluetooth": data["bluetooth"],
    })