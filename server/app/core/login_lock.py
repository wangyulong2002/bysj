"""登录失败锁定（3.6 / 9.7 / T1-6）。

- 连续失败 `LOGIN_MAX_FAIL`（默认 5）次 → 锁定账号 `LOGIN_LOCK_MINUTES`（默认 10）分钟。
- 锁定期间登录返回 4101（明确提示剩余时间）。
- 成功登录清除失败计数。
- **降级（P0-4）**：Redis 不可用时降级为进程内计数（单实例有效，多实例不保证全局一致）；
  实现上两类后端均可用，互不干扰，恢复 Redis 后自动切回。

Redis Key：
- `login_fail:{username}`  失败计数（无 TTL，成功时删除）
- `login_lock:{username}`  锁定标记（TTL = 锁定分钟数）
"""
import logging
import time
from threading import Lock

from app.core.config import settings

logger = logging.getLogger("campus.login_lock")

_FAIL_KEY = "login_fail:{username}"
_LOCK_KEY = "login_lock:{username}"

# ---- 进程内降级存储（P0-4：Redis 不可用时使用，单实例有效）----
_inmemory_lock = Lock()
_inmemory_fail: dict[str, int] = {}          # username -> 失败次数
_inmemory_locked: dict[str, float] = {}      # username -> 锁定截止时间戳


def _max_fail() -> int:
    """失败锁定阈值（默认 5 次，可配置 LOGIN_MAX_FAIL）。"""
    return int(getattr(settings, "LOGIN_MAX_FAIL", 5) or 5)


def _lock_minutes() -> int:
    """锁定分钟数（默认 10 分钟，可配置 LOGIN_LOCK_MINUTES）。"""
    return int(getattr(settings, "LOGIN_LOCK_MINUTES", 10) or 10)


def _try_redis(fn, *args, **kwargs):
    """执行 Redis 操作；Redis 不可用时返回 None（调用方降级进程内）。"""
    try:
        from app.core.redis_client import redis_client
        return fn(redis_client, *args, **kwargs)
    except Exception:  # noqa: BLE001 — Redis 故障降级
        logger.warning("登录锁定 Redis 不可用，降级进程内计数（P0-4）")
        return None


def is_locked(username: str) -> tuple[bool, int]:
    """是否锁定。返回 (locked, remaining_seconds)；未锁定 remaining=0。

    Redis 优先；Redis 故障走进程内。
    """
    # Redis
    ttl = _try_redis(lambda r, k: r.ttl(k), _LOCK_KEY.format(username=username))
    if ttl is not None:
        if ttl > 0:
            return True, int(ttl)
        return False, 0
    # 进程内
    with _inmemory_lock:
        until = _inmemory_locked.get(username)
        if until is not None and until > time.time():
            return True, int(until - time.time())
        if until is not None:
            _inmemory_locked.pop(username, None)
    return False, 0


def record_failure(username: str) -> tuple[bool, int]:
    """记录一次登录失败。达到阈值则锁定。返回 (locked_now, remaining_seconds)。"""
    max_fail = _max_fail()
    # Redis
    r = _try_redis(lambda c, k: (c.incr(k), c),
                   _FAIL_KEY.format(username=username))
    if r is not None:
        count, client = r
        if count >= max_fail:
            seconds = _lock_minutes() * 60
            client.set(_LOCK_KEY.format(username=username), "1", ex=seconds)
            client.delete(_FAIL_KEY.format(username=username))
            logger.warning("账号已锁定 username=%s 时长=%ss", username, seconds)
            return True, seconds
        return False, 0
    # 进程内
    with _inmemory_lock:
        _inmemory_fail[username] = _inmemory_fail.get(username, 0) + 1
        if _inmemory_fail[username] >= max_fail:
            seconds = _lock_minutes() * 60
            _inmemory_locked[username] = time.time() + seconds
            _inmemory_fail.pop(username, None)
            logger.warning("账号已锁定（进程内） username=%s 时长=%ss", username, seconds)
            return True, seconds
        return False, 0


def clear_failures(username: str) -> None:
    """登录成功后清除失败计数与锁定状态。"""
    _try_redis(lambda c, k: c.delete(k), _FAIL_KEY.format(username=username))
    _try_redis(lambda c, k: c.delete(k), _LOCK_KEY.format(username=username))
    with _inmemory_lock:
        _inmemory_fail.pop(username, None)
        _inmemory_locked.pop(username, None)
