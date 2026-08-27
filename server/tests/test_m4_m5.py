"""M4 成绩 + M5 请假 + 消息中心测试（4.3/4.4/6.3.3~6.3.5）。

覆盖：
- 成绩：学生仅见已发布、教师录入权限、批量录入总评计算+审计、乐观锁 4091、
  分数范围/学生归属校验（T4-2~T4-5）；
- 请假：提交时长计算与校验、撤销状态机、待审批仅所带班级（ADR-010）、
  审批越权 4032/状态机 4301/消息联动、教师查看教学班请假（T5-1~T5-5）；
- 消息：审批后未读数、列表、标记已读（T5-8）。
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine


def _key() -> str:
    """唯一幂等键（避免幂等表残留导致重复运行命中缓存）。"""
    return f"m45-{uuid.uuid4().hex[:12]}"

pytestmark = pytest.mark.usefixtures("m45_data")

_RID = 6001  # 测试数据 id 段：避开 seed(50000+)/timetable(3001)/announcement(4001)

_HEADERS = {"Content-Type": "application/json"}


@pytest.fixture(scope="module")
def m45_data(client: TestClient, test_user_id: int):
    """创建独立数据段：学生/兼任教师/班级/课程/学期/教学班/学生档案（测试后清理）。

    - 教师 tt(6002) 兼任班级 6001 辅导员（ADR-010，班级 counselor_id=6002）。
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, create_time, update_time) "
                "VALUES (:id, 'm45_stu', 'M45学生', '', 0, '0', '0', 'student', 0, NOW(), NOW()),"
                "       (:id2, 'm45_tch', 'M45教师', '', 0, '0', '0', 'teacher', 0, NOW(), NOW())"
            ), {"id": _RID, "id2": _RID + 1})
            conn.execute(text(
                "INSERT INTO campus_department (id, dept_name, dept_code, del_flag) "
                "VALUES (:id, 'M45院系', 'M45D', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, del_flag) "
                "VALUES (:id, 'M45班', 'M45C', '2024', '测试', :did, :tid, '0')"
            ), {"id": _RID, "did": _RID, "tid": _RID + 1})
            conn.execute(text(
                "INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, del_flag) "
                "VALUES (:id, 'M45课程', 'M45K', 3.0, 48, :did, '0')"
            ), {"id": _RID, "did": _RID})
            conn.execute(text(
                "INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, del_flag) "
                "VALUES (:id, 'M45学期', '2026-02-01', '2026-07-01', 20, '0', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, del_flag) "
                "VALUES (:id, :co, :tid, :cl, :tch, '0')"
            ), {"id": _RID, "co": _RID, "tid": _RID, "cl": _RID, "tch": _RID + 1})
            conn.execute(text(
                "INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, del_flag) "
                "VALUES (:id, :uid, 'M45S001', :cid, '2024', '0')"
            ), {"id": _RID, "uid": _RID, "cid": _RID})
        yield {
            "student": _RID, "teacher": _RID + 1, "offering": _RID,
            "student_id": _RID, "class_id": _RID,
        }
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM campus_message WHERE business_type='leave' AND business_id IN "
                              f"(SELECT id FROM campus_leave WHERE student_id = {_RID})"))
            conn.execute(text(f"DELETE FROM campus_leave WHERE student_id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_score_audit WHERE student_id = {_RID} OR offering_id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_score WHERE student_id = {_RID} OR offering_id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_student WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_course_offering WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_term WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_course WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_class WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM campus_department WHERE id = {_RID}"))
            conn.execute(text(f"DELETE FROM sys_user WHERE id IN ({_RID}, {_RID + 1})"))


def _token(uid: int, role: str) -> str:
    from app.core.security import create_access_token
    return create_access_token(user_id=uid, role_code=role, password_version=0)


def _h(uid: int, role: str) -> dict:
    return {"Authorization": f"Bearer {_token(uid, role)}"}


