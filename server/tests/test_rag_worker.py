"""T7-3 RAG 任务 Worker 测试（5.3.16/5.3.18/8.3）。

覆盖验收要点（验收标准 11、12）：
- upsert 整源重建链路（切分→版本+1→Embedding→HSET→旧版本清理）；
- delete 任务移除向量（Redis+MySQL）；
- 失败指数退避重试（2/4/8 分钟）与终态 FAILED（retry_count>3）；
- 崩溃恢复（PROCESSING 超时 10 分钟 → PENDING）；
- 全量重建（标记 → 清索引 → 逐源 upsert 任务 → 完成删标记）；
- 任务领取条件更新（受影响行数=1 才持有，P0-08）。

依赖本机 MySQL(3307)/Redis Stack(6379)；Embedding 以确定性向量 mock
（不真实调用方舟）。测试数据用独立 id 段（91xxxx），结束清理。
"""
import numpy as np
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.rag import worker
from app.services import vector_store

ANN_ID = 910001
KNOW_ID = 910002
MISSING_ID = 919999

UNIT_DIM = settings.EMB_DIM


def _fake_vec(seed: int) -> bytes:
    """确定性单位向量：KNN 下 seed 相同互相最近。"""
    v = np.zeros(UNIT_DIM, dtype=np.float32)
    v[seed % UNIT_DIM] = 1.0
    return v.tobytes()


def _fake_embed(texts):
    """按文本内容 seed 的 mock Embedding（标题相同的 chunk 向量一致）。"""
    return [_fake_vec(abs(hash(t)) ) for t in texts]


@pytest.fixture(autouse=True)
def _cleanup():
    """测试数据隔离与清理（MySQL 任务/分片/源文档 + Redis key）。

    快照式清理：先记录已存在的 chunk id（dev 库可能已有真实向量化数据，
    测试用 mock 向量，不得污染/误删真实数据）；结束后删除测试期间新增的
    chunk（MySQL 行 + Redis key）与测试源/任务，并清掉重建标记。
    """
    from app.core.redis_client import redis_client

    for k in redis_client.scan_iter("rag:rate:*"):
        redis_client.delete(k)
    with engine.connect() as conn:
        # 快照完整 chunk 行（全量重建测试会清表，结束后按快照恢复；
        # 恢复行的 Redis 向量如缺失，走管理端「全量重建」兜底）
        snapshot_rows = conn.execute(text(
            "SELECT id, source_type, source_id, source_version, chunk_index, "
            "content, title, url, status FROM campus_rag_chunk"
        )).fetchall()
        snapshot_ids = {int(r[0]) for r in snapshot_rows}
    yield
    with engine.begin() as conn:
        current = {int(r[0]) for r in conn.execute(
            text("SELECT id FROM campus_rag_chunk")).fetchall()}
        new_ids = sorted(current - snapshot_ids)
        if new_ids:
            vector_store.delete_chunk_keys(new_ids)
            id_list = ",".join(map(str, new_ids))
            conn.execute(text(f"DELETE FROM campus_rag_chunk WHERE id IN ({id_list})"))
        # 恢复被全量重建清掉的存量行（含测试 91xxxx 段以外的真实数据）
        missing = [r for r in snapshot_rows if int(r[0]) not in current]
        if missing:
            conn.execute(text(
                "INSERT INTO campus_rag_chunk "
                "(id, source_type, source_id, source_version, chunk_index, content, "
                " title, url, status, create_time, update_time, del_flag) VALUES "
                "(:id, :st, :sid, :ver, :idx, :content, :title, :url, :status, "
                " NOW(), NOW(), '0')"
            ), [dict(zip(("id", "st", "sid", "ver", "idx", "content", "title", "url",
                          "status"), r)) for r in missing])
        for st, sid in (("1", ANN_ID), ("2", KNOW_ID), ("1", MISSING_ID), ("2", MISSING_ID)):
            ids = [int(r[0]) for r in conn.execute(text(
                "SELECT id FROM campus_rag_chunk WHERE source_type = :st AND source_id = :sid"
            ), {"st": st, "sid": sid}).fetchall()]
            if ids:
                vector_store.delete_chunk_keys(ids)
        conn.execute(text("DELETE FROM campus_rag_chunk WHERE source_id IN (:a, :b, :m1, :m2)"),
                     {"a": ANN_ID, "b": KNOW_ID, "m1": MISSING_ID, "m2": MISSING_ID})
        conn.execute(text("DELETE FROM campus_rag_task WHERE source_id IN (:a, :b, :m1, :m2)"),
                     {"a": ANN_ID, "b": KNOW_ID, "m1": MISSING_ID, "m2": MISSING_ID})
        conn.execute(text("DELETE FROM campus_announcement WHERE id IN (:a, :m1)"),
                     {"a": ANN_ID, "m1": MISSING_ID})
        conn.execute(text("DELETE FROM campus_knowledge WHERE id IN (:b, :m2)"),
                     {"b": KNOW_ID, "m2": MISSING_ID})
    vector_store.binary_redis.delete(vector_store.REBUILD_REQUEST_KEY,
                                     vector_store.REBUILDING_KEY)


