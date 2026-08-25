"""Redis 客户端（缓存+向量+限流，Redis Stack 7+）。"""
import redis

from app.core.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=3,
    socket_connect_timeout=3,
)


def ping_redis() -> bool:
    """探测 Redis 连通性；不可用返回 False（不抛异常）。"""
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False
