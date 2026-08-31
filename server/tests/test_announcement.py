"""T3-2/T3-3 公告模块测试（4.2 / 2.3 / 10.1 / 10.2 / 10.3）。

覆盖：
- 列表可见范围（2.3）：校园公告所有人可见；院系公告按角色收敛；
  学生越权查他人院系公告 → 不可见（**v2.5/ADR-011：班级公告已移除，按院系判定**）；
- 草稿不可见（仅管理端发布，4.2 P0-02）；
- 置顶优先 + 发布时间倒序、关键字筛选、分页；
- 详情：可见返回、越权 4032（IDOR）、不存在 4001、未登录 4011；
- Redis 版本化缓存（T3-3，P1-11）：缓存命中、版本失效、故障降级直查 MySQL。
"""
import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.core.redis_client import redis_client
from app.core.security import create_access_token

pytestmark = pytest.mark.usefixtures("announcement_data")

_RID = 4001  # 测试数据 id 段：避开开发库既有数据（2002~2012）与 timetable(3001)


@pytest.fixture(scope="module")
def announcement_data(client: TestClient, test_user_id: int):
    """创建公告测试数据（模块级，测试后清理）。

    - 依赖 conftest.test_user_id 创建 publisher（sys_user 999999）；
    - 两个院系（D1/D2）、两个班级（班1 属 D1 / 班2 属 D2）；
    - 学生（班1）、教师（任教班1）、辅导员（带班1+班2）；
    - 公告（v2.5：无班级公告）：校园×2（A1 置顶 / A2）、
      院系1(A3)、院系2(A4)、院系1第二条(A5)、院系2第二条(A6)、草稿(A7)。
    """
    try:
        with engine.begin() as conn:
            # 角色用户
            conn.execute(text(
                "INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, create_time, update_time) "
                "VALUES (:id, :u, :n, '', 0, '0', '0', :r, 0, NOW(), NOW())"
            ), [
                {"id": _RID, "u": "ann_student", "n": "公告学生", "r": "student"},
                {"id": _RID + 1, "u": "ann_teacher", "n": "公告教师", "r": "teacher"},
                # 兼任教师（v2.4 无专职辅导员）：role=teacher + 班1/班2 counselor_id 指向
                {"id": _RID + 2, "u": "ann_counselor", "n": "兼任教师B", "r": "teacher"},
            ])
            conn.execute(text(
                "INSERT INTO campus_department (id, dept_name, dept_code, del_flag) "
                "VALUES (:id, '计算机学院', 'ANND1', '0'), (:id2, '外国语学院', 'ANND2', '0')"
            ), {"id": _RID, "id2": _RID + 1})
            conn.execute(text(
                "INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, del_flag) "
                "VALUES (:id, '计科2301', 'ANNC1', '2023', '计算机', :d1, :cid, '0'),"
                "       (:id2, '英语2301', 'ANNC2', '2023', '英语', :d2, :cid, '0')"
            ), {"id": _RID, "id2": _RID + 1, "d1": _RID, "d2": _RID + 1, "cid": _RID + 2})
            conn.execute(text(
                "INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, del_flag) "
                "VALUES (:id, :uid, 'A20230001', :cid, '2023', '0')"
            ), {"id": _RID, "uid": _RID, "cid": _RID})
            conn.execute(text(
                "INSERT INTO campus_teacher (id, user_id, teacher_no, title, department_id, del_flag) "
                "VALUES (:id, :uid, 'A2001', '讲师', :d1, '0')"
            ), {"id": _RID, "uid": _RID + 1, "d1": _RID})
            conn.execute(text(
                "INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, del_flag) "
                "VALUES (:id, '公告测试课', 'ANNC001', 3.0, 48, :d1, '0')"
            ), {"id": _RID, "d1": _RID})
            conn.execute(text(
                "INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, del_flag) "
                "VALUES (:id, '2025-2026学年第一学期', '2025-09-01', '2026-01-18', 20, '0', '0')"
            ), {"id": _RID})
            conn.execute(text(
                "INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, del_flag) "
                "VALUES (:id, :co, :tid, :cl1, :tch, '0')"
            ), {"id": _RID, "co": _RID, "tid": _RID, "cl1": _RID, "tch": _RID + 1})
            # 公告（publisher=admin 测试账号 999999）
            conn.execute(text(
                "INSERT INTO campus_announcement "
                "(id, title, content, ann_type, target_department_id, "
                " publisher_id, is_top, status, publish_time, create_time, update_time, del_flag) "
                "VALUES "
                "(:a1, '校园置顶公告', '置顶内容', '1', NULL, :pub, '1', '1', '2026-08-20 10:00:00', NOW(), NOW(), '0'),"
                "(:a2, '校园普通公告', '普通内容', '1', NULL, :pub, '0', '1', '2026-08-21 10:00:00', NOW(), NOW(), '0'),"
                "(:a3, '院系1公告', '院系1内容', '2', :d1, :pub, '0', '1', '2026-08-22 10:00:00', NOW(), NOW(), '0'),"
                "(:a4, '院系2公告', '院系2内容', '2', :d2, :pub, '0', '1', '2026-08-23 10:00:00', NOW(), NOW(), '0'),"
                "(:a5, '院系1公告B', '院系1内容B', '2', :d1, :pub, '0', '1', '2026-08-24 10:00:00', NOW(), NOW(), '0'),"
                "(:a6, '院系2公告B', '院系2内容B', '2', :d2, :pub, '0', '1', '2026-08-25 10:00:00', NOW(), NOW(), '0'),"
                "(:a7, '草稿公告', '草稿内容', '1', NULL, :pub, '0', '0', NULL, NOW(), NOW(), '0')"
            ), {"a1": _RID, "a2": _RID + 1, "a3": _RID + 2, "a4": _RID + 3,
                "a5": _RID + 4, "a6": _RID + 5, "a7": _RID + 6, "pub": test_user_id,
                "d1": _RID, "d2": _RID + 1})
        yield {
            "student": _RID, "teacher": _RID + 1, "counselor": _RID + 2,
            "class1": _RID, "class2": _RID + 1, "dept1": _RID, "dept2": _RID + 1,
            "school_top": _RID, "school_normal": _RID + 1,
            "dept1_ann": _RID + 2, "dept2_ann": _RID + 3,
            "dept1_ann_b": _RID + 4, "dept2_ann_b": _RID + 5, "draft": _RID + 6,
        }
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM campus_announcement WHERE id BETWEEN {_RID} AND {_RID + 6}"))
            conn.execute(text(f"DELETE FROM campus_course_offering WHERE id BETWEEN {_RID} AND {_RID}"))
            conn.execute(text(f"DELETE FROM campus_course WHERE id BETWEEN {_RID} AND {_RID}"))
            conn.execute(text(f"DELETE FROM campus_term WHERE id BETWEEN {_RID} AND {_RID}"))
            conn.execute(text(f"DELETE FROM campus_teacher WHERE id BETWEEN {_RID} AND {_RID}"))
            conn.execute(text(f"DELETE FROM campus_student WHERE id BETWEEN {_RID} AND {_RID}"))
            conn.execute(text(f"DELETE FROM campus_class WHERE id BETWEEN {_RID} AND {_RID + 1}"))
            conn.execute(text(f"DELETE FROM campus_department WHERE id BETWEEN {_RID} AND {_RID + 1}"))
            conn.execute(text(f"DELETE FROM sys_user WHERE id BETWEEN {_RID} AND {_RID + 2}"))
        # 清理测试产生的公告缓存
        for k in redis_client.scan_iter("ann:*"):
            redis_client.delete(k)


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


