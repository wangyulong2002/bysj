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
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False
