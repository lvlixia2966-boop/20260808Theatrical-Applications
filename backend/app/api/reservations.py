"""预约路由：后台管理 + 前端创建。"""
from fastapi import APIRouter, Query

from app.api.deps import AdminDep, DbDep
from app.schemas import ApiResponse, PageResult, ReservationCreate, ReservationOut, ReservationUpdate
from app.services import reservation_service

router = APIRouter(prefix="/api/reservations", tags=["预约"])


@router.post("", response_model=ApiResponse[ReservationOut])
def create_reservation(payload: ReservationCreate, db: DbDep):
    """前端扫码用户预约文本/语音讲解。"""
    reservation = reservation_service.create_reservation(db, payload)
    return ApiResponse(message="预约成功", data=reservation)


@router.get("", response_model=ApiResponse[PageResult[ReservationOut]])
def list_reservations(
    db: DbDep,
    _: AdminDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    total, items = reservation_service.list_reservations(db, page, page_size, status)
    return ApiResponse(data=PageResult(total=total, page=page, page_size=page_size, items=items))


@router.put("/{reservation_id}", response_model=ApiResponse[ReservationOut])
def update_reservation(reservation_id: int, payload: ReservationUpdate, db: DbDep, _: AdminDep):
    reservation = reservation_service.update_reservation(db, reservation_id, payload)
    return ApiResponse(message="更新成功", data=reservation)