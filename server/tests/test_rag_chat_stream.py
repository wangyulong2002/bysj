"""T7-8 SSE 流式问答 + 多轮对话测试（8.5/8.1）。

覆盖验收要点（流式渲染、多轮上下文正确）：
- SSE 契约：media_type=text/event-stream；`data: {json}\\n\\n` 帧解析；
  delta 多帧拼接 == done.answer（权威文本，L3 清洗后一致）；
  done 帧字段完整（sources/refused/refuse_reason/log_id）；
- 闸门联动：L0 越界/注入 → 拒答帧且 LLM 0 次调用；L2 哨兵 → done 拒答并
  以拒答文案覆盖流式增量；5001 双通道失败 → error 帧（携带检索资料）；
- 多轮上下文：session_id 串联最近 3 轮**非拒答**问答（拒答轮不进入上下文、
  超出截断、时间正序 user/assistant 交替）；
- 建流前错误走常规 JSON：4291 限流、4001 参数校验。

LLM/检索全 mock（与 test_rag_chat 同策略）。
"""
import json

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.rag.retriever import RetrievedChunk
from app.services.llm import LLMError

LOG_IDS = []      # 流式产生的 rag_log id（结束清理）
SESSION_IDS = []  # 多轮测试的 session_id（结束清理历史轮）


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """测试隔离：清限流计数、还原阈值、清理日志与历史轮。"""
    from app.core.redis_client import redis_client

    for k in redis_client.scan_iter("rag:rate:*"):
        redis_client.delete(k)
    monkeypatch.setattr(settings, "RAG_RATE_PER_MIN", 10)
    monkeypatch.setattr(settings, "RAG_RATE_PER_DAY", 100)
    monkeypatch.setattr(settings, "RAG_SCORE_HIGH", 0.75)
    monkeypatch.setattr(settings, "RAG_SCORE_LOW", 0.45)
    monkeypatch.setattr(settings, "RAG_STRICT_DOMAIN", 1)
    yield
    for k in redis_client.scan_iter("rag:rate:*"):
        redis_client.delete(k)
    if LOG_IDS:
        with engine.begin() as conn:
            conn.execute(text(
                f"DELETE FROM campus_rag_log WHERE id IN ({','.join(map(str, LOG_IDS))})"
            ))
        LOG_IDS.clear()
    if SESSION_IDS:
        with engine.begin() as conn:
            for sid in SESSION_IDS:
                conn.execute(text(
                    "DELETE FROM campus_rag_log WHERE session_id = :sid"
                ), {"sid": sid})
        SESSION_IDS.clear()


def _chunk(chunk_id=1, source_type="1", source_id=101, title="新生住宿指南",
           content="宿舍A栋为4人间，配备空调和独立卫浴。", sim=0.9):
    return RetrievedChunk(chunk_id=chunk_id, source_type=source_type,
                          source_id=source_id, chunk_index=0, title=title,
                          content=content, url="", score=0.03, sim=sim)


class _StreamLLM:
    """流式 LLM mock：按预设分片 yield 增量；记录 messages 供多轮断言。"""

    def __init__(self, pieces=None, fail=False):
        self.pieces = pieces or ["根据资料，", "宿舍A栋", "为4人间[1]。"]
        self.fail = fail
        self.calls = []

    def __call__(self, messages, max_tokens=None, usage_out=None):
        self.calls.append(messages)
        if self.fail:
            raise LLMError("LLM 双通道均失败（方舟+Agnes）")
        pieces = list(self.pieces)

        def gen():
            for p in pieces:
                yield p
            if usage_out is not None:
                usage_out.update({"model": "deepseek-chat",
                                  "prompt_tokens": 120, "completion_tokens": 30})
        return gen()


def _mock_retrieval(monkeypatch, chunks=None, best_sim=0.9, bm25_top_rank=None):
    from app.rag import retriever as retriever_mod

    chunks = [_chunk()] if chunks is None else chunks

    def fake_hybrid(question, q_vec, knn_k=None, top_n=None):
        return list(chunks), best_sim, len(chunks), bm25_top_rank

    def fake_embed(q):
        return b"\x00" * 4

    monkeypatch.setattr("app.api.rag_chat.hybrid_search", fake_hybrid)
    monkeypatch.setattr("app.api.rag_chat.embed_query", fake_embed)
    return fake_hybrid


def _post_stream(client, question, session_id=None):
    body = {"question": question}
    if session_id:
        body["session_id"] = session_id
    return client.post("/api/rag/chat/stream", json=body)


def _frames(resp):
    """断言 SSE 响应并解析全部 data 帧。"""
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = []
    for block in resp.text.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            frames.append(json.loads(block[len("data: "):]))
    assert frames, "至少应有一个 SSE 帧"
    return frames


def _track_log_id(frame):
    if frame.get("log_id"):
        LOG_IDS.append(frame["log_id"])


# ===== SSE 契约 =====

