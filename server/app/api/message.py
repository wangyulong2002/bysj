"""站内消息中心接口（4.4 / T5-8，5.3.13）。

- `GET /api/messages`：本人消息分页（未读过滤）；
- `GET /api/messages/unread-count`：未读数（TabBar 红点）；
- `PUT /api/messages/{id}/read`：标记已读（本人，幂等）。

保留策略（C-06）：消息保留 180 天，过期归档/清理由定时任务（del_flag=2）处理。
"""
import logging

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.database import engine
from app.core.errors import ForbiddenDataError, ParamError
from app.core.response import success

logger = logging.getLogger("campus.message")

router = APIRouter(prefix="/messages", tags=["messages"])

_MSG_TYPE_NAMES = {"1": "请假审批", "2": "系统", "3": "公告"}


# ===== T5-8：消息列表 =====

@router.get("")
def messages_list(
    user: CurrentUser,
    unread_only: int = Query(0, ge=0, le=1, description="仅未读：1"),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """本人消息分页（C-06：仅未归档 del_flag=0）。"""
    with engine.connect() as conn:
        where = ["m.user_id = :uid", "m.del_flag = '0'"]
        params: dict = {"uid": user.user_id}
        if unread_only == 1:
            where.append("m.is_read = '0'")
        where_sql = " AND ".join(where)
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM campus_message m WHERE {where_sql}"), params
        ).scalar()
        rows = conn.execute(
            text(f"SELECT m.id, m.msg_type, m.title, m.content, m.business_type, "
                 f"m.business_id, m.is_read, m.read_time, m.create_time "
                 f"FROM campus_message m WHERE {where_sql} "
                 f"ORDER BY m.create_time DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": (page_num - 1) * page_size},
        ).fetchall()

    return success({
        "total": int(total), "page_num": page_num, "page_size": page_size,
        "list": [
            {
                "id": r[0],
                "msg_type": r[1],
                "msg_type_name": _MSG_TYPE_NAMES.get(r[1], ""),
                "title": r[2],
                "content": r[3],
                "business_type": r[4],
                "business_id": r[5],
                "is_read": r[6],
                "read_time": r[7].isoformat() if r[7] else None,
                "create_time": r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ],
    })


# ===== T5-8：未读数 =====

@router.get("/unread-count")
def messages_unread_count(user: CurrentUser) -> dict:
    """未读消息数（TabBar 红点）。"""
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM campus_message "
                 "WHERE user_id = :uid AND is_read = '0' AND del_flag = '0'"),
            {"uid": user.user_id},
        ).scalar()
    return success({"count": int(count)})


# ===== T5-8：标记已读 =====

@router.put("/{message_id}/read")
def message_read(user: CurrentUser, message_id: int) -> dict:
    """标记消息已读（本人，幂等：已读重复标记无副作用）。"""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM campus_message "
                 "WHERE id = :mid AND user_id = :uid AND del_flag = '0'"),
            {"mid": message_id, "uid": user.user_id},
        ).first()
        if row is None:
            raise ForbiddenDataError("消息不存在或无权操作")
        conn.execute(
            text("UPDATE campus_message SET is_read = '1', read_time = NOW() "
                 "WHERE id = :mid AND is_read = '0'"),
            {"mid": message_id},
        )
    return success({"message_id": message_id, "is_read": "1"})
