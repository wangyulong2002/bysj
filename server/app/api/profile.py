"""个人信息接口（4.5 / M6-T6-1）：GET/PUT /api/profile + 完整手机号专门接口。

- 数据权限：仅本人记录（按 JWT user_id 查询/更新，P0-03）。
- B-09/P1-17（PIPL）：默认序列化只返回 `masked_phone`（138****1234），
  禁止把完整手机号先返回前端再由前端脱敏；完整号码走专门接口
  `GET /api/profile/phone`（权限点 `phone.full`：仅本人可见，访问写审计日志）。
- 头像走 campus_file（P1-16）：PUT 时传 `avatar_file_id`（本人上传的文件），
  读取时生成短期签名 URL（B-02，供小程序 image 渲染）。
"""
import logging
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import ForbiddenDataError, ParamError, UnauthorizedError
from app.core.response import success
from app.core.security import build_signed_file_url

logger = logging.getLogger("campus.profile")

router = APIRouter(tags=["profile"])

PHONE_RE = re.compile(r"^1\d{10}$")


def _mask_phone(phone: str | None) -> str | None:
    """手机号脱敏（B-09/P1-17）：`138****1234`；非 11 位兜底保留首尾。"""
    if not phone:
        return None
    p = str(phone).strip()
    if len(p) >= 11:
        return f"{p[:3]}****{p[-4:]}"
    if len(p) >= 2:
        return f"{p[:1]}****{p[-1:]}"
    return "****"


def _avatar_url(avatar: str | None) -> str | None:
    """头像字段：存 file_id（纯数字）→ 校验文件存在 → 返回签名 URL；否则原样返回。"""
    if not avatar:
        return None
    if str(avatar).isdigit():
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM campus_file WHERE id = :fid AND del_flag = '0'"),
                {"fid": int(avatar)},
            ).first()
        if row is None:
            return None
        return build_signed_file_url(int(avatar))
    return avatar


def _load_profile(user_id: int) -> dict:
    """查询本人完整档案（sys_user + 角色扩展：班级/职称/课程）。"""
    with engine.connect() as conn:
        user = conn.execute(
            text(
                "SELECT id, username, nick_name, gender, phone, email, avatar, "
                "student_no, teacher_no, role_code, wechat_openid "
                "FROM sys_user WHERE id = :uid AND del_flag = '0'"
            ),
            {"uid": user_id},
        ).first()
    if user is None:
        raise UnauthorizedError("账号不存在或已停用")

    (uid, username, nick_name, gender, phone, email, avatar,
     student_no, teacher_no, role_code, wechat_openid) = user
    role_code = role_code or ""
    no = student_no or teacher_no

    detail: dict = {"class_name": None, "department_name": None, "title": None, "courses": []}
    if role_code == "student":
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT s.student_no, c.class_name, s.class_id "
                    "FROM campus_student s "
                    "LEFT JOIN campus_class c ON c.id = s.class_id "
                    "WHERE s.user_id = :uid AND s.del_flag = '0'"
                ),
                {"uid": user_id},
            ).first()
        if row:
            no = row[0] or no
            detail["class_name"] = row[1]
            class_id = row[2]
            if class_id is not None:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text(
                            "SELECT DISTINCT co.course_id, c.course_name "
                            "FROM campus_course_offering co "
                            "JOIN campus_course c ON c.id = co.course_id "
                            "JOIN campus_term t ON t.id = co.term_id "
                            "WHERE co.class_id = :cid AND t.is_current = '1' "
                            "AND co.del_flag = '0' AND c.del_flag = '0'"
                        ),
                        {"cid": class_id},
                    ).all()
                detail["courses"] = [{"course_id": r[0], "course_name": r[1]} for r in rows]
    elif role_code == "teacher":
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT t.teacher_no, t.title, d.dept_name "
                    "FROM campus_teacher t "
                    "LEFT JOIN campus_department d ON d.id = t.department_id "
                    "WHERE t.user_id = :uid AND t.del_flag = '0'"
                ),
                {"uid": user_id},
            ).first()
        if row:
            no = row[0] or no
            detail["title"] = row[1]
            detail["department_name"] = row[2]
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT co.course_id, c.course_name "
                    "FROM campus_course_offering co "
                    "JOIN campus_course c ON c.id = co.course_id "
                    "JOIN campus_term t ON t.id = co.term_id "
                    "WHERE co.teacher_id = :uid AND t.is_current = '1' "
                    "AND co.del_flag = '0' AND c.del_flag = '0'"
                ),
                {"uid": user_id},
            ).all()
        detail["courses"] = [{"course_id": r[0], "course_name": r[1]} for r in rows]

    return {
        "user_id": uid,
        "username": username,
        "name": nick_name or username,
        "gender": gender,
        "masked_phone": _mask_phone(phone),
        "email": email,
        "avatar": _avatar_url(avatar),
        "role_code": role_code,
        "student_no": no if role_code == "student" else None,
        "teacher_no": no if role_code == "teacher" else None,
        "wechat_bound": bool(wechat_openid),
        **detail,
    }


@router.get("/profile")
def get_profile(user: CurrentUser) -> dict:
    """个人信息（4.5 / T6-1）：默认手机号脱敏展示（B-09/P1-17）。"""
    return success(_load_profile(user.user_id))


class ProfileUpdateIn(BaseModel):
    """个人信息修改请求（T6-1）：手机号 / 头像（campus_file id）。"""

    phone: str | None = Field(None, max_length=20, description="手机号（11 位）")
    avatar_file_id: int | None = Field(None, ge=1, description="头像文件 id（本人上传，P1-16）")


@router.put("/profile")
def update_profile(body: ProfileUpdateIn, user: CurrentUser) -> dict:
    """修改个人信息（T6-1）：手机号、头像；仅本人记录（数据权限）。"""
    updates: list[str] = []
    params: dict = {"uid": user.user_id}

    if body.phone is not None:
        phone = body.phone.strip()
        if not PHONE_RE.match(phone):
            raise ParamError("手机号格式不正确（需为 1 开头的 11 位号码）")
        updates.append("phone = :phone")
        params["phone"] = phone

    if body.avatar_file_id is not None:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT owner_id, uploader_id FROM campus_file "
                     "WHERE id = :fid AND del_flag = '0'"),
                {"fid": body.avatar_file_id},
            ).first()
        if row is None:
            raise ParamError("头像文件不存在")
        owner_id, uploader_id = row
        if owner_id != user.user_id and uploader_id != user.user_id:
            raise ForbiddenDataError("只能使用本人上传的头像文件")
        updates.append("avatar = :avatar")
        params["avatar"] = str(body.avatar_file_id)

    if not updates:
        raise ParamError("没有需要修改的字段")

    with engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE sys_user SET {', '.join(updates)}, update_time = NOW() "
                "WHERE id = :uid"
            ),
            params,
        )
    logger.info("个人信息更新 user_id=%s fields=%s", user.user_id,
                [u.split("=")[0].strip() for u in updates])
    return success(_load_profile(user.user_id))


@router.get("/profile/phone")
def get_full_phone(user: CurrentUser) -> dict:
    """完整手机号（B-09/P1-17，权限点 `phone.full`：仅本人可见，访问写审计日志）。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT phone FROM sys_user WHERE id = :uid AND del_flag = '0'"),
            {"uid": user.user_id},
        ).first()
    if row is None:
        raise UnauthorizedError("账号不存在或已停用")
    logger.info("PHONE.FULL 完整手机号查看审计 user_id=%s", user.user_id)
    return success({"phone": row[0]}, message="ok")
