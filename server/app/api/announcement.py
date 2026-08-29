"""公告模块接口（4.2 / T3-2/T3-3）。

- `GET /api/announcements`：公告列表（类型/关键字/时间/置顶筛选 + 分页，
  置顶优先 + 发布时间倒序，6.2）；
- `GET /api/announcements/{id}`：公告详情。

数据权限（2.3 实体归属规则）：全部角色仅可查看自己可见范围内的公告：
- 校园公告（ann_type=1）：全部登录用户可见；
- 院系公告（ann_type=2）：本人所属院系 == 目标院系
  （学生取档案班级院系；教师取档案院系+任教班级院系；辅导员取所带班级院系）。

**v2.5（ADR-011）**：班级公告类型（ann_type=3）与 `target_class_id` 已移除，
可见范围仅按「校园 / 院系」两路判定（`ann_type` 入参仅接受 1/2）。

应用端只读（4.2 P0-02 方案 B：公告仅管理端发布），仅返回已发布（status=1）。
Redis 版本化缓存（T3-3，P1-11）：列表走 `ann:list:{N}:{scope}:{type}:{page}`，
Redis 故障降级直查 MySQL（9.7 降级矩阵）。
"""
import json
from datetime import date

from fastapi import APIRouter, Path, Query
from sqlalchemy import text

from app.api.deps import CurrentUser
from app.core.announcement_cache import (
    build_list_key,
    cache_get,
    cache_set,
    get_ann_version,
)
from app.core.database import engine
from app.core.errors import ForbiddenDataError, ParamError
from app.core.response import success

router = APIRouter(prefix="/announcements", tags=["announcements"])

_ANN_COLUMNS = (
    "a.id, a.title, a.content, a.ann_type, a.target_department_id, "
    "a.is_top, a.status, a.publish_time, a.create_time, "
    "COALESCE(u.nick_name, u.username) AS publisher_name, "
    "d.dept_name AS target_department_name"
)
_ANN_JOIN = (
    " FROM campus_announcement a "
    "LEFT JOIN sys_user u ON a.publisher_id = u.id "
    "LEFT JOIN campus_department d ON a.target_department_id = d.id AND d.del_flag = '0' "
)

_ANN_TYPE_NAMES = {"1": "校园公告", "2": "院系公告"}  # v2.5/ADR-011：班级公告已移除


def _visible_dept_ids(user: CurrentUser) -> list[int]:
    """计算用户可见的院系集合（2.3 数据权限，公告可见范围）。

    v2.5（ADR-011）：班级公告类型已移除，可见范围不再按班级判定——
    - 校园公告（ann_type=1）：所有人可见（不走过滤）；
    - 院系公告（ann_type=2）：target_department ∈ 本集合。

    院系来源：学生 = 档案班级院系；教师 = 档案院系 ∪ 任教/所带班级院系（ADR-010）；
    admin = 全量（返回空集合表示不过滤）。
    """
    role = user.role_code
    with engine.connect() as conn:
        if role == "student":
            row = conn.execute(
                text("SELECT st.class_id, cl.department_id "
                     "FROM campus_student st "
                     "LEFT JOIN campus_class cl ON st.class_id = cl.id AND cl.del_flag = '0' "
                     "WHERE st.user_id = :uid AND st.del_flag = '0' LIMIT 1"),
                {"uid": user.user_id},
            ).first()
            if row is None:
                raise ParamError("当前账号未关联班级，请联系管理员")
            return [int(row[1])] if row[1] else []

        if role == "teacher":
            # 任教班级 ∪ 所带班级（兼任辅导员，ADR-010/v2.4）+ 档案院系 + 班级院系
            rows = conn.execute(
                text("SELECT class_id FROM campus_course_offering "
                     "WHERE teacher_id = :uid AND del_flag = '0' "
                     "UNION SELECT id FROM campus_class "
                     "WHERE counselor_id = :uid AND del_flag = '0'"),
                {"uid": user.user_id},
            ).fetchall()
            class_ids = list({int(r[0]) for r in rows})
            class_id_str = ",".join(str(c) for c in class_ids) or "0"
            dept_rows = conn.execute(
                text(f"SELECT department_id FROM campus_class "
                     f"WHERE id IN ({class_id_str}) AND del_flag = '0'"),
            ).fetchall()
            dept_ids = list({int(r[0]) for r in dept_rows if r[0] is not None})
            own = conn.execute(
                text("SELECT department_id FROM campus_teacher "
                     "WHERE user_id = :uid AND del_flag = '0' LIMIT 1"),
                {"uid": user.user_id},
            ).first()
            if own and own[0] is not None:
                dept_ids.append(int(own[0]))
            return list(set(dept_ids))

        # admin：全量（P1-10 仅管理端，应用端接口按登录态收敛，此处不额外过滤）
        return []


