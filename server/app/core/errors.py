"""统一错误码与业务异常（设计报告 6.1，v2.2 B-07/P2-21）。

全局错误码：0 成功、4001 参数、4011 未登录、4031 无权限、4032 越权、
4091 冲突并发、4291 限流、5000 服务异常、5001 上游 LLM 不可用、5002 向量检索不可用。
业务错误码：4101 账号锁定、4102 密码错误、4201 教学班不存在、
4301 请假状态不可变更、4401 成绩未发布。
采用 HTTP status + code 双层映射（HTTP 4xx/5xx + 业务 code，见 6.1）。
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
    LLM_UNAVAILABLE = 5001   # B-07：上游 LLM 服务不可用
    VECTOR_UNAVAILABLE = 5002  # B-07：向量检索不可用

    # 业务错误码（P2-21）
    ACCOUNT_LOCKED = 4101      # 账号锁定
    PASSWORD_WRONG = 4102      # 密码错误
    OFFERING_NOT_FOUND = 4201  # 教学班不存在
    LEAVE_STATUS_INVALID = 4301  # 请假状态不可变更
    SCORE_NOT_PUBLISHED = 4401  # 成绩未发布


ERROR_MESSAGES = {
    ErrorCode.PARAM_ERROR: "参数错误",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.FORBIDDEN: "无操作权限",
    ErrorCode.FORBIDDEN_DATA: "无权访问该数据",
    ErrorCode.CONFLICT: "数据冲突或并发更新，请刷新后重试",
    ErrorCode.RATE_LIMITED: "请求过于频繁，请稍后再试",
    ErrorCode.SERVER_ERROR: "服务异常，请稍后再试",
    ErrorCode.LLM_UNAVAILABLE: "AI 服务暂不可用，请稍后再试",
    ErrorCode.VECTOR_UNAVAILABLE: "智能检索暂不可用，请稍后再试",
    ErrorCode.ACCOUNT_LOCKED: "账号已锁定，请稍后再试",
    ErrorCode.PASSWORD_WRONG: "用户名或密码错误",
    ErrorCode.OFFERING_NOT_FOUND: "教学班不存在",
    ErrorCode.LEAVE_STATUS_INVALID: "请假状态不可变更",
    ErrorCode.SCORE_NOT_PUBLISHED: "成绩尚未发布",
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


class LLMUnavailableError(BizError):
    """上游 LLM 服务不可用（B-07/5001）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.LLM_UNAVAILABLE, message)


class VectorUnavailableError(BizError):
    """向量检索不可用（B-07/5002）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.VECTOR_UNAVAILABLE, message)


class AccountLockedError(BizError):
    """账号锁定（P2-21/4101）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.ACCOUNT_LOCKED, message)


class PasswordWrongError(BizError):
    """密码错误（P2-21/4102）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.PASSWORD_WRONG, message)


class OfferingNotFoundError(BizError):
    """教学班不存在（P2-21/4201）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.OFFERING_NOT_FOUND, message)


class LeaveStatusInvalidError(BizError):
    """请假状态不可变更（P2-21/4301）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.LEAVE_STATUS_INVALID, message)


class ScoreNotPublishedError(BizError):
    """成绩未发布（P2-21/4401）。"""

    def __init__(self, message: str = None):
        super().__init__(ErrorCode.SCORE_NOT_PUBLISHED, message)
