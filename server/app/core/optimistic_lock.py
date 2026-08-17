"""乐观锁工具（3.6/P1-09 / T0-6）。

成绩批量录入、请假状态更新等并发写操作使用 `version`（乐观锁）字段：
更新语句携带 `WHERE version = ?` 条件，受影响行数为 0（版本不一致）时抛 4091，
客户端需刷新后重试，防止并发覆盖。

约定：目标模型须含 `version` 整型列（campus_score / campus_leave 已含，见 5.3.x + 04 迁移脚本）。
"""
from sqlalchemy import and_, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError


def optimistic_update(
    db: Session,
    model,
    obj_id: int,
    expected_version: int,
    values: dict,
) -> int:
    """按 `id + version` 条件更新并自动 version+1。

    Args:
        db: SQLAlchemy 会话。
        model: ORM 模型（须含 `id` 与 `version` 列）。
        obj_id: 主键 id。
        expected_version: 客户端提交的期望版本号。
        values: 需更新的业务字段（不可包含 version，version 由本工具维护）。

    Returns:
        受影响行数（正常为 1）。

    Raises:
        ConflictError(4091): 版本不一致或记录不存在。
    """
    if "version" in values:
        raise ValueError("version 由乐观锁自动维护，不允许在 values 中传入")

    stmt = (
        update(model)
        .where(and_(model.id == obj_id, model.version == expected_version))
        .values(**values, version=model.version + 1)
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        raise ConflictError("数据已变更，请刷新后重试")
    return result.rowcount


def bump_version(db: Session, model, obj_id: int, expected_version: int) -> int:
    """仅自增 version（不更新业务字段），用于并发写前置校验。

    Raises:
        ConflictError(4091): 版本不一致或记录不存在。
    """
    return optimistic_update(db, model, obj_id, expected_version, {})
