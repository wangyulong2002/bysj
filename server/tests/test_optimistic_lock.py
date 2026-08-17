"""T0-6 乐观锁工具测试（3.6/P1-09）。

使用内存 SQLite 验证逻辑，不依赖 MySQL。
"""
import pytest
from sqlalchemy import create_engine, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.errors import ConflictError, ErrorCode
from app.core.optimistic_lock import bump_version, optimistic_update


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "t_opt_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    item = Item(name="init", version=0)
    session.add(item)
    session.commit()
    yield session, item.id
    session.close()


def test_successful_update_bumps_version(db):
    session, item_id = db
    optimistic_update(session, Item, item_id, 0, {"name": "updated"})
    session.commit()

    item = session.get(Item, item_id)
    assert item.name == "updated"
    assert item.version == 1, "更新成功应自增 version"


def test_stale_version_raises_conflict(db):
    session, item_id = db
    with pytest.raises(ConflictError) as exc_info:
        optimistic_update(session, Item, item_id, 99, {"name": "x"})
    assert exc_info.value.code == ErrorCode.CONFLICT, "版本不一致应抛 4091"


def test_unknown_id_raises_conflict(db):
    session, _ = db
    with pytest.raises(ConflictError):
        optimistic_update(session, Item, 123456, 0, {"name": "x"})


def test_version_in_values_rejected(db):
    session, item_id = db
    with pytest.raises(ValueError):
        optimistic_update(session, Item, item_id, 0, {"version": 5})


def test_bump_version_only(db):
    session, item_id = db
    bump_version(session, Item, item_id, 0)
    session.commit()
    assert session.get(Item, item_id).version == 1

    with pytest.raises(ConflictError):
        bump_version(session, Item, item_id, 0)  # 旧版本 0 已失效
