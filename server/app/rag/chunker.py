"""文档切分（T7-3，8.4 检索优化）。

- 按段落边界切分，chunk 300~500 字、相邻重叠 50~100 字；
- 超长段落（>500 字）按 450 字窗口硬切；
- 每片携带标题元数据（campus_rag_chunk.title 冗余存储，Embedding 输入
  为「标题 + 正文」，便于问题与标题语义对齐）。
"""

CHUNK_MAX = 500     # 单片目标上限（300~500 字）
CHUNK_WINDOW = 450  # 超长段落硬切窗口
CHUNK_OVERLAP = 80  # 相邻重叠（50~100 字）


def split_content(text: str, max_size: int = CHUNK_MAX,
                  overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按段落切分正文：段落合并至 ≤max_size，超长段落硬切，相邻重叠。

    Args:
        text: 已剥离 HTML 的纯文本。
    Returns:
        分片列表（每片 ≤ max_size + overlap 字符量级；首片无重叠）。
    """
    paras = [p.strip() for p in (text or "").split("\n") if p.strip()]
    segments: list[str] = []
    cur = ""
    for para in paras:
        if len(para) > max_size:
            if cur:
                segments.append(cur)
                cur = ""
            for i in range(0, len(para), CHUNK_WINDOW):
                segments.append(para[i:i + CHUNK_WINDOW])
            continue
        if not cur:
            cur = para
        elif len(cur) + len(para) + 1 <= max_size:
            cur = f"{cur}\n{para}"
        else:
            segments.append(cur)
            cur = para
    if cur:
        segments.append(cur)

    chunks: list[str] = []
    prev_tail = ""
    for seg in segments:
        chunk = f"{prev_tail}{seg}" if prev_tail else seg
        chunks.append(chunk)
        prev_tail = seg[-overlap:] if len(seg) > overlap else seg
    return chunks
