"""认证接口（3.4 / T1-2）：POST /api/auth/login。

- 校验 sys_user 账号密码（Django PBKDF2，T1-2）。
- 签发 JWT：payload 含 user_id / role_code / password_version。
- 返回结构与 6.3.1 一致：{ token, expires_in, user }。
- 错误码：4011 未登录/账号不存在；4101 账号锁定；4102 密码错误；4291 登录限流（B-13）。
- 登录不要求 Idempotency-Key（P0-3）。
"""
import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.errors import (
    AccountLockedError,
    PasswordWrongError,
    RateLimitedError,
    UnauthorizedError,
)
from app.core.response import success
from app.core.security import check_django_password, create_access_token

logger = logging.getLogger("campus.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    """登录请求（6.3.1）。"""

    username: str = Field(..., min_length=1, max_length=30, description="账号")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserOut(BaseModel):
    """登录响应用户信息（6.3.1）。"""

    user_id: int
    name: str
    role_code: str


def _check_login_rate(ip: str) -> None:
    """登录 IP 限流（B-13，LOGIN_RATE_PER_MIN 次/分钟）；Redis 不可用时放行并告警。"""
    limit = getattr(settings, "LOGIN_RATE_PER_MIN", 5) or 5
    try:
        from app.core.redis_client import redis_client

        key = f"login_rate:{ip}"
        n = redis_client.incr(key)
        if n == 1:
            redis_client.expire(key, 60)
        if n > limit:
            raise RateLimitedError("登录过于频繁，请稍后再试")
    except RateLimitedError:
        raise
    except Exception:  # noqa: BLE001 — Redis 不可用放行
        logger.warning("登录限流 Redis 不可用，本次放行")


@router.post("/login")
def login(body: LoginIn, request: Request) -> dict:
    """账号密码登录（6.3.1）。"""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate(client_ip)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, username, nick_name, password, role_code, status, "
                "password_version, del_flag "
                "FROM sys_user WHERE username = :u"
            ),
            {"u": body.username},
        ).first()

    # 账号不存在（统一返回 4102 避免账号枚举）
    if row is None:
        logger.info("登录失败：账号不存在 username=%s ip=%s", body.username, client_ip)
        raise PasswordWrongError()

    user_id, username, nick_name, pwd_hash, role_code, status, pw_version, del_flag = row

    if del_flag != "0" or status != "0":
        logger.info("登录失败：账号锁定/停用 username=%s status=%s del=%s", username, status, del_flag)
        raise AccountLockedError("账号已锁定或停用")

    if not check_django_password(body.password, pwd_hash):
        logger.info("登录失败：密码错误 username=%s ip=%s", username, client_ip)
        raise PasswordWrongError()

    # 签发 JWT（6.3.1）
    token = create_access_token(user_id=int(user_id), role_code=str(role_code),
                                password_version=int(pw_version))
    logger.info("登录成功 username=%s role=%s", username, role_code)
    return success(
        {
            "token": token,
            "expires_in": settings.JWT_EXPIRE,
            "user": {
                "user_id": int(user_id),
                "name": nick_name or username,
                "role_code": role_code,
            },
        },
        message="ok",
    )