def test_stream_basic_contract(client, monkeypatch):
    """delta 多帧拼接 == done.answer；done 帧字段完整；sources 映射公告 url。"""
    llm = _StreamLLM(["根据资料，", "宿舍A栋", "为4人间[1]。"])
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)

    resp = _post_stream(client, "宿舍是几人间？", session_id="sess-basic")
    frames = _frames(resp)

    types = [f["type"] for f in frames]
    assert types[0] == "delta" and types[-1] == "done"
    deltas = [f["content"] for f in frames if f["type"] == "delta"]
    done = frames[-1]
    assert "".join(deltas) == done["answer"]          # 增量拼接 == 权威文本
    assert done["refused"] is False and done["refuse_reason"] is None
    assert done["sources"] == [{"id": 101, "title": "新生住宿指南",
                                "url": "/api/announcements/101", "type": "announcement"}]
    assert done["hit_count"] == 1 and done["log_id"]
    _track_log_id(done)
    # Prompt 组装在首帧前完成：LLM 恰好被调用 1 次
    assert len(llm.calls) == 1


def test_stream_param_validation_json(client):
    """入参校验在建流前 → 常规 JSON 4001（非 SSE）。"""
    resp = _post_stream(client, "长" * 501)
    assert resp.status_code == 200
    assert resp.json()["code"] == 4001


def test_stream_rate_limited_json(client, monkeypatch):
    """限流在建流前 → 常规 JSON 4291（非 SSE 帧）。"""
    monkeypatch.setattr(settings, "RAG_RATE_PER_MIN", 1)
    _mock_retrieval(monkeypatch)
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream",
                        _StreamLLM())
    first = _post_stream(client, "宿舍几人间", session_id="sess-rate")
    for f in _frames(first):
        _track_log_id(f)
    second = _post_stream(client, "食堂几点开门")
    body = second.json()
    assert body["code"] == 4291
    assert "event-stream" not in second.headers.get("content-type", "")


# ===== 闸门联动（拒答走帧契约）=====

def test_stream_l0_refusal_frames(client, monkeypatch):
    """L0 越界：拒答 delta + done(refused)；LLM 0 次调用、不检索。"""
    llm = _StreamLLM()
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)

    def _fail(*a, **k):  # 检索不应发生
        raise AssertionError("L0 拒答不应触发检索")

    monkeypatch.setattr("app.api.rag_chat.hybrid_search", _fail)
    monkeypatch.setattr("app.api.rag_chat.embed_query", _fail)

    frames = _frames(_post_stream(client, "帮我写代码实现快速排序"))
    assert [f["type"] for f in frames] == ["delta", "done"]
    done = frames[-1]
    assert done["refused"] is True and done["refuse_reason"] == "out_of_scope"
    assert done["answer"] and done["sources"] == []
    assert frames[0]["content"] == done["answer"]
    assert len(llm.calls) == 0  # LLM 0 次调用
    _track_log_id(done)


def test_stream_l2_sentinel_overrides_streamed_text(client, monkeypatch):
    """L2 哨兵：流式增量已发出，done 帧以拒答文案覆盖（answer 为权威文本）。"""
    llm = _StreamLLM(["好的，", "这是一首诗……[[OUT_OF_SCOPE]]"])
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)

    frames = _frames(_post_stream(client, "宿舍几人间", session_id="sess-l2"))
    done = frames[-1]
    assert done["type"] == "done" and done["refused"] is True
    assert done["refuse_reason"] == "out_of_scope"
    assert "[[OUT_OF_SCOPE]]" not in done["answer"]   # 权威文本不含哨兵
    assert done["answer"].startswith("抱歉")          # 覆盖为拒答文案
    _track_log_id(done)


def test_stream_l2_empty_answer_refused_no_context(client, monkeypatch):
    """流式 LLM 返回空 content → done 帧拒答 no_context（权威文本覆盖）。"""
    llm = _StreamLLM([""])
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)
    frames = _frames(_post_stream(client, "第三食堂什么时候开业",
                                  session_id="sess-empty"))
    done = frames[-1]
    assert done["type"] == "done" and done["refused"] is True
    assert done["refuse_reason"] == "no_context"
    assert done["answer"].startswith("暂时没有")
    _track_log_id(done)


def test_stream_llm_error_frame(client, monkeypatch):
    """双通道失败 → error 帧（5001 + 检索资料列表），无 done 帧、不编造。"""
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream",
                        _StreamLLM(fail=True))
    _mock_retrieval(monkeypatch)

    frames = _frames(_post_stream(client, "宿舍几人间"))
    assert frames[-1]["type"] == "error"
    err = frames[-1]
    assert err["code"] == 5001
    assert err["data"]["sources"]                     # 降级返回检索资料
    assert all(f["type"] != "done" for f in frames)   # 不发结束帧


# ===== 多轮上下文（T7-8/8.1）=====

