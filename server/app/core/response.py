"""统一响应封装（设计报告 6.1）：{ code, message, data }，code=0 成功。"""
from typing import Any

from fastapi.responses import JSONResponse


def success(data: Any = None, message: str = "成功") -> dict:
    """构造成功响应体：{ code: 0, message, data }（6.1）。"""
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    """构造失败响应体：{ code, message, data }（错误码见 6.1）。"""
    return {"code": code, "message": message, "data": data}


def success_response(data: Any = None, message: str = "成功") -> JSONResponse:
    """构造成功响应（JSONResponse 形式），用于直接返回。"""
    return JSONResponse(content={"code": 0, "message": message, "data": data})