def _ann_ids(data) -> set:
    """提取公告列表的 id 集合。"""
    return {a["id"] for a in data["list"]}


# ===== T3-2：列表可见范围（2.3 数据权限）=====

def test_student_sees_school_and_own_dept(client: TestClient, announcement_data):
    """学生（班1/院系1）：可见 校园公告 + 院系1公告（2 条）。"""
    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["student"], "student")))
    ids = _ann_ids(data)
    assert {announcement_data["school_top"], announcement_data["school_normal"],
            announcement_data["dept1_ann"], announcement_data["dept1_ann_b"]} <= ids


def test_student_cannot_see_other_dept(client: TestClient, announcement_data):
    """学生：不可见院系2公告（2.3 收敛）。"""
    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["student"], "student")))
    ids = _ann_ids(data)
    assert announcement_data["dept2_ann"] not in ids
    assert announcement_data["dept2_ann_b"] not in ids


def test_teacher_sees_teaching_scope(client: TestClient, announcement_data):
    """教师（任教班1/档案院系1）：可见 校园 + 院系1；不可见院系2。"""
    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["teacher"], "teacher")))
    ids = _ann_ids(data)
    assert {announcement_data["school_top"], announcement_data["school_normal"],
            announcement_data["dept1_ann"], announcement_data["dept1_ann_b"]} <= ids
    assert announcement_data["dept2_ann"] not in ids
    assert announcement_data["dept2_ann_b"] not in ids


