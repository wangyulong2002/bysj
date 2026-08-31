"""pytest 共享夹具（T0-6/T0-7 单元测试）。

约定：
- 使用独立测试用户（user_id=999999，测试后清理），避免污染真实账号。
- 上传目录指向 pytest 临时目录，测试后自动清理。
- 依赖本机已运行的 MySQL(Docker 3307) / Redis(6379)。
"""
import os
import sys

# 测试环境关闭 RAG Worker 后台调度（T7-3），须在导入 app 之前设置
os.environ.setdefault("RAG_WORKER_ENABLED", "0")

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
    """会话级：切换上传目录到临时路径；清空幂等缓存；测试结束恢复。"""
    import app.core.config as config_mod
    from app.core.redis_client import redis_client

    # 清空上次运行残留的幂等缓存，保证测试隔离
    for k in redis_client.scan_iter("idem:*"):
        redis_client.delete(k)

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
