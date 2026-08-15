"""健康检查接口（9.6/T0-6）：GET /health 检查 FastAPI/MySQL/Redis/RAG 索引状态。"""
from fastapi import APIRouter

from app.core.database import engine
from app.core.redis_client import redis_client, ping_redis
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    checks = {}

    # FastAPI 进程
    checks["fastapi"] = {"status": "UP"}

    # MySQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["mysql"] = {"status": "UP"}
    except Exception as exc:  # noqa: BLE001
        checks["mysql"] = {"status": "DOWN", "error": str(exc)[:200]}

    # Redis
    checks["redis"] = {"status": "UP" if ping_redis() else "DOWN"}

    # RAG 索引（v1 阶段尚未建索引时视为 not_configured，不判 DOWN）
    try:
        if redis_client.exists("rag_index_ready"):
            checks["rag"] = {"status": "UP"}
        else:
            checks["rag"] = {"status": "NOT_CONFIGURED"}
    except Exception:  # noqa: BLE001
        checks["rag"] = {"status": "UNKNOWN"}

    status = "UP"
    for name, check in checks.items():
        if check.get("status") == "DOWN":
            status = "DOWN"
            break
    if status == "UP" and any(c.get("status") not in ("UP", "NOT_CONFIGURED") for c in checks.values()):
        status = "DEGRADED"

    return {"status": status, "checks": checks}