def test_counselor_sees_all_managed(client: TestClient, announcement_data):
    """兼任教师（带班1+2 → 院系1+2，counselor_id=本人）：可见全部已发布测试公告。"""
    # page_size=50：dev 库存量已发布公告（120000+）会占满默认第 1 页（10 条），
    # 避免分页截断导致断言误报（测试与开发数据隔离）
    data = _json(client.get("/api/announcements", params={"page_size": 50},
                            headers=_headers(announcement_data["counselor"], "teacher")))
    ids = _ann_ids(data)
    assert {announcement_data["school_top"], announcement_data["school_normal"],
            announcement_data["dept1_ann"], announcement_data["dept1_ann_b"],
            announcement_data["dept2_ann"], announcement_data["dept2_ann_b"]} <= ids
    assert announcement_data["draft"] not in ids


def test_draft_not_visible(client: TestClient, announcement_data):
    """草稿公告（status=0）不可见（4.2：应用端只读已发布）。"""
    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["student"], "student")))
    assert announcement_data["draft"] not in _ann_ids(data)


# ===== T3-2：排序 / 筛选 / 分页 =====

def test_top_first_then_publish_desc(client: TestClient, announcement_data):
    """置顶优先 + 发布时间倒序（全局排序性质，兼容 seed 数据）。"""
    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["student"], "student")))
    items = data["list"]
    assert items and items[0]["is_top"] == "1", "置顶公告应排最前"
    tops = [i for i in items if i["is_top"] == "1"]
    rest = [i for i in items if i["is_top"] != "1"]
    assert items == tops + rest, "置顶公告应全部在非置顶之前"
    rest_times = [i["publish_time"] for i in rest]
    assert rest_times == sorted(rest_times, reverse=True), "非置顶按发布时间倒序"


def test_filter_by_type_and_keyword(client: TestClient, announcement_data):
    """类型 + 关键字筛选（v2.5：类型仅 1校园/2院系）。"""
    # 院系类型（兼任教师可见院系1+2 全部 4 条院系公告）
    data = _json(client.get("/api/announcements", params={"ann_type": "2"},
                            headers=_headers(announcement_data["counselor"], "teacher")))
    assert _ann_ids(data) == {announcement_data["dept1_ann"], announcement_data["dept1_ann_b"],
                              announcement_data["dept2_ann"], announcement_data["dept2_ann_b"]}
    # 已移除的班级类型（ann_type=3）→ 参数校验拒绝（统一异常处理包装为 code=4001）
    resp3 = client.get("/api/announcements", params={"ann_type": "3"},
                       headers=_headers(announcement_data["counselor"], "teacher"))
    assert resp3.json()["code"] == 4001
    # 关键字
    data = _json(client.get("/api/announcements", params={"keyword": "置顶"},
                            headers=_headers(announcement_data["student"], "student")))
    assert _ann_ids(data) == {announcement_data["school_top"]}


def test_is_top_filter(client: TestClient, announcement_data):
    """is_top=1 仅返回置顶公告（首页热点卡片用），测试置顶应包含其中。"""
    data = _json(client.get("/api/announcements", params={"is_top": "1"},
                            headers=_headers(announcement_data["student"], "student")))
    ids = _ann_ids(data)
    assert announcement_data["school_top"] in ids
    assert all(a["is_top"] == "1" for a in data["list"])


def test_pagination(client: TestClient, announcement_data):
    """分页：total 正确、pageSize 截断、遍历无遗漏（兼容 seed 数据）。"""
    seen = set()
    total = 0
    for page in range(1, 30):
        d = _json(client.get("/api/announcements",
                             params={"page_num": page, "page_size": 2},
                             headers=_headers(announcement_data["student"], "student")))
        total = d["total"]
        seen |= _ann_ids(d)
        if len(d["list"]) < 2:
            break
    assert total >= 4
    assert {announcement_data["school_top"], announcement_data["school_normal"],
            announcement_data["dept1_ann"], announcement_data["dept1_ann_b"]} <= seen


