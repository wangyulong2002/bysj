"""幂等中间件（3.6/P1-09 / T0-6）。

写接口（登录、成绩录入、请假提交、请假审批）支持 `Idempotency-Key` 请求头：
- 服务端以 Redis 记录已处理 key，重复提交直接返回首次结果，防止网络重试导致重复数据。
- Redis 故障时降级为直通（9.7），不阻塞业务。

缓存键：`idem:{method}:{path}:{sha256(key)}`，避免不同接口间的 key 碰撞。
TTL 由配置 `IDEMPOTENCY_EXPIRE_SECONDS` 控制（默认 24h）。
"""
import base64
import hashlib
import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings  # pyright: ignore[reportImplicitRelativeImport]
from app.core.redis_client import redis_client  # pyright: ignore[reportImplicitRelativeImport]

logger = logging.getLogger("campus.idempotency")

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def idempotency_cache_key(request: Request, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"idem:{request.method}:{request.url.path}:{digest}"


def _serialize(response: Response, body: bytes) -> str:
    """将响应序列化为 JSON 字符串（body 以 base64 保存，兼容非 JSON 响应）。"""
    return json.dumps(
        {
            "status": response.status_code,
            "media_type": response.media_type,
            "body": base64.b64encode(body).decode("ascii"),
        }
    )


def _deserialize(raw: str) -> Response | None:
    try:
        data = json.loads(raw)
        body = base64.b64decode(data["body"])
        return Response(content=body, status_code=data["status"], media_type=data.get("media_type"))
    except (ValueError, KeyError, TypeError):
        logger.warning("幂等缓存反序列化失败: %s", raw[:100])
        return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """对携带 Idempotency-Key 的写请求做幂等处理。"""

    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(IDEMPOTENCY_HEADER)
        # 仅处理携带幂等键的写方法；读请求 / 无幂等键直接放行
        if request.method not in IDEMPOTENT_METHODS or not key:
            return await call_next(request)

        cache_key = idempotency_cache_key(request, key)

        # 1. 命中缓存：直接返回首次结果
        try:
            cached = redis_client.get(cache_key)
        except Exception:  # noqa: BLE001 — Redis 故障降级直通（9.7）
            logger.warning("Redis 不可用，幂等降级为直通")
            cached = None
        if cached:
            resp = _deserialize(cached)
            if resp is not None:
                logger.info("幂等命中: %s", cache_key)
                return resp

        # 2. 首次处理：执行请求、缓冲响应体并缓存
        response = await call_next(request)
        if response.status_code >= 500:
            return response
        body_iterator = getattr(response, "body_iterator", None)  # pyright: ignore[reportUnknownMemberType]
        if body_iterator is None:
            logger.warning("幂等：无法读取响应体，跳过缓存")
            return response
        try:
            body = b"".join([chunk async for chunk in body_iterator])
        except Exception:  # noqa: BLE001 — 无法读取响应体则不缓存
            logger.warning("幂等：读取响应体失败，跳过缓存")
            return response
        try:
            redis_client.set(
                cache_key,
                _serialize(response, body),
                ex=settings.IDEMPOTENCY_EXPIRE_SECONDS,
            )
        except Exception:  # noqa: BLE001
            logger.warning("幂等写入缓存失败（不影响本次响应）")
        # 用已缓冲的 body 重建响应（body_iterator 已被消费）
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=dict(response.headers),
        )
