"""JWT 签发与校验（3.4 / T0-7 鉴权基础）。

- JWT payload：`user_id`、`role_code`、`password_version`（改密后自增使旧 token 失效，见 4.5）。
- 签发/校验均使用配置项 JWT_SECRET / JWT_EXPIRE / JWT_ALGORITHM（9.3）。
"""
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError


def create_access_token(
    user_id: int,
    role_code: str,
    password_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    """签发 JWT，默认有效期 JWT_EXPIRE 秒（2 小时）。"""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(seconds=settings.JWT_EXPIRE)
    )
    payload = {
        "user_id": user_id,
        "role_code": role_code,
        "password_version": password_version,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码并校验 JWT；失败抛 4011。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("无效的登录凭证") from exc
