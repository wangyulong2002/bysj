"""知识库状态流转与 RAG 任务联动（T7-2，8.3 / P0-08 / P0-09）。

- 状态：0 草稿 ↔ 1 发布（发布即触发向量化，5.3.15）；
- content_hash 变更检测（P0-09）：保存时对**剥离 HTML 后的正文**（含标题，
  实现约定：标题同样参与检索元数据，变化即视为内容变化）取 SHA-256；
  与库中既有值一致且 status 不变 → **不写向量化任务**（杜绝无变化重复向量化）；
- 同事务任务写入（P0-08）：发布/编辑已发布 → upsert（operation=1）；
  下架/删除 → delete（operation=2）；任务与业务数据一起提交。
"""
import hashlib
import html
import re
from html.parser import HTMLParser

from django.utils import timezone

from .models import CampusRagTask


class _TextExtractor(HTMLParser):
    """剥离 HTML 标签取纯文本（富文本正文 hash 与切分共用）。"""

    _SKIP_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    @property
    def text(self) -> str:
        return "".join(self._chunks)


def strip_html(content: str | None) -> str:
    """剥离 HTML 标签/script/style → 纯文本（实体反转义，空白规整）。"""
    if not content:
        return ""
    parser = _TextExtractor()
    parser.feed(content)
    text = html.unescape(parser.text)
    return re.sub(r"[\s\u00a0]+", " ", text).strip()


def compute_content_hash(title: str, content: str | None) -> str:
    """SHA-256 hex 64 位（P0-09）：标题 + 剥离 HTML 后的正文。"""
    plain = strip_html(content)
    return hashlib.sha256(f"{title}\n{plain}".encode("utf-8")).hexdigest()


def _write_rag_task(knowledge, operation: str) -> None:
    """写入 RAG 任务（8.3：与业务变更同一事务）。source_type='2' 知识库。"""
    CampusRagTask.objects.create(
        operation=operation,
        source_type="2",
        source_id=knowledge.id,
        status="0",  # PENDING（T7-3 Worker 消费）
        retry_count=0,
        del_flag="0",
        create_time=timezone.now(),
        update_time=timezone.now(),
    )


def on_knowledge_saved(knowledge, old_status=None, old_hash=None,
                       is_create=False) -> None:
    """知识库保存后的状态流转联动（须在事务内调用，P0-08/P0-09）。

    Args:
        old_status: 保存前状态（None 时按创建处理）。
        old_hash: 保存前库中 content_hash（创建时 None）。
            调用方须在把新 hash 写入 instance.content_hash **之前**取库中旧值。

    - 发布（草稿 → 发布）或编辑已发布且 content_hash 变化 → upsert；
    - 编辑已发布但 hash 与 status 均未变 → 不写任务（P0-09 核心）；
    - 下架（发布 → 草稿）→ delete（移除向量）。
    """
    new_status = knowledge.status
    old_status = old_status if old_status is not None else ("0" if is_create else new_status)

    if new_status == "1":
        # 发布 / 编辑已发布：首次发布或 hash 变化才触发向量化（P0-09）
        hash_changed = knowledge.content_hash != old_hash
        if old_status != "1" or hash_changed:
            _write_rag_task(knowledge, "1")
    elif new_status == "0" and old_status == "1":
        _write_rag_task(knowledge, "2")  # 发布 → 草稿（下架）：移除向量


def on_knowledge_deleted(knowledge) -> None:
    """逻辑删除联动：已发布知识库文档移除向量。"""
    if knowledge.status == "1":
        _write_rag_task(knowledge, "2")
