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
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import engine
from app.core.errors import (
    AccountLockedError,
    ConflictError,
    ParamError,
    PasswordWrongError,
    RateLimitedError,
    UnauthorizedError,
)
from app.core.login_lock import clear_failures, is_locked, record_failure
from app.core.response import success
from app.core.security import (
    check_django_password,
    create_access_token,
    make_django_password,
)
from app.services.wechat import code2session

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
    """账号密码登录（6.3.1）。

    T1-6：接入登录失败锁定（连续 5 次失败锁 10 分钟，锁定返回 4101）。
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate(client_ip)

    # 锁定检查（T1-6）：锁定期间无论密码是否正确均拒绝
    locked, remaining = is_locked(body.username)
    if locked:
        logger.info("登录被拒：账号锁定中 username=%s", body.username)
        raise AccountLockedError(f"账号已锁定，请 {max(1, (remaining + 59) // 60)} 分钟后再试")

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, username, nick_name, password, role_code, status, "
                "password_version, del_flag "
                "FROM sys_user WHERE username = :u"
            ),
            {"u": body.username},
        ).first()

    # 账号不存在（统一返回 4102 避免账号枚举；同样计入失败锁定）
    if row is None:
        record_failure(body.username)
        logger.info("登录失败：账号不存在 username=%s ip=%s", body.username, client_ip)
        raise PasswordWrongError()

    user_id, username, nick_name, pwd_hash, role_code, status, pw_version, del_flag = row

    if del_flag != "0" or status != "0":
        logger.info("登录失败：账号锁定/停用 username=%s status=%s del=%s", username, status, del_flag)
        raise AccountLockedError("账号已锁定或停用")

    if not check_django_password(body.password, pwd_hash):
        record_failure(body.username)
        logger.info("登录失败：密码错误 username=%s ip=%s", username, client_ip)
        raise PasswordWrongError()

    # 登录成功：清除失败计数与锁定（T1-6）
    clear_failures(body.username)

    # 签发 JWT（6.3.1）
    data = _build_login_data(user_id=int(user_id), username=username,
                             nick_name=nick_name, role_code=role_code, pw_version=int(pw_version))
    logger.info("登录成功 username=%s role=%s", username, role_code)
    return success(data, message="ok")


# ===== 微信授权登录/绑定/解绑（3.4 / T1-4）=====

_USER_COLUMNS = (
    "id, username, nick_name, password, role_code, status, "
    "password_version, del_flag, wechat_openid"
)


class WechatLoginIn(BaseModel):
    """微信授权登录/绑定请求。

    - 仅 `code`：微信登录（openid 已绑定 → 直接登录；未绑定 → need_bind）。
    - `code + username + password`：首次绑定——校验账号密码后绑定 openid 并登录。
    """

    code: str = Field(..., min_length=1, max_length=128, description="微信登录 code")
    username: str | None = Field(None, min_length=1, max_length=30, description="绑定用账号（可选）")
    password: str | None = Field(None, min_length=1, max_length=128, description="绑定用密码（可选）")


def _build_login_data(user_id: int, username: str, nick_name: str | None,
                      role_code: str | None, pw_version: int) -> dict:
    """组装登录响应 data（与 6.3.1 对齐）：token / expires_in / user。"""
    token = create_access_token(user_id=user_id, role_code=role_code or "",
                                password_version=pw_version)
    return {
        "token": token,
        "expires_in": settings.JWT_EXPIRE,
        "user": {
            "user_id": user_id,
            "name": nick_name or username,
            "role_code": role_code or "",
        },
    }


def _find_user_by_openid(openid: str):
    """按 wechat_openid 查有效用户（del_flag=0），返回行或 None。"""
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT {_USER_COLUMNS} FROM sys_user "
                 "WHERE wechat_openid = :o AND del_flag = '0'"),
            {"o": openid},
        ).first()


def _find_user_by_username(username: str):
    """按 username 查用户（含已删除，便于统一判定），返回行或 None。"""
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT {_USER_COLUMNS} FROM sys_user WHERE username = :u"),
            {"u": username},
        ).first()


@router.post("/wechat/login")
def wechat_login(body: WechatLoginIn, request: Request) -> dict:
    """微信授权登录/绑定（3.4 / T1-4）。

    - 微信 code 换 openid（code2session，B-01 可 mock）。
    - openid 已绑定账号 → 直接登录，签发 JWT（含角色）。
    - openid 未绑定 + 请求带账号密码 → 校验账号密码后绑定并登录。
    - openid 未绑定 + 未带账号密码 → 返回 need_bind=true，前端引导绑定。
    - 错误码：4001 凭证无效；4101 账号锁定；4102 密码错误；4091 绑定冲突；4291 限流。
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate(client_ip)

    wx_data = code2session(body.code)
    openid = wx_data["openid"]

    # 场景 1：纯微信登录（不带账号密码）
    if not body.username and not body.password:
        row = _find_user_by_openid(openid)
        if row is None:
            logger.info("微信登录：openid 未绑定，需引导绑定 ip=%s", client_ip)
            return success(
                {"need_bind": True, "token": None, "expires_in": settings.JWT_EXPIRE, "user": None},
                message="该微信尚未绑定账号，请先绑定",
            )
        user_id, username, nick_name, _pwd, role_code, status, pw_version, del_flag, _oid = row
        if del_flag != "0" or status != "0":
            raise AccountLockedError("账号已锁定或停用")
        data = _build_login_data(int(user_id), username, nick_name, role_code, int(pw_version))
        data["need_bind"] = False
        logger.info("微信登录成功 username=%s role=%s", username, role_code)
        return success(data, message="ok")

    # 场景 2：微信绑定（code + 账号密码）
    if not (body.username and body.password):
        raise ParamError("绑定需同时提供账号与密码")
    # 锁定检查（T1-6）
    locked, remaining = is_locked(body.username)
    if locked:
        logger.info("微信绑定被拒：账号锁定中 username=%s", body.username)
        raise AccountLockedError(f"账号已锁定，请 {max(1, (remaining + 59) // 60)} 分钟后再试")
    row = _find_user_by_username(body.username)
    # 账号不存在统一返回 4102（防账号枚举；同样计入失败锁定）
    if row is None:
        record_failure(body.username)
        logger.info("微信绑定：账号不存在 username=%s", body.username)
        raise PasswordWrongError()
    user_id, username, nick_name, pwd_hash, role_code, status, pw_version, del_flag, cur_openid = row

    if del_flag != "0" or status != "0":
        logger.info("微信绑定：账号停用 username=%s", username)
        raise AccountLockedError("账号已锁定或停用")
    if not check_django_password(body.password, pwd_hash):
        record_failure(body.username)
        logger.info("微信绑定：密码错误 username=%s", username)
        raise PasswordWrongError()
    # 该账号已绑定其他微信 → 拒绝（换绑需先解绑）
    if cur_openid and cur_openid != openid:
        raise ConflictError("该账号已绑定其他微信，请先解绑再换绑")

    # 写入 openid（wechat_openid 唯一约束兜底并发：冲突说明已被其他账号绑定）
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE sys_user SET wechat_openid = :o, update_time = NOW() "
                     "WHERE id = :uid AND del_flag = '0'"),
                {"o": openid, "uid": user_id},
            )
    except IntegrityError as exc:
        logger.warning("微信绑定：openid 已被其他账号绑定 username=%s openid=%s", username, openid)
        raise ConflictError("该微信已绑定其他账号") from exc

    clear_failures(body.username)
    data = _build_login_data(int(user_id), username, nick_name, role_code, int(pw_version))
    data["need_bind"] = False
    logger.info("微信绑定成功 username=%s", username)
    return success(data, message="ok")


