"""公告缓存版本失效工具（T3-3，P1-11 版本化缓存）。

Django 侧发布/下架/删除公告时调用 `bump_ann_version()` 使 FastAPI 侧
`ann:list:{N}:...` 旧版本缓存自然失效（9.7 降级矩阵：公告缓存 =
Redis 故障直查 MySQL，最终一致，TTL ≤5min 兜底）。

Redis 故障时静默降级：本次未及时失效由缓存 TTL 兜底，Redis 恢复后
公告缓存自动回填（P0-4：恢复策略）。
"""
import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

ANN_VERSION_KEY = "ann:version"

_client = None


def _get_client() -> "redis.Redis":
    """懒加载 Redis 客户端（短超时，故障快速失败）。"""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    return _client


def get_redis_client() -> "redis.Redis":
    """公共入口：共享 Redis 客户端（T7-2 RAG 索引状态等复用）。"""
    return _get_client()


def bump_ann_version() -> None:
    """公告缓存版本自增（发布/下架/删除后调用）。

    Redis 不可用时静默降级：本次未及时失效由 TTL（≤5min）兜底，
    不阻断业务（P0-4 降级矩阵：公告缓存不依赖 Redis 可用性）。
    """
    try:
        _get_client().incr(ANN_VERSION_KEY)
    except redis.RedisError:
        logger.warning("ann:version INCR 失败（Redis 不可用），公告缓存由 TTL 兜底")
