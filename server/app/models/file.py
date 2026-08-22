"""文件模型（5.3.14 / T0-7）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CampusFile(Base):
    """campus_file 文件表（5.3.14）。

    安全策略（P1-06）：存储名服务端随机生成（UUID，杜绝路径穿越）；
    大小 ≤10MB；类型白名单；MIME+扩展名双重校验。
    """

    __tablename__ = "campus_file"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    stored_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务端存储名（随机 UUID）")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="MIME 类型")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="大小（字节）")
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False, comment="存储相对路径")
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="文件哈希（去重/校验）")
    uploader_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="上传人（sys_user.id）")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="归属用户（B-03/P1-16，ACL 判定）")
    biz_type: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="业务类型（avatar/leave_attachment/announcement_attachment，P1-16）")
    biz_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="业务记录 id（P1-16：leave_id/announcement_id）")
    visibility: Mapped[str] = mapped_column(String(1), nullable=False, server_default="2", comment="可见性（P1-16：1私有 2本人+授权 3登录可见 4公开）")

    # 审计字段（5.1）
    create_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, server_default="0")
