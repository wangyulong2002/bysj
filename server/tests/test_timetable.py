"""T2-4/T2-5/T2-6 课表模块测试（4.1 / 10.1 / 10.2）。

覆盖：
- current-week：正常推算 / 学期前（week=0）/ 学期后（week=total_weeks）/ 无当前学期 4001
- timetable：学生推导 class_id（忽略入参，P0-03）、教师/辅导员越权 4032、
  管理员全量、week 过滤（week ∈ [week_start, week_end]）
- classes/mine：学生/教师/辅导员/管理员返回正确班级
- classes：C-09 数据范围收敛
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.core.security import create_access_token

pytestmark = pytest.mark.usefixtures("timetable_data")


_RID = 3001  # 测试数据 id 段：避开开发库既有演示数据（2002~2012）


@pytest.fixture(scope="module")
def timetable_data(client: TestClient):
    """创建课表测试数据（模块级，测试后清理）。

    - 使用独立 id 段（3001~3003），不影响既有数据；
    - 处理 campus_term.uk_term_current 唯一约束：临时取消既有当前学期，测试后恢复。
    """
    prev_term = None
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM campus_term WHERE is_current='1' LIMIT 1")).first()
        if row:
            prev_term = row[0]
            conn.execute(text("UPDATE campus_term SET is_current='0' WHERE id=:id"), {"id": prev_term})
    try:
        with engine.begin() as conn:
            # 角色用户
            conn.execute(text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, create_time, update_time) "
                "VALUES (:id, :u, :n, '', 0, '0', '0', :r, 0, NOW(), NOW())"
            ), [
                {"id": _RID, "u": "tt_student", "n": "测试学生", "r": "student"},
                {"id": _RID + 1, "u": "tt_teacher", "n": "测试教师", "r": "teacher"},
                {"id": _RID + 2, "u": "tt_counselor", "n": "测试辅导员", "r": "counselor"},
            ])
            conn.execute(text(
                "INSERT INTO campus_department (id, dept_name, dept_code, del_flag) "
                "VALUES (:id, '测试学院', 'T01', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, del_flag) "
                "VALUES (:id, '测试班1', 'TC01', '2025', '测试专业', :did, :cid, '0'),"
                "       (:id2, '测试班2', 'TC02', '2025', '测试专业', :did, :cid, '0')"
            ), {"id": _RID, "id2": _RID + 1, "did": _RID, "cid": _RID + 2})
            conn.execute(text(
                "INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, del_flag) "
                "VALUES (:id, '测试数学', 'TM101', 4.0, 64, :did, '0'),"
                "       (:id2, '测试英语', 'TE102', 2.0, 32, :did, '0')"
            ), {"id": _RID, "id2": _RID + 1, "did": _RID})
            conn.execute(text(
                "INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, del_flag) "
                "VALUES (:id, '2025-2026学年第一学期', '2025-09-01', '2026-01-18', 20, '1', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, del_flag) "
                "VALUES (:id, :uid, 'T20250001', :cid, '2025', '0')"
            ), {"id": _RID, "uid": _RID, "cid": _RID})
            conn.execute(text(
                "INSERT INTO campus_teacher (id, user_id, teacher_no, title, department_id, del_flag) "
                "VALUES (:id, :uid, 'T2001', '讲师', :did, '0')"
            ), {"id": _RID, "uid": _RID + 1, "did": _RID})
            conn.execute(text(
                "INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, del_flag) "
                "VALUES (:id, :co1, :tid, :cl1, :tch, '0'),"
                "       (:id2, :co2, :tid, :cl1, :tch, '0'),"
                "       (:id3, :co1, :tid, :cl2, :tch, '0')"
            ), {"id": _RID, "id2": _RID + 1, "id3": _RID + 2, "co1": _RID, "co2": _RID + 1,
                "tid": _RID, "cl1": _RID, "cl2": _RID + 1, "tch": _RID + 1})
            conn.execute(text(
                "INSERT INTO campus_course_schedule (id, offering_id, week_start, week_end, day_of_week, period_start, period_end, location, del_flag) "
                "VALUES (:id, :o1, 1, 16, 1, 1, 2, 'A-301', '0'),"   # 班1 周一 1-2 节
                "       (:id2, :o2, 3, 18, 2, 3, 4, 'B-202', '0'),"  # 班1 周二 3-4 节
                "       (:id3, :o3, 1, 16, 1, 1, 2, 'C-101', '0')"   # 班2 周一 1-2 节
            ), {"id": _RID, "id2": _RID + 1, "id3": _RID + 2,
                "o1": _RID, "o2": _RID + 1, "o3": _RID + 2})
        yield {
            "student": _RID, "teacher": _RID + 1, "counselor": _RID + 2,
            "class1": _RID, "class2": _RID + 1,
        }
    finally:
        with engine.begin() as conn:
            for t in ("campus_course_schedule", "campus_course_offering", "campus_teacher",
                      "campus_student", "campus_term", "campus_course", "campus_class",
                      "campus_department"):
                conn.execute(text(f"DELETE FROM {t} WHERE id BETWEEN {_RID} AND {_RID + 2}"))
            conn.execute(text(f"DELETE FROM sys_user WHERE id BETWEEN {_RID} AND {_RID + 2}"))
            if prev_term:
                conn.execute(text("UPDATE campus_term SET is_current='1' WHERE id=:id"),
                             {"id": prev_term})


def _headers(user_id: int, role: str) -> dict:
    """构造指定角色测试用户的 Bearer JWT 请求头。"""
    token = create_access_token(user_id=user_id, role_code=role, password_version=0)
    return {"Authorization": f"Bearer {token}"}


def _json(resp):
    """断言 HTTP 200 + code=0 并返回 data 部分。"""
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


# ===== T2-4：当前教学周 =====

def test_current_week_ongoing(timetable_data):
    """学期中：week = (today - start)//7 + 1。"""
    from app.api.timetable import current_week

    from app.api.deps import UserIdentity

    user = UserIdentity(user_id=timetable_data["student"], role_code="student", password_version=0)
    data = current_week(user, today=date(2025, 9, 15))["data"]  # 开学第 15 天（第 3 周）
    assert data["current_week"] == 3
    assert data["term_name"] == "2025-2026学年第一学期"
    assert data["total_weeks"] == 20
    assert data["semester_status"] == "ongoing"