# ===== T3-2：详情 =====

def test_detail_visible_with_content(client: TestClient, announcement_data):
    """详情：可见公告返回完整内容。"""
    data = _json(client.get(
        f"/api/announcements/{announcement_data['school_top']}",
        headers=_headers(announcement_data["student"], "student")))
    assert data["title"] == "校园置顶公告"
    assert data["content"] == "置顶内容"
    assert data["is_top"] == "1"
    assert data["publisher_name"] == "测试账号"


def test_detail_forbidden_other_dept(client: TestClient, announcement_data):
    """详情越权：学生访问院系2公告 → 4032（防 IDOR）。"""
    resp = client.get(f"/api/announcements/{announcement_data['dept2_ann']}",
                      headers=_headers(announcement_data["student"], "student"))
    assert resp.json()["code"] == 4032


def test_detail_not_found(client: TestClient, announcement_data):
    """详情：不存在或草稿 → 4001。"""
    resp = client.get("/api/announcements/999999",
                      headers=_headers(announcement_data["student"], "student"))
    assert resp.json()["code"] == 4001
    resp = client.get(f"/api/announcements/{announcement_data['draft']}",
                      headers=_headers(announcement_data["student"], "student"))
    assert resp.json()["code"] == 4001


def test_announcement_requires_login(client: TestClient):
    """未登录 → 4011。"""
    resp = client.get("/api/announcements")
    assert resp.json()["code"] == 4011


# ===== T3-3：Redis 版本化缓存 =====

def test_cache_hit_and_invalidate(client: TestClient, announcement_data):
    """缓存命中 + 版本失效（P1-11）。

    首次请求写入缓存；INCR ann:version 后旧 key 不再命中。
    """
    h = _headers(announcement_data["student"], "student")
    data1 = _json(client.get("/api/announcements", headers=h))
    # 缓存 key 已写入
    v = int(redis_client.get("ann:version") or 0)
    assert any(redis_client.keys(f"ann:list:{v}:*")), "首次请求应写入版本化缓存"

    # 版本自增（模拟 Django 发布/下架）→ 新请求走新版本 key，旧 key 不再命中
    redis_client.incr("ann:version")
    data2 = _json(client.get("/api/announcements", headers=h))
    assert _ann_ids(data1) == _ann_ids(data2)  # 数据一致
    new_v = int(redis_client.get("ann:version") or 0)
    assert new_v == v + 1
    # P1-11：旧版本缓存不主动 SCAN+DEL（避免大 keyspace 扫描），随 TTL 自然过期
    assert any(redis_client.keys(f"ann:list:{new_v}:*")), "新版本缓存 key 应写入"
    assert any(redis_client.keys(f"ann:list:{v}:*")), "旧版本缓存保留至 TTL 过期（不 SCAN+DEL）"


def test_cache_key_isolated_by_scope(client: TestClient, announcement_data):
    """缓存 key 按 scope（role:user_id）隔离，不同用户不串数据。"""
    h1 = _headers(announcement_data["student"], "student")
    h2 = _headers(announcement_data["counselor"], "teacher")
    data1 = _json(client.get("/api/announcements", headers=h1))
    data2 = _json(client.get("/api/announcements", headers=h2))
    assert _ann_ids(data1) != _ann_ids(data2)  # 可见范围不同


def test_cache_fallback_when_redis_down(client: TestClient, announcement_data, monkeypatch):
    """Redis 故障降级：直查 MySQL，功能可用（9.7 降级矩阵）。"""
    import app.core.announcement_cache as ann_cache

    def _boom(*args, **kwargs):
        raise redis.RedisError("connection refused")

    monkeypatch.setattr(ann_cache.redis_client, "get", _boom)
    monkeypatch.setattr(ann_cache.redis_client, "set", _boom)
    monkeypatch.setattr(ann_cache, "get_ann_version", lambda: 0)

    data = _json(client.get("/api/announcements",
                            headers=_headers(announcement_data["student"], "student")))
    ids = _ann_ids(data)
    assert announcement_data["school_top"] in ids
    assert announcement_data["dept2_ann"] not in ids  # 降级时权限过滤仍生效