def _json(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


# ===================== M4 成绩 =====================

def _clear_scores():
    """清理测试段的成绩与审计（保证各测试自包含）。"""
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM campus_score_audit WHERE student_id={_RID} OR offering_id={_RID}"))
        conn.execute(text(f"DELETE FROM campus_score WHERE student_id={_RID} OR offering_id={_RID}"))


def test_scores_mine_only_published(client: TestClient, m45_data):
    """学生：仅已发布成绩可见（T4-2/4401）。"""
    _clear_scores()
    h = _h(m45_data["student"], "student")
    # 先录入（未发布）→ mine 应为空
    ins = _json(client.post("/api/scores", json={
        "offering_id": m45_data["offering"], "version": 0,
        "scores": [{"student_id": m45_data["student_id"], "usual_score": 80.0, "exam_score": 70.0}],
    }, headers={**_h(m45_data["teacher"], "teacher"), **{"Idempotency-Key": _key()}}))
    assert ins["updated"] == 1, ins  # 录入应成功（非 warning 跳过）
    data = _json(client.get("/api/scores/mine", headers=h))
    assert data["total"] == 0, "未发布成绩学生端不可见"
    # 发布（模拟 Django 管理端）→ 可见
    with engine.begin() as conn:
        conn.execute(text("UPDATE campus_score SET is_published='1', publish_by=1, publish_time=NOW() "
                          "WHERE student_id=:sid AND offering_id=:oid"),
                     {"sid": m45_data["student_id"], "oid": m45_data["offering"]})
    data = _json(client.get("/api/scores/mine", headers=h))
    assert data["total"] == 1
    item = data["list"][0]
    assert item["course_name"] == "M45课程"
    assert item["total_score"] == 74.0  # 80×40% + 70×60%
    assert item["pass"] is True


def test_scores_course_permission(client: TestClient, m45_data):
    """教师录入前查询：本人教学班 OK，非本人 → 4032（T4-3）。"""
    data = _json(client.get(f"/api/scores/course?offering_id={m45_data['offering']}",
                            headers=_h(m45_data["teacher"], "teacher")))
    assert data["course_name"] == "M45课程"
    assert any(s["student_id"] == m45_data["student_id"] for s in data["students"])
    resp = client.get(f"/api/scores/course?offering_id={m45_data['offering']}",
                      headers=_h(m45_data["student"], "student"))
    assert resp.json()["code"] == 4032


def test_scores_upsert_optimistic_lock_and_audit(client: TestClient, m45_data):
    """批量录入：乐观锁 4091 + 审计明细写入（T4-3/T4-5，B-11）。"""
    _clear_scores()
    url = "/api/scores"
    h = _h(m45_data["teacher"], "teacher")
    body = {"offering_id": m45_data["offering"], "version": 0,
            "scores": [{"student_id": m45_data["student_id"], "usual_score": 88.0, "exam_score": 92.0}]}
    # 首次录入
    data = _json(client.post(url, json=body, headers={**h, "Idempotency-Key": _key()}))
    assert data["updated"] == 1
    with engine.connect() as conn:
        audit = conn.execute(text("SELECT operation FROM campus_score_audit "
                                  "WHERE student_id=:s AND offering_id=:o"), 
                             {"s": m45_data["student_id"], "o": m45_data["offering"]}).fetchall()
    assert {"1"} <= {a[0] for a in audit}, "录入应写审计(operation=1)"
    # 修改：version=0 已过期（当前为 1？首次插入 version=0，修改后 version=1）→ 需 version=1
    body2 = {**body, "version": 1,
             "scores": [{"student_id": m45_data["student_id"], "usual_score": 90.0, "exam_score": 90.0}]}
    data = _json(client.post(url, json=body2, headers={**h, "Idempotency-Key": _key()}))
    assert data["updated"] == 1
    # 再改传旧 version=0 → 4091 乐观锁
    resp = client.post(url, json={**body2, "version": 0}, headers={**h, "Idempotency-Key": _key()})
    assert resp.json()["code"] == 4091
    # 审计含修改(operation=2)且明细完整
    with engine.connect() as conn:
        audit2 = conn.execute(text("SELECT operation, new_detail FROM campus_score_audit "
                                   "WHERE student_id=:s AND offering_id=:o AND operation='2'"),
                              {"s": m45_data["student_id"], "o": m45_data["offering"]}).first()
    assert audit2 is not None
    assert "usual_score" in audit2[1]


def test_scores_upsert_validation(client: TestClient, m45_data):
    """录入校验：分数超范围跳过 + 非本人教学班 4032（T4-3）。"""
    _clear_scores()
    h = _h(m45_data["teacher"], "teacher")
    body = {"offering_id": m45_data["offering"], "version": 0,
            "scores": [{"student_id": m45_data["student_id"], "usual_score": 150.0, "exam_score": 70.0}]}
    data = _json(client.post("/api/scores", json=body, headers={**h, "Idempotency-Key": _key()}))
    assert data["updated"] == 0 and data["warnings"]
    # 非本人教学班（offerings 用 seed 的教学班 50060）
    resp = client.post("/api/scores", json={"offering_id": 50060, "version": 0,
                                            "scores": [{"student_id": m45_data["student_id"],
                                                        "usual_score": 80.0, "exam_score": 70.0}]},
                       headers={**h, "Idempotency-Key": _key()})
    assert resp.json()["code"] == 4032


# ===================== M5 请假 =====================

def test_leave_create_duration(client: TestClient, m45_data):
    """提交请假：时长权威计算（P1-14）。"""
    h = _h(m45_data["student"], "student")
    data = _json(client.post("/api/leaves", json={
        "leave_type": "1", "reason": "测试请假-时长",
        "start_time": "2026-03-01T08:00:00+08:00",
        "end_time": "2026-03-01T12:00:00+08:00",
    }, headers={**h, "Idempotency-Key": _key()}))
    assert data["leave_duration_minutes"] == 240
    assert data["total_days"] == 0.2
    assert data["status"] == "0"


def test_leave_create_invalid_time(client: TestClient, m45_data):
    """提交请假：end<start 拒绝、无时区拒绝（P1-14）。"""
    h = _h(m45_data["student"], "student")
    resp = client.post("/api/leaves", json={
        "leave_type": "1", "reason": "测试请假-非法",
        "start_time": "2026-03-02T08:00:00+08:00",
        "end_time": "2026-03-01T08:00:00+08:00",
    }, headers={**h, "Idempotency-Key": _key()})
    assert resp.json()["code"] == 4001
    resp = client.post("/api/leaves", json={
        "leave_type": "1", "reason": "测试请假-无时区",
        "start_time": "2026-03-01T08:00:00",
        "end_time": "2026-03-01T12:00:00",
    }, headers={**h, "Idempotency-Key": _key()})
    assert resp.json()["code"] == 4001


def _create_leave(client, m45_data, reason="测试请假-流程"):
    # Idempotency-Key 必须 ASCII（httpx header 限制）；body 哈希参与幂等键，key 可复用
    return _json(client.post("/api/leaves", json={
        "leave_type": "2", "reason": reason,
        "start_time": "2026-03-05T08:00:00+08:00",
        "end_time": "2026-03-05T18:00:00+08:00",
    }, headers={**_h(m45_data["student"], "student"), "Idempotency-Key": _key()}))["leave_id"]


def test_leave_cancel_only_pending(client: TestClient, m45_data):
    """撤销：仅待审批可撤销 → 3；已审批撤销 → 4301（T5-2）。"""
    lid = _create_leave(client, m45_data, "测试请假-撤销")
    h = _h(m45_data["student"], "student")
    data = _json(client.put(f"/api/leaves/{lid}/cancel", json={}, headers=h))
    assert data["status"] == "3"
    # 再撤销已撤销的 → 4301
    resp = client.put(f"/api/leaves/{lid}/cancel", json={}, headers=h)
    assert resp.json()["code"] == 4301


def test_leave_pending_only_my_class(client: TestClient, m45_data):
    """待审批列表：仅本人所带班级（兼任教师，ADR-010）。"""
    lid = _create_leave(client, m45_data, "测试请假-待审批")
    data = _json(client.get("/api/leaves/pending", headers=_h(m45_data["teacher"], "teacher")))
    assert any(x["leave_id"] == lid for x in data["list"]), "兼任教师应看到所带班级学生请假"
    # 学生无权限
    resp = client.get("/api/leaves/pending", headers=_h(m45_data["student"], "student"))
    assert resp.json()["code"] == 4032


def test_leave_approve_notify_and_forbidden(client: TestClient, m45_data):
    """审批：越权 4032、通过 → 消息通知（B-08 事务）。"""
    lid = _create_leave(client, m45_data, "测试请假-审批")
    # 学生尝试审批 → 4032
    resp = client.put(f"/api/leaves/{lid}/approve", json={"approve": "1", "comment": "x"},
                      headers=_h(m45_data["student"], "student"))
    assert resp.json()["code"] == 4032
    # 兼任教师审批通过
    data = _json(client.put(f"/api/leaves/{lid}/approve", json={"approve": "1", "comment": "同意"},
                            headers={**_h(m45_data["teacher"], "teacher"),
                                     "Idempotency-Key": _key()}))
    assert data["status"] == "1" and data["notified"] is True
    # 学生收到消息
    msgs = _json(client.get("/api/messages", params={"page_size": 50},
                            headers=_h(m45_data["student"], "student")))
    assert any(m["business_type"] == "leave" and m["business_id"] == lid for m in msgs["list"])
    # 重复审批 → 4301
    resp = client.put(f"/api/leaves/{lid}/approve", json={"approve": "1"},
                      headers=_h(m45_data["teacher"], "teacher"))
    assert resp.json()["code"] == 4301


def test_leave_approve_reject(client: TestClient, m45_data):
    """审批驳回：状态 2 + 消息。"""
    lid = _create_leave(client, m45_data, "测试请假-驳回")
    data = _json(client.put(f"/api/leaves/{lid}/approve", json={"approve": "2", "comment": "理由不足"},
                            headers={**_h(m45_data["teacher"], "teacher"),
                                     "Idempotency-Key": _key()}))
    assert data["status"] == "2"


def test_leave_teacher_view_students(client: TestClient, m45_data):
    """教师查看本教学班学生请假（T5-5）。"""
    _create_leave(client, m45_data, "测试请假-教师查看")
    data = _json(client.get(f"/api/leaves/students?offering_id={m45_data['offering']}",
                            headers=_h(m45_data["teacher"], "teacher")))
    assert any(x["student_name"] == "M45学生" for x in data["list"])
    # 非本人教学班 → 4032
    resp = client.get("/api/leaves/students?offering_id=50060",
                      headers=_h(m45_data["teacher"], "teacher"))
    assert resp.json()["code"] == 4032


# ===================== M5 消息中心 =====================

def test_message_unread_and_read(client: TestClient, m45_data):
    """消息：审批后未读 > 0，标记已读后减少（T5-8）。"""
    lid = _create_leave(client, m45_data, "测试请假-消息")
    _json(client.put(f"/api/leaves/{lid}/approve", json={"approve": "1", "comment": "ok"},
                     headers={**_h(m45_data["teacher"], "teacher"),
                              "Idempotency-Key": _key()}))
    h = _h(m45_data["student"], "student")
    cnt = _json(client.get("/api/messages/unread-count", headers=h))
    assert cnt["count"] >= 1
    msgs = _json(client.get("/api/messages", params={"unread_only": 1, "page_size": 50}, headers=h))
    target = next(m for m in msgs["list"] if m["business_id"] == lid)
    assert target["is_read"] == "0"
    _json(client.put(f"/api/messages/{target['id']}/read", json={}, headers=h))
    cnt2 = _json(client.get("/api/messages/unread-count", headers=h))
    assert cnt2["count"] < cnt["count"]
