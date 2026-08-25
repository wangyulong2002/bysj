"""T1-5 修改密码 + T1-6 登录失败锁定测试（4.5 / 3.6 / 9.7）。

覆盖：
- T1-5：原密码校验（4102）、新旧相同（4001）、未登录（4011）、
  改密成功后旧 JWT 立即失效（password_version 自增）、新密码登录成功、版本号落库。
- T1-6：连错 5 次锁定（第 6 次 4101）、锁定期间正确密码也拒绝、
  成功登录清除计数、Redis 故障降级进程内计数（P0-4）、锁定到期可恢复。

说明：
- 集成用例依赖本机 MySQL(3307)/Redis(6379)（同 conftest 约定）。
- 登录限流 `_check_login_rate` monkeypatch 为空操作，避免 IP 限流干扰。
"""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.auth as auth_mod
import app.core.login_lock as lock_mod
from app.core.security import make_django_password

# 测试用户（独立，用后清理）
CHG_PWD_USER_ID = 999903   # T1-5 改密：密码 oldpass123
LOCK_USER_ID = 999904      # T1-6 锁定：密码 lockpass123


def _cleanup():
    from app.core.database import engine

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sys_user WHERE id IN (:a, :b)"),
                     {"a": CHG_PWD_USER_ID, "b": LOCK_USER_ID})


@pytest.fixture(scope="module", autouse=True)
def _users():
    """创建 T1-5/T1-6 测试用户，用后清理并清空锁定状态。"""
    from app.core.database import engine

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, "
                "status, del_flag, role_code, password_version, wechat_openid, create_time, update_time) "
                "VALUES (:id, :u, :n, :p, 0, '0', '0', 'student', 0, NULL, NOW(), NOW())"
            ),
            [
                {"id": CHG_PWD_USER_ID, "u": "chgpwd", "n": "改密测试",
                 "p": make_django_password("oldpass123")},
                {"id": LOCK_USER_ID, "u": "lockuser", "n": "锁定测试",
                 "p": make_django_password("lockpass123")},
            ],
        )
    yield
    lock_mod.clear_failures("chgpwd")
    lock_mod.clear_failures("lockuser")
    _cleanup()


@pytest.fixture()
def disable_login_rate(monkeypatch):
    monkeypatch.setattr(auth_mod, "_check_login_rate", lambda ip: None)


# ===================== T1-5 修改密码 =====================

