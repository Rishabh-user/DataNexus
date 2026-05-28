from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class StatusResponse(BaseModel):
    status: str
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool
