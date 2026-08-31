"""混合检索与 RRF 融合（T7-1，8.4）。

- 向量 KNN Top-K（HNSW+COSINE）+ BM25 关键词 Top-K（兜底"XX 宿舍/教授姓名"
  类专有名词），RRF 融合 `score = Σ 1/(60 + rank_i)`（融合常数 60）；
- 同一 chunk 两路均命中时得分相加，合并去重后按分数取 Top-`RAG_TOP_N`；
- LangChain 集成：自定义 `HybridRetriever`（BaseRetriever 子类）包装
  KNN/BM25+RRF，返回 `Document(page_content=content, metadata={source_type,
  source_id, title, chunk_index, url, score})`；T7-4 问答链路复用
  `hybrid_search()`（同一核心，便于取 best_sim 做 L1 相关度闸门）。
- chunk 正文存 MySQL `campus_rag_chunk`（Redis 只存向量+元数据，5.3.16），
  检索命中后回表取 content/url。
"""
import logging
import re
from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.services import vector_store

logger = logging.getLogger("campus.rag.retriever")

RRF_CONSTANT = 60  # 8.4：融合常数 60

# 中文虚词/疑问助词等停用字：不参与 BM25 单字召回
_STOP_CHARS = set("的了吗呢吧啊呀哦么是我不他她它有没有和与及或在去去怎么如何请问请告知一下这个那个什么哪些多少几")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass
class Hit:
    """一路检索命中（chunk_id + 路内排名，rank 从 1 起）。"""

    chunk_id: int
    rank: int


@dataclass
class RetrievedChunk:
    """融合后的检索结果（含 MySQL 元数据）。"""

    chunk_id: int
    source_type: str      # '1' 公告 / '2' 知识库
    source_id: int
    chunk_index: int
    title: str
    content: str
    url: str
    score: float          # RRF 融合分
    sim: float | None     # 余弦相似度（仅 KNN 命中的 chunk 有，1 - cosine_distance）


def extract_keywords(question: str) -> list[str]:
    """从问题提取 BM25 关键词：中文单字（去停用字）+ 英数词（小写）。

    title 索引值含"单字空格序列"（见 vector_store.title_index_value），
    中文按单字 OR 召回，由 BM25 评分排序。
    """
    cjk = [c for c in question if _CJK_RE.match(c) and c not in _STOP_CHARS]
    words = [w.lower() for w in _ASCII_WORD_RE.findall(question)]
    seen: list[str] = []
    for t in cjk + words:
        if t not in seen:
            seen.append(t)
    return seen[:24]  # 控制查询规模（注入防护第 5 层：限制上下文规模）


def rrf_fuse(knn_hits: list[tuple[int, float]],
             bm25_hits: list[tuple[int, float]],
             top_n: int | None = None) -> list[tuple[int, float, float | None]]:
    """RRF 融合两路召回：score = Σ 1/(60 + rank_i)，同 chunk 两路命中得分相加。

    Returns:
        [(chunk_id, rrf_score, sim)] 按 rrf_score 降序，截取 Top-N；
        sim = KNN 路的余弦相似度（该 chunk 未被 KNN 命中时为 None）。
    """
    n = top_n or settings.RAG_TOP_N
    scores: dict[int, float] = {}
    sims: dict[int, float | None] = {}
    for rank, (cid, dist) in enumerate(knn_hits, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_CONSTANT + rank)
        sims[cid] = 1.0 - dist  # cosine_distance → 相似度
    for rank, (cid, _score) in enumerate(bm25_hits, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_CONSTANT + rank)
        sims.setdefault(cid, None)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(cid, score, sims.get(cid)) for cid, score in ranked]


