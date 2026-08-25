"""T1-3 数据权限测试（3.5 / 10.2）。

覆盖：
- require_role：角色不匹配返回 4031（功能权限）
- require_data_scope：数据范围注入正确（2.3）
- assert_owner：IDOR 防护——非本人资源返回 4032
- admin 应用端边界（P1-10）：admin 调应用端业务接口被拒

说明：require_role 绑定真实 get_current_user（生产正确行为），故直接
调用依赖函数做纯函数测试，不通过 HTTP（HTTP 层由集成测试覆盖）。
"""
import pytest

from app.api.deps import UserIdentity
from app.core.errors import ForbiddenDataError, ForbiddenError
from app.core.permissions import (
    DataScope,
    assert_owner,
    require_data_scope,
    require_role,
)


def _user(role: str, user_id: int = 100) -> UserIdentity:
    """构造指定角色的测试用户身份。"""
    return UserIdentity(user_id=user_id, role_code=role, password_version=0)


def test_role_match_ok():
    """角色匹配时 require_role 通过。"""
    dep = require_role("student")
    u = dep(_user("student"))
    assert u.role_code == "student"


def test_role_mismatch_forbidden():
    """角色不匹配 → 4031。"""
    dep = require_role("student")
    with pytest.raises(ForbiddenError) as exc:
        dep(_user("teacher"))
    assert exc.value.code == 4031


def test_admin_not_allowed_on_app_api():
    """P1-10：admin 不通过应用端业务接口。"""
    dep = require_role("student")
    with pytest.raises(ForbiddenError):
        dep(_user("admin"))
    # 显式放行 admin 时可通过
    dep_admin = require_role("admin")
    assert dep_admin(_user("admin")).role_code == "admin"


def test_data_scope_injected_per_role():
    """按角色注入默认数据范围（ROLE_SCOPE_MAP）。"""
    cases = {
        "student": DataScope.USER_SELF,
        "teacher": DataScope.TEACHING_SCOPE,
        "counselor": DataScope.COUNSELOR_CLASS_SCOPE,
        "admin": DataScope.ALL,
    }
    for role, expect in cases.items():
        _, scope = require_data_scope()(_user(role))
        assert scope == expect, f"{role} 数据范围应为 {expect}"


def test_data_scope_mismatch_forbidden():
    """要求 USER_SELF 但角色是 counselor → 4032。"""
    with pytest.raises(ForbiddenDataError) as exc:
        require_data_scope(DataScope.USER_SELF)(_user("counselor"))
    assert exc.value.code == 4032
    # admin（ALL）可访问任意范围
    require_data_scope(DataScope.USER_SELF)(_user("admin"))


def test_assert_owner_idor():
    """IDOR：目标 owner 非本人 → 4032；本人 → 通过。"""
    u = _user("student", user_id=100)
    assert_owner(u, 100, resource="档案")  # 本人不抛
    with pytest.raises(ForbiddenDataError) as exc:
        assert_owner(u, 200, resource="档案")
    assert exc.value.code == 4032