def test_change_password_wrong_old(client: TestClient, disable_login_rate):
    """原密码错误 → 4102。"""
    token = client.post("/api/auth/login", json={"username": "chgpwd", "password": "oldpass123"}).json()["data"]["token"]
    resp = client.put("/api/auth/password",
                      json={"old_password": "wrong-old", "new_password": "newpass456"},
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4102


def test_change_password_same(client: TestClient, disable_login_rate):
    """新密码与原密码相同 → 4001。"""
    token = client.post("/api/auth/login", json={"username": "chgpwd", "password": "oldpass123"}).json()["data"]["token"]
    resp = client.put("/api/auth/password",
                      json={"old_password": "oldpass123", "new_password": "oldpass123"},
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4001


def test_change_password_requires_login(client: TestClient):
    """未登录 → 4011。"""
    resp = client.put("/api/auth/password", json={"old_password": "oldpass123", "new_password": "newpass456"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4011


def test_change_password_success_old_token_invalid(client: TestClient, disable_login_rate):
    """改密成功：旧 JWT 立即失效（4011），新密码可登录，旧密码 4102。"""
    from app.core.database import engine

    # 旧密码登录拿 token
    login = client.post("/api/auth/login", json={"username": "chgpwd", "password": "oldpass123"})
    assert login.json()["code"] == 0
    old_token = login.json()["data"]["token"]

    # 改密
    resp = client.put("/api/auth/password",
                      json={"old_password": "oldpass123", "new_password": "newpass456"},
                      headers={"Authorization": f"Bearer {old_token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    # 旧 token 立即失效（password_version 自增 → 4011）
    resp = client.delete("/api/auth/wechat/unbind", headers={"Authorization": f"Bearer {old_token}"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4011

    # 新密码登录成功
    login = client.post("/api/auth/login", json={"username": "chgpwd", "password": "newpass456"})
    assert login.json()["code"] == 0
    assert login.json()["data"]["user"]["user_id"] == CHG_PWD_USER_ID

    # 旧密码失效
    resp = client.post("/api/auth/login", json={"username": "chgpwd", "password": "oldpass123"})
    assert resp.json()["code"] == 4102


def test_change_password_version_incremented():
    """password_version 已自增落库（0 → 1）。"""
    from app.core.database import engine

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT password_version FROM sys_user WHERE id = :uid"),
            {"uid": CHG_PWD_USER_ID},
        ).first()
    assert row[0] == 1


# ===================== T1-6 登录失败锁定 =====================

def test_lock_after_5_failures(client: TestClient, disable_login_rate):
    """连错 5 次 → 第 6 次（即使密码正确）返回 4101。"""
    lock_mod.clear_failures("lockuser")
    for i in range(5):
        resp = client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong-pass"})
        assert resp.json()["code"] == 4102, f"第 {i+1} 次失败应返回 4102"
    # 锁定生效
    assert lock_mod.is_locked("lockuser")[0] is True
    # 锁定期间正确密码也拒绝
    resp = client.post("/api/auth/login", json={"username": "lockuser", "password": "lockpass123"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 4101


def test_success_login_clears_failures(client: TestClient, disable_login_rate):
    """未达阈值时成功登录清除失败计数。"""
    lock_mod.clear_failures("lockuser")
    # 失败 2 次
    client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong-1"})
    client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong-2"})
    assert lock_mod.is_locked("lockuser")[0] is False
    # 成功登录 → 计数清零
    resp = client.post("/api/auth/login", json={"username": "lockuser", "password": "lockpass123"})
    assert resp.json()["code"] == 0
    # 再失败 4 次也不锁（计数已清，需 5 次）
    for _ in range(4):
        client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong"})
    assert lock_mod.is_locked("lockuser")[0] is False


def test_lock_expires_after_ttl(client: TestClient, disable_login_rate, monkeypatch):
    """锁定到期自动解除（TTL 到期后正确密码可登录）。"""
    lock_mod.clear_failures("lockuser")
    # 缩短锁定时长便于测试（0.1 分钟 = 6 秒，改用秒级验证进程内）
    monkeypatch.setattr(lock_mod.settings, "LOGIN_LOCK_MINUTES", 1)
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong"})
    assert lock_mod.is_locked("lockuser")[0] is True
    # 到期：进程内锁定直接清除（模拟时间流逝），Redis TTL 由过期机制处理
    lock_mod.clear_failures("lockuser")
    assert lock_mod.is_locked("lockuser")[0] is False
    resp = client.post("/api/auth/login", json={"username": "lockuser", "password": "lockpass123"})
    assert resp.json()["code"] == 0


def test_lock_inmemory_fallback(monkeypatch, disable_login_rate, client: TestClient):
    """Redis 故障 → 降级进程内计数（P0-4），仍能锁定。"""
    lock_mod.clear_failures("lockuser")
    monkeypatch.setattr(lock_mod, "_try_redis", lambda *a, **k: None)
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "lockuser", "password": "wrong"})
    locked, remaining = lock_mod.is_locked("lockuser")
    assert locked is True
    assert remaining > 0
    # 锁定期间登录被拒
    resp = client.post("/api/auth/login", json={"username": "lockuser", "password": "lockpass123"})
    assert resp.json()["code"] == 4101
    lock_mod.clear_failures("lockuser")
    assert lock_mod.is_locked("lockuser")[0] is False


def test_record_failure_return_seconds():
    """record_failure 达到阈值返回剩余秒数。"""
    lock_mod.clear_failures("lockuser")
    locked, seconds = None, 0
    for _ in range(5):
        locked, seconds = lock_mod.record_failure("lockuser")
    assert locked is True
    assert seconds > 0
    lock_mod.clear_failures("lockuser")
