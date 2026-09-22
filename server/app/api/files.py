"""文件上传/下载服务（5.3.14 / T0-7）。

安全策略（P1-06/B-03/P1-16）：
- 大小限制 ≤10MB；类型白名单（jpg/png/gif/pdf/docx/xlsx）。
- 存储名服务端随机生成（UUID），杜绝用户可控路径 / 路径穿越。
- MIME + 扩展名双重校验，并校验文件头（magic bytes）拒绝伪装文件。
- 下载/预览需登录鉴权 + **对象级 ACL**（B-03/P1-16）：
  avatar 本人/登录可见；leave_attachment 本人/审批辅导员/管理员；
  announcement_attachment 按公告可见范围（v1 按 visibility 简化）。
- 签名 URL（B-02）：`GET /api/files/{id}/url` 返回 5 分钟短期签名链接，
  供小程序 <image> 直接渲染头像/附件（image 组件无法带 Authorization）。
"""
import hashlib
import logging
import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import FileMissingError, ForbiddenDataError, ParamError
from app.core.response import success
from app.core.security import SIGNED_URL_TTL_SECONDS, verify_signed_url_token
from app.core.time import now as campus_now
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
    biz_type: Annotated[str | None, Query(description="业务类型：avatar/leave_attachment/announcement_attachment，P1-16")] = None,
    biz_id: Annotated[int | None, Query(description="业务记录 id，P1-16")] = None,
    visibility: Annotated[str | None, Query(description="可见性：1私有 2本人+授权 3登录可见 4公开，P1-16")] = None,
) -> dict:
    """上传文件（≤10MB，白名单，MIME+扩展名+文件头三重校验 + ACL 元数据 P1-16）。"""
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
    file_path = upload_dir / stored_name

    # ACL 默认值（P1-16）：头像默认登录可见（3），其余默认私有（1）
    default_vis = "3" if biz_type == "avatar" else "1"
    now = campus_now()
    record = CampusFile(
        original_name=original_name,
        stored_name=stored_name,
        mime_type=file.content_type.split(";")[0].strip(),
        file_size=len(data),
        storage_path=storage_path,
        file_hash=hashlib.sha256(data).hexdigest(),
        uploader_id=user.user_id,
        owner_id=user.user_id,
        biz_type=biz_type,
        biz_id=biz_id,
        visibility=visibility or default_vis,
        create_by=user.user_id,
        # P1-13：审计时间由应用侧显式给出（统一 Asia/Shanghai 时间源）。
        # 不再依赖数据库默认值 —— 迁移建出的列是 nullable 且无 DEFAULT
        # （历史手写 DDL 的 DEFAULT CURRENT_TIMESTAMP 未在模型中表达），
        # 依赖 DB 默认值会写入 NULL 并使 FileOut 校验失败。
        create_time=now,
        update_time=now,
    )

    # P1-7：先占位入库（flush 拿到自增 id，尚未提交）→ 写盘 → 提交。
    # 原实现「先写盘再 commit」在事务失败时会在磁盘留下永久孤儿文件；
    # 现改为任一步失败都回滚事务并清理磁盘文件，保证「库有记录 ⟺ 盘有文件」。
    try:
        db.add(record)
        db.flush()
        file_path.write_bytes(data)
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        logger.warning("文件上传失败，已回滚并清理磁盘文件: %s", file_path, exc_info=True)
        raise

    logger.info("文件上传成功 id=%s user=%s name=%s size=%s biz=%s", record.id, user.user_id, original_name, len(data), biz_type)
    return success(FileOut.model_validate(record), message="上传成功")


def _is_leave_approver(db: Session, biz_id: int | None, user: CurrentUser) -> bool:
    """请假附件授权可见判定（P1-7）：申请人所在班级的辅导员（含兼任教师）可读。

    "是否辅导员"的权威判定与请假审批保持一致 = `campus_class.counselor_id = 本人`
    （ADR-010，v2.4 无专职辅导员）；此处按 `biz_type + biz_id` 动态判权，
    不额外引入 ACL 表。
    """
    if not biz_id:
        return False
    row = db.execute(
        text(
            """
            SELECT 1
              FROM campus_leave l
              JOIN campus_student s ON s.id = l.student_id AND s.del_flag = '0'
              JOIN campus_class   c ON c.id = s.class_id    AND c.del_flag = '0'
             WHERE l.id = :biz_id AND l.del_flag = '0' AND c.counselor_id = :uid
             LIMIT 1
            """
        ),
        {"biz_id": int(biz_id), "uid": user.user_id},
    ).first()
    return row is not None


