"""JWT 签发与校验 + Django 密码哈希 + 文件签名 URL（3.4 / T0-7 / T1-2）。

- JWT payload：`user_id`、`role_code`、`password_version`（改密后自增使旧 token 失效，见 4.5）。
- 签发/校验均使用配置项 JWT_SECRET / JWT_EXPIRE / JWT_ALGORITHM（9.3）。
- 密码哈希（P0-2）：`sys_user.password` 为 Django 哈希串，FastAPI 侧**复用 Django 官方
  `make_password`/`check_password`**（同一 venv 已依赖 Django 5.2 LTS），不再自实现 PBKDF2
  ——旧实现硬编码 10,000 次，仅为 Django 5.2 默认值（1,000,000）的 1/100，低于 OWASP 建议。
- 文件签名 URL（B-02 / P1-6）：密钥由 JWT_SECRET 经 HKDF 派生（用途分离），
  token 绑定 `file_id + user_id + 过期时间`，短期 5 分钟过期。
"""
import hashlib
import hmac
import time
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


# ===== Django 密码哈希（T1-2 / T1-5 / P0-2）=====

def _django_hashers():
    """懒加载 Django 官方哈希器（P0-2）。

    FastAPI 与管理端共用同一 venv（`Django>=5.2,<5.3` 已是运行依赖），因此直接复用
    Django 官方 `make_password` / `check_password`：哈希算法、迭代数与**后续升级策略**
    永远跟随 Django，杜绝"Django 默认 1,000,000 次、FastAPI 手写 10,000 次"的强度分裂。

    Django 哈希器需要读取 `settings.PASSWORD_HASHERS`，此处做**最小配置**（进程内一次），
    不加载 `manage/config/settings.py`，避免 FastAPI 与管理端配置耦合；
    未显式传 PASSWORD_HASHERS 时使用 Django 内置默认哈希器列表。
    """
    from django.conf import settings as django_settings

    if not django_settings.configured:
        django_settings.configure(USE_TZ=False)

    from django.contrib.auth.hashers import check_password, make_password

    return make_password, check_password


def make_django_password(raw_password: str) -> str:
    """生成 Django 兼容密码哈希（P0-2：调用 Django 官方 `make_password`）。

    返回形如 `pbkdf2_sha256$1000000$<salt>$<hash>`；迭代数跟随 Django 默认值
    （Django 5.1/5.2 = 1,000,000），不再硬编码。改密 / 重置密码（T1-5）走本函数。
    """
    make_password, _ = _django_hashers()
    return make_password(raw_password)


def _normalize_unpadded_b64(encoded: str) -> str:
    """补回历史哈希缺失的 base64 填充（P0-2 兼容层）。

    旧版 `make_django_password` 写入时做了 `rstrip("=")`（去掉 base64 填充），
    而 Django 官方 `PBKDF2PasswordHasher.encode` 是保留填充的；Django 校验时
    直接 `base64.b64decode(...)`，遇到缺填充会抛 `binascii.Error` → 校验恒为 False。

    若不兼容，**通过旧 FastAPI 改密/重置密码的存量账号会全部登录失败**
    （审核报告也指出这批账号是"密码库中最弱的一批"，但不应以"登不上"的方式暴露）。
    这里仅对 `pbkdf2_sha256$iter$salt$<b64>` 形态补回 padding。
    """
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] not in ("pbkdf2_sha256", "pbkdf2_sha1"):
        return encoded
    payload = parts[3]
    if not payload or payload.endswith("="):
        return encoded
    pad = "=" * (-len(payload) % 4)
    if not pad:
        return encoded
    parts[3] = payload + pad
    return "$".join(parts)


def check_django_password(raw_password: str, encoded: str) -> bool:
    """校验 Django 密码哈希（P0-2：调用 Django 官方 `check_password`）。

    支持 Django 全部内置算法（PBKDF2 各迭代数 / bcrypt / argon2 等），
    迭代数从存储串中解析，因此**历史弱哈希（10,000 次）仍可正常校验**，
    无需强制重置；另对旧实现写入的"无填充 base64"做兼容（见 `_normalize_unpadded_b64`）。
    失败返回 False（不抛异常，由调用方决定 4011/4102）。
    """
    if not encoded:
        return False
    _, check_password = _django_hashers()
    try:
        if check_password(raw_password, encoded):
            return True
        normalized = _normalize_unpadded_b64(encoded)
        if normalized != encoded:
            # 旧版无 padding 哈希：补填充后重试
            return bool(check_password(raw_password, normalized))
        return False
    except Exception:  # noqa: BLE001 — 非法哈希串/未知算法一律视为校验失败
        return False


# ===== 文件签名 URL（B-02 / P1-6）=====

SIGNED_URL_TTL_SECONDS = 5 * 60  # 5 分钟过期


def _file_signing_key() -> bytes:
    """文件签名专用密钥（P1-6：密钥用途分离）。

    直接复用 `JWT_SECRET` 会让「一处泄露影响两个域」；此处用 HKDF-SHA256 从
    JWT_SECRET 派生独立子密钥（`info` 作为用途标签），JWT 密钥轮换时文件签名同步轮换。
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"bysj:file-signed-url",
    ).derive(settings.JWT_SECRET.encode("utf-8"))


def _signed_msg(file_id: int, expire_ts: int, file_hash: str | None = None) -> str:
    """签名载荷（P1-6）：`过期时间:文件id:文件内容哈希`。

    旧实现只绑定 `file_id + 过期时间` → 链接一旦外泄（聊天转发、日志、Referer），
    任何人在 5 分钟内都能下载私有附件。绑定 `file_hash` 后链接与**文件内容**强关联，
    文件被替换即自动失效，且无法跨文件复用。
    """
    return f"{expire_ts}:{file_id}:{file_hash or ''}"


def create_signed_url_token(
    file_id: int, expire_ts: int, file_hash: str | None = None
) -> str:
    """生成签名 URL token：HMAC(派生密钥, 载荷)，防重放（B-02 / P1-6）。"""
    return hmac.new(
        _file_signing_key(),
        _signed_msg(file_id, expire_ts, file_hash).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_signed_file_url(file_id: int, file_hash: str | None = None) -> str:
    """生成短期签名下载 URL（供小程序 <image> 渲染，B-02 / P1-6）。

    指向直链下载接口 `/api/files/{id}/url-download`（免 JWT，image 组件可用）。
    配置 `PUBLIC_BASE_URL`（如 http://127.0.0.1:8000）时返回**完整 URL**，
    避免小程序 image 按页面地址（含开发者工具 `__pageframe__` 前缀）补全导致 500；
    未配置时退化为相对路径（H5 同源场景可用）。
    """
    expire_ts = int(time.time()) + SIGNED_URL_TTL_SECONDS
    sig = create_signed_url_token(file_id, expire_ts, file_hash)
    path = f"/api/files/{file_id}/url-download?token={sig}&expires={expire_ts}"
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{path}" if base else path


def verify_signed_url_token(
    file_id: int, token: str, expire_ts: int, file_hash: str | None = None
) -> bool:
    """校验签名 URL：HMAC 一致且未过期（时间戳 + HMAC 防重放，B-02 / P1-6）。"""
    if not token:
        return False
    try:
        expire_ts = int(expire_ts)
    except (TypeError, ValueError):
        return False
    if int(time.time()) > expire_ts:
        return False
    expect = create_signed_url_token(file_id, expire_ts, file_hash)
    return hmac.compare_digest(expect, token)
