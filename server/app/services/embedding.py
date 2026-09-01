"""Embedding 客户端封装（T7-1，8.2/9.3）。

- 火山方舟 doubao-embedding-vision（**实测 2048 维** float32，与向量库 DDL 绑定）；
- **不接入 Agnes 兜底**（换模型将污染索引，ADR-013 边界）；
- 支持批量（Worker 切分后整批向量化，EMB_BATCH_SIZE=16 条/批）；
- 实测向量维度与 `EMB_DIM` 一致性校验，不一致 fail-fast（防脏向量入库）。
"""
import logging
import struct

import numpy as np  # pyright: ignore[reportMissingImports]
import openai  # pyright: ignore[reportMissingImports]

from app.core.config import settings
from app.services.llm import get_ark_client

logger = logging.getLogger("campus.rag.embedding")


class EmbeddingError(Exception):
    """向量化失败（含维度不一致 fail-fast）。"""


def _to_float32_bytes(vector: list[float]) -> bytes:
    """单条向量 → float32 小端字节序列（RediSearch FLOAT32 格式）。"""
    arr = np.asarray(vector, dtype=np.float32)
    if arr.shape != (settings.EMB_DIM,):
        # fail-fast：维度与 DDL 绑定不一致，拒绝入库（防脏向量污染索引）
        raise EmbeddingError(
            f"embedding 维度不一致: 期望 {settings.EMB_DIM}, 实际 {arr.shape[0]}"
        )
    return arr.tobytes()  # numpy 默认小端 float32


def embed_texts(texts: list[str]) -> list[bytes]:
    """批量向量化：texts → float32 bytes 列表（维度=EMB_DIM，doubao-embedding-vision 为 2048）。

    内部按 EMB_BATCH_SIZE 分批调用方舟接口（建议 8~16 条/批）。
    任何一批失败（含维度校验失败）整体抛 EmbeddingError，由 Worker 记失败重试。
    """
    if not texts:
        return []
    client = get_ark_client()
    result: list[bytes] = []
    batch_size = max(1, settings.EMB_BATCH_SIZE)
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            resp = client.embeddings.create(model=settings.EMB_MODEL, input=batch)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError(f"embedding 调用失败: {exc}") from exc
        if len(resp.data) != len(batch):
            raise EmbeddingError(
                f"embedding 返回条数不一致: 期望 {len(batch)}, 实际 {len(resp.data)}"
            )
        # 按 index 排序，保证与入参顺序一致
        for item in sorted(resp.data, key=lambda d: d.index):
            result.append(_to_float32_bytes(item.embedding))
    return result


def embed_query(question: str) -> bytes:
    """单条问题向量化（T7-4 问答检索用）。"""
    return embed_texts([question])[0]
