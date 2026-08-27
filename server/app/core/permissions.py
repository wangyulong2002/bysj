"""数据权限依赖（3.5 / T1-3）。

- `require_role("student")`：功能权限——校验 JWT 角色，不匹配返回 4031。
- `require_data_scope("CLASS")`：数据权限——按角色注入数据范围过滤器。
- `DataScope` 枚举：USER_SELF / TEACHING_SCOPE / COUNSELOR_CLASS_SCOPE / ALL。
  **ADR-010（v2.4 无专职辅导员）**：COUNSELOR_CLASS_SCOPE 不再绑定 counselor 角色，
  由教师兼任（role_code=teacher 且 `campus_class.counselor_id = 本人`）动态获得，
  请假审批等接口按 counselor_id 动态判定。
- `assert_owner`：IDOR 防护——服务端重算归属，不信任前端 ID（2.3/3.5）。
- admin 边界（P1-10）：应用端 `require_role` 默认拒绝 admin 调用业务接口。
"""
from enum import Enum
from typing import Annotated

from fastapi import Depends

from app.api.deps import CurrentUser, UserIdentity
from app.core.errors import ForbiddenDataError, ForbiddenError


class DataScope(str, Enum):
    """数据范围枚举（3.5/2.3）。"""

    USER_SELF = "USER_SELF"              # 本人
    TEACHING_SCOPE = "TEACHING_SCOPE"    # 本人任课教学班覆盖
    COUNSELOR_CLASS_SCOPE = "COUNSELOR_CLASS_SCOPE"  # 本人所带班级（教师兼任动态获得）
    ALL = "ALL"                          # 全量（仅管理端，P1-10）


# 角色 → 默认数据范围（2.3；v2.4 去除专职辅导员，counselor 由教师兼任动态叠加）
ROLE_SCOPE_MAP: dict[str, DataScope] = {
    "student": DataScope.USER_SELF,
    "teacher": DataScope.TEACHING_SCOPE,
    "admin": DataScope.ALL,
}


def require_role(*roles: str):
    """功能权限依赖工厂：JWT 角色必须在 roles 中，否则 4031。

    P1-10：admin 不通过应用端业务接口——除非显式传入 'admin'。
    """
    def _dep(user: CurrentUser) -> UserIdentity:
        if user.role_code not in roles:
            raise ForbiddenError(f"需要角色: {'/'.join(roles)}")
        return user
    return _dep


def require_data_scope(scope: DataScope | None = None):
    """数据范围依赖工厂：校验当前用户数据范围满足要求，否则 4032。

    - 传 scope：要求用户角色默认范围等于/覆盖该范围（简化为等值校验 + admin 例外）；
    - 不传：仅注入用户的 data_scope（调用方在查询中按 ROLE_SCOPE_MAP 过滤）。
    """
    def _dep(user: CurrentUser) -> tuple[UserIdentity, DataScope]:
        user_scope = ROLE_SCOPE_MAP.get(user.role_code, DataScope.USER_SELF)
        if scope is not None:
            # 数据范围满足性：ALL > 其他；其余按角色等值判定
            if user_scope != DataScope.ALL and user_scope != scope:
                raise ForbiddenDataError("无权访问该数据范围")
        return user, user_scope
    return _dep


def assert_owner(user: CurrentUser, owner_user_id: int, resource: str = "资源") -> None:
    """IDOR 防护（3.5/2.3）：服务端重算归属，不信任前端 ID。

    仅允许本人访问；admin 在应用端默认拒绝（P1-10），但如需放行可显式传入。
    """
    if int(owner_user_id) != int(user.user_id):
        raise ForbiddenDataError(f"无权访问该{resource}")


# 常用依赖快捷方式（v2.4：无专职辅导员，辅导员由教师兼任、按 counselor_id 动态判定）
RequireStudent = Annotated[UserIdentity, Depends(require_role("student"))]
RequireTeacher = Annotated[UserIdentity, Depends(require_role("teacher"))]
RequireAdminApi = Annotated[UserIdentity, Depends(require_role("admin"))]
