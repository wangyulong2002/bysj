"""T0-6 幂等中间件测试（3.6/P1-09）。

用独立的迷你应用验证中间件行为，不依赖业务接口。
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

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


def test_same_key_returns_cached_result():
    app, state = _make_app()
    with TestClient(app) as c:
        r1 = c.post("/echo", headers={"Idempotency-Key": "key-1"})
        r2 = c.post("/echo", headers={"Idempotency-Key": "key-1"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert state["count"] == 1, "重复 key 应直接返回首次结果，业务只执行一次"


def test_different_keys_execute_separately():
    app, state = _make_app()
    with TestClient(app) as c:
        c.post("/echo", headers={"Idempotency-Key": "key-a"})
        c.post("/echo", headers={"Idempotency-Key": "key-b"})
    assert state["count"] == 2


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


def test_redis_down_degrades_to_pass_through(monkeypatch):
    """Redis 故障时降级直通（9.7），业务照常执行。"""
    import app.core.idempotency as idem_mod

    app, state = _make_app()

    def raise_error(*args, **kwargs):
        raise idem_mod.redis_client.RedisError("redis down")

    # 中间件使用的是 app.core.idempotency.redis_client（实例）
    monkeypatch.setattr(idem_mod.redis_client, "get", raise_error)
    monkeypatch.setattr(idem_mod.redis_client, "set", raise_error)

    with TestClient(app) as c:
        r = c.post("/echo", headers={"Idempotency-Key": "k-down"})
    assert r.status_code == 200
    assert state["count"] == 1, "Redis 故障时应直通而非阻断"
