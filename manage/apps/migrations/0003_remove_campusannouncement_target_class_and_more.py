# v2.5/v2.6 结构与数据迁移（2026-08-29）
#
# - v2.5/ADR-011：移除班级公告类型——
#   ① 数据迁移：存量 ann_type=3（班级公告）改为院系公告（target_department 取班级所属院系，
#      班级无院系 → 下架 status=2），在 RemoveField 之前执行（仍需 target_class_id 定位院系）；
#   ② RemoveField target_class（MySQL 会自动移除包含该列的 idx_announcement_type 索引）；
#   ③ 索引迁移：重建 idx_announcement_type(ann_type, target_department_id)（设计 5.5，P1-03）。
# - v2.6/ADR-012/8.4.1：CampusRagLog 增 refuse_reason（拒答原因）+ idx_rag_log_refuse 索引。
#
# 注：这两个索引由 init_all.sql/SQL 层维护（Django 模型未声明 Meta.indexes），
#     因此用 introspection 检测 + 条件建索引，保证幂等（对 init_all.sql 新建库同样安全）。

from django.db import migrations, models


def migrate_class_announcements(apps, schema_editor):
    """存量班级公告 → 院系公告（ADR-011）。

    - ann_type='3'：target_department_id ← 班级所属院系，ann_type → '2'；
    - 班级缺失或无院系 → 下架（status='2'），不丢数据。
    """
    Announcement = apps.get_model('apps', 'CampusAnnouncement')
    Class = apps.get_model('apps', 'CampusClass')
    for ann in Announcement.objects.filter(ann_type='3').iterator():
        cls = Class.objects.filter(pk=ann.target_class_id).first()
        dept_id = cls.department_id if cls else None
        if dept_id:
            ann.ann_type = '2'
            ann.target_department_id = dept_id
            ann.save(update_fields=['ann_type', 'target_department_id'])
        else:
            # 无法归类的班级公告：下架（应用端仅展示已发布）
            ann.status = '2'
            ann.save(update_fields=['status'])


def noop(apps, schema_editor):
    """数据迁移不可逆（旧类型语义已移除）。"""


def _index_columns(schema_editor, table: str, index_name: str):
    """返回索引的列集合；索引不存在返回 None。"""
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table)
    con = constraints.get(index_name)
    return set(con["columns"]) if con else None


def _ensure_index(apps, schema_editor, table: str, index_name: str, columns: str) -> None:
    """幂等建索引：不存在或列集不符（如删列后被 MySQL 缩减为单列）时重建。

    columns 形如 "(`a`, `b`)"（含外层括号，直接用于 CREATE INDEX）。
    """
    expected = {c.strip("` ") for c in columns.strip("()").split(",")}
    existing = _index_columns(schema_editor, table, index_name)
    if existing == expected:
        return
    with schema_editor.connection.cursor() as cursor:
        if existing is not None:
            cursor.execute(f"ALTER TABLE `{table}` DROP INDEX `{index_name}`")
        cursor.execute(f"CREATE INDEX {index_name} ON `{table}` {columns}")


def create_announcement_index(apps, schema_editor):
    _ensure_index(
        apps, schema_editor,
        'campus_announcement', 'idx_announcement_type',
        '(`ann_type`, `target_department_id`)',
    )


def create_rag_log_refuse_index(apps, schema_editor):
    _ensure_index(
        apps, schema_editor,
        'campus_rag_log', 'idx_rag_log_refuse',
        '(`refuse_reason`, `create_time`)',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0002_sysdictdata_sysdicttype'),
    ]

    operations = [
        # ① 存量班级公告数据处置（必须在删列之前，需 target_class_id 定位院系）
        migrations.RunPython(migrate_class_announcements, noop),
        # ② 公告表：删除班级目标字段（连带自动移除旧 idx_announcement_type）
        migrations.RemoveField(
            model_name='campusannouncement',
            name='target_class',
        ),
        migrations.AlterField(
            model_name='campusannouncement',
            name='ann_type',
            field=models.CharField(db_comment='1校园 2院系（v2.5/ADR-011：移除 3班级）', max_length=1),
        ),
        # ③ 索引重建（5.5）
        migrations.RunPython(create_announcement_index, migrations.RunPython.noop),
        # ④ 问答日志表：refuse_reason 拒答原因（v2.6/8.4.1）+ 观测索引
        migrations.AddField(
            model_name='campusraglog',
            name='refuse_reason',
            field=models.CharField(blank=True, db_comment='拒答原因（v2.6/ADR-012 8.4.1：no_context 无相关资料 / out_of_scope 越界领域 / unsafe 敏感内容；未拒答为 NULL）', max_length=20, null=True),
        ),
        migrations.RunPython(create_rag_log_refuse_index, migrations.RunPython.noop),
    ]
