"""请假模块接口（4.4 / M5，T5-1~T5-5）。

- `POST /api/leaves`：学生提交（P1-14 时长权威 + 幂等 + 附件）；
- `GET /api/leaves/mine`：本人记录（分页/状态筛选）；
- `PUT /api/leaves/{id}/cancel`：撤销（仅待审批 0→3，乐观锁）；
- `GET /api/leaves/pending`：辅导员/兼任教师待审批（counselor_id=本人 所带班级，ADR-010）；
- `PUT /api/leaves/{id}/approve`：审批（越权 4032、状态机 0→1/2、乐观锁、
  审批更新+站内消息+审计同事务 B-08）；
- `GET /api/leaves/students?offering_id=`：教师查看本教学班学生请假（A-02 时间关联）。

状态机：0 待审批 → 1 通过 / 2 驳回；0 → 3 撤销（学生发起）。
"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import (
    ConflictError,
    ForbiddenDataError,
    LeaveStatusInvalidError,
    ParamError,
)
from app.core.response import success

logger = logging.getLogger("campus.leave")

router = APIRouter(prefix="/leaves", tags=["leaves"])

TZ = ZoneInfo("Asia/Shanghai")
MAX_LEAVE_MINUTES = 30 * 24 * 60  # 30 天上限（4.4，可配置）

_STATUS_NAMES = {"0": "待审批", "1": "通过", "2": "驳回", "3": "撤销"}


def _parse_dt(value) -> datetime:
    """解析 ISO-8601 时间，统一转 Asia/Shanghai（4.4：禁止无约束时区串）。"""
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ParamError("时间格式必须为 ISO-8601（如 2026-09-01T08:00:00+08:00）") from exc
    if dt.tzinfo is None:
        raise ParamError("时间必须携带时区（禁止无约束时区串）")
    return dt.astimezone(TZ)


def _get_student_id(conn, user_id: int) -> int:
    """当前登录用户的学生档案 id。"""
    row = conn.execute(
        text("SELECT id FROM campus_student WHERE user_id = :uid AND del_flag = '0' LIMIT 1"),
        {"uid": user_id},
    ).first()
    if row is None:
        raise ForbiddenDataError("当前账号未关联学生档案")
    return int(row[0])


def _check_attachment(conn, attachment_id: int | None, owner_user_id: int) -> None:
    """附件校验：存在且属于本人（可空）。"""
    if attachment_id is None:
        return
    row = conn.execute(
        text("SELECT 1 FROM campus_file WHERE id = :fid AND uploader_id = :uid "
             "AND del_flag = '0'"),
        {"fid": attachment_id, "uid": owner_user_id},
    ).first()
    if row is None:
        raise ParamError("附件不存在或无权使用")


def _leave_row(r, with_student: bool = True) -> dict:
    """请假行 → 响应字典。"""
    d = {
        "leave_id": int(r[0]),
        "leave_type": r[1],
        "reason": r[2],
        "start_time": r[3].isoformat() if r[3] else None,
        "end_time": r[4].isoformat() if r[4] else None,
        "leave_duration_minutes": r[5],
        "total_days": float(r[6]),
        "status": r[7],
        "status_name": _STATUS_NAMES.get(r[7], r[7]),
        "attachment_id": r[8],
        "approve_comment": r[9],
        "approve_time": r[10].isoformat() if r[10] else None,
        "create_time": r[11].isoformat() if r[11] else None,
    }
    if with_student:
        d["student_id"] = int(r[12])
        d["student_no"] = r[13]
        d["student_name"] = r[14]
    return d


# ===== T5-1：学生提交请假 =====

@router.post("")
def leave_create(user: CurrentUser, body: dict) -> dict:
    """学生提交请假（6.3.4 / P1-14）。

    - 时长权威字段 leave_duration_minutes（分钟），total_days 换算；
    - end > start、≤30 天、时区统一 Asia/Shanghai、跨学期允许；
    - 附件复用 campus_file（attachment_id）；
    - 幂等：Idempotency-Key 由中间件处理（P1-12）。
    """
    leave_type = str(body.get("leave_type", ""))
    reason = str(body.get("reason") or "").strip()
    start_time = _parse_dt(body.get("start_time"))
    end_time = _parse_dt(body.get("end_time"))
    attachment_id = body.get("attachment_id")

    if leave_type not in {"1", "2", "3"}:
        raise ParamError("请假类型无效（1事假 2病假 3其他）")
    if not reason:
        raise ParamError("请填写请假事由")
    if len(reason) > 500:
        raise ParamError("请假事由不能超过 500 字")
    if end_time <= start_time:
        raise ParamError("结束时间必须晚于开始时间")
    minutes = int((end_time - start_time).total_seconds() // 60)
    if minutes <= 0:
        raise ParamError("请假时长必须大于 0")
    if minutes > MAX_LEAVE_MINUTES:
        raise ParamError("单次请假最长 30 天")

    with engine.begin() as conn:
        student_id = _get_student_id(conn, user.user_id)
        _check_attachment(conn, attachment_id, user.user_id)
        total_days = round(minutes / 1440, 1)
        r = conn.execute(
            text("INSERT INTO campus_leave "
                 "(student_id, leave_type, reason, start_time, end_time, "
                 " leave_duration_minutes, total_days, status, attachment_id, version, "
                 " create_time, del_flag) "
                 "VALUES (:sid, :lt, :reason, :st, :et, :min, :days, '0', :att, 0, NOW(), '0')"),
            {"sid": student_id, "lt": leave_type, "reason": reason,
             "st": start_time, "et": end_time, "min": minutes,
             "days": total_days, "att": attachment_id},
        )
        leave_id = r.lastrowid

    return success({
        "leave_id": leave_id,
        "status": "0",
        "leave_duration_minutes": minutes,
        "total_days": total_days,
        "message": "申请已提交，等待辅导员审批",
    })


# ===== T5-2：我的请假记录 + 撤销 =====

@router.get("/mine")
def leaves_mine(
    user: CurrentUser,
    status: str | None = Query(None, pattern="^[0123]$", description="按状态筛选"),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """我的请假记录（仅本人，2.3 USER_SELF）。"""
    with engine.connect() as conn:
        student_id = _get_student_id(conn, user.user_id)
        where = ["l.student_id = :sid", "l.del_flag = '0'"]
        params: dict = {"sid": student_id}
        if status:
            where.append("l.status = :st")
            params["st"] = status
        where_sql = " AND ".join(where)
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM campus_leave l WHERE {where_sql}"), params
        ).scalar()
        rows = conn.execute(
            text(f"SELECT l.id, l.leave_type, l.reason, l.start_time, l.end_time, "
                 f"l.leave_duration_minutes, l.total_days, l.status, l.attachment_id, "
                 f"l.approve_comment, l.approve_time, l.create_time, "
                 f"l.student_id, '' AS no, '' AS name "
                 f"FROM campus_leave l WHERE {where_sql} "
                 f"ORDER BY l.create_time DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": (page_num - 1) * page_size},
        ).fetchall()

    return success({
        "total": int(total), "page_num": page_num, "page_size": page_size,
        "list": [_leave_row(r, with_student=False) for r in rows],
    })


@router.put("/{leave_id}/cancel")
def leave_cancel(user: CurrentUser, leave_id: int) -> dict:
    """撤销请假（T5-2：仅 status=0 待审批可撤销 → 3，乐观锁）。"""
    with engine.begin() as conn:
        student_id = _get_student_id(conn, user.user_id)
        row = conn.execute(
            text("SELECT id, status, version FROM campus_leave "
                 "WHERE id = :lid AND student_id = :sid AND del_flag = '0' FOR UPDATE"),
            {"lid": leave_id, "sid": student_id},
        ).first()
        if row is None:
            raise ParamError("请假记录不存在")
        if row[1] != "0":
            raise LeaveStatusInvalidError("仅待审批的请假可撤销")
        conn.execute(
            text("UPDATE campus_leave SET status = '3', version = version + 1 "
                 "WHERE id = :id AND version = :v"),
            {"id": row[0], "v": row[2]},
        )
    return success({"leave_id": leave_id, "status": "3", "message": "已撤销"})


# ===== T5-3：辅导员（含兼任教师）待审批列表 =====

@router.get("/pending")
def leaves_pending(
    user: CurrentUser,
    status: str | None = Query(None, pattern="^[0123]$", description="按状态筛选（默认待审批）"),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """待审批列表（T5-3/ADR-010）：仅本人所带班级（campus_class.counselor_id=本人）学生申请。"""
    if user.role_code not in {"teacher", "admin"}:
        raise ForbiddenDataError("仅辅导员（教师兼任）可查看待审批列表")
    with engine.connect() as conn:
        where = [
            "l.del_flag = '0'",
            "cl.counselor_id = :uid",  # 所带班级（动态判定，ADR-010）
        ]
        params: dict = {"uid": user.user_id}
        if status:
            where.append("l.status = :st")
            params["st"] = status
        else:
            where.append("l.status = '0'")
        where_sql = " AND ".join(where)

        total = conn.execute(
            text(f"SELECT COUNT(*) FROM campus_leave l "
                 f"JOIN campus_student s ON l.student_id = s.id "
                 f"JOIN campus_class cl ON s.class_id = cl.id AND cl.del_flag = '0' "
                 f"WHERE {where_sql}"),
            params,
        ).scalar()
        rows = conn.execute(
            text(f"SELECT l.id, l.leave_type, l.reason, l.start_time, l.end_time, "
                 f"l.leave_duration_minutes, l.total_days, l.status, l.attachment_id, "
                 f"l.approve_comment, l.approve_time, l.create_time, "
                 f"s.id, s.student_no, u.nick_name "
                 f"FROM campus_leave l "
                 f"JOIN campus_student s ON l.student_id = s.id "
                 f"JOIN campus_class cl ON s.class_id = cl.id AND cl.del_flag = '0' "
                 f"JOIN sys_user u ON s.user_id = u.id AND u.del_flag = '0' "
                 f"WHERE {where_sql} ORDER BY l.create_time ASC "
                 f"LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": (page_num - 1) * page_size},
        ).fetchall()

    return success({
        "total": int(total), "page_num": page_num, "page_size": page_size,
        "list": [_leave_row(r) for r in rows],
    })


# ===== T5-4：审批 =====

@router.put("/{leave_id}/approve")
def leave_approve(user: CurrentUser, leave_id: int, body: dict) -> dict:
    """审批请假（6.3.5 / T5-4）。

    - 越权：审批人必须是该生班级 counselor_id（4032，ADR-010）；
    - 状态机 0→1/2（4301 其他状态）；乐观锁 version；
    - 事务（B-08）：更新请假 + 写站内消息通知学生同事务；
    - 幂等：Idempotency-Key 由中间件处理。
    """
    if user.role_code not in {"teacher", "admin"}:
        raise ForbiddenDataError("无审批权限")
    approve = str(body.get("approve", ""))
    comment = str(body.get("comment") or "").strip()
    if approve not in {"1", "2"}:
        raise ParamError("审批结果无效（1通过 2驳回）")
    if len(comment) > 500:
        raise ParamError("审批意见不能超过 500 字")

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT l.id, l.student_id, l.status, l.version, s.user_id AS stu_user_id, "
                 "cl.counselor_id AS counselor_id "
                 "FROM campus_leave l "
                 "JOIN campus_student s ON l.student_id = s.id "
                 "JOIN campus_class cl ON s.class_id = cl.id AND cl.del_flag = '0' "
                 "WHERE l.id = :lid AND l.del_flag = '0' FOR UPDATE"),
            {"lid": leave_id},
        ).first()
        if row is None:
            raise ParamError("请假记录不存在")
        if user.role_code == "teacher" and int(row[5]) != user.user_id:
            raise ForbiddenDataError("无权审批该申请（仅本人所带班级学生）")
        if row[2] != "0":
            raise LeaveStatusInvalidError("该申请已处理，无法重复审批")

        r = conn.execute(
            text("UPDATE campus_leave SET status = :st, approver_id = :ap, "
                 "approve_time = NOW(), approve_comment = :cm, version = version + 1 "
                 "WHERE id = :id AND version = :v"),
            {"st": approve, "ap": user.user_id, "cm": comment,
             "id": row[0], "v": row[3]},
        )
        if r.rowcount == 0:
            raise ConflictError("该申请已被并发处理，请刷新后重试")

        # 站内消息通知学生（B-08：同事务）
        title = "请假审批通过" if approve == "1" else "请假审批驳回"
        content = f"您的请假（{row[1]}）已{'通过' if approve == '1' else '驳回'}"
        if comment:
            content += f"：{comment}"
        conn.execute(
            text("INSERT INTO campus_message (user_id, msg_type, title, content, "
                 " business_type, business_id, is_read, create_time, del_flag) "
                 "VALUES (:uid, '1', :title, :content, 'leave', :bid, '0', NOW(), '0')"),
            {"uid": row[4], "title": title, "content": content, "bid": leave_id},
        )

    return success({"leave_id": leave_id, "status": approve, "notified": True})


# ===== T5-5：教师查看本教学班学生请假 =====

@router.get("/students")
def leaves_students(
    user: CurrentUser,
    offering_id: int = Query(ge=1, description="教学班 id"),
) -> dict:
    """教师查看本教学班学生请假（只读，便于考勤；A-02：按时间返回，考勤自行关联）。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT class_id FROM campus_course_offering "
                 "WHERE id = :oid AND teacher_id = :tid AND del_flag = '0'"),
            {"oid": offering_id, "tid": user.user_id},
        ).first()
        if row is None:
            raise ForbiddenDataError("无权查看该教学班（仅本人任课教学班）")
        class_id = row[0]
        rows = conn.execute(
            text("SELECT l.id, l.leave_type, l.reason, l.start_time, l.end_time, "
                 "l.leave_duration_minutes, l.total_days, l.status, l.attachment_id, "
                 "l.approve_comment, l.approve_time, l.create_time, "
                 "s.id, s.student_no, u.nick_name "
                 "FROM campus_leave l "
                 "JOIN campus_student s ON l.student_id = s.id AND s.class_id = :cid "
                 "JOIN sys_user u ON s.user_id = u.id AND u.del_flag = '0' "
                 "WHERE l.del_flag = '0' ORDER BY l.create_time DESC"),
            {"cid": class_id},
        ).fetchall()

    return success({"offering_id": offering_id, "list": [_leave_row(r) for r in rows]})