def _seed_history(session_id: str, rounds: list[tuple[str, str]],
                  refuse_last: bool = False):
    """写入历史轮（含可选的拒答轮，拒答轮不应进入上下文）。"""
    ids = []
    with engine.begin() as conn:
        for q, a in rounds:
            conn.execute(text(
                "INSERT INTO campus_rag_log (session_id, question, answer, "
                " ref_ids, hit_count, model, prompt_tokens, completion_tokens, "
                " cost_time_ms, ip, feedback, refuse_reason, create_time, "
                " update_time, del_flag) VALUES "
                "(:sid, :q, :a, NULL, 1, 'deepseek-chat', 10, 10, 10, "
                " '1.2.3.4.x/x', '0', NULL, NOW(), NOW(), '0')"
            ), {"sid": session_id, "q": q, "a": a})
            ids.append(int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()))
        if refuse_last:
            conn.execute(text(
                "INSERT INTO campus_rag_log (session_id, question, answer, "
                " ref_ids, hit_count, model, prompt_tokens, completion_tokens, "
                " cost_time_ms, ip, feedback, refuse_reason, create_time, "
                " update_time, del_flag) VALUES "
                "(:sid, '帮我写首诗', '抱歉……', NULL, 0, '', 0, 0, 10, "
                " '1.2.3.4.x/x', '0', 'out_of_scope', NOW(), NOW(), '0')"
            ), {"sid": session_id})
    LOG_IDS.extend(ids)
    SESSION_IDS.append(session_id)


def test_stream_multi_turn_history_included(client, monkeypatch):
    """session_id 串联最近 3 轮：user/assistant 交替进入 Prompt，拒答轮排除。"""
    llm = _StreamLLM()
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)

    sid = "sess-mt"
    _seed_history(sid, [
        ("宿舍几人间？", "4人间与6人间。"),
        ("食堂几点开门？", "早餐6:30。"),
        ("图书馆几点闭馆？", "22:00。"),
    ], refuse_last=True)  # 拒答轮不进入上下文

    frames = _frames(_post_stream(client, "奖学金怎么申请？", session_id=sid))
    done = frames[-1]
    _track_log_id(done)

    assert len(llm.calls) == 1
    messages = llm.calls[0]
    # system + 3 轮历史(user/assistant×3) + 最终 user = 8 条
    assert len(messages) == 8
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user" and messages[1]["content"] == "宿舍几人间？"
    assert messages[2]["role"] == "assistant" and messages[2]["content"] == "4人间与6人间。"
    assert messages[-3]["role"] == "user" and messages[-3]["content"] == "图书馆几点闭馆？"
    assert messages[-2]["role"] == "assistant" and messages[-2]["content"] == "22:00。"
    assert messages[-1]["role"] == "user" and "奖学金怎么申请？" in messages[-1]["content"]
    # 拒答轮的问题不得进入上下文
    assert all("帮我写首诗" not in m["content"] for m in messages)


def test_stream_history_truncated_to_three_rounds(client, monkeypatch):
    """超出 3 轮截断：仅最近 3 轮进入 Prompt。"""
    llm = _StreamLLM()
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)

    sid = "sess-trunc"
    _seed_history(sid, [
        ("最早问题1？", "答1"),
        ("最早问题2？", "答2"),
        ("中段问题3？", "答3"),
        ("较新问题4？", "答4"),
        ("最近问题5？", "答5"),
    ])

    frames = _frames(_post_stream(client, "最新问题？", session_id=sid))
    _track_log_id(frames[-1])

    messages = llm.calls[0]
    assert len(messages) == 1 + 3 * 2 + 1  # system + 最近 3 轮 + 最终 user
    assert "最早问题1？" not in json.dumps(messages, ensure_ascii=False)
    assert "最近问题5？" in json.dumps(messages, ensure_ascii=False)


def test_stream_no_session_no_history(client, monkeypatch):
    """无 session_id → 无历史（system + user 两条）。"""
    llm = _StreamLLM()
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    _mock_retrieval(monkeypatch)

    frames = _frames(_post_stream(client, "宿舍几人间"))
    _track_log_id(frames[-1])
    messages = llm.calls[0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system" and messages[1]["role"] == "user"


def test_stream_multi_turn_retrieval_rewritten(client, monkeypatch):
    """§5.3 修复：指代类追问检索前改写为"上一轮问题 + 当前问题"；
    生成 Prompt 仍用原始问题（历史已注入），不改变多轮消息结构。"""
    llm = _StreamLLM()
    monkeypatch.setattr("app.api.rag_chat.chat_completion_stream", llm)
    fake = _mock_retrieval(monkeypatch)
    captured: dict = {}
    def _spy(question, *a, **kw):
        captured["q"] = question
        return fake(question, *a, **kw)
    monkeypatch.setattr("app.api.rag_chat.hybrid_search", _spy)

    sid = "sess-rewrite"
    _seed_history(sid, [("图书馆几点开门？", "早8点到晚10点。")])

    frames = _frames(_post_stream(client, "那它周末也开放吗？", session_id=sid))
    _track_log_id(frames[-1])

    # 检索查询已被改写（指代消解）
    assert captured["q"] == "图书馆几点开门？，那它周末也开放吗？"
    # 生成 Prompt 结构不变：system + 历史(user/assistant) + 最终 user
    messages = llm.calls[0]
    assert len(messages) == 4
    assert messages[1]["content"] == "图书馆几点开门？"
    assert "那它周末也开放吗？" in messages[-1]["content"]
