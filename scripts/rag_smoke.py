"""T7-1 冒烟验证（8.2/9.3）。

验证内容：
1. 同一 ARK_API_KEY 下生成（deepseek-chat）与 embedding（doubao-embedding）可调用；
2. 实测向量维度与 EMB_DIM 一致性校验（不一致 fail-fast）；
3. 写入 2 条测试 chunk 后 KNN 往返命中（DIM=2560、COSINE）；
4. BM25 标题词命中（中文单字召回，见 vector_store 实现约定）；
5. LLM 双通道兜底（v2.7/ADR-013）：主通道不可用时自动切 Agnes。

运行：`server/venv_wsl/bin/python scripts/rag_smoke.py`
（读取项目根 .env 的真实密钥；会真实调用方舟/Agnes，产生少量 token 费用）
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from app.core.config import settings  # noqa: E402
from app.services import vector_store  # noqa: E402
from app.services.embedding import embed_texts  # noqa: E402
from app.services.llm import agnes_enabled, chat_completion  # noqa: E402

SMOKE_CHUNK_IDS = [990001, 990002]  # 独立测试 id 段，结束清理


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" —— {detail}" if detail else ""))
    return ok


def main() -> int:
    all_ok = True
    print("== 1. 方舟生成 + embedding 冒烟 ==")
    try:
        content, usage = chat_completion([
            {"role": "system", "content": "你是校园助手，只回答测试问题。"},
            {"role": "user", "content": "回复两个字：正常"},
        ], max_tokens=64)
        ok = bool(content.strip())
        all_ok &= check("chat_completion 生成可用", ok, f"model={usage['model']} content={content.strip()[:20]!r}")
        if usage.get("model") != settings.LLM_MODEL:
            print(f"  [WARN] 主通道方舟不可用（ARK_API_KEY 可能仍是占位 ark-xxx），本次经兜底通道应答")
    except Exception as exc:  # noqa: BLE001
        all_ok &= check("chat_completion 生成可用", False, str(exc)[:200])
        content, usage = "", {}

    texts = ["智慧校园第一食堂提供多个风味窗口，营业时间为早上七点到晚上八点。",
             "新生宿舍A栋为四人间，配备空调与独立卫浴。"]
    try:
        vecs = embed_texts(texts)
        dim = len(vecs[0]) // 4
        all_ok &= check(f"embed_texts 维度 == EMB_DIM({settings.EMB_DIM})", dim == settings.EMB_DIM, f"实际 {dim}")
        all_ok &= check("embed_texts 批量条数", len(vecs) == 2)
    except Exception as exc:  # noqa: BLE001
        all_ok &= check("embed_texts", False, str(exc)[:200])
        print("  [SKIP] 方舟 embedding 不可用（ARK_API_KEY 未配置真实 key），KNN 往返用随机向量替代")
        import numpy as np
        rng = np.random.default_rng(42)
        vecs = [rng.standard_normal(settings.EMB_DIM).astype(np.float32).tobytes() for _ in texts]

    print("== 2. RediSearch 索引与 KNN/BM25 往返 ==")
    vector_store.ensure_index()
    chunks = [
        {"id": SMOKE_CHUNK_IDS[0], "source_type": "2", "source_id": 99001,
         "title": "第一食堂风味窗口", "chunk_index": 0, "embedding": vecs[0]},
        {"id": SMOKE_CHUNK_IDS[1], "source_type": "2", "source_id": 99002,
         "title": "新生宿舍分配指南", "chunk_index": 0, "embedding": vecs[1]},
    ]
    vector_store.upsert_chunks(chunks)

    import time
    time.sleep(0.5)  # 等待后台索引生效

    knn = vector_store.knn_search(vecs[0], k=2)
    top_id, top_dist = knn[0] if knn else (None, None)
    all_ok &= check("KNN 往返命中自身（COSINE 距离最小）", top_id == SMOKE_CHUNK_IDS[0],
                    f"top={top_id} dist={top_dist:.4f}" if top_id is not None else "无结果")
    all_ok &= check("KNN 距离 ∈ [0,2]（余弦距离）", top_dist is not None and -1e-6 <= top_dist <= 2.0,
                    f"dist={top_dist}")

    bm25 = vector_store.bm25_search(["食", "堂", "窗"], k=2)
    bm25_ids = [cid for cid, _s in bm25]
    all_ok &= check("BM25 标题词命中（食堂窗口）", SMOKE_CHUNK_IDS[0] in bm25_ids and SMOKE_CHUNK_IDS[1] not in bm25_ids,
                    f"hits={bm25_ids}")
    bm25_2 = vector_store.bm25_search(["宿", "舍"], k=2)
    all_ok &= check("BM25 标题词命中（宿舍）", SMOKE_CHUNK_IDS[1] in [cid for cid, _s in bm25_2])

    stats = vector_store.index_stats()
    all_ok &= check("index_stats().num_docs > 0", stats.get("num_docs", 0) > 0, str(stats))

    print("== 3. LLM 双通道兜底（ADR-013） ==")
    if agnes_enabled():
        import openai
        import app.services.llm as llm_mod
        orig = llm_mod._ark_client
        # 主通道指向不可达地址，触发同请求内切 Agnes
        llm_mod._ark_client = openai.OpenAI(base_url="http://127.0.0.1:9", api_key="x", timeout=2, max_retries=0)
        try:
            content2, usage2 = chat_completion([
                {"role": "user", "content": "回复两个字：兜底"}
            ], max_tokens=64)
            all_ok &= check("主通道失败自动切 Agnes", bool(content2.strip()) and usage2["model"] == settings.AGNES_MODEL,
                            f"model={usage2['model']} content={content2.strip()[:20]!r}")
        except Exception as exc:  # noqa: BLE001
            all_ok &= check("主通道失败自动切 Agnes", False, str(exc)[:200])
        finally:
            llm_mod._ark_client = orig
    else:
        print("  [SKIP] 未配置 AGNES_*，兜底通道视为未启用（v2.6 行为）")

    print("== 4. 清理测试数据 ==")
    vector_store.delete_chunk_keys(SMOKE_CHUNK_IDS)
    print(f"已删除测试 key: {[f'rag:chunk:{i}' for i in SMOKE_CHUNK_IDS]}")

    print("\n冒烟结果:", "全部通过 ✅" if all_ok else "存在失败项 ❌")
    return int(not all_ok)


if __name__ == "__main__":
    raise SystemExit(main())