def _check_acl(record: CampusFile, user: CurrentUser, db: Session) -> None:
    """对象级 ACL（B-03/P1-16/P1-7）。

    规则：
    - admin（管理端 P1-10）：可读全部；
    - visibility=4（公开）/ 3（登录可见，头像）：登录用户均可读；
    - 本人（owner_id）：可读；
    - visibility=2 且 biz_type=leave_attachment（P1-7）：**审批辅导员（含兼任教师）可读**
      ——原实现该分支与 visibility=1 一致地退化为"仅本人"，注释承诺的
      "审批辅导员可读请假附件"并未生效，导致审批人打开附件 4032；
    - 其余（含 visibility=1 私有）：仅本人 / admin 可读。
    禁止仅凭"已登录"判断权限。
    """
    if user.role_code == "admin":
        return
    if record.visibility in ("3", "4"):
        return
    if record.owner_id == user.user_id:
        return
    # P1-7：请假附件的授权可见分支（按 biz_type + biz_id 动态判权）
    if record.biz_type == "leave_attachment" and _is_leave_approver(db, record.biz_id, user):
        return
    raise ForbiddenDataError("无权访问该文件")


@router.get("/files/{file_id}")
def download_file(
    file_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """下载/预览（需登录鉴权 + 对象级 ACL，B-03/P1-16）。"""
    record = db.execute(
        select(CampusFile).where(CampusFile.id == file_id, CampusFile.del_flag == "0")
    ).scalar_one_or_none()
    if record is None:
        raise FileMissingError()
    _check_acl(record, user, db)

    path = settings.file_upload_dir / record.storage_path
    if not path.is_file():
        logger.warning("文件记录存在但物理文件缺失: %s", path)
        raise FileMissingError("文件已损坏或丢失")

    return FileResponse(
        path=str(path),
        media_type=record.mime_type,
        filename=record.original_name,
    )


@router.get("/files/{file_id}/url")
def get_signed_url(
    file_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """返回签名下载 URL（B-02）：5 分钟短期链接，供小程序 <image> 渲染。

    携带 JWT 调用本接口 → 校验 ACL 通过后返回带签名参数的 URL；
    随后用该 URL 访问 `GET /api/files/{id}/url-download`（免 JWT，image 组件可用）。

    P1-6：删除历史上声明却**从未使用**的 `token`/`expires` 查询参数（死参数）。
    """
    record = db.execute(
        select(CampusFile).where(CampusFile.id == file_id, CampusFile.del_flag == "0")
    ).scalar_one_or_none()
    if record is None:
        raise FileMissingError()
    _check_acl(record, user, db)

    from app.core.security import build_signed_file_url

    # P1-6：签名绑定 file_hash，链接无法跨文件复用
    url = build_signed_file_url(file_id, record.file_hash)
    return success(
        {"url": url, "expires_in": SIGNED_URL_TTL_SECONDS},
        message="签名 URL",
    )


@router.get("/files/{file_id}/url-download")
def signed_download(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Query()] = "",
    expires: Annotated[int, Query()] = 0,
) -> FileResponse:
    """签名 URL 直链下载（B-02）：校验 HMAC 签名后返回文件，免 JWT（供 image 组件）。

    P1-6：先取文件记录，再用其 `file_hash` 参与验签（签名已绑定文件内容）。
    """
    if not token or not expires:
        raise ParamError("签名链接无效或已过期")
    record = db.execute(
        select(CampusFile).where(CampusFile.id == file_id, CampusFile.del_flag == "0")
    ).scalar_one_or_none()
    if record is None:
        raise FileMissingError()
    if not verify_signed_url_token(file_id, token, int(expires), record.file_hash):
        raise ParamError("签名链接无效或已过期")
    path = settings.file_upload_dir / record.storage_path
    if not path.is_file():
        logger.warning("文件记录存在但物理文件缺失: %s", path)
        raise FileMissingError("文件已损坏或丢失")
    return FileResponse(
        path=str(path),
        media_type=record.mime_type,
        filename=record.original_name,
    )