def test_current_week_before_start():
    """学期前：week=0。"""
    from app.api.deps import UserIdentity
    from app.api.timetable import current_week

    user = UserIdentity(user_id=_RID, role_code="student", password_version=0)
    data = current_week(user, today=date(2025, 8, 20))["data"]
    assert data["current_week"] == 0
    assert data["semester_status"] == "before_start"


def test_current_week_after_end():
    """学期后：week=total_weeks。"""
    from app.api.deps import UserIdentity
    from app.api.timetable import current_week

    user = UserIdentity(user_id=_RID, role_code="student", password_version=0)
    data = current_week(user, today=date(2026, 3, 1))["data"]
    assert data["current_week"] == 20
    assert data["semester_status"] == "after_end"


def test_current_week_no_term(client: TestClient):
    """无当前学期 → 4001（临时置 0 再恢复）。"""
    with engine.begin() as conn:
        conn.execute(text("UPDATE campus_term SET is_current = '0' WHERE id = :id"), {"id": _RID})
    try:
        resp = client.get("/api/timetable/current-week", headers=_headers(_RID, "student"))
        assert resp.json()["code"] == 4001
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE campus_term SET is_current = '1' WHERE id = :id"), {"id": _RID})


# ===== T2-5：课表查询 =====

def test_student_timetable_ignores_class_id(client: TestClient, timetable_data):
    """学生：忽略入参 class_id（篡改为班2 仍返回本人班1 课表，P0-03）。"""
    resp = client.get("/api/timetable", params={"class_id": timetable_data["class2"], "week": 8},
                      headers=_headers(timetable_data["student"], "student"))
    data = _json(resp)
    assert data["week"] == 8
    items = data["items"]
    assert len(items) == 2  # 班1 周一+周二
    assert {i["day_of_week"] for i in items} == {1, 2}


def test_student_timetable_week_filter(client: TestClient, timetable_data):
    """week 过滤：班1 第 2 周仅有周一课程（英语 3-18 周未开）。"""
    resp = client.get("/api/timetable", params={"week": 2},
                      headers=_headers(timetable_data["student"], "student"))
    items = _json(resp)["items"]
    assert len(items) == 1
    assert items[0]["course_name"] == "测试数学"
    assert items[0]["teacher_name"] == "测试教师"
    assert items[0]["location"] == "A-301"
    assert items[0]["day_of_week"] == 1
    assert items[0]["period_start"] == 1
    assert items[0]["period_end"] == 2


def test_teacher_timetable_ok(client: TestClient, timetable_data):
    """教师：本人教学班覆盖的班级可查（班1/班2）。"""
    resp = client.get("/api/timetable", params={"class_id": timetable_data["class2"], "week": 8},
                      headers=_headers(timetable_data["teacher"], "teacher"))
    items = _json(resp)["items"]
    assert len(items) == 1
    assert items[0]["course_name"] == "测试数学"