def _visibility_sql(dept_ids: list[int]) -> str:
    """构造公告可见范围 SQL 片段（2.3；v2.5：仅校园/院系两路匹配）。"""
    dept_list = ",".join(str(d) for d in dept_ids) or "0"
    return (
        " (a.ann_type = '1' "
        f" OR (a.ann_type = '2' AND a.target_department_id IN ({dept_list})) )"
    )


def _fmt_dt(v) -> str | None:
    """时间格式化：datetime → ISO 字符串；已是字符串则原样返回（兼容 mock/驱动差异）。"""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _row_to_dict(r, with_content: bool = True) -> dict:
    """公告查询结果行 → 接口返回字典。"""
    return {
        "id": int(r[0]),
        "title": r[1],
        **({"content": r[2]} if with_content else {}),
        "ann_type": r[3],
        "ann_type_name": _ANN_TYPE_NAMES.get(r[3], ""),
        "target_department_id": int(r[4]) if r[4] is not None else None,
        "is_top": r[5],
        "status": r[6],
        "publish_time": _fmt_dt(r[7]),
        "create_time": _fmt_dt(r[8]),
        "publisher_name": r[9],
        "target_department_name": r[10],
    }


def _check_visibility(a_row: dict, dept_ids: list[int]) -> bool:
    """公告可见性判定（详情接口用，2.3：越权返回 4032；v2.5 仅校园/院系）。"""
    ann_type = a_row["ann_type"]
    if ann_type == "1":
        return True
    if ann_type == "2":
        return a_row["target_department_id"] in dept_ids
    return False


# ===== T3-2：公告列表 =====

@router.get("")
def announcement_list(
    user: CurrentUser,
    ann_type: str | None = Query(None, pattern="^[12]$", description="类型：1校园 2院系（v2.5 移除班级）"),
    keyword: str | None = Query(None, max_length=50, description="标题关键字"),
    start_date: date | None = Query(None, description="发布时间起始（含）"),
    end_date: date | None = Query(None, description="发布时间截止（含）"),
    is_top: str | None = Query(None, pattern="^[01]$", description="仅置顶：1"),
    page_num: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
) -> dict:
    """公告列表（6.2 / T3-2）：类型/关键字/时间筛选 + 分页 + 置顶优先。

    数据权限（2.3）：按角色过滤可见范围（校园/院系，v2.5 移除班级）；
    仅返回已发布公告；Redis 版本化缓存（T3-3），故障降级直查 MySQL。
    """
    dept_ids = _visible_dept_ids(user)
    scope = f"{user.role_code}:{user.user_id}"

    # ---- Redis 缓存（P1-11：版本化，scope 区分可见范围）----
    version = get_ann_version()
    cache_key = build_list_key(
        version, scope, ann_type, page_num, page_size, keyword, is_top
    )
    cached = cache_get(cache_key)
    if cached is not None:
        return success(json.loads(cached))

    where = ["a.status = '1'", "a.del_flag = '0'", _visibility_sql(dept_ids)]
    params: dict = {}
    if ann_type:
        where.append("a.ann_type = :ann_type")
        params["ann_type"] = ann_type
    if keyword:
        where.append("a.title LIKE :kw")
        params["kw"] = f"%{keyword}%"
    if start_date:
        where.append("a.publish_time >= :start_date")
        params["start_date"] = start_date.isoformat()
    if end_date:
        where.append("a.publish_time <= :end_date")
        params["end_date"] = f"{end_date.isoformat()} 23:59:59"
    if is_top == "1":
        where.append("a.is_top = '1'")

    where_sql = " AND ".join(where)
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM campus_announcement a WHERE {where_sql}"),
            params,
        ).scalar()

        rows = conn.execute(
            text(
                f"SELECT {_ANN_COLUMNS}{_ANN_JOIN} "
                f"WHERE {where_sql} "
                "ORDER BY a.is_top DESC, a.publish_time DESC, a.id DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": (page_num - 1) * page_size},
        ).fetchall()

    data = {
        "total": int(total),
        "page_num": page_num,
        "page_size": page_size,
        "list": [_row_to_dict(r, with_content=False) for r in rows],
    }
    cache_set(cache_key, data)
    return success(data)


# ===== T3-2：公告详情 =====

@router.get("/{ann_id}")
def announcement_detail(
    user: CurrentUser,
    ann_id: int = Path(ge=1, description="公告 id"),
) -> dict:
    """公告详情（6.2 / T3-2）：可见范围校验（2.3，防 IDOR）。

    仅已发布公告可查看；公告不存在或不可见返回 4001/4032。
    """
    dept_ids = _visible_dept_ids(user)

    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT {_ANN_COLUMNS}{_ANN_JOIN} "
                 "WHERE a.id = :aid AND a.status = '1' AND a.del_flag = '0'"),
            {"aid": ann_id},
        ).first()

    if row is None:
        raise ParamError("公告不存在或已下架")

    ann = _row_to_dict(row)
    if not _check_visibility(ann, dept_ids):
        raise ForbiddenDataError("无权查看该公告（不在可见范围内）")
    return success(ann)
