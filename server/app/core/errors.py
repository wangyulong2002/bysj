"""统一错误码与业务异常（设计报告 6.1）。

错误码：0 成功、4001 参数、4011 未登录、4031 无权限、4032 越权、
4091 冲突并发、4291 限流、5000 服务异常。
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0
    PARAM_ERROR = 4001
    UNAUTHORIZED = 4011
    FORBIDDEN = 4031
    FORBIDDEN_DATA = 4032
    CONFLICT = 4091
    RATE_LIMITED = 4291
    SERVER_ERROR = 5000


ERROR_MESSAGES = {
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.FORBIDDEN: "无操作权限",
    ErrorCode.FORBIDDEN_DATA: "无权访问该数据",
    ErrorCode.CONFLICT: "数据冲突或并发更新，请刷新后重试",
    ErrorCode.RATE_LIMITED: "请求过于频繁，请稍后再试",
    ErrorCode.SERVER_ERROR: "服务异常，请稍后再试",
}


class BizError(Exception):
    """业务异常：携带统一错误码，由全局异常处理器转为响应。"""

    def __init__(self, code: ErrorCode | int = ErrorCode.SERVER_ERROR,
                 message: str | None = None, data=None):
        self.code = int(code)
        self.message = message or ERROR_MESSAGES.get(ErrorCode(code), "未知错误")
        self.data = data
        super().__init__(self.message)


class ParamError(BizError):
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.PARAM_ERROR, message)


class UnauthorizedError(BizError):
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.UNAUTHORIZED, message)


class ForbiddenError(BizError):
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.FORBIDDEN, message)


class ForbiddenDataError(BizError):
    """越权（数据范围不匹配，防 IDOR）。"""
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.FORBIDDEN_DATA, message)


class ConflictError(BizError):
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.CONFLICT, message)


class RateLimitedError(BizError):
    def __init__(self, message: str = None):
        super().__init__(ErrorCode.RATE_LIMITED, message)
