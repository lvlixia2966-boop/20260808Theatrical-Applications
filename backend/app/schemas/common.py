"""通用响应模式。"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PageResult(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    items: list[T]