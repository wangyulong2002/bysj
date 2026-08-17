"""ORM 模型汇总：导入各模型使其注册到 Base.metadata。"""
from app.core.database import Base  # noqa: F401
from app.models.file import CampusFile  # noqa: F401

__all__ = ["Base", "CampusFile"]
