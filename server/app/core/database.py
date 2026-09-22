"""SQLAlchemy 2.x 引擎与会话（MySQL，唯一权威数据源）。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import (
    MYSQL_COLLATION,
    MYSQL_SQL_MODE,
    MYSQL_TIME_ZONE,
    settings,
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    # P1-3：echo 常态关闭（原 echo=settings.DEBUG 会把 SQL 与绑定参数写进日志）
    echo=settings.DB_ECHO,
    connect_args={
        # P1-18：与 Django 侧显式设置相同的 sql_mode / collation_connection，
        # 避免同一句 SQL 在两端行为不一致（一侧报错、一侧静默截断）
        # P1-13：会话时区固定 +08:00，使 SQL 的 NOW() 与应用侧时间源同基准
        "init_command": (
            f"SET time_zone = '{MYSQL_TIME_ZONE}', "
            f"sql_mode='{MYSQL_SQL_MODE}', "
            f"collation_connection = '{MYSQL_COLLATION}'"
        ),
    },
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级会话，结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
