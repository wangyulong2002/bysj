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
import time
from datetime import datetime

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import ConflictError, ForbiddenDataError, ParamError
from app.core.response import success
from app.core.time import now as campus_now

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
    """教师本人任教教学班列表（T4-6：成绩录入页教学班选择）。

    P1-17：原实现放行 `{"teacher","admin"}`，但查询条件恒为
    `WHERE o.teacher_id = :uid` —— admin 的 user_id 不是任何 teacher_id，
    因此**恒返回空列表**（"接口通了但数据是空的"，极耗排查时间）。
    现按数据范围给 admin 全量视图（设计 2.3：admin 数据范围 = ALL）。
    """
    if user.role_code not in {"teacher", "admin"}:
        raise ForbiddenDataError("仅教师可查询")
    where = "o.del_flag = '0'"
    params: dict = {"uid": user.user_id}
    if user.role_code != "admin":
        where += " AND o.teacher_id = :uid"
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT o.id, o.term_id, o.course_id, o.class_id, "
                 "c.course_name, t.term_name, cl.class_name "
                 "FROM campus_course_offering o "
                 "JOIN campus_course c ON o.course_id = c.id AND c.del_flag = '0' "
                 "JOIN campus_term t ON o.term_id = t.id AND t.del_flag = '0' "
                 "JOIN campus_class cl ON o.class_id = cl.id AND cl.del_flag = '0' "
                 f"WHERE {where} ORDER BY o.id"),
            params,
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

class ScoreItemIn(BaseModel):
    """单条学生成绩（6.3.3，P1-11）。

    注意：`usual_score` / `exam_score` **不做 ge/le 范围约束** —— 成绩越界属于
    "逐条跳过"的行级校验（P1-9：返回值里给出结构化 `skipped`），若在 schema 层
    拒收会让**整批 200 条一起失败**，正好踩中 P1-9 要修的问题。
    """

    student_id: int = Field(..., ge=1, description="学生档案 id")
    usual_score: float | None = Field(None, description="平时成绩（0~100，越界该行跳过）")
    exam_score: float | None = Field(None, description="考试成绩（0~100，越界该行跳过）")
    version: int = Field(0, ge=0, description="乐观锁版本号（修改时必传当前值）")


class ScoresUpsertIn(BaseModel):
    """成绩批量录入请求（P1-11）。

    原实现签名为 `body: dict`：无 schema、无类型、无范围校验，Swagger 上看不到
    请求体结构，且 `int(body.get("offering_id"))` 在缺字段时抛 `TypeError` →
    被兜底成 5000「服务异常」（明明是客户端参数问题却报成服务端故障）。
    """

    offering_id: int = Field(..., ge=1, description="教学班 id")
    scores: list[ScoreItemIn] = Field(
        ..., min_length=1, max_length=200, description="成绩明细（单次最多 200 条）"
    )


