"""T1-4 微信授权登录/绑定/解绑测试（3.4 / 10.3）。

覆盖：
- code2session 服务：配置缺失 / 网络失败 / 微信业务错误 / 正常返回（monkeypatch httpx，无网络依赖）
- 微信登录：已绑定直接登录；未绑定引导（need_bind）；带账号密码完成绑定
- 绑定冲突：openid 已被占用（4091）/ 账号已绑其他微信（4091）/ 密码错误（4102）/ 账号停用（4101）
- 解绑：登录态解绑后 openid 置空；未登录 4011
- 唯一约束：sys_user.wechat_openid 存在唯一索引（T1-4）

说明：
- 集成用例依赖本机 MySQL(3307)/Redis(6379)（同 conftest 约定）。
- code2session 通过 monkeypatch 注入固定 openid，不依赖真实微信网络。
- 限流 `_check_login_rate` monkeypatch 为空操作，避免 Redis 干扰。
"""
import base64
import hashlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.auth as auth_mod
from app.core.redis_client import redis_client
from app.services import wechat as wechat_mod


def _clear_code_cache(code: str) -> None:
    """清理指定 code 的 code2session 缓存（单元测试隔离）。"""
    redis_client.delete(f"wechat:code2session:{code}")

# 测试用户（独立于 conftest 的 999999，用后清理）
WX_USER_A_ID = 999901
WX_USER_B_ID = 999902


def _make_django_password(raw: str, iterations: int = 10000) -> str:
    """生成本地 PBKDF2 密码哈希（与 security.check_django_password 兼容，无 Django 依赖）。"""
    salt = os.urandom(8).hex()
    derived = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), iterations)
    b64 = base64.b64encode(derived).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt}${b64}"


# ===================== fixture =====================

@pytest.fixture(scope="module")
def wx_users():
    """创建两个微信测试用户（A 绑定 openid-a；B 未绑定），用后清理。"""
    pwd_hash = _make_django_password("123456")
    with engine_begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, "
                "status, del_flag, role_code, password_version, wechat_openid, create_time, update_time) "
                "VALUES (:id, :u, :n, :p, 0, '0', '0', 'student', 0, :oid, NOW(), NOW())"
            ),
            [
                {"id": WX_USER_A_ID, "u": "wxtest_a", "n": "微信测试A",
                 "p": pwd_hash, "oid": "mock-openid-A"},
                {"id": WX_USER_B_ID, "u": "wxtest_b", "n": "微信测试B",
                 "p": pwd_hash, "oid": None},
            ],
        )
    yield
    with engine_begin() as conn:
        conn.execute(text("DELETE FROM sys_user WHERE id IN (:a, :b)"),
                     {"a": WX_USER_A_ID, "b": WX_USER_B_ID})


@pytest.fixture()
def disable_login_rate(monkeypatch):
    """限流置为空操作，避免 Redis 计数干扰。"""
    monkeypatch.setattr(auth_mod, "_check_login_rate", lambda ip: None)


@pytest.fixture()
def fake_code2session(monkeypatch):
    """注入 code → openid 映射（模拟微信 code2session，B-01 mock）。"""

    def _install(code2openid: dict):
        def _fake(code: str) -> dict:
            if code not in code2openid:
                raise RuntimeError(f"未预期的 code: {code}")
            return {"openid": code2openid[code], "session_key": "mock-session-key"}
        monkeypatch.setattr(auth_mod, "code2session", _fake)
        return _fake

    return _install


# ===================== code2session 单元测试（无 DB 依赖）=====================

def test_code2session_missing_config(monkeypatch):
    """未配置 AppID/Secret → 5000。"""
    _clear_code_cache("wx-code")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "")
    from app.core.errors import BizError

    with pytest.raises(BizError) as exc:
        wechat_mod.code2session("wx-code")
    assert exc.value.code == 5000