def _insert_ann(aid: int, title: str, content: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_announcement "
            "(id, title, content, ann_type, is_top, status, del_flag, create_time, update_time) "
            "VALUES (:id, :t, :c, '1', '0', '1', '0', NOW(), NOW())"
        ), {"id": aid, "t": title, "c": content})


def _insert_knowledge(kid: int, title: str, content: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_knowledge "
            "(id, title, category, content, status, del_flag, create_time, update_time) "
            "VALUES (:id, :t, '2', :c, '1', '0', NOW(), NOW())"
        ), {"id": kid, "t": title, "c": content})


def _insert_task(operation: str, source_type: str, source_id: int) -> int:
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_rag_task "
            "(operation, source_type, source_id, status, retry_count, del_flag, create_time, update_time) "
            "VALUES (:op, :st, :sid, '0', 0, '0', NOW(), NOW())"
        ), {"op": operation, "st": source_type, "sid": source_id})
        return int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar())


def _task_row(task_id: int):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT operation, status, retry_count, next_retry_time, last_error "
            "FROM campus_rag_task WHERE id = :tid"
        ), {"tid": task_id}).first()


def _chunk_rows(source_type: str, source_id: int):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT id, source_version, chunk_index, content, title, url, status "
            "FROM campus_rag_chunk WHERE source_type = :st AND source_id = :sid "
            "ORDER BY source_version, chunk_index"
        ), {"st": source_type, "sid": source_id}).fetchall()


# ===== upsert 链路 =====

def test_upsert_creates_chunks_and_vectors(monkeypatch):
    """upsert：切分→chunk 批次（version=1）→向量化→Redis 写入→SUCCESS。"""
    long_line = "食堂服务监督与建议反馈渠道全天候开放，营业高峰期请错峰用餐，节约粮食人人有责，光盘行动从我做起。" * 14
    _insert_ann(ANN_ID, "第一食堂风味窗口指南",
                "第一食堂位于校园东区，共三层。\n一楼提供早餐与大众窗口，营业时间6:30-19:00。\n"
                "二楼为风味窗口：川菜、粤菜、西北面食、麻辣烫、黄焖鸡米饭、兰州拉面应有尽有。\n"
                "三楼为清真餐厅与教工餐厅，周末照常营业。\n" + long_line)
    task_id = _insert_task("1", "1", ANN_ID)
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)

    result = worker.run_round()
    assert result["processed"] == 1 and result["failed"] == 0

    row = _task_row(task_id)
    assert row[1] == "2"  # SUCCESS
    chunks = _chunk_rows("1", ANN_ID)
    assert len(chunks) >= 2  # 300~500 字切段
    assert all(c[6] == "1" for c in chunks)          # 已向量化
    assert {c[1] for c in chunks} == {1}             # 初版 version=1
    assert chunks[0][4] == "第一食堂风味窗口指南"     # 标题元数据
    assert chunks[0][5] == f"/api/announcements/{ANN_ID}"  # url 规则
    for c in chunks:
        assert vector_store.binary_redis.exists(f"{vector_store.KEY_PREFIX}{c[0]}")

    # KNN 往返：同文本向量检索命中自身 chunk
    q_vec = _fake_vec(abs(hash(f"第一食堂风味窗口指南\n{chunks[0][3]}")))
    hits = vector_store.knn_search(q_vec, k=3)
    assert hits and hits[0][0] == chunks[0][0]


def test_upsert_new_version_removes_old_chunks(monkeypatch):
    """P0-09 整源重建：再发布生成 version=2，旧版本 chunk（MySQL+Redis）清理。"""
    _insert_ann(ANN_ID, "图书馆开放时间", "图书馆开放时间为每日 8:00-22:00。")
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)
    _insert_task("1", "1", ANN_ID)
    worker.run_round()
    old_chunks = _chunk_rows("1", ANN_ID)
    old_ids = [c[0] for c in old_chunks]

    # 内容变化 → 新任务
    with engine.begin() as conn:
        conn.execute(text("UPDATE campus_announcement SET content = :c WHERE id = :i"),
                     {"c": "图书馆自下周起开放时间调整为 7:30-23:00，考试周通宵开放。",
                      "i": ANN_ID})
    _insert_task("1", "1", ANN_ID)
    worker.run_round()

    new_chunks = _chunk_rows("1", ANN_ID)
    assert {c[1] for c in new_chunks} == {2}
    for cid in old_ids:
        assert not vector_store.binary_redis.exists(f"{vector_store.KEY_PREFIX}{cid}")
    assert all(vector_store.binary_redis.exists(f"{vector_store.KEY_PREFIX}{c[0]}")
               for c in new_chunks)


def test_upsert_missing_source_cleans_and_succeeds(monkeypatch):
    """源已下架/不存在：按 delete 语义清理，任务幂等 SUCCESS。"""
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)
    task_id = _insert_task("1", "1", MISSING_ID)
    worker.run_round()
    assert _task_row(task_id)[1] == "2"
    assert _chunk_rows("1", MISSING_ID) == []


