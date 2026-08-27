"""公告热点缓存（T3-3，P1-11 版本化缓存）。

设计基线：设计报告 3.3（跨服务缓存契约 B-06/P1-11）+ 9.7（统一降级矩阵）。

- 版本键 `ann:version`（int）：Django 发布/下架/删除时 INCR，旧版本缓存随
  TTL 自然过期（TTL ≤5min 兜底），避免 SCAN+DEL 大 keyspace 扫描；
- 列表键 `ann:list:{N}:{scope}:{type}:{page}:{size}:{kw}`（N=当前版本），
  scope 为 `{role}:{user_id}`（不同用户可见范围不同，2.3 数据权限）；
- Redis 故障降级：`get`/`set` 均捕获 RedisError → 直查 MySQL（9.7：
  公告缓存故障直查 MySQL，功能可用，最终一致 TTL ≤5min）。
"""
import json
import logging

import redis

from app.core.redis_client import redis_client

logger = logging.getLogger("campus")

ANN_VERSION_KEY = "ann:version"
ANN_LIST_PREFIX = "ann:list"
ANN_CACHE_TTL = 300  # 5 分钟兜底（9.7：最终一致）


def get_ann_version() -> int:
    """读取全局公告缓存版本（Redis 故障返回 0，等效不使用缓存）。"""
    try:
        v = redis_client.get(ANN_VERSION_KEY)
        return int(v) if v is not None else 0
    except redis.RedisError:
        return 0


def build_list_key(version: int, scope: str, ann_type: str | None,
                   page: int, size: int, keyword: str | None, is_top: str | None) -> str:
    """构造公告列表缓存 key（P1-11：`ann:list:{N}:{scope}:{type}:{page}` 扩展）。

    - scope：`{role}:{user_id}`（2.3 数据权限：不同用户可见范围不同）；
    - keyword/is_top 参与 key，避免不同筛选条件串数据。
    """
    kw_hash = ""
    if keyword:
        import hashlib

        kw_hash = hashlib.md5(keyword.encode("utf-8")).hexdigest()[:8]
    return (
        f"{ANN_LIST_PREFIX}:{version}:{scope}:{ann_type or 'all'}:"
        f"{is_top or 'all'}:{page}:{size}:{kw_hash}"
    )


def cache_get(key: str) -> str | None:
    """读取缓存（Redis 故障降级返回 None → 调用方直查 MySQL）。"""
    try:
        return redis_client.get(key)
    except redis.RedisError:
        logger.warning("公告缓存读取失败（Redis 不可用），降级直查 MySQL")
        return None


def cache_set(key: str, data, ttl: int = ANN_CACHE_TTL) -> None:
    """写入缓存（JSON 序列化；Redis 故障静默忽略，TTL 兜底）。"""
    try:
        redis_client.set(key, json.dumps(data, ensure_ascii=False, default=str), ex=ttl)
    except redis.RedisError:
        logger.warning("公告缓存写入失败（Redis 不可用），本次不缓存")
