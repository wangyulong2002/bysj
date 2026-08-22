"""T0-6 幂等中间件测试（3.6/P1-09，v2.2 P1-12）。

用独立的迷你应用验证中间件行为，不依赖业务接口。
P1-12：幂等记录存 MySQL 唯一表 campus_idempotency_key，Redis 仅缓存；
Redis 故障降级 MySQL 直查，不拒绝写（P0-4）。
"""
import hashlib
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.responses import JSONResponse

from app.core.database import engine
from app.core.idempotency import IdempotencyMiddleware


def _make_app():
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)
    state = {"count": 0}

    @app.post("/echo")
    def echo():
        state["count"] += 1
        return JSONResponse({"count": state["count"]})

    @app.get("/ping")
    def ping():
        return JSONResponse({"ok": True})

    return app, state


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _cleanup(*keys):
    """清理测试产生的幂等记录（MySQL + Redis），避免残留污染。

    幂等键构造（P0-3）：sha256(key:user_id:method:path:body_hash)。
    无登录时 user_id 为空；POST /echo 无 body，body_hash 为 sha256(b"")。
    """
    import app.core.idempotency as idem_mod

    for k in keys:
        raw = f"{k}::POST:/echo:{_sha('')}"
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM campus_idempotency_key WHERE biz_key = :k"),
                    {"k": _sha(raw)},
                )
        except Exception:
            pass
        try:
            idem_mod.redis_client.delete(f"idem:POST:/echo:{_sha(k)}")
        except Exception:
            pass


def test_same_key_returns_cached_result():
    app, state = _make_app()
    key = "key-" + uuid.uuid4().hex
    try:
        with TestClient(app) as c:
            r1 = c.post("/echo", headers={"Idempotency-Key": key})
            r2 = c.post("/echo", headers={"Idempotency-Key": key})
        assert r1.status_code == r2.status_code == 200
        assert r1.json() == r2.json()
        assert state["count"] == 1, "重复 key 应直接返回首次结果，业务只执行一次"
        # 验证 MySQL 唯一表有记录（P1-12）
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM campus_idempotency_key "
                     "WHERE method='POST' AND path='/echo' AND body_hash IS NOT NULL")
            ).scalar()
        assert row >= 1, "幂等记录应写入 MySQL 唯一表"
    finally:
        _cleanup(f":POST:/echo:{_sha(key)}", key)


def test_different_keys_execute_separately():
    app, state = _make_app()
    k1, k2 = "key-a-" + uuid.uuid4().hex, "key-b-" + uuid.uuid4().hex
    try:
        with TestClient(app) as c:
            c.post("/echo", headers={"Idempotency-Key": k1})
            c.post("/echo", headers={"Idempotency-Key": k2})
        assert state["count"] == 2
    finally:
        _cleanup(f":POST:/echo:{_sha(k1)}", k1, f":POST:/echo:{_sha(k2)}", k2)


def test_post_without_header_not_idempotent():
    app, state = _make_app()
    with TestClient(app) as c:
        c.post("/echo")
        c.post("/echo")
    assert state["count"] == 2, "未携带 Idempotency-Key 不应幂等"


def test_get_not_idempotent():
    app, state = _make_app()
    with TestClient(app) as c:
        c.get("/ping")
        c.get("/ping")
    assert state["count"] == 0  # GET 不受中间件影响


def test_redis_down_still_idempotent_via_mysql(monkeypatch):
    """Redis 故障时降级 MySQL 直查（P1-12/P0-4）：重复 key 仍不产生重复数据。"""
    import app.core.idempotency as idem_mod

    app, state = _make_app()
    key = "k-down-" + uuid.uuid4().hex

    def raise_error(*args, **kwargs):
        raise idem_mod.redis_client.RedisError("redis down")

    monkeypatch.setattr(idem_mod.redis_client, "get", raise_error)
    monkeypatch.setattr(idem_mod.redis_client, "set", raise_error)

    try:
        with TestClient(app) as c:
            r1 = c.post("/echo", headers={"Idempotency-Key": key})
            r2 = c.post("/echo", headers={"Idempotency-Key": key})
        assert r1.status_code == r2.status_code == 200
        assert state["count"] == 1, "Redis 故障时由 MySQL 唯一表兜底，业务只执行一次"
    finally:
        _cleanup(f":POST:/echo:{_sha(key)}", key)
