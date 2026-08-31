"""RediSearch 向量库封装（T7-1，8.2）。

- 索引 DDL 以设计 8.2 为权威，字段不得增减：
  `FT.CREATE rag_idx ON HASH PREFIX 1 rag:chunk: SCHEMA
   source_type TAG source_id NUMERIC SORTABLE title TEXT chunk_index NUMERIC
   embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 2560 DISTANCE_METRIC COSINE`
- Redis key 约定 `rag:chunk:{chunk_id}`，与 MySQL `campus_rag_chunk.id` 一一对应；
- 使用**独立二进制 Redis 客户端**（decode_responses=False）：向量 float32 bytes
  不能经文本编解码（公告缓存用的 redis_client 是文本客户端，不复用）；
- 本环境实测实现约定：RediSearch `DEFAULT_DIALECT=1`，KNN 查询必须显式
  `DIALECT 2` 且置于 `PARAMS` **之前**（否则 `Syntax error near >[`）；
- FT.SEARCH 返回为 dict 结构（`total_results` / `results[].id` /
  `results[].extra_attributes`），解析兼容旧版数组结构；
- 中文分词实测约定：默认分词器将整段中文视为单 token（子串无法命中 BM25），
  故写入 title 时附加"单字空格序列"（如 `食堂 食 堂 …`），查询侧对中文取
  单字 OR 组合——SCHEMA 字段集不变，属索引内容预处理实现约定。
"""
import logging

import redis  # pyright: ignore[reportMissingImports]
from redis.exceptions import ResponseError

from app.core.config import settings

logger = logging.getLogger("campus.rag.vector_store")

INDEX_NAME = "rag_idx"
KEY_PREFIX = "rag:chunk:"
REBUILDING_KEY = "rag:rebuilding"          # 全量重建中标记（health C-10 判定）
REBUILD_REQUEST_KEY = "rag:rebuild_requested"  # 管理端重建请求（Worker 消费）

# 二进制客户端：向量 bytes 直传（文本客户端会破坏 float32 序列化）
binary_redis: redis.Redis = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=False,
    socket_timeout=5,
    socket_connect_timeout=5,
)

_FT_CREATE_DDL = [
    "FT.CREATE", INDEX_NAME, "ON", "HASH", "PREFIX", "1", KEY_PREFIX,
    "SCHEMA",
    "source_type", "TAG",
    "source_id", "NUMERIC", "SORTABLE",
    "title", "TEXT",
    "chunk_index", "NUMERIC",
    "embedding", "VECTOR", "HNSW", "6",
    "TYPE", "FLOAT32", "DIM", str(settings.EMB_DIM),
    "DISTANCE_METRIC", "COSINE",
]


def _index_exists() -> bool:
    """探测索引是否存在（FT.INFO；未知索引名视为不存在）。"""
    try:
        binary_redis.execute_command("FT.INFO", INDEX_NAME)
        return True
    except ResponseError as exc:
        if "unknown index" in str(exc).lower():
            return False
        raise


def ensure_index() -> bool:
    """幂等建索引：先 FT.INFO 探测，缺失才按 8.2 权威 DDL 创建。

    Returns:
        True=本次创建；False=已存在（未变更）。
    """
    if _index_exists():
        return False
    binary_redis.execute_command(*_FT_CREATE_DDL)
    logger.info("RediSearch 索引 %s 创建成功 (DIM=%s, COSINE)", INDEX_NAME, settings.EMB_DIM)
    return True


def drop_index() -> None:
    """删除索引但保留 hash 文档（全量重建由调用方另行清理 key）。"""
    try:
        binary_redis.execute_command("FT.DROPINDEX", INDEX_NAME)
    except ResponseError as exc:
        if "unknown index" not in str(exc).lower():
            raise


def index_stats() -> dict:
    """索引统计（9.6 C-10）：返回 {num_docs}，索引不存在/Redis 故障返回空 dict。"""
    try:
        info = binary_redis.execute_command("FT.INFO", INDEX_NAME)
    except (ResponseError, redis.RedisError) as exc:
        logger.warning("FT.INFO 失败: %s", exc)
        return {}
    # 响应为交替键值对（list）或 dict（不同版本差异），统一摊平
    pairs: dict = {}
    if isinstance(info, dict):
        pairs = {k: v for k, v in info.items()}
    else:
        it = iter(info)
        pairs = dict(zip(it, it))
    num_docs = pairs.get(b"num_docs") or pairs.get("num_docs")
    return {"num_docs": int(num_docs) if num_docs is not None else 0}


def _parse_search_results(resp) -> list[dict]:
    """解析 FT.SEARCH 响应 → [{id, fields{...}}]，兼容 dict/数组两种结构。"""
    results: list[dict] = []
    if isinstance(resp, dict):
        for item in resp.get(b"results") or resp.get("results") or []:
            results.append({
                "id": item.get(b"id") or item.get("id"),
                "fields": item.get(b"extra_attributes") or item.get("extra_attributes") or {},
            })
        return results
    # 旧版数组结构：[total, id1, [f1, v1, ...], id2, [...], ...]
    rows = resp[1:] if isinstance(resp, (list, tuple)) else []
    i = 0
    while i < len(rows):
        rid = rows[i]
        fields: dict = {}
        if i + 1 < len(rows) and isinstance(rows[i + 1], (list, tuple)):
            fv = rows[i + 1]
            fields = dict(zip(fv[::2], fv[1::2]))
            i += 2
        else:
            i += 1
        results.append({"id": rid, "fields": fields})
    return results