def test_teacher_timetable_forbidden_other_class(client: TestClient, timetable_data):
    """教师：非本人教学班覆盖的班级 → 4032（防 IDOR）。"""
    # 班2 也是教师所带（offering3），需要构造一个不属于教师教学班的班级
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, del_flag) "
            "VALUES (:id, '其他班', 'TOTH', '2025', '其他专业', :did, NULL, '0')"
        ), {"id": _RID + 10, "did": _RID})
    try:
        resp = client.get("/api/timetable", params={"class_id": _RID + 10, "week": 8},
                          headers=_headers(timetable_data["teacher"], "teacher"))
        assert resp.json()["code"] == 4032
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM campus_class WHERE id = :id"), {"id": _RID + 10})


def test_counselor_timetable_forbidden_other_class(client: TestClient, timetable_data):
    """辅导员：非所带班级 → 4032（counselor_id 指向其他用户）。"""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, del_flag) "
            "VALUES (:id, '无主班', 'TNOC', '2025', '其他专业', :did, :uid, '0')"
        ), {"id": _RID + 11, "did": _RID, "uid": _RID})
    try:
        resp = client.get("/api/timetable", params={"class_id": _RID + 11, "week": 8},
                          headers=_headers(timetable_data["counselor"], "counselor"))
        assert resp.json()["code"] == 4032
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM campus_class WHERE id = :id"), {"id": _RID + 11})


def test_counselor_timetable_ok(client: TestClient, timetable_data):
    """辅导员：所带班级（班1/班2）可查。"""
    resp = client.get("/api/timetable", params={"class_id": timetable_data["class1"], "week": 8},
                      headers=_headers(timetable_data["counselor"], "counselor"))
    items = _json(resp)["items"]
    assert len(items) == 2


def test_admin_timetable_all(client: TestClient, timetable_data, test_user_id):
    """管理员：全量（可查任意班级）。"""
    resp = client.get("/api/timetable", params={"class_id": timetable_data["class2"], "week": 8},
                      headers=_headers(test_user_id, "admin"))
    items = _json(resp)["items"]
    assert len(items) == 1


def test_timetable_week_out_of_range(client: TestClient, timetable_data):
    """week 超出范围 → 4001。"""
    resp = client.get("/api/timetable", params={"week": 99},
                      headers=_headers(timetable_data["student"], "student"))
    assert resp.json()["code"] == 4001


# ===== T2-6：我的班级 / 班级列表（C-09）=====

def test_classes_mine_student(client: TestClient, timetable_data):
    """学生：仅本人班级（班1）。"""
    data = _json(client.get("/api/classes/mine",
                            headers=_headers(timetable_data["student"], "student")))
    assert [c["class_id"] for c in data] == [timetable_data["class1"]]
    assert data[0]["class_name"] == "测试班1"
    assert data[0]["department_name"] == "测试学院"


def test_classes_mine_teacher(client: TestClient, timetable_data):
    """教师：本人教学班覆盖的班级（班1 + 班2）。"""
    data = _json(client.get("/api/classes/mine",
                            headers=_headers(timetable_data["teacher"], "teacher")))
    ids = {c["class_id"] for c in data}
    assert ids == {timetable_data["class1"], timetable_data["class2"]}


def test_classes_mine_counselor(client: TestClient, timetable_data):
    """辅导员：所带班级（班1 + 班2）。"""
    data = _json(client.get("/api/classes/mine",
                            headers=_headers(timetable_data["counselor"], "counselor")))
    ids = {c["class_id"] for c in data}
    assert ids == {timetable_data["class1"], timetable_data["class2"]}


def test_classes_mine_admin(client: TestClient, timetable_data, test_user_id):
    """管理员：全部班级。"""
    data = _json(client.get("/api/classes/mine", headers=_headers(test_user_id, "admin")))
    ids = {c["class_id"] for c in data}
    assert timetable_data["class1"] in ids and timetable_data["class2"] in ids


def test_classes_list_scope(client: TestClient, timetable_data):
    """GET /api/classes：C-09 数据范围收敛（学生仅本人班级）。"""
    data = _json(client.get("/api/classes", headers=_headers(timetable_data["student"], "student")))
    assert [c["class_id"] for c in data] == [timetable_data["class1"]]


def test_timetable_requires_login(client: TestClient):
    """未登录 → 4011。"""
    resp = client.get("/api/timetable", params={"week": 1})
    assert resp.json()["code"] == 4011
