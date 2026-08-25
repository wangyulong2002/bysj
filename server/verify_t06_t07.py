"""T0-6/T0-7 验收验证脚本：健康检查、文件上传/下载、鉴权、恶意文件拒绝。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402

UID = 999999


def main():
    """执行 T0-6/T0-7 验收用例：健康检查/上传/下载/恶意文件/幂等，并清理测试数据。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sys_user "
                "(id, username, nick_name, password, is_superuser, status, del_flag, role_code, password_version, create_time, update_time) "
                "VALUES (:uid, 'tester', '测试账号', '', 0, '0', '0', 'admin', 0, NOW(), NOW())"
            ),
            {"uid": UID},
        )
    try:
        c = TestClient(app)
        token = create_access_token(user_id=UID, role_code="admin", password_version=0)
        h = {"Authorization": f"Bearer {token}"}

        # 1. 健康检查
        r = c.get("/health")
        print("HEALTH:", json.dumps(r.json(), ensure_ascii=False))

        # 2. 未登录上传 -> 4011
        r = c.post("/api/files", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, "image/png")})
        print("NO-AUTH:", r.json()["code"])

        # 3. 登录上传
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        r = c.post("/api/files", headers=h, files={"file": ("avatar.png", png, "image/png")})
        b = r.json()
        print(
            "UPLOAD code=", b["code"],
            "| data=", {k: b["data"][k] for k in ("id", "original_name", "mime_type", "file_size", "storage_path")},
        )
        fid = b["data"]["id"]

        # 4. 下载
        r = c.get(f"/api/files/{fid}", headers=h)
        print("DOWNLOAD status=", r.status_code, "len=", len(r.content), "disposition=", r.headers.get("content-disposition"))

        # 5. 恶意文件 -> 4001
        r = c.post("/api/files", headers=h, files={"file": ("evil.sh", b"#!/bin/sh\nrm -rf /", "application/x-sh")})
        print("EVIL-SCRIPT code=", r.json()["code"], "msg=", r.json()["message"])

        # 6. 幂等：同 Idempotency-Key 重复上传只落一条
        r1 = c.post("/api/files", headers={**h, "Idempotency-Key": "idem-verify"}, files={"file": ("i.png", png, "image/png")})
        r2 = c.post("/api/files", headers={**h, "Idempotency-Key": "idem-verify"}, files={"file": ("i.png", png, "image/png")})
        same = r1.json()["data"]["id"] == r2.json()["data"]["id"]
        with engine.connect() as conn:
            cnt = conn.execute(text("SELECT COUNT(*) FROM campus_file WHERE uploader_id = :uid"), {"uid": UID}).scalar()
        print("IDEMPOTENT same_id=", same, "| 该用户总文件数=", cnt)
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM campus_file WHERE uploader_id = :uid"), {"uid": UID})
            conn.execute(text("DELETE FROM sys_user WHERE id = :uid"), {"uid": UID})


if __name__ == "__main__":
    main()
    print("T0-6/T0-7 验收验证完成。")