def test_code2session_http_error(monkeypatch):
    """微信接口网络/HTTP 错误 → 5000。"""
    _clear_code_cache("wx-code")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "wx-a")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "s")

    def _raise(*args, **kwargs):
        import httpx
        raise httpx.ConnectError("mock connect error")

    monkeypatch.setattr(wechat_mod.httpx, "get", _raise)
    from app.core.errors import BizError

    with pytest.raises(BizError) as exc:
        wechat_mod.code2session("wx-code")
    assert exc.value.code == 5000


def test_code2session_errcode(monkeypatch):
    """微信返回业务错误码（如 40029）→ 4001。"""
    _clear_code_cache("invalid-code")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "wx-a")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "s")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"errcode": 40029, "errmsg": "invalid code"}

    monkeypatch.setattr(wechat_mod.httpx, "get", lambda *a, **k: _Resp())
    from app.core.errors import BizError

    with pytest.raises(BizError) as exc:
        wechat_mod.code2session("invalid-code")
    assert exc.value.code == 4001


def test_code2session_ok(monkeypatch):
    """正常返回 openid（mock 微信响应）。"""
    _clear_code_cache("wx-abc")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "wx-a")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "s")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "mock-openid-abc", "session_key": "k", "unionid": ""}

    monkeypatch.setattr(wechat_mod.httpx, "get", lambda *a, **k: _Resp())
    data = wechat_mod.code2session("wx-abc")
    assert data["openid"] == "mock-openid-abc"


# ===================== code 缓存（绑定复用 code 二次调用 40163 修复）=====================

def test_code2session_cache_second_call(monkeypatch):
    """同一 code 二次调用命中缓存，不再请求微信（避免 40163 code been used）。

    模拟绑定流程：先登录（code2session 一次）→ 绑定（复用 code，应命中缓存）。
    """
    _clear_code_cache("wx-cache")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "wx-a")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "s")
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "mock-openid-cache", "session_key": "k", "unionid": ""}

    def _mock_get(*args, **kwargs):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(wechat_mod.httpx, "get", _mock_get)
    assert wechat_mod.code2session("wx-cache")["openid"] == "mock-openid-cache"
    # 第二次调用：命中缓存，不请求微信
    assert wechat_mod.code2session("wx-cache")["openid"] == "mock-openid-cache"
    assert calls["n"] == 1, "二次调用应命中缓存（微信 code 一次性）"
    _clear_code_cache("wx-cache")


def test_code2session_cache_redis_down(monkeypatch):
    """Redis 故障降级：直连微信，功能可用（9.7 降级矩阵）。"""
    _clear_code_cache("wx-fallback")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_APPID", "wx-a")
    monkeypatch.setattr(wechat_mod.settings, "WECHAT_SECRET", "s")

    import redis as redis_lib

    def _boom(*args, **kwargs):
        raise redis_lib.RedisError("connection refused")

    monkeypatch.setattr(wechat_mod.redis_client, "get", _boom)
    monkeypatch.setattr(wechat_mod.redis_client, "set", _boom)

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "mock-openid-fb", "session_key": "k", "unionid": ""}

    monkeypatch.setattr(wechat_mod.httpx, "get", lambda *a, **k: _Resp())
    data = wechat_mod.code2session("wx-fallback")
    assert data["openid"] == "mock-openid-fb"


# ===================== 集成测试（需 MySQL/Redis）=====================

