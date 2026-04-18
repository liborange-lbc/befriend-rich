from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


def ok(data: Any = None, meta: dict[str, Any] | None = None) -> dict:
    return {"success": True, "data": data, "error": None, "meta": meta}


def fail(error: str, status_code: int = 400) -> dict:
    return {"success": False, "data": None, "error": error}
