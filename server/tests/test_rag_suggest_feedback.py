"""T7-5 推荐问题 + 反馈接口测试（6.2/8.5）。

覆盖验收要点：列表返回、反馈入库且不可重复评价。
反馈接口依赖 campus_rag_log，测试直接插入独立日志行（结束清理），
不经过 chat mock 链路（chat 链路已在 test_rag_chat.py 覆盖）。
"""
import pytest
from sqlalchemy import text

from app.core.database import engine

LOG_IDS = []  # 本文件插入的 rag_log id，结束清理


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    if LOG_IDS:
        with engine.begin() as conn:
            conn.execute(text(
                f"DELETE FROM campus_rag_log WHERE id IN ({','.join(map(str, LOG_IDS))})"
            ))
        LOG_IDS.clear()


def _insert_log(feedback: str = "0") -> int:
    """插入一条测试问答日志，返回 id。"""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO campus_rag_log "
            "(session_id, question, answer, ref_ids, hit_count, model, "
            " prompt_tokens, completion_tokens, cost_time_ms, ip, feedback, "
            " refuse_reason, create_time, update_time, del_flag) VALUES "
            "(NULL, '测试问题', '测试回答', NULL, 0, 'test-model', 0, 0, 1, "
            "'10.0.x/xxxx', :fb, NULL, NOW(), NOW(), '0')"
        ), {"fb": feedback})
        return int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar())


# ===== 推荐问题 GET /api/rag/suggest =====

def test_suggest_returns_items(client):
    """公开接口：返回非空推荐问题列表（字符串数组）。"""
    resp = client.get("/api/rag/suggest").json()
    assert resp["code"] == 0
    items = resp["data"]["items"]
    assert isinstance(items, list) and len(items) >= 6
    assert all(isinstance(q, str) and q for q in items)
    assert len(items) == len(set(items))  # 去重保序


def test_suggest_covers_categories(client):
    """按知识分类（1~6）各 1~2 条：覆盖宿舍/食堂/师资等校园域问题。"""
    resp = client.get("/api/rag/suggest").json()
    joined = " ".join(resp["data"]["items"])
    for kw in ("宿舍", "食堂"):
        assert kw in joined


# ===== 反馈 POST /api/rag/feedback =====

def test_feedback_success_and_persisted(client):
    """log 存在且未评价：feedback=1 更新成功并落库。"""
    log_id = _insert_log()
    LOG_IDS.append(log_id)
    resp = client.post("/api/rag/feedback",
                       json={"log_id": log_id, "feedback": 1}).json()
    assert resp["code"] == 0
    assert resp["data"]["log_id"] == log_id
    with engine.connect() as conn:
        fb = conn.execute(text(
            "SELECT feedback FROM campus_rag_log WHERE id = :i"
        ), {"i": log_id}).scalar()
    assert fb == "1"


def test_feedback_dislike(client):
    """feedback=2（踩）同样入库。"""
    log_id = _insert_log()
    LOG_IDS.append(log_id)
    resp = client.post("/api/rag/feedback",
                       json={"log_id": log_id, "feedback": 2}).json()
    assert resp["code"] == 0


def test_feedback_duplicate_rejected(client):
    """已评价（feedback!=0）再次评价 → 4001（防重复评价/刷数）。"""
    log_id = _insert_log(feedback="1")
    LOG_IDS.append(log_id)
    resp = client.post("/api/rag/feedback",
                       json={"log_id": log_id, "feedback": 2}).json()
    assert resp["code"] == 4001
    assert "已评价" in resp["message"]


def test_feedback_log_missing(client):
    """log 不存在 → 4001。"""
    resp = client.post("/api/rag/feedback",
                       json={"log_id": 999999999, "feedback": 1}).json()
    assert resp["code"] == 4001


def test_feedback_param_validation(client):
    """feedback ∉ {1,2}、log_id ≤0 → 4001（Pydantic 校验）。"""
    for body in ({"log_id": 1, "feedback": 3},
                 {"log_id": 1, "feedback": 0},
                 {"log_id": 0, "feedback": 1},
                 {"log_id": -1, "feedback": 2}):
        resp = client.post("/api/rag/feedback", json=body).json()
        assert resp["code"] == 4001