def _scores_upsert_impl(user: CurrentUser, body: ScoresUpsertIn) -> dict:
    """教师批量录入/修改成绩（6.3.3，POST 语义）。

    - 仅本人任课教学班（4032）；学生必须属于该教学班班级；
    - 分数范围 0~100（Pydantic 已声明校验）；总评自动计算并固化比例快照（T4-4）；
    - version 乐观锁：修改时 `WHERE version = :v`，0 行受影响 → 4091（并发冲突）；
    - B-11：录入/修改写入 `campus_score_audit`（old_detail/new_detail 快照）；
    - `Idempotency-Key` 幂等由中间件处理（P1-12）。
    """
    offering_id = int(body.offering_id)
    # P1-9：按 student_id 升序加锁 —— 原实现按「前端提交顺序」逐个 FOR UPDATE，
    # 两个教师同时提交不同顺序的名单会形成循环等待，死锁概率大幅上升
    #（项目自己的 1213 重试就是给它兜底的）。统一升序后加锁顺序全局一致。
    scores = sorted(body.scores, key=lambda s: s.student_id)

    with engine.begin() as conn:
        _check_offering_teacher(conn, offering_id, user.user_id)
        u_ratio, e_ratio = _get_score_ratio(conn)
        updated = 0
        skipped: list[dict] = []

        for item in scores:
            sid = int(item.student_id)
            usual = item.usual_score
            exam = item.exam_score
            version = int(item.version or 0)
            if usual is None or exam is None:
                skipped.append({"student_id": sid, "reason": "缺少平时/考试成绩"})
                continue
            usual = float(usual)
            exam = float(exam)
            if not (0 <= usual <= 100 and 0 <= exam <= 100):
                # 行级校验（P1-9）：越界只跳过该生，不影响整批
                skipped.append({"student_id": sid, "reason": "成绩超出 0~100"})
                continue
            if not _check_student_in_offering_class(conn, offering_id, sid):
                skipped.append({"student_id": sid, "reason": "学生不属于该教学班班级"})
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

            # P1-13：统一时间源（Asia/Shanghai），不再裸用 datetime.now()
            now = campus_now()
            if existing is None:
                # 首次录入（operation=1）
                try:
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
                except IntegrityError as exc:
                    # 并发首次录入：uk_score_student_offering 唯一冲突 →
                    # 乐观锁语义 4091（他人已先录入，事务由引擎回滚，B-08）
                    logger.warning("成绩并发录入唯一冲突（student=%s offering=%s）", sid, offering_id)
                    raise ConflictError(f"学生 {sid} 的成绩已被他人录入，请刷新后重试") from exc
            else:
                # 修改（operation=2）：乐观锁校验
                cur_version = int(existing[1])
                if version != cur_version:
                    raise ConflictError(f"学生 {sid} 的成绩已被他人修改，请刷新后重试")
                old_detail = {"usual_score": float(existing[2]), "exam_score": float(existing[3]),
                              "usual_ratio": existing[4], "exam_ratio": existing[5]}
                # P1-9：`version = version + 1` 与业务字段合并在**同一条 UPDATE**，
                # 原实现拆成两条 —— 一旦有人删掉上面的 FOR UPDATE（很自然的"优化"），
                # 乐观锁就形同虚设并静默丢更新。
                r = conn.execute(
                    text("UPDATE campus_score SET usual_score = :u, exam_score = :e, "
                         "total_score = :t, update_by = :ub, update_time = :now, "
                         "version = version + 1 "
                         "WHERE id = :id AND version = :v"),
                    {"u": usual, "e": exam, "t": total, "ub": user.user_id, "now": now,
                     "id": existing[0], "v": cur_version},
                )
                if r.rowcount == 0:
                    raise ConflictError(f"学生 {sid} 的成绩已被他人修改，请刷新后重试")
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

    # P1-9：返回结构化 skipped（原实现只把原因拼进 warnings 文本，前端若不展示
    # warnings，教师会以为全班录入成功）。warnings 保留以兼容既有前端。
    warnings = [f"学生 {s['student_id']} {s['reason']}，已跳过" for s in skipped]
    return success({"updated": updated, "skipped": skipped, "warnings": warnings})


@router.post("")
def scores_upsert(
    user: CurrentUser,
    body: ScoresUpsertIn,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> dict:
    """教师批量录入/修改成绩（6.3.3）。

    - 并发写入同教学班成绩时可能触发 InnoDB 死锁（1213）——
      自动重试（B-08 死锁重试约定，重试幂等，`Idempotency-Key` 由中间件保证）；
    - 其余校验/乐观锁/审计逻辑见 `_scores_upsert_impl`。
    """
    for attempt in range(3):
        try:
            return _scores_upsert_impl(user, body)
        except OperationalError as exc:
            if getattr(exc.orig, "args", [None])[0] != 1213:
                raise
            if attempt == 2:
                raise
            logger.warning("成绩写入死锁(1213)，第 %d 次重试", attempt + 1)
            time.sleep(0.05 * (attempt + 1))
    raise AssertionError("unreachable")  # pragma: no cover