def test_delete_task_removes_chunks(monkeypatch):
    """delete 任务：Redis DEL + MySQL 删行 → SUCCESS。"""
    _insert_knowledge(KNOW_ID, "新生宿舍分配指南", "宿舍A栋为四人间，配备空调与独立卫浴，独立阳台。")
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)
    _insert_task("1", "2", KNOW_ID)
    worker.run_round()
    assert _chunk_rows("2", KNOW_ID)
    chunk_ids = [c[0] for c in _chunk_rows("2", KNOW_ID)]

    del_task = _insert_task("2", "2", KNOW_ID)
    worker.run_round()
    assert _task_row(del_task)[1] == "2"
    assert _chunk_rows("2", KNOW_ID) == []
    for cid in chunk_ids:
        assert not vector_store.binary_redis.exists(f"{vector_store.KEY_PREFIX}{cid}")


def test_knowledge_html_stripped_before_chunking(monkeypatch):
    """知识库富文本：剥离 HTML 后切分（8.3）。"""
    _insert_knowledge(KNOW_ID, "师资介绍",
                      "<p>张伟教授，计算机学院博士生导师。</p><p>研究方向：分布式系统。</p>"
                      "<script>alert(1)</script>")
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)
    _insert_task("1", "2", KNOW_ID)
    worker.run_round()
    chunks = _chunk_rows("2", KNOW_ID)
    assert chunks
    joined = "\n".join(c[3] for c in chunks)
    assert "张伟教授" in joined and "alert" not in joined and "<p>" not in joined


# ===== 失败重试 / 崩溃恢复 =====

def test_failure_exponential_backoff(monkeypatch):
    """失败：retry_count+1、退避 2^retry_count 分钟回 PENDING；>3 次终态 FAILED。"""
    _insert_ann(ANN_ID, "重试测试", "内容")
    task_id = _insert_task("1", "1", ANN_ID)

    def _boom(texts):
        raise RuntimeError("embedding 服务超时")
    monkeypatch.setattr(worker, "embed_texts", _boom)

    for expect_retry in (1, 2, 3):
        worker.run_round()
        row = _task_row(task_id)
        assert row[1] == "0"                       # 回 PENDING 等退避
        assert row[2] == expect_retry
        assert row[4] and "超时" in row[4]
        # 退避到期（测试压缩时间：清 next_retry_time 模拟到期）
        with engine.begin() as conn:
            conn.execute(text("UPDATE campus_rag_task SET next_retry_time = NULL WHERE id = :t"),
                         {"t": task_id})

    worker.run_round()  # 第 4 次失败 → 终态
    row = _task_row(task_id)
    assert row[1] == "3" and row[2] == 4           # FAILED 终态，不再重试


def test_recover_stale_processing_tasks():
    """崩溃恢复：PROCESSING 超 10 分钟 → 重置 PENDING（P0-08）。"""
    task_id = _insert_task("1", "1", MISSING_ID)
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE campus_rag_task SET status = '1', "
            "update_time = NOW() - INTERVAL 15 MINUTE WHERE id = :t"
        ), {"t": task_id})
    assert worker.recover_stale_tasks() >= 1
    assert _task_row(task_id)[1] == "0"


def test_claim_conditional_update():
    """任务领取：条件更新置 PROCESSING；重复领取不再持有（P0-08）。"""
    task_id = _insert_task("2", "1", MISSING_ID)
    task = worker.claim_next_task()
    assert task and task["id"] == task_id
    assert _task_row(task_id)[1] == "1"
    # 任务已 PROCESSING，无 PENDING 可领
    assert worker.claim_next_task() is None


# ===== 全量重建 =====

def test_full_rebuild(monkeypatch):
    """全量重建：请求标记 → 清索引 → 逐源 upsert 任务 → 队列清空删标记。"""
    _insert_ann(ANN_ID, "重建公告测试", "重建公告内容：全校师生请注意。")
    _insert_knowledge(KNOW_ID, "重建知识测试", "重建知识内容：奖学金评定办法。")
    monkeypatch.setattr(worker, "embed_texts", _fake_embed)

    vector_store.binary_redis.set(vector_store.REBUILD_REQUEST_KEY, "1")
    worker.run_round()  # 启动重建 + 处理部分任务
    assert vector_store.is_rebuilding()

    # 跑到队列清空（重建任务全部处理）
    for _ in range(5):
        if not vector_store.is_rebuilding():
            break
        worker.run_round()
    assert not vector_store.is_rebuilding()
    assert not vector_store.binary_redis.exists(vector_store.REBUILD_REQUEST_KEY)

    # 两个源均已向量化，索引有文档
    assert _chunk_rows("1", ANN_ID)
    assert _chunk_rows("2", KNOW_ID)
    assert vector_store.index_stats()["num_docs"] >= 2
    with engine.connect() as conn:
        stuck = conn.execute(text(
            "SELECT COUNT(*) FROM campus_rag_task WHERE status IN ('0','1') AND del_flag='0'"
        )).scalar()
    assert int(stuck) == 0
