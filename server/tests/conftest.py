"""pytest 共享夹具（T0-6/T0-7 单元测试）。

约定：
- 使用独立测试用户（user_id=999999，测试后清理），避免污染真实账号。
- 上传目录指向 pytest 临时目录，测试后自动清理。
- 依赖本机已运行的 MySQL(Docker 3307) / Redis(6379)。

**Redis 测试隔离（事故复盘 RAG专项测试报告 §5.6，P0）**：
- 注意：**RediSearch 模块不支持在 db≠0 建索引**（`Cannot create index on
  db != 0`，实测 Redis Stack 模块限制），故不采用"独立逻辑库"方案；
- 采用**命名空间隔离**：测试进程将索引名/键前缀打上 `_test` 后缀
  （`rag_idx_test` / `rag:chunk:test:` / `rag:rebuild_requested:test`），
  任何 FT.DROPINDEX / SCAN+DEL / HSET 只落在测试命名空间；
- 配合 `vector_store._require_isolated_db()` 护栏：`RAG_TEST_ISOLATION=1`
  且仍指向生产索引名 `rag_idx` / `rag:chunk:` 时直接抛错，
  杜绝"跑单测清空线上索引"再次发生（生产进程未设置该标记，不受影响）。
"""
import os
import sys

# ===== 测试环境标记（必须在导入任何 app 模块之前）=====
os.environ.setdefault("RAG_WORKER_ENABLED", "0")   # 关闭 RAG Worker 后台调度（T7-3）
os.environ["RAG_TEST_ISOLATION"] = "1"             # 触发 vector_store 写操作护栏

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402

TEST_USER_ID = 999999


@pytest.fixture(scope="session", autouse=True)
def _test_env(tmp_path_factory):
    """会话级：打测试命名空间 + 清理测试索引/键 + 建测试索引；上传目录切临时路径。

    RediSearch 不支持 db≠0（模块限制），改为命名空间隔离：
    `rag_idx_test` / `rag:chunk:test:*` 等**只清理测试命名空间**，
    不触碰共享 db0 上的生产索引 `rag_idx` 与 `rag:chunk:*`（护栏兜底）。
    """
    import app.core.config as config_mod
    from app.core.redis_client import redis_client
    from app.rag import worker as rag_worker
    from app.services import vector_store
    from redis.exceptions import ResponseError

    # ---- 测试命名空间（索引名/键前缀/重建标记均打 _test 后缀）----
    vector_store.INDEX_NAME = "rag_idx_test"
    vector_store.KEY_PREFIX = "rag:chunk:test:"
    vector_store.REBUILD_REQUEST_KEY = "rag:rebuild_requested:test"
    vector_store.REBUILDING_KEY = "rag:rebuilding:test"
    rag_worker.REBUILD_REQUEST_KEY = vector_store.REBUILD_REQUEST_KEY
    rag_worker.REBUILDING_KEY = vector_store.REBUILDING_KEY

    # ---- 清理上一会话残留的测试命名空间数据（不触碰生产键）----
    try:
        vector_store.binary_redis.execute_command("FT.DROPINDEX", "rag_idx_test")
    except ResponseError as exc:
        if "unknown index" not in str(exc).lower():
            raise
    for k in vector_store.binary_redis.scan_iter(match="rag:chunk:test:*"):
        vector_store.binary_redis.delete(k)
    vector_store.binary_redis.delete("rag:rebuild_requested:test", "rag:rebuilding:test")
    vector_store.ensure_index()  # 建测试索引（worker 单测的 KNN 需真实索引）

    tmp_upload = tmp_path_factory.mktemp("uploads")
    original = config_mod.settings.FILE_UPLOAD_DIR
    config_mod.settings.FILE_UPLOAD_DIR = str(tmp_upload)
    yield tmp_upload
    config_mod.settings.FILE_UPLOAD_DIR = original


@pytest.fixture(scope="session")
def test_user_id() -> int:
    """创建独立测试用户（sys_user），测试结束后连同其文件记录一并清理。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sys_user "
                "(id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, create_time, update_time) "
                "VALUES (:uid, 'tester', '测试账号', '', 0, '0', '0', 'admin', 0, NOW(), NOW())"
            ),
            {"uid": TEST_USER_ID},
        )
    yield TEST_USER_ID
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM campus_file WHERE uploader_id = :uid"), {"uid": TEST_USER_ID})
        conn.execute(text("DELETE FROM sys_user WHERE id = :uid"), {"uid": TEST_USER_ID})


@pytest.fixture(scope="session")
def auth_headers(test_user_id: int) -> dict:
    """构造测试用户的 Bearer JWT 请求头。"""
    token = create_access_token(user_id=test_user_id, role_code="admin", password_version=0)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    """提供 FastAPI TestClient 实例（会话级）。"""
    with TestClient(app) as c:
        yield c
