"""统一响应封装（设计报告 6.1）：{ code, message, data }，code=0 成功。"""
from typing import Any

from fastapi.responses import JSONResponse


def success(data: Any = None, message: str = "成功") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def success_response(data: Any = None, message: str = "成功") -> JSONResponse:
    return JSONResponse(content={"code": 0, "message": message, "data": data})
