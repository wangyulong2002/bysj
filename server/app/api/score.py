"""成绩模块接口（4.3 / M4，T4-2~T4-5）。

- `GET /api/scores/mine`：学生查询本人**已发布**成绩（学期/课程筛选，2.3 USER_SELF）；
- `GET /api/scores/course?offering_id=`：教师录入前查询（仅本人任课教学班，T4-3）；
- `POST /api/scores`：教师批量录入/修改（6.3.3：offering 权限 + 乐观锁 + B-11 审计明细 +
  总评自动计算与比例快照固化；`Idempotency-Key` 由中间件处理）。

成绩状态机：教师录入为草稿（is_published=0，学生端不可见）；发布/撤销由 Django
管理端（T4-1）操作并写审计。仅本人任课教学班可操作（10.2 验收）。
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Header, Query
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import ConflictError, ForbiddenDataError, ParamError
from app.core.response import success

logger = logging.getLogger("campus.score")

router = APIRouter(prefix="/scores", tags=["scores"])

SCORE_LEVEL = 60  # 及格线（<60 不及格）


def _get_score_ratio(conn) -> tuple[int, int]:
    """读取成绩占比字典（campus_score_ratio，格式 '40:60'），缺省 40:60（T4-4）。"""
    row = conn.execute(
        text("SELECT dict_value FROM sys_dict_data "
             "WHERE dict_type = 'campus_score_ratio' AND del_flag = '0' ORDER BY id LIMIT 1")
    ).first()
    if row:
        parts = str(row[0]).split(":")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    return 40, 60


def _calc_total(usual: float, exam: float, u_ratio: int, e_ratio: int) -> float:
    """总评 = 平时×平时占比% + 考试×考试占比%（T4-4，比例快照固化）。"""
    return round(usual * u_ratio / 100 + exam * e_ratio / 100, 2)


def _get_student_id(conn, user_id: int) -> int:
    """按登录用户查学生档案 id（不存在 → 4032）。"""
    row = conn.execute(
        text("SELECT id FROM campus_student WHERE user_id = :uid AND del_flag = '0' LIMIT 1"),
        {"uid": user_id},
    ).first()
    if row is None:
        raise ForbiddenDataError("当前账号未关联学生档案")
    return int(row[0])


def _check_offering_teacher(conn, offering_id: int, teacher_id: int) -> None:
    """校验教学班属于本人任课（T4-3/6.3.3，越权 4032）。"""
    row = conn.execute(
        text("SELECT 1 FROM campus_course_offering "
             "WHERE id = :oid AND teacher_id = :tid AND del_flag = '0'"),
        {"oid": offering_id, "tid": teacher_id},
    ).first()
    if row is None:
        raise ForbiddenDataError("无权操作该教学班成绩（仅本人任课教学班）")


def _check_student_in_offering_class(conn, offering_id: int, student_id: int) -> bool:
    """学生是否属于教学班对应班级。"""
    row = conn.execute(
        text("SELECT 1 FROM campus_course_offering o "
             "JOIN campus_student s ON s.class_id = o.class_id AND s.del_flag = '0' "
             "WHERE o.id = :oid AND s.id = :sid"),
        {"oid": offering_id, "sid": student_id},
    ).first()
    return row is not None


# ===== T4-2：学生成绩查询（仅已发布）=====

@router.get("/mine")
def scores_mine(
    user: CurrentUser,
    term_id: int | None = Query(None, description="按学期筛选"),
    course_id: int | None = Query(None, description="按课程筛选"),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """学生本人已发布成绩（4.3/2.3：仅 is_published=1，4401 未发布不可见）。"""
    with engine.connect() as conn:
        student_id = _get_student_id(conn, user.user_id)
        where = ["sc.is_published = '1'", "sc.del_flag = '0'", "sc.student_id = :sid"]
        params: dict = {"sid": student_id}
        if term_id:
            where.append("o.term_id = :tid")
            params["tid"] = term_id
        if course_id:
            where.append("o.course_id = :cid")
            params["cid"] = course_id
        where_sql = " AND ".join(where)

        total = conn.execute(
            text(f"SELECT COUNT(*) FROM campus_score sc "
                 f"JOIN campus_course_offering o ON sc.offering_id = o.id "
                 f"WHERE {where_sql}"),
            params,
        ).scalar()
        rows = conn.execute(
            text(f"SELECT sc.id, sc.offering_id, sc.usual_score, sc.exam_score, sc.total_score, "
                 f"sc.usual_ratio, sc.exam_ratio, sc.publish_time, "
                 f"c.course_name, o.course_id, t.term_name, o.term_id "
                 f"FROM campus_score sc "
                 f"JOIN campus_course_offering o ON sc.offering_id = o.id "
                 f"JOIN campus_course c ON o.course_id = c.id AND c.del_flag = '0' "
                 f"JOIN campus_term t ON o.term_id = t.id AND t.del_flag = '0' "
                 f"WHERE {where_sql} ORDER BY sc.update_time DESC "
                 f"LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": (page_num - 1) * page_size},
        ).fetchall()

    data = {
        "total": int(total),
        "page_num": page_num,
        "page_size": page_size,
        "list": [
            {
                "score_id": r[0],
                "offering_id": r[1],
                "usual_score": float(r[2]) if r[2] is not None else None,
                "exam_score": float(r[3]) if r[3] is not None else None,
                "total_score": float(r[4]) if r[4] is not None else None,
                "pass": r[4] is not None and float(r[4]) >= SCORE_LEVEL,
                "usual_ratio": r[5],
                "exam_ratio": r[6],
                "publish_time": r[7].isoformat() if r[7] else None,
                "course_name": r[8],
                "course_id": r[9],
                "term_name": r[10],
                "term_id": r[11],
            }
            for r in rows
        ],
    }
    return success(data)


# ===== T4-6：教师任教教学班列表（录入页选择用）=====

@router.get("/teacher-offerings")
def teacher_offerings(user: CurrentUser) -> dict:
    """教师本人任教教学班列表（T4-6：成绩录入页教学班选择）。"""
    if user.role_code not in {"teacher", "admin"}:
        raise ForbiddenDataError("仅教师可查询")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT o.id, o.term_id, o.course_id, o.class_id, "
                 "c.course_name, t.term_name, cl.class_name "
                 "FROM campus_course_offering o "
                 "JOIN campus_course c ON o.course_id = c.id AND c.del_flag = '0' "
                 "JOIN campus_term t ON o.term_id = t.id AND t.del_flag = '0' "
                 "JOIN campus_class cl ON o.class_id = cl.id AND cl.del_flag = '0' "
                 "WHERE o.teacher_id = :uid AND o.del_flag = '0' ORDER BY o.id"),
            {"uid": user.user_id},
        ).fetchall()
    return success({
        "list": [
            {
                "offering_id": r[0], "term_id": r[1], "course_id": r[2], "class_id": r[3],
                "course_name": r[4], "term_name": r[5], "class_name": r[6],
            }
            for r in rows
        ],
    })


# ===== T4-3：教师录入前查询 =====

@router.get("/course")
def scores_course(
    user: CurrentUser,
    offering_id: int = Query(ge=1, description="教学班 id"),
) -> dict:
    """教师录入前查询：教学班学生名单 + 现有成绩（6.3.3，仅本人任课教学班）。"""
    with engine.connect() as conn:
        _check_offering_teacher(conn, offering_id, user.user_id)
        # 教学班信息
        offering = conn.execute(
            text("SELECT o.id, o.term_id, o.course_id, c.course_name, t.term_name, "
                 "cl.class_name, o.class_id "
                 "FROM campus_course_offering o "
                 "JOIN campus_course c ON o.course_id = c.id AND c.del_flag = '0' "
                 "JOIN campus_term t ON o.term_id = t.id AND t.del_flag = '0' "
                 "JOIN campus_class cl ON o.class_id = cl.id AND cl.del_flag = '0' "
                 "WHERE o.id = :oid"),
            {"oid": offering_id},
        ).first()
        # 学生名单（含已有成绩）
        rows = conn.execute(
            text("SELECT s.id, s.student_no, u.nick_name, "
                 "sc.usual_score, sc.exam_score, sc.total_score, sc.is_published, sc.version "
                 "FROM campus_student s "
                 "JOIN sys_user u ON s.user_id = u.id AND u.del_flag = '0' "
                 "LEFT JOIN campus_score sc ON sc.student_id = s.id "
                 "AND sc.offering_id = :oid AND sc.del_flag = '0' "
                 "WHERE s.class_id = :cid AND s.del_flag = '0' ORDER BY s.student_no"),
            {"oid": offering_id, "cid": offering[6]},
        ).fetchall()

    return success({
        "offering_id": offering[0],
        "term_id": offering[1],
        "course_id": offering[2],
        "course_name": offering[3],
        "term_name": offering[4],
        "class_name": offering[5],
        "students": [
            {
                "student_id": r[0],
                "student_no": r[1],
                "student_name": r[2],
                "usual_score": float(r[3]) if r[3] is not None else None,
                "exam_score": float(r[4]) if r[4] is not None else None,
                "total_score": float(r[5]) if r[5] is not None else None,
                "is_published": r[6] or "0",
                "version": int(r[7] or 0),
            }
            for r in rows
        ],
    })


# ===== T4-3：批量录入/修改 =====

@router.post("")
def scores_upsert(
    user: CurrentUser,
    body: dict,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict:
    """教师批量录入/修改成绩（6.3.3，POST 语义）。

    - 仅本人任课教学班（4032）；学生必须属于该教学班班级；
    - 分数范围 0~100；总评自动计算并固化比例快照（T4-4）；
    - version 乐观锁：修改时 `WHERE version = :v`，0 行受影响 → 4091（并发冲突）；
    - B-11：录入/修改写入 `campus_score_audit`（old_detail/new_detail 快照）；
    - `Idempotency-Key` 幂等由中间件处理（P1-12）。
    """
    offering_id = int(body.get("offering_id"))
    scores = body.get("scores") or []
    if not scores:
        raise ParamError("scores 不能为空")
    if len(scores) > 200:
        raise ParamError("单次最多提交 200 名学生成绩")

    with engine.begin() as conn:
        _check_offering_teacher(conn, offering_id, user.user_id)
        u_ratio, e_ratio = _get_score_ratio(conn)
        updated = 0
        warnings: list[str] = []

        for item in scores:
            sid = int(item.get("student_id"))
            usual = item.get("usual_score")
            exam = item.get("exam_score")
            version = int(item.get("version") or 0)
            if usual is None or exam is None:
                warnings.append(f"学生 {sid} 缺少平时/考试成绩，已跳过")
                continue
            try:
                usual = float(usual)
                exam = float(exam)
            except (TypeError, ValueError):
                warnings.append(f"学生 {sid} 成绩格式错误，已跳过")
                continue
            if not (0 <= usual <= 100 and 0 <= exam <= 100):
                warnings.append(f"学生 {sid} 成绩超出 0~100，已跳过")
                continue
            if not _check_student_in_offering_class(conn, offering_id, sid):
                warnings.append(f"学生 {sid} 不属于该教学班班级，已跳过")
                continue

            total = _calc_total(usual, exam, u_ratio, e_ratio)
            new_detail = {"usual_score": usual, "exam_score": exam,
                          "usual_ratio": u_ratio, "exam_ratio": e_ratio}

            existing = conn.execute(
                text("SELECT id, version, usual_score, exam_score, usual_ratio, exam_ratio "
                     "FROM campus_score WHERE student_id = :sid AND offering_id = :oid "
                     "AND del_flag = '0' FOR UPDATE"),
                {"sid": sid, "oid": offering_id},
            ).first()

            now = datetime.now()
            if existing is None:
                # 首次录入（operation=1）
                conn.execute(
                    text("INSERT INTO campus_score "
                         "(student_id, offering_id, usual_score, exam_score, total_score, "
                         " usual_ratio, exam_ratio, is_published, version, "
                         " create_by, update_by, update_time, del_flag) "
                         "VALUES (:sid, :oid, :u, :e, :t, :ur, :er, '0', 0, "
                         " :cb, :ub, :now, '0')"),
                    {"sid": sid, "oid": offering_id, "u": usual, "e": exam, "t": total,
                     "ur": u_ratio, "er": e_ratio, "cb": user.user_id, "ub": user.user_id,
                     "now": now},
                )
                conn.execute(
                    text("INSERT INTO campus_score_audit "
                         "(student_id, offering_id, old_score, new_score, old_detail, new_detail, "
                         " operator_id, operation, operation_time) "
                         "VALUES (:sid, :oid, NULL, :t, NULL, :nd, :op, '1', :now)"),
                    {"sid": sid, "oid": offering_id, "t": total, "nd": json.dumps(new_detail),
                     "op": user.user_id, "now": now},
                )
            else:
                # 修改（operation=2）：乐观锁校验
                cur_version = int(existing[1])
                if version != cur_version:
                    raise ConflictError(f"学生 {sid} 的成绩已被他人修改，请刷新后重试")
                old_detail = {"usual_score": float(existing[2]), "exam_score": float(existing[3]),
                              "usual_ratio": existing[4], "exam_ratio": existing[5]}
                r = conn.execute(
                    text("UPDATE campus_score SET usual_score = :u, exam_score = :e, "
                         "total_score = :t, update_by = :ub, update_time = :now "
                         "WHERE id = :id AND version = :v"),
                    {"u": usual, "e": exam, "t": total, "ub": user.user_id, "now": now,
                     "id": existing[0], "v": cur_version},
                )
                if r.rowcount == 0:
                    raise ConflictError(f"学生 {sid} 的成绩已被他人修改，请刷新后重试")
                conn.execute(
                    text("UPDATE campus_score SET version = version + 1 WHERE id = :id"),
                    {"id": existing[0]},
                )
                conn.execute(
                    text("INSERT INTO campus_score_audit "
                         "(student_id, offering_id, old_score, new_score, old_detail, new_detail, "
                         " operator_id, operation, operation_time) "
                         "VALUES (:sid, :oid, :os, :t, :od, :nd, :op, '2', :now)"),
                    {"sid": sid, "oid": offering_id, "os": float(existing[2]),
                     "t": total, "od": json.dumps(old_detail), "nd": json.dumps(new_detail),
                     "op": user.user_id, "now": now},
                )
            updated += 1

    return success({"updated": updated, "warnings": warnings})
