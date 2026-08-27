"""公告状态流转与 RAG 任务联动（T3-1，4.2 / 8.3）。

- 状态机：0 草稿 → 1 发布 → 2 下架（4.2，应用端只读，仅管理端发布）。
- 发布：记录 `publish_time`/`publisher_id`（T3-1 完成事项）。
- RAG 任务（8.3 触发点：status 变更时**同一事务**写入 `campus_rag_task`）：
  - 发布 / 编辑已发布公告 → upsert（operation=1，T7-3 Worker 消费）；
  - 下架 / 删除已发布公告 → delete（operation=2）。
- 缓存失效（P1-11，T3-3）：发布/下架/删除后 INCR `ann:version`。
"""
from django.utils import timezone

from .announcement_cache import bump_ann_version
from .models import CampusRagTask


def _write_rag_task(announcement, operation: str) -> None:
    """写入 RAG 任务（8.3：与业务变更同一事务）。

    operation: '1'=upsert（发布/编辑） '2'=delete（下架/删除）
    source_type: '1'=公告（'2'=知识库，T7-2 使用）
    """
    CampusRagTask.objects.create(
        operation=operation,
        source_type="1",
        source_id=announcement.id,
        status="0",  # 0 PENDING（T7-3 Worker 消费）
        retry_count=0,
        del_flag="0",
        create_time=timezone.now(),
        update_time=timezone.now(),
    )


def on_announcement_saved(announcement, old_status=None, operator_id=None,
                          is_create=False) -> None:
    """公告保存后的状态流转联动（须在事务内调用，8.3 同事务写 RAG 任务）。

    - 发布（草稿/下架 → 发布）：记录 publish_time/publisher，触发 upsert；
    - 编辑已发布公告：内容变化重新触发 upsert；
    - 下架（发布 → 下架）：触发 delete。
    """
    new_status = announcement.status
    old_status = old_status or ("0" if is_create else new_status)

    if new_status == "1":
        # 发布：记录发布时间/发布人（仅首次发布写入）
        if announcement.publish_time is None:
            announcement.publish_time = timezone.now()
        if announcement.publisher_id is None and operator_id is not None:
            announcement.publisher_id = operator_id
        _write_rag_task(announcement, "1")  # 发布/编辑已发布 → 向量化（upsert）
        bump_ann_version()
    elif new_status == "2":
        if old_status == "1":
            _write_rag_task(announcement, "2")  # 发布 → 下架：移除向量
        bump_ann_version()

    if new_status == "1" and (
        announcement.publish_time is not None or announcement.publisher_id is not None
    ):
        # publish_time/publisher_id 可能是新写入的，落库（update_fields 仅这些字段）
        announcement.save(update_fields=["publish_time", "publisher_id", "update_time"])


def on_announcement_deleted(announcement) -> None:
    """逻辑删除联动（5.1 删除走 del_flag）：已发布公告移除向量 + 缓存失效。"""
    if announcement.status == "1":
        _write_rag_task(announcement, "2")
    bump_ann_version()