def _chunk_id(doc_id) -> int | None:
    """doc id（bytes/str，形如 rag:chunk:123）→ chunk id int。"""
    if doc_id is None:
        return None
    if isinstance(doc_id, bytes):
        doc_id = doc_id.decode()
    return int(doc_id.rsplit(":", 1)[-1])


def title_index_value(title: str) -> str:
    """写入 TEXT 字段 title 的索引值：原标题 + 单字空格序列（中文 BM25 可命中）。

    默认分词器把整段中文当一个 token（子串无法命中），附加单字序列后
    查询侧可按"单字 OR"召回标题包含这些字的 chunk（实现约定，见模块 docstring）。
    """
    chars = " ".join(dict.fromkeys(title))  # 去重保序
    return f"{title} {chars}"


def upsert_chunks(chunks: list[dict]) -> int:
    """逐片写入向量（8.2：字段与 SCHEMA 一一对应）。

    Args:
        chunks: [{id, source_type(1|2 str), source_id(int), title(str),
                  chunk_index(int), embedding(float32 bytes)}]
    """
    pipe = binary_redis.pipeline(transaction=False)
    for c in chunks:
        key = f"{KEY_PREFIX}{c['id']}"
        pipe.hset(key, mapping={
            "source_type": str(c["source_type"]),
            "source_id": int(c["source_id"]),
            "title": title_index_value(c["title"]),
            "chunk_index": int(c["chunk_index"]),
            "embedding": c["embedding"],
        })
    pipe.execute()
    return len(chunks)


def knn_search(q_vec: bytes, k: int | None = None) -> list[tuple[int, float]]:
    """向量 KNN 检索：`*=>[KNN $K @embedding $q_vec AS knn_score]`（HNSW+COSINE）。

    实现约定：本环境 RediSearch 的 KNN 结果默认不按距离排序，须显式
    `AS knn_score` + `SORTBY knn_score`（升序 = 距离越小越相似）。

    Returns:
        [(chunk_id, cosine_distance)] 按距离升序（越小越相似）。
    """
    top_k = k or settings.RAG_KNN_K
    resp = binary_redis.execute_command(
        "FT.SEARCH", INDEX_NAME,
        "*=>[KNN $K @embedding $q_vec AS knn_score]",
        "DIALECT", "2",
        "LIMIT", 0, top_k,
        "SORTBY", "knn_score",
        "PARAMS", 4, "K", top_k, "q_vec", q_vec,
    )
    out: list[tuple[int, float]] = []
    for item in _parse_search_results(resp):
        cid = _chunk_id(item["id"])
        if cid is None:
            continue
        fields = item["fields"]
        score = (fields.get(b"knn_score") or fields.get("knn_score")
                 or fields.get(b"__embedding_score") or fields.get("__embedding_score"))
        try:
            dist = float(score) if score is not None else 1.0
        except (TypeError, ValueError):
            dist = 1.0
        out.append((cid, dist))
    return out


def bm25_search(keywords: list[str], k: int | None = None) -> list[tuple[int, float]]:
    """BM25 关键词检索（title TEXT，默认 BM25 评分，兜底专有名词召回）。

    Args:
        keywords: 查询词列表（中文词由调用方拆为单字，见 title_index_value 约定）。
    Returns:
        [(chunk_id, bm25_score)] 按评分降序。
    """
    if not keywords:
        return []
    top_k = k or settings.RAG_KNN_K
    terms = "|".join(f"({t})" for t in keywords if t)
    if not terms:
        return []
    resp = binary_redis.execute_command(
        "FT.SEARCH", INDEX_NAME,
        f"@title:({terms})",
        "DIALECT", "2",
        "LIMIT", 0, top_k,
    )
    out: list[tuple[int, float]] = []
    for item in _parse_search_results(resp):
        cid = _chunk_id(item["id"])
        if cid is None:
            continue
        out.append((cid, 1.0))  # 数组/dict 结构均不含 BM25 分值，按命中排序近似
    return out


def delete_chunk_keys(chunk_ids: list[int]) -> int:
    """删除 chunk 对应的 Redis key（旧版本清理 / delete 任务）。"""
    if not chunk_ids:
        return 0
    keys = [f"{KEY_PREFIX}{cid}" for cid in chunk_ids]
    return int(binary_redis.delete(*keys))


def scan_chunk_keys() -> list[str]:
    """扫描全部 rag:chunk:* key（全量重建前清理残留）。"""
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = binary_redis.scan(cursor=cursor, match=f"{KEY_PREFIX}*", count=500)
        keys.extend(k.decode() if isinstance(k, bytes) else k for k in batch)
        if cursor == 0:
            break
    return keys


def is_rebuilding() -> bool:
    """是否存在全量重建中标记（9.6 C-10）。"""
    try:
        return bool(binary_redis.exists(REBUILDING_KEY))
    except redis.RedisError:
        return False
