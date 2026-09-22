"""登录失败锁定（3.6 / 9.7 / T1-6）。

- 连续失败 `LOGIN_MAX_FAIL`（默认 5）次 → 锁定账号 `LOGIN_LOCK_MINUTES`（默认 10）分钟。
- 锁定期间登录返回 4101（明确提示剩余时间）。
- 成功登录清除失败计数。
- **降级（P0-4）**：Redis 不可用时降级为进程内计数（单实例有效，多实例不保证全局一致）；
  实现上两类后端均可用，互不干扰，恢复 Redis 后自动切回。

Redis Key：
- `login_fail:{username}`  失败计数（**P1-4：滚动窗口 TTL**，成功时删除）
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

# ---- 通用限流降级存储（P1-4：Redis 不可用时使用，单实例有效）----
_inmemory_rate: dict[str, tuple[int, float]] = {}   # key -> (计数, 窗口截止时间戳)
_rate_lock = Lock()


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
    """记录一次登录失败。达到阈值则锁定。返回 (locked_now, remaining_seconds)。

    P1-4：`login_fail` 计数键加**滚动窗口 TTL**（= 锁定分钟数）。原实现只在登录
    成功时删除该键，攻击者对 100 万个不存在的用户名各试一次，就会在 Redis 留下
    100 万个永不回收的 key（内存耗尽型攻击面）。
    """
    max_fail = _max_fail()
    window = _lock_minutes() * 60
    fail_key = _FAIL_KEY.format(username=username)
    lock_key = _LOCK_KEY.format(username=username)

    def _redis_record(client) -> tuple[bool, int]:
        """Redis 计数 + 滚动窗口 TTL + 达阈值加锁。"""
        count = client.incr(fail_key)
        client.expire(fail_key, window)   # P1-4：每次失败刷新窗口，键不会永久驻留
        if count >= max_fail:
            client.set(lock_key, "1", ex=window)
            client.delete(fail_key)
            return True, window
        return False, 0

    r = _try_redis(_redis_record)
    if r is not None:
        locked, seconds = r
        if locked:
            logger.warning("账号已锁定 username=%s 时长=%ss", username, seconds)
        return locked, seconds
    # 进程内
    with _inmemory_lock:
        _inmemory_fail[username] = _inmemory_fail.get(username, 0) + 1
        if _inmemory_fail[username] >= max_fail:
            seconds = window
            _inmemory_locked[username] = time.time() + seconds
            _inmemory_fail.pop(username, None)
            logger.warning("账号已锁定（进程内） username=%s 时长=%ss", username, seconds)
            return True, seconds
        return False, 0


def check_rate_limit(
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
    *,
    key_override: str | None = None,
    on_redis_failure: str = "inproc",
) -> bool:
    """滑动窗口限流（P1-4）。返回 True = 放行，False = 超限。

    背景：原实现中登录限流与 RAG 限流的降级行为各自硬编码，且都直接 fail-open，
    而账号锁定却降级为进程内计数 —— 同一系统两套降级口径、且散落各处。
    现统一收敛到本函数，并把**降级策略显式化**为参数，避免"看代码才知道行为"：

    Args:
        scope: 业务域（用于日志与默认键命名空间）。
        identity: 限流主体（IP / openid 等）。
        limit: 窗口内允许的最大次数。
        window_seconds: 窗口长度（秒）。
        key_override: 显式指定 Redis 键（保持既有键名，兼容运维/测试的清理约定）。
        on_redis_failure:
            `"inproc"`（默认）—— Redis 故障时降级为进程内计数（单实例有效）；
            适用**安全敏感**入口（登录/账号锁定）：宁可误拒也不放行爆破。
            `"allow"` —— Redis 故障时放行；
            适用**公开只读**入口（RAG 问答），与设计 9.7 降级矩阵一致
            （可用性优先，且该接口无账号资产可爆破）。
    """
    if limit <= 0:
        return True
    key = key_override or f"rate:{scope}:{identity}"
    now = time.time()

    def _redis_hit(client) -> bool:
        n = client.incr(key)
        if n == 1:
            client.expire(key, window_seconds)
        return int(n) <= limit

    allowed = _try_redis(_redis_hit)
    if allowed is not None:
        return bool(allowed)

    if on_redis_failure == "allow":
        # 设计 9.7 降级矩阵：RAG 限流遇 Redis 故障 → 放行（并已由 _try_redis 记告警）
        logger.warning("限流 Redis 不可用，%s 按降级策略放行（scope=%s）", scope, identity)
        return True

    # 进程内降级（与账号锁定同一套降级口径）
    with _rate_lock:
        count, end = _inmemory_rate.get(key, (0, now + window_seconds))
        if now > end:
            count, end = 0, now + window_seconds
        count += 1
        _inmemory_rate[key] = (count, end)
        return count <= limit


def clear_failures(username: str) -> None:
    """登录成功后清除失败计数与锁定状态。"""
    _try_redis(lambda c, k: c.delete(k), _FAIL_KEY.format(username=username))
    _try_redis(lambda c, k: c.delete(k), _LOCK_KEY.format(username=username))
    with _inmemory_lock:
        _inmemory_fail.pop(username, None)
        _inmemory_locked.pop(username, None)
