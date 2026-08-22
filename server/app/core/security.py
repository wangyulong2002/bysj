"""JWT 签发与校验 + 文件签名 URL（3.4 / T0-7）。

- JWT payload：`user_id`、`role_code`、`password_version`（改密后自增使旧 token 失效，见 4.5）。
- 签发/校验均使用配置项 JWT_SECRET / JWT_EXPIRE / JWT_ALGORITHM（9.3）。
- 文件签名 URL（B-02）：短期 5 分钟过期，时间戳 + HMAC 防重放。
"""
import hashlib
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


# ===== 文件签名 URL（B-02/P1-16）=====

SIGNED_URL_TTL_SECONDS = 5 * 60  # 5 分钟过期


def create_signed_url_token(file_id: int, expire_ts: int) -> str:
    """生成签名 URL token：HMAC(expire_ts:file_id)，防重放。"""
    import hmac

    msg = f"{expire_ts}:{file_id}"
    return hmac.new(settings.JWT_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def build_signed_file_url(file_id: int) -> str:
    """生成短期签名下载 URL（供小程序 <image> 渲染，B-02）。

    指向直链下载接口 `/api/files/{id}/url-download`（免 JWT，image 组件可用）。
    """
    import time as _time

    expire_ts = int(_time.time()) + SIGNED_URL_TTL_SECONDS
    sig = create_signed_url_token(file_id, expire_ts)
    return f"/api/files/{file_id}/url-download?token={sig}&expires={expire_ts}"


def verify_signed_url_token(file_id: int, token: str, expire_ts: int) -> bool:
    """校验签名 URL：HMAC 一致且未过期（时间戳 + HMAC 防重放，B-02）。"""
    import hmac
    import time as _time

    if int(_time.time()) > expire_ts:
        return False
    expect = hmac.new(settings.JWT_SECRET.encode(),
                      f"{expire_ts}:{file_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, token)
