"""LLM 客户端封装（T7-1，8.2/9.3；v2.7 双通道兜底 ADR-013）。

- 主通道：火山方舟 deepseek-chat（OpenAI 兼容接口，生成唯一权威选型）；
- 兜底通道：Agnes（agnes-2.5-flash，OpenAI 兼容）——主通道失败（连接异常/
  超时/429/5xx）时**同一请求内**自动切换重试一次，双通道均失败才抛错走 5001；
- **仅生成（chat）兜底，Embedding 不兜底**（2560 维向量与方舟 doubao-embedding
  绑定，属向量库 DDL 硬约束，换模型将污染索引）；
- `AGNES_*` 任一缺省视为未启用兜底（行为与 v2.6 一致）；
- 必须显式限制输出 max_tokens（8.4 注入防护第 5 层）并设置请求超时（8.6 P95≤4s）。

LangChain 集成：`get_chat_model()` 返回 `langchain_openai.ChatOpenAI`（主通道）
作为 LangChain 生成端入口（供自定义链/后续扩展使用）；运行时问答链路
（T7-4）走 `chat_completion()` 以获得双通道兜底能力——ChatOpenAI 无法表达
"同请求内主→备切换"，此为实现约定（偏差已向设计报告 8.2 记录）。
"""
import logging
from typing import Any

import openai  # pyright: ignore[reportMissingImports]

from app.core.config import settings

logger = logging.getLogger("campus.rag.llm")

_ark_client: openai.OpenAI | None = None
_agnes_client: openai.OpenAI | None = None


class LLMError(Exception):
    """LLM 调用失败（双通道均失败），由上层转 5001（降级返回检索资料）。"""


def get_ark_client() -> openai.OpenAI:
    """方舟主通道客户端（模块级单例，base_url/api_key 来自 9.3）。"""
    global _ark_client
    if _ark_client is None:
        _ark_client = openai.OpenAI(
            base_url=settings.ARK_BASE_URL,
            api_key=settings.ARK_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,  # 重试交给兜底通道，不在主通道内消耗时间
        )
    return _ark_client


def agnes_enabled() -> bool:
    """兜底通道是否已配置（AGNES_BASE_URL/API_KEY 任一缺省视为未启用）。"""
    return bool(settings.AGNES_BASE_URL and settings.AGNES_API_KEY)


def get_agnes_client() -> openai.OpenAI:
    """Agnes 兜底通道客户端（模块级单例，仅 chat 兜底用）。"""
    global _agnes_client
    if _agnes_client is None:
        _agnes_client = openai.OpenAI(
            base_url=settings.AGNES_BASE_URL,
            api_key=settings.AGNES_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _agnes_client


def _chat(client: openai.OpenAI, model: str, messages: list[dict],
          max_tokens: int) -> tuple[str, dict[str, Any]]:
    """单通道调用：返回 (content, usage)。任何异常向上抛（由调用方切换通道）。"""
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )
    content = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
        "model": model,
    }
    return content, usage


def chat_completion(messages: list[dict],
                    max_tokens: int | None = None) -> tuple[str, dict[str, Any]]:
    """生成调用（主通道方舟 → 失败自动切 Agnes 兜底 → 双失败抛 LLMError）。

    Args:
        messages: OpenAI 格式消息（系统提示置最前，8.4）。
        max_tokens: 输出 token 上限（默认 LLM_MAX_TOKENS，注入防护第 5 层）。

    Returns:
        (content, usage) —— usage 含 prompt_tokens/completion_tokens/model
        （model 为实际应答通道，供 campus_rag_log.model 落库）。
    """
    limit = max_tokens or settings.LLM_MAX_TOKENS
    try:
        return _chat(get_ark_client(), settings.LLM_MODEL, messages, limit)
    except Exception as exc:  # noqa: BLE001 —— 连接异常/超时/429/5xx 一律切兜底
        if not agnes_enabled():
            raise LLMError(f"LLM 主通道失败且未配置兜底: {exc}") from exc
        logger.warning("LLM 主通道(方舟 %s)失败，切换 Agnes 兜底: %s",
                       settings.LLM_MODEL, exc)
    # 兜底通道重试一次（仅 chat）
    try:
        return _chat(get_agnes_client(), settings.AGNES_MODEL, messages, limit)
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"LLM 双通道均失败（方舟+Agnes）: {exc}") from exc


def get_chat_model():
    """LangChain 生成端入口（8.2）：主通道 ChatOpenAI。

    供 LangChain 链路/自定义 Retriever 组合使用；T7-4 问答链路因需要
    双通道兜底走 `chat_completion()`，见模块 docstring。
    """
    from langchain_openai import ChatOpenAI  # pyright: ignore[reportMissingImports]

    return ChatOpenAI(
        base_url=settings.ARK_BASE_URL,
        api_key=settings.ARK_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )
