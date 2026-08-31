"""RAG 任务 Worker（T7-3，5.3.16/5.3.18/8.3/9.6）。

- 调度：FastAPI lifespan 启动 APScheduler，每 30s 一轮（实现约定）；
  每轮顺序：全量重建检查 → 崩溃恢复 → 领取任务 → 逐条处理；
- 任务领取（P0-08 防多 worker 重复消费）：`UPDATE ... SET status=1 WHERE
  id=%s AND status=0`，受影响行数=1 才继续；
- upsert 链路（P0-09 整源重建，顺序不可颠倒）：
  ①读源文档 → ②切分 → ③写新 chunk 批次（source_version+1，status=0）
  → ④批量 Embedding → ⑤HSET 写 RediSearch → ⑥删除旧版本 chunk
  （新 chunk 全部成功后才删旧，避免新旧向量并存答案冲突）；
- delete 任务：查该 source 全部 chunk → Redis DEL → MySQL 删除 → SUCCESS；
- 失败处理：retry_count+=1、指数退避 2/4/8 分钟回 PENDING；retry_count>3
  终态 FAILED 不再重试（last_error 截断 500 字）；
- 崩溃恢复：PROCESSING 超过 10 分钟重置 PENDING（整源重建幂等，重复无害）；
- 全量重建（8.3 兜底）：管理端 POST /admin/api/rag/index/rebuild 只置
  `rag:rebuild_requested` 标记（Django 侧，跨进程实现约定），Worker 检测后：
  置 `rag:rebuilding`（TTL 防崩溃残留）→ 清空索引与残留 key → 重建空索引
  → 对全部已发布公告+知识库逐源写 upsert 任务 → 队列清空后删标记。
- 对接 /health 的 rag_index（9.6 C-10）：num_docs>0 且无 rebuilding → UP。
"""
import logging

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.rag.chunker import split_content
from app.services import vector_store
from app.services.embedding import embed_texts  # 测试可 monkeypatch（模块级引用）

logger = logging.getLogger("campus.rag.worker")

ROUND_INTERVAL_SECONDS = 30     # 每轮间隔（实现约定）
STALE_PROCESSING_MINUTES = 10   # PROCESSING 超时阈值（8.3）
MAX_RETRY = 3                   # 重试上限（2/4/8 分钟指数退避）
TASKS_PER_ROUND = 20            # 单轮最多处理任务数（避免长事务阻塞）
REBUILDING_TTL_SECONDS = 7200   # rebuilding 标记 TTL（防崩溃残留）

REBUILD_REQUEST_KEY = vector_store.REBUILD_REQUEST_KEY
REBUILDING_KEY = vector_store.REBUILDING_KEY


def strip_html(content: str | None) -> str:
    """剥离 HTML 标签（FastAPI 侧轻量实现，与 Django knowledge_flow 等价）。"""
    import html as _html
    import re

    if not content:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", content or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


# ===== 源文档读取 =====

def load_source(source_type: str, source_id: int) -> tuple[str, str] | None:
    """读源文档 → (title, 纯文本正文)；源不存在/未发布返回 None。

    source_type: '1' 公告（已发布 title+content）；'2' 知识库（剥离 HTML）。
    """
    if source_type == "1":
        sql = ("SELECT title, content FROM campus_announcement "
               "WHERE id = :sid AND status = '1' AND del_flag = '0'")
    else:
        sql = ("SELECT title, content FROM campus_knowledge "
               "WHERE id = :sid AND status = '1' AND del_flag = '0'")
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"sid": source_id}).first()
    if row is None:
        return None
    content = row[1] or ""
    if source_type == "2":
        content = strip_html(content)
    return row[0] or "", content


def _source_url(source_type: str, source_id: int) -> str:
    """来源链接（T7-4 url 规则）：公告 → 应用端详情；知识库 → v1 置空串。"""
    if source_type == "1":
        return f"/api/announcements/{source_id}"
    return ""


# ===== 任务领取 / 状态流转 =====

def recover_stale_tasks() -> int:
    """崩溃恢复（P0-08）：PROCESSING 超时 10 分钟 → 重置 PENDING。"""
    with engine.begin() as conn:
        result = conn.execute(text(
            "UPDATE campus_rag_task SET status = '0', update_time = NOW() "
            "WHERE status = '1' AND del_flag = '0' "
            "AND update_time < NOW() - INTERVAL :mins MINUTE"
        ), {"mins": STALE_PROCESSING_MINUTES})
    if result.rowcount:
        logger.warning("崩溃恢复：%s 个超时 PROCESSING 任务已重置 PENDING", result.rowcount)
    return result.rowcount


def claim_next_task() -> dict | None:
    """领取一个到期 PENDING 任务：条件更新受影响行数=1 才持有（P0-08）。"""
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT id, operation, source_type, source_id FROM campus_rag_task "
            "WHERE status = '0' AND del_flag = '0' "
            "AND (next_retry_time IS NULL OR next_retry_time <= NOW()) "
            "ORDER BY id LIMIT 1"
        )).first()
        if row is None:
            return None
        claimed = conn.execute(text(
            "UPDATE campus_rag_task SET status = '1', update_time = NOW() "
            "WHERE id = :tid AND status = '0'"
        ), {"tid": row[0]})
        if claimed.rowcount != 1:  # 被其他 worker 抢占，放弃本轮领取
            return None
    return {"id": row[0], "operation": row[1], "source_type": row[2],
            "source_id": int(row[3])}


def _mark_success(task_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE campus_rag_task SET status = '2', last_error = NULL, "
            "update_time = NOW() WHERE id = :tid"
        ), {"tid": task_id})


def _mark_failed(task_id: int, error: str) -> None:
    """失败处理：retry_count+=1；超上限终态 FAILED，否则指数退避回 PENDING。

    退避间隔 = 2^retry_count 分钟（retry_count 已自增：2/4/8 分钟）。
    注意：MySQL UPDATE 的 SET 从左到右求值，retry_count 赋值须放在
    引用它的表达式**之后**，保证读到自增前的旧值。
    """
    err = (error or "")[:500]
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE campus_rag_task SET "
            "status = IF(retry_count + 1 > :max_retry, '3', '0'), "
            "next_retry_time = IF(retry_count + 1 > :max_retry, NULL, "
            "                     NOW() + INTERVAL POWER(2, retry_count + 1) MINUTE), "
            "last_error = :err, update_time = NOW(), "
            "retry_count = retry_count + 1 "
            "WHERE id = :tid"
        ), {"err": err, "max_retry": MAX_RETRY, "tid": task_id})
    logger.warning("RAG 任务 %s 失败: %s", task_id, err[:200])


# ===== upsert / delete 链路 =====

def _delete_chunks(conn, source_type: str, source_id: int) -> list[int]:
    """查该 source 全部 chunk id（供 Redis DEL，须在 MySQL 删除前取）。"""
    rows = conn.execute(text(
        "SELECT id FROM campus_rag_chunk "
        "WHERE source_type = :st AND source_id = :sid AND del_flag = '0'"
    ), {"st": source_type, "sid": source_id}).fetchall()
    return [int(r[0]) for r in rows]


def _remove_source_chunks(source_type: str, source_id: int) -> None:
    """移除该 source 全部 chunk（Redis DEL + MySQL 删行）。"""
    with engine.begin() as conn:
        chunk_ids = _delete_chunks(conn, source_type, source_id)
        conn.execute(text(
            "DELETE FROM campus_rag_chunk WHERE source_type = :st AND source_id = :sid"
        ), {"st": source_type, "sid": source_id})
    if chunk_ids:
        vector_store.delete_chunk_keys(chunk_ids)


def process_upsert(task: dict) -> None:
    """upsert 链路（P0-09 整源重建，顺序见模块 docstring）。"""
    source_type, source_id = task["source_type"], task["source_id"]
    loaded = load_source(source_type, source_id)
    if loaded is None:
        # 源已下架/删除（任务与状态变更间竞态）：按 delete 语义清理，幂等成功
        _remove_source_chunks(source_type, source_id)
        return
    title, content = loaded
    chunks = split_content(content)
    if not chunks:
        _remove_source_chunks(source_type, source_id)
        return

    # ③ 写新 chunk 批次：source_version = 现有最大版本 + 1（初版 1），status=0
    with engine.begin() as conn:
        version = conn.execute(text(
            "SELECT COALESCE(MAX(source_version), 0) FROM campus_rag_chunk "
            "WHERE source_type = :st AND source_id = :sid"
        ), {"st": source_type, "sid": source_id}).scalar() or 0
        version = int(version) + 1
        url = _source_url(source_type, source_id)
        rows = [
            {"st": source_type, "sid": source_id, "ver": version, "idx": i,
             "content": c, "title": title, "url": url}
            for i, c in enumerate(chunks)
        ]
        conn.execute(text(
            "INSERT INTO campus_rag_chunk "
            "(source_type, source_id, source_version, chunk_index, content, title, url, status, "
            " create_time, update_time, del_flag) VALUES "
            "(:st, :sid, :ver, :idx, :content, :title, :url, '0', NOW(), NOW(), '0')"
        ), rows)
        chunk_ids = [int(r[0]) for r in conn.execute(text(
            "SELECT id FROM campus_rag_chunk "
            "WHERE source_type = :st AND source_id = :sid AND source_version = :ver"
        ), {"st": source_type, "sid": source_id, "ver": version}).fetchall()]

    # ④ 批量 Embedding（标题 + 分片文本，便于语义对齐）
    embeddings = embed_texts([f"{title}\n{c}" for c in chunks])

    # ⑤ 逐片 HSET 写 RediSearch（索引自动生效）
    vector_store.upsert_chunks([
        {"id": cid, "source_type": source_type, "source_id": source_id,
         "title": title, "chunk_index": i, "embedding": emb}
        for i, (cid, emb) in enumerate(zip(chunk_ids, embeddings))
    ])

    # 分片置已向量化 + ⑥ 新旧切换：全部写入成功后删除旧版本 chunk
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE campus_rag_chunk SET status = '1', update_time = NOW() "
            "WHERE source_type = :st AND source_id = :sid AND source_version = :ver"
        ), {"st": source_type, "sid": source_id, "ver": version})
        old_ids = [int(r[0]) for r in conn.execute(text(
            "SELECT id FROM campus_rag_chunk WHERE source_type = :st AND source_id = :sid "
            "AND source_version < :ver"
        ), {"st": source_type, "sid": source_id, "ver": version}).fetchall()]
        conn.execute(text(
            "DELETE FROM campus_rag_chunk WHERE source_type = :st AND source_id = :sid "
            "AND source_version < :ver"
        ), {"st": source_type, "sid": source_id, "ver": version})
    if old_ids:
        vector_store.delete_chunk_keys(old_ids)


def process_delete(task: dict) -> None:
    """delete 任务：移除该 source 全部向量（Redis+MySQL）→ SUCCESS。"""
    _remove_source_chunks(task["source_type"], task["source_id"])


def process_task(task: dict) -> None:
    """处理单个任务：upsert/delete 分流，异常转失败重试。"""
    try:
        if task["operation"] == "1":
            process_upsert(task)
        else:
            process_delete(task)
        _mark_success(task["id"])
    except Exception as exc:  # noqa: BLE001 —— 单任务失败不阻塞本轮
        _mark_failed(task["id"], str(exc))


# ===== 全量重建（8.3 兜底）=====

def start_rebuild() -> int:
    """执行全量重建启动段：清索引 → 重建空索引 → 逐源写 upsert 任务。

    Returns:
        本次写入的 upsert 任务数。
    """
    client = vector_store.binary_redis
    client.delete(REBUILD_REQUEST_KEY)
    client.set(REBUILDING_KEY, "1", ex=REBUILDING_TTL_SECONDS)
    vector_store.drop_index()
    # 清理 DROPINDEX 残留的 hash key（不带 DD，文档仍存）+ MySQL 旧分片
    stale_keys = vector_store.scan_chunk_keys()
    if stale_keys:
        client.delete(*stale_keys)
    vector_store.ensure_index()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM campus_rag_chunk"))
        for st, table in (("1", "campus_announcement"), ("2", "campus_knowledge")):
            conn.execute(text(
                "INSERT INTO campus_rag_task "
                "(operation, source_type, source_id, status, retry_count, "
                " create_time, update_time, del_flag) "
                f"SELECT '1', '{st}', t.id, '0', 0, NOW(), NOW(), '0' FROM {table} t "
                "WHERE t.status = '1' AND t.del_flag = '0'"
            ))
        count = conn.execute(text(
            "SELECT COUNT(*) FROM campus_rag_task WHERE status = '0' AND del_flag = '0'"
        )).scalar()
    logger.info("RAG 全量重建已启动：索引已重建空索引，写入 %s 个 upsert 任务", count)
    return int(count)


def finish_rebuild_if_done() -> bool:
    """重建完成判定：无 PENDING/PROCESSING 任务 → 删除 rebuilding 标记。"""
    with engine.connect() as conn:
        pending = conn.execute(text(
            "SELECT COUNT(*) FROM campus_rag_task "
            "WHERE status IN ('0', '1') AND del_flag = '0'"
        )).scalar()
    if int(pending) == 0:
        vector_store.binary_redis.delete(REBUILDING_KEY)
        logger.info("RAG 全量重建完成：rebuilding 标记已移除")
        return True
    return False


def run_rebuild_if_requested() -> None:
    """每轮重建检查：有请求 → 启动重建；重建中且队列清空 → 删标记。"""
    try:
        if vector_store.binary_redis.exists(REBUILD_REQUEST_KEY):
            start_rebuild()
        elif vector_store.is_rebuilding():
            finish_rebuild_if_done()
    except Exception as exc:  # noqa: BLE001 —— Redis 故障不阻塞任务处理
        logger.warning("重建检查失败（Redis 故障？）: %s", exc)


# ===== 每轮入口 / 调度 =====

def run_round() -> dict:
    """单轮执行：重建检查 → 崩溃恢复 → 领取并处理任务（≤TASKS_PER_ROUND）。"""
    run_rebuild_if_requested()
    recovered = recover_stale_tasks()
    processed = failed = 0
    for _ in range(TASKS_PER_ROUND):
        task = claim_next_task()
        if task is None:
            break
        before_failed = _count_failed()
        process_task(task)
        processed += 1
        if _count_failed() > before_failed:
            failed += 1
    return {"recovered": recovered, "processed": processed, "failed": failed}


def _count_failed() -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(
            "SELECT COUNT(*) FROM campus_rag_task WHERE status = '3' AND del_flag = '0'"
        )).scalar())


def cleanup_expired_logs() -> int:
    """日志清理（C-06/8.8）：删除超过 RAG_LOG_RETENTION_DAYS 的问答日志。"""
    with engine.begin() as conn:
        result = conn.execute(text(
            "DELETE FROM campus_rag_log WHERE create_time < "
            "NOW() - INTERVAL :days DAY"
        ), {"days": settings.RAG_LOG_RETENTION_DAYS})
    if result.rowcount:
        logger.info("RAG 日志清理：%s 条过期记录已删除", result.rowcount)
    return result.rowcount


# ===== APScheduler 调度（lifespan 启停）=====

_scheduler = None


def start_scheduler() -> None:
    """启动后台调度（30s 一轮 + 每日 03:30 日志清理），并幂等建索引。"""
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler  # pyright: ignore[reportMissingImports]
    from apscheduler.triggers.cron import CronTrigger  # pyright: ignore[reportMissingImports]
    from apscheduler.triggers.interval import IntervalTrigger  # pyright: ignore[reportMissingImports]

    try:
        vector_store.ensure_index()
    except Exception as exc:  # noqa: BLE001 —— Redis 未就绪不阻塞服务启动
        logger.warning("启动时建索引失败（Redis 未就绪？）: %s", exc)

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(run_round, IntervalTrigger(seconds=ROUND_INTERVAL_SECONDS),
                       id="rag_worker", max_instances=1, coalesce=True)
    _scheduler.add_job(cleanup_expired_logs, CronTrigger(hour=3, minute=30),
                       id="rag_log_cleanup", max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("RAG Worker 调度已启动（每 %ss 一轮）", ROUND_INTERVAL_SECONDS)


def stop_scheduler() -> None:
    """停止后台调度（应用关闭时调用）。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("RAG Worker 调度已停止")


def rag_index_health() -> dict:
    """rag_index 健康判定（9.6 C-10）：num_docs>0 且无 rebuilding → UP。"""
    stats = vector_store.index_stats()
    if not stats:  # Redis 故障/索引不存在
        return {"status": "UNKNOWN"}
    if stats.get("num_docs", 0) <= 0:
        return {"status": "NOT_CONFIGURED"}
    if vector_store.is_rebuilding():
        return {"status": "DEGRADED", "detail": "index rebuilding"}
    return {"status": "UP", "num_docs": stats.get("num_docs")}
