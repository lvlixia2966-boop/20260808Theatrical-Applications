"""节目服务：增删改查与上下架。"""
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Program
from app.schemas.program import ProgramCreate, ProgramUpdate


def list_programs(db: Session, page: int, page_size: int, only_online: bool = False):
    query = select(Program)
    if only_online:
        query = query.where(Program.is_online.is_(True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Program.sort_order.asc(), Program.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return total, items


def get_program(db: Session, program_id: int) -> Program:
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="节目不存在")
    return program


def create_program(db: Session, payload: ProgramCreate) -> Program:
    program = Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def update_program(db: Session, program_id: int, payload: ProgramUpdate) -> Program:
    program = get_program(db, program_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(program, key, value)
    db.commit()
    db.refresh(program)
    return program


def delete_program(db: Session, program_id: int) -> None:
    program = get_program(db, program_id)
    db.delete(program)
    db.commit()