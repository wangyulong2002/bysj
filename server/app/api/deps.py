"""认证依赖（3.4、3.5 / T0-7 鉴权基础）。

`get_current_user`：解析 Authorization: Bearer <JWT>，
解码后比对 `ry.sys_user.password_version`（4.5 改密使旧 token 失效），
不一致返回 4011。返回当前登录用户身份。
"""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.core.database import engine
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class UserIdentity:
    """当前登录用户身份（从 JWT + sys_user 校验后得到）。"""

    user_id: int
    role_code: str
    password_version: int


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserIdentity:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("未登录或缺少凭证")

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    role_code = payload.get("role_code")
    token_pw_version = payload.get("password_version")
    if user_id is None or role_code is None or token_pw_version is None:
        raise UnauthorizedError("无效的登录凭证")

    # password_version 比对（4.5）：改密后旧 token 失效
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT password_version FROM ry.sys_user "
                "WHERE user_id = :uid AND del_flag = '0'"
            ),
            {"uid": user_id},
        ).first()
    if row is None:
        raise UnauthorizedError("账号不存在或已停用")
    if int(row[0]) != int(token_pw_version):
        raise UnauthorizedError("登录状态已失效，请重新登录")

    return UserIdentity(user_id=int(user_id), role_code=str(role_code), password_version=int(token_pw_version))


CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]
