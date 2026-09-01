"""M8 T8-1 安全测试补充（10.3，验收标准 13 相关项）。

覆盖现有套件未覆盖的安全用例：
- JWT 篡改 / 过期 token → 4011；
- 登录 IP 限流（LOGIN_RATE_PER_MIN=5 次/分钟，B-13）超限 → 4291；
- SQL 注入：登录用户名 / 公告搜索关键字注入 payload 不越权、不崩溃（参数化查询）；
- XSS：公告搜索关键字 / 个人资料手机号注入脚本 payload 被校验或参数化安全。

依赖本机 MySQL(3307)/Redis(6379)；测试数据独立 id 段，用后清理。
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.core.security import create_access_token

# 测试用户（独立 id 段，用后清理）
RID = 8801


@pytest.fixture(scope="module")
def sec_user():
    """创建安全测试用户（student，密码 secpass123），用后清理。"""
    from app.core.security import make_django_password

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, "
            "del_flag, role_code, password_version, create_time, update_time) "
            "VALUES (:id, 'sec_user', '安全测试', :p, 0, '0', '0', 'student', 0, NOW(), NOW())"
        ), {"id": RID, "p": make_django_password("secpass123")})
    yield RID
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sys_user WHERE id = :id"), {"id": RID})


def _token(uid: int = RID, role: str = "student", expires_delta: timedelta | None = None) -> str:
    return create_access_token(user_id=uid, role_code=role, password_version=0,
                               expires_delta=expires_delta)


# ===== JWT 篡改 / 过期（10.3 / 验收 13）=====

def test_jwt_tampered_signature_4011(client: TestClient):
    """篡改 token 签名 → 4011（InvalidTokenError）。"""
    token = _token()
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.json()["code"] == 4011


def test_jwt_tampered_payload_4011(client: TestClient):
    """篡改 payload（伪造 user_id）后用错误密钥重签 → 4011。"""
    import jwt as pyjwt
    from app.core.config import settings

    forged = pyjwt.encode(
        {"user_id": RID + 999, "role_code": "admin", "password_version": 0,
         "exp": 9999999999},
        "wrong-secret", algorithm="HS256",
    )
    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {forged}"})
    assert resp.json()["code"] == 4011
    assert resp.json()["code"] != 0


def test_jwt_expired_4011(client: TestClient):
    """过期 token → 4011（ExpiredSignatureError）。"""
    token = _token(expires_delta=timedelta(seconds=-10))
    resp = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 4011


# ===== 登录 IP 限流（B-13 / 10.3 / 验收 13）=====

def test_login_rate_limited_4291(client: TestClient):
    """同一 IP 登录超过 LOGIN_RATE_PER_MIN 次 → 4291（Redis 计数）。"""
    from app.core.redis_client import redis_client

    for k in redis_client.scan_iter("login_rate:*"):
        redis_client.delete(k)
    codes = []
    for _ in range(6):
        resp = client.post("/api/auth/login", json={"username": "no_such_user_x", "password": "x"})
        codes.append(resp.json()["code"])
    # 前 5 次：账号不存在/密码错误/锁定（非 4291）；第 6 次必为 4291
    assert codes[5] == 4291, codes
    assert all(c in (4101, 4102, 4001, 4291) for c in codes[:5]), codes


# ===== SQL 注入（10.3 / 参数化查询）=====

def test_sql_injection_username_safe(client: TestClient):
    """登录用户名注入 payload → 不越权登录（返回 4102 而非成功）。"""
    resp = client.post("/api/auth/login",
                       json={"username": "' OR '1'='1", "password": "' OR '1'='1"})
    body = resp.json()
    assert body["code"] != 0          # 绝不登录成功
    assert body["code"] in (4101, 4102, 4001, 4291)


def test_sql_injection_announcement_keyword(client: TestClient, auth_headers):
    """公告搜索关键字注入 → 参数化安全（code=0，无 SQL 错误）。"""
    for payload in ("%' OR 1=1 --", "' UNION SELECT 1,2,3 --", "<script>alert(1)</script>"):
        resp = client.get("/api/announcements",
                          params={"keyword": payload, "page_size": 5},
                          headers=auth_headers)
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, (payload, body)


# ===== XSS（10.3）=====

def test_xss_keyword_safe(client: TestClient, auth_headers):
    """公告搜索关键字 XSS payload → 正常返回（参数化，不注入 SQL/HTML）。"""
    resp = client.get("/api/announcements", params={"keyword": "<img src=x onerror=alert(1)>"},
                      headers=auth_headers)
    assert resp.json()["code"] == 0


def test_xss_phone_rejected(client: TestClient, auth_headers):
    """个人资料手机号写入脚本 payload → 4001（格式校验拒绝，不落库）。"""
    resp = client.put("/api/profile", json={"phone": "<script>alert(1)</script>"},
                      headers=auth_headers)
    assert resp.json()["code"] == 4001