def test_wechat_login_already_bound(client: TestClient, wx_users,
                                    disable_login_rate, fake_code2session):
    """已绑定 openid → 纯微信登录直接签发 JWT（含角色）。"""
    fake_code2session({"wx-code-a": "mock-openid-A"})
    resp = client.post("/api/auth/wechat/login", json={"code": "wx-code-a"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["need_bind"] is False
    assert data["data"]["token"]
    assert data["data"]["user"]["user_id"] == WX_USER_A_ID
    assert data["data"]["user"]["role_code"] == "student"


def test_wechat_login_unbound_need_bind(client: TestClient, wx_users,
                                        disable_login_rate, fake_code2session):
    """openid 未绑定且不带账号密码 → need_bind=true 引导绑定。"""
    fake_code2session({"wx-new": "mock-openid-NEW"})
    resp = client.post("/api/auth/wechat/login", json={"code": "wx-new"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["need_bind"] is True
    assert data["data"]["token"] is None


def test_wechat_login_bind_success(client: TestClient, wx_users,
                                   disable_login_rate, fake_code2session):
    """未绑定 openid + 正确账号密码 → 绑定成功并登录。"""
    fake_code2session({"wx-code-b": "mock-openid-B2"})
    resp = client.post("/api/auth/wechat/login",
                       json={"code": "wx-code-b", "username": "wxtest_b", "password": "123456"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["token"]
    assert data["data"]["user"]["user_id"] == WX_USER_B_ID
    # openid 已写入
    with engine_connect() as conn:
        row = conn.execute(
            text("SELECT wechat_openid FROM sys_user WHERE id = :uid"),
            {"uid": WX_USER_B_ID},
        ).first()
    assert row[0] == "mock-openid-B2"


def test_wechat_login_bind_wrong_password(client: TestClient, wx_users,
                                          disable_login_rate, fake_code2session):
    """绑定时密码错误 → 4102。"""
    fake_code2session({"wx-code-b": "mock-openid-B3"})
    resp = client.post("/api/auth/wechat/login",
                       json={"code": "wx-code-b", "username": "wxtest_b", "password": "wrong"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4102


def test_wechat_login_bind_openid_conflict(client: TestClient, wx_users,
                                           disable_login_rate, fake_code2session):
    """openid 已绑定其他账号（唯一约束冲突）→ 4091。"""
    fake_code2session({"wx-conflict": "mock-openid-A"})  # A 已绑定该 openid
    resp = client.post("/api/auth/wechat/login",
                       json={"code": "wx-conflict", "username": "wxtest_b", "password": "123456"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4091


def test_wechat_login_bind_account_conflict(client: TestClient, wx_users,
                                            disable_login_rate, fake_code2session):
    """账号已绑定其他微信 → 4091（换绑需先解绑）。"""
    fake_code2session({"wx-other": "mock-openid-OTHER"})
    resp = client.post("/api/auth/wechat/login",
                       json={"code": "wx-other", "username": "wxtest_a", "password": "123456"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4091


def test_wechat_unbind(client: TestClient, wx_users, disable_login_rate,
                       fake_code2session):
    """登录态解绑 → openid 置空。"""
    fake_code2session({"wx-unbind": "mock-openid-A"})
    login = client.post("/api/auth/wechat/login", json={"code": "wx-unbind"})
    token = login.json()["data"]["token"]
    resp = client.delete("/api/auth/wechat/unbind",
                         headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    with engine_connect() as conn:
        row = conn.execute(
            text("SELECT wechat_openid FROM sys_user WHERE id = :uid"),
            {"uid": WX_USER_A_ID},
        ).first()
    assert row[0] is None
    # 解绑后 openid 可再绑定（用已解绑的 wxtest_a 重新绑定同一 openid）
    fake_code2session({"wx-rebind": "mock-openid-A"})
    resp = client.post("/api/auth/wechat/login",
                       json={"code": "wx-rebind", "username": "wxtest_a", "password": "123456"})
    assert resp.json()["code"] == 0


def test_wechat_unbind_requires_login(client: TestClient):
    """未登录解绑 → 4011。"""
    resp = client.delete("/api/auth/wechat/unbind")
    assert resp.status_code == 200
    assert resp.json()["code"] == 4011


def test_wechat_openid_unique_constraint():
    """T1-4：sys_user.wechat_openid 存在唯一索引。"""
    with engine_connect() as conn:
        rows = conn.execute(
            text("SHOW INDEX FROM sys_user WHERE Column_name = 'wechat_openid'")
        ).fetchall()
    assert rows, "sys_user.wechat_openid 应存在唯一索引"
    assert any(r[1] == 0 for r in rows), "应存在非空唯一索引（Non_unique=0）"


# ===================== 工具 =====================

from app.core.database import engine  # noqa: E402


def engine_connect():
    """获取只读数据库连接（测试用）。"""
    return engine.connect()


def engine_begin():
    """获取事务数据库连接（测试用）。"""
    return engine.begin()
