"""健康检查接口（9.6/T0-6）：GET /health。

返回结构（对齐设计 9.6）：
  { "status": "UP"|"DEGRADED"|"DOWN", "checks": { "app": "UP", "mysql": "UP", "redis": "UP", "rag_index": "UP"|"NOT_CONFIGURED" } }
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine
from app.core.redis_client import ping_redis, redis_client

router = APIRouter(tags=["health"])

# 各检查项的告警级别：DOWN=>DOWN；UNKNOWN=>DEGRADED；NOT_CONFIGURED 视为可接受（v1 RAG 未建索引是常态）
WARN_LEVELS = {"DOWN": 2, "UNKNOWN": 1, "NOT_CONFIGURED": 0, "UP": 0}


@router.get("/health")
def health():
    checks = {}

    # 应用进程
    checks["app"] = {"status": "UP"}

    # MySQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["mysql"] = {"status": "UP"}
    except Exception as exc:  # noqa: BLE001
        checks["mysql"] = {"status": "DOWN", "error": str(exc)[:200]}

    # Redis
    try:
        checks["redis"] = {"status": "UP" if ping_redis() else "DOWN"}
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = {"status": "DOWN", "error": str(exc)[:200]}

    # RAG 索引（v1 阶段尚未建索引时视为 not_configured，不判 DOWN）
    try:
        if redis_client.exists("rag_index_ready"):
            checks["rag_index"] = {"status": "UP"}
        else:
            checks["rag_index"] = {"status": "NOT_CONFIGURED"}
    except Exception:  # noqa: BLE001
        checks["rag_index"] = {"status": "UNKNOWN"}

    # 汇总：存在 DOWN => DOWN；否则存在非 UP（除 NOT_CONFIGURED）=> DEGRADED
    status = "UP"
    max_level = max(WARN_LEVELS.get(c.get("status"), 0) for c in checks.values())
    if max_level >= 2:
        status = "DOWN"
    elif max_level >= 1:
        status = "DEGRADED"

    return {"status": status, "checks": checks}
