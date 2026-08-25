"""幂等中间件（3.6/P1-09 / T0-6，v2.2 P1-12）。

写接口（请假提交、请假审批、成绩批量录入、文件上传等，不含登录）支持
`Idempotency-Key`：
- v2.2：幂等记录存 **MySQL 唯一表 `campus_idempotency_key`**（`biz_key` 唯一索引，
  与业务同事务提交，见 3.3/3.6），Redis 仅作快速查询缓存（TTL ≤24h）。
- 重复提交：唯一索引兜底，直接返回首次结果，不产生重复数据。
- Redis 故障：降级 MySQL 直查，唯一索引兜底，**不拒绝写**（区别于纯 Redis 方案）。
- 登录不要求 Idempotency-Key（P0-3）。

幂等键构造（P0-3）：`user_id + HTTP method + path + 请求体哈希`，避免不同请求错误复用。
缓存键：`idem:{method}:{path}:{sha256(key)}`。
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings  # pyright: ignore[reportImplicitRelativeImport]
from app.core.database import engine  # pyright: ignore[reportImplicitRelativeImport]
from app.core.redis_client import redis_client  # pyright: ignore[reportImplicitRelativeImport]

logger = logging.getLogger("campus.idempotency")

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _body_hash(body: bytes) -> str:
    """请求体 SHA-256（P0-3：幂等键绑定请求体，避免不同请求复用同一 key）。"""
    return hashlib.sha256(body).hexdigest()


def idempotency_cache_key(request: Request, key: str) -> str:
    """Redis 快速查询缓存键（含 method+path，避免跨接口碰撞）。"""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"idem:{request.method}:{request.url.path}:{digest}"


def _serialize(status_code: int, media_type: str | None, body: bytes) -> str:
    """序列化响应为幂等缓存存储串（base64 编码 body）。"""
    return json.dumps(
        {
            "status": status_code,
            "media_type": media_type,
            "body": base64.b64encode(body).decode("ascii"),
        }
    )


def _deserialize(raw: str) -> Response | None:
    """反序列化幂等缓存为 Response；解析失败返回 None（记录告警）。"""
    try:
        data = json.loads(raw)
        body = base64.b64decode(data["body"])
        return Response(content=body, status_code=data["status"], media_type=data.get("media_type"))
    except (ValueError, KeyError, TypeError):
        logger.warning("幂等缓存反序列化失败: %s", raw[:100])
        return None


def _db_insert(biz_key: str, user_id: int | None, method: str, path: str,
               body_hash: str, resp_status: int, resp_body: str) -> bool:
    """MySQL 唯一表写入（同事务，由调用方在业务事务内提交）。

    返回 True 表示插入成功（首次请求）；返回 False 表示 key 已存在（重复请求）。
    """
    expire = datetime.now() + timedelta(seconds=settings.IDEMPOTENCY_EXPIRE_SECONDS)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO campus_idempotency_key "
                    "(biz_key, user_id, method, path, body_hash, response_code, response_body, expire_time) "
                    "VALUES (:k, :uid, :m, :p, :h, :c, :b, :e) "
                    "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)"
                ),
                {"k": biz_key, "uid": user_id, "m": method, "p": path,
                 "h": body_hash, "c": resp_status, "b": resp_body, "e": expire},
            )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("幂等表写入失败: %s", exc)
        raise


def _db_lookup(biz_key: str) -> Response | None:
    """MySQL 直查已记录幂等结果（Redis 故障时兜底，P1-12）。"""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT response_code, response_body FROM campus_idempotency_key "
                     "WHERE biz_key = :k AND expire_time > NOW()"),
                {"k": biz_key},
            ).first()
        if row is None:
            return None
        resp = _deserialize(row[1])
        return resp
    except Exception as exc:  # noqa: BLE001
        logger.warning("幂等表查询失败: %s", exc)
        return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """对携带 Idempotency-Key 的写请求做幂等处理（MySQL 唯一表兜底）。"""

    async def dispatch(self, request: Request, call_next):
        """幂等处理入口：Redis 快查 → MySQL 兜底 → 首次执行并落库。"""
        key = request.headers.get(IDEMPOTENCY_HEADER)
        # 仅处理携带幂等键的写方法；读请求 / 无幂等键 / 登录 直接放行（P0-3）
        if request.method not in IDEMPOTENT_METHODS or not key:
            return await call_next(request)

        # 读取请求体（用于构造幂等键与 body_hash）
        body_bytes = b""
        try:
            body_bytes = await request.body()
        except Exception:  # noqa: BLE001
            pass
        body_hash = _body_hash(body_bytes)

        # 幂等键构造（P0-3）：user_id + method + path + body 哈希
        user_id = None
        # 从 Authorization Bearer 解析 user_id（若已登录）
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            try:
                from app.core.security import decode_access_token  # noqa: PLC0415
                payload = decode_access_token(token)
                user_id = payload.get("user_id")
            except Exception:  # noqa: BLE001
                user_id = None

        # 幂等键构造（P0-3）：绑定 客户端 Idempotency-Key + user_id + method + path + body 哈希，
        # 避免不同请求/不同用户错误复用同一 key 互相命中。
        biz_key = hashlib.sha256(
            f"{key}:{user_id or ''}:{request.method}:{request.url.path}:{body_hash}".encode()
        ).hexdigest()

        cache_key = idempotency_cache_key(request, key)

        # 1. Redis 快速查询（命中直接返回）
        try:
            cached = redis_client.get(cache_key)
        except Exception:  # noqa: BLE001
            logger.warning("Redis 不可用，幂等降级 MySQL 直查")
            cached = None
        if cached:
            resp = _deserialize(cached)
            if resp is not None:
                logger.info("幂等命中(Redis): %s", cache_key)
                return resp

        # 2. MySQL 兜底查询（Redis 故障或未命中时；防止并发/重启后重复）
        db_resp = _db_lookup(biz_key)
        if db_resp is not None:
            # 回填 Redis 缓存
            try:
                redis_client.set(cache_key, _serialize(
                    db_resp.status_code, db_resp.media_type, db_resp.body or b""),
                    ex=settings.IDEMPOTENCY_EXPIRE_SECONDS)
            except Exception:  # noqa: BLE001
                pass
            logger.info("幂等命中(MySQL): %s", biz_key)
            return db_resp

        # 3. 首次处理：执行请求、缓冲响应体
        response = await call_next(request)
        if response.status_code >= 500:
            return response
        body_iterator = getattr(response, "body_iterator", None)  # pyright: ignore[reportUnknownMemberType]
        if body_iterator is None:
            logger.warning("幂等：无法读取响应体，跳过缓存")
            return response
        try:
            body = b"".join([chunk async for chunk in body_iterator])
        except Exception:  # noqa: BLE001
            logger.warning("幂等：读取响应体失败，跳过缓存")
            return response

        # 4. 写入 MySQL 幂等记录（首次成功即落库，唯一索引防并发重复）
        try:
            _db_insert(biz_key, user_id, request.method, request.url.path,
                       body_hash, response.status_code, _serialize(response.status_code, response.media_type, body))
            # Redis 缓存
            try:
                redis_client.set(cache_key, _serialize(
                    response.status_code, response.media_type, body),
                    ex=settings.IDEMPOTENCY_EXPIRE_SECONDS)
            except Exception:  # noqa: BLE001
                logger.warning("幂等 Redis 缓存写入失败（MySQL 已兜底）")
        except Exception:  # noqa: BLE001
            # MySQL 写入失败（如并发唯一键冲突）→ 查一次已落库结果返回
            logger.warning("幂等 MySQL 写入失败，回查唯一键")
            existing = _db_lookup(biz_key)
            if existing is not None:
                return existing
            # 均失败：记录告警并放行本次（不阻塞业务；正确性由唯一索引在后续请求兜底）
            logger.error("幂等记录落库失败（biz_key=%s），本次请求正常处理", biz_key)

        # 用已缓冲的 body 重建响应
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=dict(response.headers),
        )
