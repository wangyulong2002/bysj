"""T0-7 文件上传/下载安全测试（5.3.14、10.3）。

覆盖：鉴权、类型白名单、大小上限、MIME+扩展名+文件头校验、路径穿越、下载鉴权。
"""
import os

import pytest

from app.core.config import settings

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
PNG_DATA = PNG_HEADER + b"\x00" * 100


def _upload(client, headers, filename, data, mime, idem_key=None):
    """封装上传请求：可选携带 Idempotency-Key。"""
    req_headers = dict(headers or {})
    if idem_key:
        req_headers["Idempotency-Key"] = idem_key
    return client.post(
        "/api/files",
        headers=req_headers or None,
        files={"file": (filename, data, mime)},
    )


# ---------- 鉴权 ----------

def test_upload_without_token_unauthorized(client):
    """未登录上传 → 4011。"""
    r = _upload(client, {}, "a.png", PNG_DATA, "image/png")
    assert r.status_code == 200
    assert r.json()["code"] == 4011


def test_download_without_token_unauthorized(client, auth_headers):
    """未登录下载 → 4011。"""
    up = _upload(client, auth_headers, "a.png", PNG_DATA, "image/png")
    file_id = up.json()["data"]["id"]
    r = client.get(f"/api/files/{file_id}")
    assert r.status_code == 200
    assert r.json()["code"] == 4011


# ---------- 正常上传 / 下载 ----------

def test_upload_and_download_ok(client, auth_headers):
    """登录用户上传（随机存储名落盘）并下载成功。"""
    up = _upload(client, auth_headers, "photo.png", PNG_DATA, "image/png")
    assert up.status_code == 200
    body = up.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["original_name"] == "photo.png"
    assert data["mime_type"] == "image/png"
    assert data["file_size"] == len(PNG_DATA)

    # 存储名随机（UUID），且不包含原始名
    assert data["storage_path"] != "photo.png"
    assert os.path.isfile(os.path.join(settings.file_upload_dir, data["storage_path"]))

    # 下载
    dl = client.get(f"/api/files/{data['id']}", headers=auth_headers)
    assert dl.status_code == 200
    assert dl.content == PNG_DATA
    assert "photo.png" in dl.headers.get("content-disposition", "")


# ---------- 类型白名单 ----------

@pytest.mark.parametrize("filename,mime", [
    ("evil.exe", "application/octet-stream"),
    ("script.sh", "application/x-sh"),
    ("bad.html", "text/html"),
    ("evil.php", "application/x-php"),
])
def test_upload_disallowed_extension(client, auth_headers, filename, mime):
    """白名单外扩展名（exe/sh/html/php）→ 4001 拒绝。"""
    r = _upload(client, auth_headers, filename, b"MZ\x90\x00", mime)
    assert r.status_code == 200
    assert r.json()["code"] == 4001


# ---------- 大小上限 ----------

def test_upload_over_size_limit(client, auth_headers):
    """超过 10MB 大小上限 → 4001。"""
    big = PNG_HEADER + b"\x00" * (11 * 1024 * 1024)  # >10MB
    r = _upload(client, auth_headers, "big.png", big, "image/png")
    assert r.status_code == 200
    assert r.json()["code"] == 4001
    assert "超过限制" in r.json()["message"]


# ---------- MIME 与扩展名不匹配 ----------

def test_upload_mime_mismatch(client, auth_headers):
    """扩展名与 MIME 不匹配 → 4001。"""
    # 扩展名 png 但 Content-Type 是 pdf
    r = _upload(client, auth_headers, "pic.png", PNG_DATA, "application/pdf")
    assert r.status_code == 200
    assert r.json()["code"] == 4001


# ---------- 文件头（magic bytes）校验 ----------

def test_upload_magic_mismatch(client, auth_headers):
    """文件头（magic bytes）与声明类型不符 → 4001 拒绝伪装文件。"""
    # 声明为 png（扩展名 + MIME 都对），但文件头不是 PNG —— 伪装文件应拒绝
    r = _upload(client, auth_headers, "fake.png", b"#!/bin/sh echo hacked", "image/png")
    assert r.status_code == 200
    assert r.json()["code"] == 4001


# ---------- 路径穿越 / 恶意文件名 ----------

@pytest.mark.parametrize("filename", [
    "../evil.png",
    "..\\evil.png",
    "a/../../evil.png",
])
def test_upload_path_traversal_rejected(client, auth_headers, filename):
    """路径穿越/危险文件名 → 4001 拒绝。"""
    r = _upload(client, auth_headers, filename, PNG_DATA, "image/png")
    assert r.status_code == 200
    assert r.json()["code"] == 4001


# ---------- 幂等（T0-6 中间件集成） ----------

def test_upload_idempotent_with_same_key(client, auth_headers):
    """相同 Idempotency-Key 重复上传只落一条记录，返回首次结果。"""
    from sqlalchemy import text

    from app.core.database import engine

    r1 = _upload(client, auth_headers, "idem.png", PNG_DATA, "image/png", idem_key="idem-f1")
    r2 = _upload(client, auth_headers, "idem.png", PNG_DATA, "image/png", idem_key="idem-f1")
    assert r1.json()["data"]["id"] == r2.json()["data"]["id"]
    assert r1.json()["data"]["storage_path"] == r2.json()["data"]["storage_path"]

    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM campus_file WHERE original_name = 'idem.png' AND uploader_id = 999999")
        ).scalar()
    assert cnt == 1, "重复提交幂等后只应有一条记录"
