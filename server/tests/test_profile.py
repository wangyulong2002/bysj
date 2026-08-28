"""M6 个人信息接口测试（4.5 / T6-1）。

覆盖：
- GET /api/profile：本人信息（角色/班级/课程）+ 手机号脱敏 masked_phone（B-09/P1-17）；
- PUT /api/profile：修改手机号（格式校验 4001）、头像（campus_file，本人 ACL）；
- GET /api/profile/phone：完整手机号（phone.full 权限点，仅本人）；
- 数据权限：仅本人记录（修改他人无入口，字段按 JWT 身份读取）。
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine

pytestmark = pytest.mark.usefixtures("p6_data")

_RID = 7001  # 测试数据 id 段：避开 seed(50000+)/m45(6001)/timetable(3001)/announcement(4001)


def _auth_headers(uid: int) -> dict:
    from app.core.security import create_access_token

    token = create_access_token(user_id=uid, role_code="student", password_version=0)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def p6_data(client: TestClient):
    """创建独立数据段：学生用户 + 班级 + 当前学期课程（测试后清理）。

    当前学期全局唯一（uk_term_current）：临时把原当前学期置 0、P6 学期置 1，
    测试结束恢复原当前学期。
    """
    orig_id: int | None = None
    with engine.begin() as conn:
        orig = conn.execute(
            text("SELECT id FROM campus_term WHERE is_current = '1' AND del_flag = '0' "
                 "ORDER BY id LIMIT 1")
        ).first()
        orig_id = orig[0] if orig else None
        conn.execute(text("UPDATE campus_term SET is_current = '0' WHERE is_current = '1'"))
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, phone, create_time, update_time) "
                "VALUES (:id, 'p6_stu', 'P6学生', '', 0, '0', '0', 'student', 0, '13800001234', NOW(), NOW())"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_department (id, dept_name, dept_code, del_flag) "
                "VALUES (:id, 'P6院系', 'P6D', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, del_flag) "
                "VALUES (:id, 'P6班', 'P6C', '2026', '测试', :did, '0')"
            ), {"id": _RID, "did": _RID})
            conn.execute(text(
                "INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, del_flag) "
                "VALUES (:id, 'P6课程', 'P6K', 3.0, 48, :did, '0')"
            ), {"id": _RID, "did": _RID})
            conn.execute(text(
                "INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, del_flag) "
                "VALUES (:id, 'P6学期', '2026-02-01', '2026-07-01', 20, '1', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, del_flag) "
                "VALUES (:id, :cid, :tid, :clsid, :uid, '0')"
            ), {"id": _RID, "cid": _RID, "tid": _RID, "clsid": _RID, "uid": _RID})
            conn.execute(text(
                "INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, del_flag) "
                "VALUES (:id, :uid, 'P6001', :clsid, '2026', '0')"
            ), {"id": _RID, "uid": _RID, "clsid": _RID})
    except Exception:
        if orig_id is not None:
            with engine.begin() as conn:
                conn.execute(text("UPDATE campus_term SET is_current = '1' WHERE id = :oid"),
                             {"oid": orig_id})
        raise
    yield _RID
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM campus_student WHERE id = :id"), {"id": _RID})
        conn.execute(text("DELETE FROM campus_course_offering WHERE id = :id"), {"id": _RID})
        conn.execute(text("DELETE FROM campus_term WHERE id = :id"), {"id": _RID})
        conn.execute(text("DELETE FROM campus_course WHERE id = :id"), {"id": _RID})
        conn.execute(text("DELETE FROM campus_class WHERE id = :id"), {"id": _RID})
        conn.execute(text("DELETE FROM campus_department WHERE id = :id"), {"id": _RID})
        # 头像用例会上传 campus_file（uploader_id 外键 ON DELETE RESTRICT），先清理
        conn.execute(text("DELETE FROM campus_file WHERE owner_id = :id OR uploader_id = :id"),
                     {"id": _RID})
        conn.execute(text("DELETE FROM sys_user WHERE id = :id"), {"id": _RID})
        if orig_id is not None:
            conn.execute(text("UPDATE campus_term SET is_current = '1' WHERE id = :oid"),
                         {"oid": orig_id})


def test_get_profile_masked_phone(p6_data, client: TestClient):
    """GET /api/profile：返回本人信息（角色/班级/课程），手机号脱敏。"""
    resp = client.get("/api/profile", headers=_auth_headers(_RID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["user_id"] == _RID
    assert data["role_code"] == "student"
    assert data["class_name"] == "P6班"
    assert data["student_no"] == "P6001"
    assert data["masked_phone"] == "138****1234"
    assert "phone" not in data  # 默认序列化不返回完整手机号
    assert [c["course_name"] for c in data["courses"]] == ["P6课程"]


def test_update_profile_phone(p6_data, client: TestClient):
    """PUT /api/profile：修改手机号成功，回显仍为脱敏值。"""
    headers = _auth_headers(_RID)
    resp = client.put("/api/profile", json={"phone": "13900005678"}, headers=headers)
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["masked_phone"] == "139****5678"
    # 完整号码已写入
    with engine.connect() as conn:
        row = conn.execute(text("SELECT phone FROM sys_user WHERE id = :uid"), {"uid": _RID}).first()
    assert row[0] == "13900005678"


def test_update_profile_invalid_phone(p6_data, client: TestClient):
    """手机号格式错误 → 4001。"""
    resp = client.put("/api/profile", json={"phone": "123"}, headers=_auth_headers(_RID))
    assert resp.json()["code"] == 4001


def test_get_full_phone_audit(p6_data, client: TestClient):
    """GET /api/profile/phone：完整手机号（phone.full 权限点，返回当前库中最新值）。"""
    resp = client.get("/api/profile/phone", headers=_auth_headers(_RID))
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    # 与库中实际值一致（此前用例已把手机号改为 13900005678）
    with engine.connect() as conn:
        row = conn.execute(text("SELECT phone FROM sys_user WHERE id = :uid"), {"uid": _RID}).first()
    assert body["data"]["phone"] == row[0]


def test_update_avatar_requires_own_file(p6_data, client: TestClient, test_user_id):
    """头像：使用本人上传的 campus_file 成功；他人文件 → 4032。"""
    headers = _auth_headers(_RID)
    # 本人上传头像文件（biz_type=avatar，visibility 默认 3）
    up = client.post(
        "/api/files?biz_type=avatar",
        files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")},
        headers=_auth_headers(_RID),
    )
    assert up.json()["code"] == 0
    file_id = up.json()["data"]["id"]

    resp = client.put("/api/profile", json={"avatar_file_id": file_id}, headers=headers)
    assert resp.json()["code"] == 0
    avatar = resp.json()["data"]["avatar"]
    assert avatar and "/api/files/" in avatar  # 返回签名 URL

    # 不存在的文件 → 4001
    resp = client.put("/api/profile", json={"avatar_file_id": 99999999}, headers=headers)
    assert resp.json()["code"] == 4001

    # 他人文件 → 4032（用会话级测试管理员上传的文件）
    from app.core.security import create_access_token

    admin_token = create_access_token(user_id=test_user_id, role_code="admin", password_version=0)
    up2 = client.post(
        "/api/files?biz_type=avatar",
        files={"file": ("b.png", b"\x89PNG\r\n\x1a\n" + b"1" * 100, "image/png")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert up2.json()["code"] == 0
    other_file = up2.json()["data"]["id"]
    resp = client.put("/api/profile", json={"avatar_file_id": other_file}, headers=headers)
    assert resp.json()["code"] == 4032
