"""课表模块接口（4.1 / T2-4/T2-5/T2-6）。

- `GET /api/timetable/current-week`：当前教学周自动推算（4.1 教学周历）。
- `GET /api/timetable?class_id=&week=`：课表查询（4.1/6.3.2）。
- `GET /api/classes/mine`：我的班级（按角色区分，6.2/T2-6）。
- `GET /api/classes`：班级列表（C-09：按数据范围收敛，6.2）。

数据权限（4.1 P0-03，防 IDOR）：
- 学生：忽略入参 class_id，从 campus_student.class_id 推导；
- 教师：class_id 必须属于本人教学班覆盖的班级（否则 4032）；
- 辅导员：class_id 必须属于本人所带班级（否则 4032）；
- 管理员：全量（T2-5）。
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import ForbiddenDataError, ParamError
from app.core.response import success

router = APIRouter(prefix="/timetable", tags=["timetable"])
classes_router = APIRouter(prefix="/classes", tags=["classes"])

_TERM_COLUMNS = "id, term_name, start_date, end_date, total_weeks, is_current"


def _get_current_term():
    """取当前学期（is_current='1' 且未删除），无则返回 None。"""
    with engine.connect() as conn:
        return conn.execute(
            text(
                f"SELECT {_TERM_COLUMNS} FROM campus_term "
                "WHERE is_current = '1' AND del_flag = '0' LIMIT 1"
            )
        ).first()


def _calc_week(term, today: date) -> int:
    """按 (当前日期 - 学期开始)/7 + 1 推算教学周（4.1）。"""
    start = term.start_date
    end = term.end_date
    if today < start:
        return 0
    if today > end:
        return term.total_weeks
    return ((today - start).days // 7) + 1


def _resolve_class_id(user: CurrentUser, class_id: int | None) -> tuple[int, str]:
    """按角色解析课表查询的 class_id（4.1 P0-03，防 IDOR）。

    返回 (class_id, scope)。scope 用于日志/调试；越权抛 4032。
    """
    role = user.role_code
    with engine.connect() as conn:
        if role == "student":
            # 学生：忽略入参，从本人档案推导（P0-03）
            row = conn.execute(
                text("SELECT class_id FROM campus_student "
                     "WHERE user_id = :uid AND del_flag = '0' LIMIT 1"),
                {"uid": user.user_id},
            ).first()
            if row is None or row[0] is None:
                raise ParamError("当前账号未关联班级，请联系管理员")
            return int(row[0]), "student"

        if role == "teacher":
            if class_id is None:
                raise ParamError("教师查询课表必须指定 class_id")
            # 任教班级 ∪ 所带班级（兼任辅导员，ADR-010/v2.4）
            ok = conn.execute(
                text("SELECT 1 FROM campus_course_offering "
                     "WHERE teacher_id = :uid AND class_id = :cid AND del_flag = '0' "
                     "UNION SELECT 1 FROM campus_class "
                     "WHERE id = :cid AND counselor_id = :uid AND del_flag = '0' LIMIT 1"),
                {"uid": user.user_id, "cid": class_id},
            ).first()
            if ok is None:
                raise ForbiddenDataError("无权查看该班级课表（仅限本人任课或所带班级）")
            return int(class_id), "teacher"

        # admin：全量（T2-5），入参 class_id 生效
        if class_id is None:
            raise ParamError("必须指定 class_id")
        row = conn.execute(
            text("SELECT 1 FROM campus_class WHERE id = :cid AND del_flag = '0'"),
            {"cid": class_id},
        ).first()
        if row is None:
            raise ParamError("班级不存在")
        return int(class_id), "admin"

    raise ForbiddenDataError("无权查看课表")  # pragma: no cover


# ===== T2-4：当前教学周 =====

@router.get("/current-week")
def current_week(user: CurrentUser, today: date | None = None) -> dict:
    """获取当前教学周（4.1 / T2-4）。

    取当前学期（is_current=1），按 (当前日期-学期开始)/7+1 推算。
    边界：学期前返回 0（未开始）；学期后返回 total_weeks（已结束）。
    """
    term = _get_current_term()
    if term is None:
        raise ParamError("当前学期未配置，请联系管理员")
    _id, term_name, start, end, total_weeks, is_current = term
    today = today or date.today()
    week = _calc_week(term, today)

    if today < start:
        status = "before_start"
    elif today > end:
        status = "after_end"
    else:
        status = "ongoing"

    return success({
        "term_id": int(_id),
        "term_name": term_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_weeks": int(total_weeks),
        "current_week": int(week),
        "semester_status": status,
    })


# ===== T2-5：课表查询 =====

@router.get("")
def timetable(
    user: CurrentUser,
    class_id: int | None = Query(None, ge=1, description="班级 id（学生忽略此参数，P0-03）"),
    week: int | None = Query(None, ge=1, description="教学周（默认当前周）"),
) -> dict:
    """查询课表（4.1 / 6.3.2 / T2-5）。

    返回该班级第 week 周实际开设课程（week ∈ [week_start, week_end]），
    按星期 + 起始节次排序。
    """
    term = _get_current_term()
    if term is None:
        raise ParamError("当前学期未配置，请联系管理员")
    _term_id, term_name, _start, _end, total_weeks, _is_current = term

    target_class_id, _scope = _resolve_class_id(user, class_id)

    if week is None:
        week = _calc_week(term, date.today())
    if week < 1 or week > total_weeks:
        raise ParamError(f"教学周超出范围（1~{total_weeks}）")

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT s.day_of_week, s.period_start, s.period_end, "
                "       c.course_name, COALESCE(u.nick_name, u.username) AS teacher_name, "
                "       s.location "
                "FROM campus_course_schedule s "
                "JOIN campus_course_offering o ON s.offering_id = o.id "
                "JOIN campus_course c ON o.course_id = c.id "
                "JOIN sys_user u ON o.teacher_id = u.id "
                "WHERE o.term_id = :tid AND o.class_id = :cid "
                "  AND s.week_start <= :wk AND s.week_end >= :wk "
                "  AND s.del_flag = '0' AND o.del_flag = '0' AND c.del_flag = '0' "
                "ORDER BY s.day_of_week, s.period_start"
            ),
            {"tid": int(_term_id), "cid": target_class_id, "wk": week},
        ).fetchall()

    items = [
        {
            "day_of_week": int(r[0]),
            "period_start": int(r[1]),
            "period_end": int(r[2]),
            "course_name": r[3],
            "teacher_name": r[4],  # COALESCE 处理昵称为空
            "location": r[5],
        }
        for r in rows
    ]
    return success({"term_name": term_name, "week": int(week), "items": items})


# ===== T2-6：我的班级 / 班级列表 =====

_CLASS_JOIN = (
    "SELECT cl.id AS class_id, cl.class_name, cl.class_code, cl.grade, cl.major, "
    "       cl.department_id, d.dept_name AS department_name "
    "FROM campus_class cl "
    "LEFT JOIN campus_department d ON cl.department_id = d.id AND d.del_flag = '0' "
)


def _my_classes(user: CurrentUser) -> list[dict]:
    """按角色返回本人可见班级（T2-6 / C-09）。"""
    role = user.role_code
    with engine.connect() as conn:
        if role == "student":
            rows = conn.execute(
                text(_CLASS_JOIN + "WHERE cl.id = (SELECT class_id FROM campus_student "
                     "WHERE user_id = :uid AND del_flag = '0' LIMIT 1) "
                     "AND cl.del_flag = '0'"),
                {"uid": user.user_id},
            ).fetchall()
        elif role == "teacher":
            # 任教班级 ∪ 所带班级（兼任辅导员，ADR-010/v2.4）
            rows = conn.execute(
                text(_CLASS_JOIN + "WHERE cl.id IN (SELECT DISTINCT class_id FROM campus_course_offering "
                     "WHERE teacher_id = :uid AND del_flag = '0' "
                     "UNION SELECT id FROM campus_class "
                     "WHERE counselor_id = :uid AND del_flag = '0') AND cl.del_flag = '0' "
                     "ORDER BY cl.id"),
                {"uid": user.user_id},
            ).fetchall()
        else:  # admin：全量
            rows = conn.execute(
                text(_CLASS_JOIN + "WHERE cl.del_flag = '0' ORDER BY cl.id"),
            ).fetchall()
    return [_class_row(r) for r in rows]


def _class_row(r) -> dict:
    """班级查询结果行 → 接口返回字典（含院系名称）。"""
    return {
        "class_id": int(r[0]),
        "class_name": r[1],
        "class_code": r[2],
        "grade": r[3],
        "major": r[4],
        "department_id": int(r[5]) if r[5] is not None else None,
        "department_name": r[6],
    }


@classes_router.get("/mine")
def classes_mine(user: CurrentUser) -> dict:
    """我的班级（6.2 / T2-6）：按角色区分。"""
    return success(_my_classes(user))


@classes_router.get("")
def classes_list(user: CurrentUser) -> dict:
    """班级列表（6.2，C-09）：按数据范围收敛（学生仅本人班级/教师仅任教班级/辅导员仅所带班级）。"""
    return success(_my_classes(user))
