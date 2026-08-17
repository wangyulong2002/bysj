"""文件上传/下载服务（5.3.14 / T0-7）。

安全策略（P1-06）：
- 大小限制 ≤10MB；类型白名单（jpg/png/gif/pdf/docx/xlsx）。
- 存储名服务端随机生成（UUID），杜绝用户可控路径 / 路径穿越。
- MIME + 扩展名双重校验，并校验文件头（magic bytes）拒绝伪装文件。
- 下载/预览需登录鉴权；文件存放独立目录（不入 web 可执行路径）。
"""
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ParamError
from app.core.response import success
from app.models.file import CampusFile
from app.schemas.file import FileOut

logger = logging.getLogger("campus.files")

router = APIRouter(tags=["files"])

# 白名单：扩展名 -> 允许的 MIME 与文件头（magic bytes）前缀
ALLOWED_FILES: dict[str, dict] = {
    "jpg":  {"mime": ("image/jpeg",),                       "magic": (b"\xff\xd8\xff",)},
    "jpeg": {"mime": ("image/jpeg",),                       "magic": (b"\xff\xd8\xff",)},
    "png":  {"mime": ("image/png",),                        "magic": (b"\x89PNG\r\n\x1a\n",)},
    "gif":  {"mime": ("image/gif",),                        "magic": (b"GIF87a", b"GIF89a")},
    "pdf":  {"mime": ("application/pdf",),                  "magic": (b"%PDF-",)},
    "docx": {"mime": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),
             "magic": (b"PK\x03\x04",)},
    "xlsx": {"mime": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
             "magic": (b"PK\x03\x04",)},
}

# 与配置 FILE_ALLOWED_TYPES 取交集（默认配置即白名单全集）
CONFIG_ALLOWED = settings.file_allowed_types
if CONFIG_ALLOWED:
    ALLOWED_FILES = {ext: v for ext, v in ALLOWED_FILES.items() if ext in CONFIG_ALLOWED}

CHUNK_SIZE = 1024 * 1024  # 1MB，用于大小校验与累积


async def _read_limited(upload: UploadFile) -> bytes:
    """分块读取并强制大小上限（≤FILE_MAX_SIZE_MB）。"""
    total = 0
    buf = bytearray()
    while chunk := await upload.read(CHUNK_SIZE):
        total += len(chunk)
        if total > settings.file_max_size:
            raise ParamError(f"文件大小超过限制（{settings.FILE_MAX_SIZE_MB}MB）")
        buf.extend(chunk)
    if total == 0:
        raise ParamError("文件内容为空")
    return bytes(buf)


def _validate_extension(filename: str) -> str:
    """校验扩展名并返回小写扩展名；拒绝路径穿越 / 可执行文件。"""
    # 拒绝路径穿越与危险字符
    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise ParamError("非法的文件名")
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_FILES:
        raise ParamError(f"不支持的文件类型：.{ext}（白名单：jpg/png/gif/pdf/docx/xlsx）")
    return ext


def _validate_mime(content_type: str, ext: str) -> None:
    """MIME 校验：Content-Type 必须落在白名单类型内。"""
    if not content_type:
        raise ParamError("缺少文件 MIME 类型")
    mime = content_type.split(";")[0].strip().lower()
    if mime not in ALLOWED_FILES[ext]["mime"]:
        raise ParamError(f"MIME 类型与扩展名不匹配：{mime}")


def _validate_magic(data: bytes, ext: str) -> None:
    """文件头（magic bytes）校验：拒绝伪装成图片/文档的可执行文件。"""
    if not any(data.startswith(m) for m in ALLOWED_FILES[ext]["magic"]):
        raise ParamError("文件内容与声明类型不符，已拒绝上传")


@router.post("/files")
async def upload_file(
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="待上传文件")],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """上传文件（≤10MB，白名单，MIME+扩展名+文件头三重校验）。"""
    original_name = file.filename or "unnamed"
    ext = _validate_extension(original_name)
    _validate_mime(file.content_type or "", ext)

    data = await _read_limited(file)
    _validate_magic(data, ext)

    # 服务端随机存储名（UUID），杜绝用户可控路径
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    storage_path = stored_name  # 相对 uploads/ 的路径
    upload_dir = settings.file_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / stored_name).write_bytes(data)

    record = CampusFile(
        original_name=original_name,
        stored_name=stored_name,
        mime_type=file.content_type.split(";")[0].strip(),
        file_size=len(data),
        storage_path=storage_path,
        file_hash=hashlib.sha256(data).hexdigest(),
        uploader_id=user.user_id,
        create_by=user.user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info("文件上传成功 id=%s user=%s name=%s size=%s", record.id, user.user_id, original_name, len(data))
    return success(FileOut.model_validate(record), message="上传成功")


@router.get("/files/{file_id}")
def download_file(
    file_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """下载/预览（需登录鉴权）。"""
    record = db.execute(
        select(CampusFile).where(CampusFile.id == file_id, CampusFile.del_flag == "0")
    ).scalar_one_or_none()
    if record is None:
        raise ParamError("文件不存在")

    path = settings.file_upload_dir / record.storage_path
    if not path.is_file():
        logger.warning("文件记录存在但物理文件缺失: %s", path)
        raise ParamError("文件已损坏或丢失")

    return FileResponse(
        path=str(path),
        media_type=record.mime_type,
        filename=record.original_name,
    )