@router.delete("/wechat/unbind")
def wechat_unbind(user: CurrentUser) -> dict:
    """微信解绑/换绑（3.4 / T1-4）：清除当前用户 wechat_openid。

    - 需登录（4011）。
    - 解绑后该 openid 可重新绑定其他账号（openid 唯一约束解除占用）。
    """
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE sys_user SET wechat_openid = NULL, update_time = NOW() "
                 "WHERE id = :uid"),
            {"uid": user.user_id},
        )
    logger.info("微信解绑成功 user_id=%s", user.user_id)
    return success(None, message="已解绑微信")


# ===== 修改密码（4.5 / T1-5）=====


class ChangePasswordIn(BaseModel):
    """修改密码请求（4.5 / T1-5）。"""

    old_password: str = Field(..., min_length=1, max_length=128, description="原密码")
    new_password: str = Field(..., min_length=6, max_length=32, description="新密码（6~32 位）")


@router.put("/password")
def change_password(body: ChangePasswordIn, user: CurrentUser) -> dict:
    """修改密码（4.5 / T1-5）。

    - 校验原密码（错误 4102）→ 写入新密码（Django PBKDF2 格式）。
    - `password_version` 自增 → 已签发 JWT 立即失效（deps.get_current_user 比对版本，4011）。
    - 前端改密成功后清理本地 token 重新登录。
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT password FROM sys_user WHERE id = :uid AND del_flag = '0'"),
            {"uid": user.user_id},
        ).first()
    if row is None:
        raise UnauthorizedError("账号不存在或已停用")

    if not check_django_password(body.old_password, row[0]):
        logger.info("改密失败：原密码错误 user_id=%s", user.user_id)
        raise PasswordWrongError("原密码错误")
    if body.old_password == body.new_password:
        raise ParamError("新密码不能与原密码相同")

    new_hash = make_django_password(body.new_password)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE sys_user SET password = :p, password_version = password_version + 1, "
                 "update_time = NOW() WHERE id = :uid"),
            {"p": new_hash, "uid": user.user_id},
        )
    logger.info("改密成功 user_id=%s password_version 已自增", user.user_id)
    return success(None, message="密码修改成功，请重新登录")
