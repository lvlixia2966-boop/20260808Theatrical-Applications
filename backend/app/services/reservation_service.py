"""预约服务：创建与更新预约（文本/语音讲解）。"""
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Program, Reservation
from app.schemas.reservation import ReservationCreate, ReservationUpdate


def create_reservation(db: Session, payload: ReservationCreate) -> Reservation:
    reservation = Reservation(**payload.model_dump())
    # 若指定了节目，自动填充节目标题与内容快照
    if payload.program_id:
        program = db.get(Program, payload.program_id)
        if program:
            reservation.program_title = program.title
            reservation.text_content = payload.text_content or program.text_content
            reservation.voice_content = payload.voice_content or program.voice_content
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def list_reservations(db: Session, page: int, page_size: int, status_filter: str | None = None):
    query = select(Reservation)
    if status_filter:
        query = query.where(Reservation.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Reservation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return total, items


def get_reservation(db: Session, reservation_id: int) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    return reservation


def update_reservation(db: Session, reservation_id: int, payload: ReservationUpdate) -> Reservation:
    reservation = get_reservation(db, reservation_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(reservation, key, value)
    db.commit()
    db.refresh(reservation)
    return reservation