def fetch_chunks_meta(chunk_ids: list[int]) -> dict[int, dict]:
    """按 chunk id 回表 MySQL 取 content/title/url 等元数据（5.3.16）。"""
    if not chunk_ids:
        return {}
    id_list = ",".join(str(int(c)) for c in chunk_ids)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source_type, source_id, chunk_index, content, title, url "
                f"FROM campus_rag_chunk WHERE id IN ({id_list}) AND status = '1' AND del_flag = '0'"
            )
        ).fetchall()
    return {
        int(r[0]): {
            "source_type": r[1],
            "source_id": int(r[2]),
            "chunk_index": int(r[3]),
            "content": r[4] or "",
            "title": r[5] or "",
            "url": r[6] or "",
        }
        for r in rows
    }


def hybrid_search(question: str, q_vec: bytes,
                  knn_k: int | None = None,
                  top_n: int | None = None) -> tuple[list[RetrievedChunk], float, int]:
    """混合检索 + RRF（8.4）：KNN Top-K ∪ BM25 Top-K → 融合取 Top-N。

    Args:
        question: 用户问题（BM25 关键词来源）。
        q_vec: 问题向量（float32 bytes，调用方经 embedding.embed_query 生成）。

    Returns:
        (chunks, best_sim, hit_count)：
        - chunks：融合 Top-N（含 MySQL 元数据）；
        - best_sim = 1 - min(cosine_distance)（KNN 路最高相似度，L1 闸门判据；
          KNN 无命中时为 0.0）；
        - hit_count：融合后命中片段数（≤ Top-N）。
    """
    knn_hits = vector_store.knn_search(q_vec, k=knn_k or settings.RAG_KNN_K)
    bm25_hits = vector_store.bm25_search(extract_keywords(question), k=settings.RAG_KNN_K)
    best_sim = max((1.0 - dist for _cid, dist in knn_hits), default=0.0)

    fused = rrf_fuse(knn_hits, bm25_hits, top_n=top_n)
    meta = fetch_chunks_meta([cid for cid, _s, _sim in fused])
    chunks: list[RetrievedChunk] = []
    for cid, score, sim in fused:
        m = meta.get(cid)
        if m is None:  # MySQL 无对应已向量化 chunk（脏数据），跳过
            continue
        chunks.append(RetrievedChunk(
            chunk_id=cid, score=round(score, 6), sim=sim, **m,
        ))
    return chunks, best_sim, len(chunks)


# ===== LangChain Retriever（8.2：自定义 Retriever，不用内置 VectorStore 抽象）=====

try:  # langchain 为 RAG 编排依赖（8.2），缺失时核心检索仍可用
    from langchain_core.callbacks import CallbackManagerForRetrieverRun  # pyright: ignore[reportMissingImports]
    from langchain_core.documents import Document  # pyright: ignore[reportMissingImports]
    from langchain_core.retrievers import BaseRetriever  # pyright: ignore[reportMissingImports]

    class HybridRetriever(BaseRetriever):
        """KNN+BM25+RRF 混合检索器（LangChain BaseRetriever，8.2/8.4）。

        `invoke(question)` / LangChain 链路统一入口；向量生成经 embed_fn
        注入（默认 embedding.embed_query，测试可替换）。
        """

        knn_k: int = settings.RAG_KNN_K
        top_n: int = settings.RAG_TOP_N

        def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
        ) -> list[Document]:
            from app.services.embedding import embed_query

            q_vec = embed_query(query)
            chunks, _best, _hit = hybrid_search(
                query, q_vec, knn_k=self.knn_k, top_n=self.top_n
            )
            return [
                Document(
                    page_content=c.content,
                    metadata={
                        "chunk_id": c.chunk_id,
                        "source_type": c.source_type,
                        "source_id": c.source_id,
                        "title": c.title,
                        "chunk_index": c.chunk_index,
                        "url": c.url,
                        "score": c.score,
                    },
                )
                for c in chunks
            ]

except ImportError:  # pragma: no cover —— langchain 未安装时降级
    HybridRetriever = None  # type: ignore[assignment, misc]
    logger.warning("langchain 未安装，HybridRetriever 不可用（核心检索不受影响）")
