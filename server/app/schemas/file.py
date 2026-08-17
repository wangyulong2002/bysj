"""文件相关 schema（5.3.14 / T0-7）。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    mime_type: str
    file_size: int
    storage_path: str
    uploader_id: int | None
    create_time: datetime
