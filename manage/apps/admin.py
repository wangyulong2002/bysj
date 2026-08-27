"""Django Admin 注册（T0-4/T2+）：业务模型 + 字典。

说明：19 张 campus_* 业务表的模型由 inspectdb 生成（apps/models.py），
DDL 权威为 Django migrations（P0-1/B-05）。
T2-1~T2-3：注册院系/班级/课程/学期/教学班/排课管理；
- 学期 is_current 切换：save_model 事务内保证任意时刻仅一个（5.1/P1-04）；
- 排课保存时执行班级/教师冲突校验（4.1 P0-06，与 DRF 接口共用校验逻辑）。
"""
from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from .announcement_flow import on_announcement_saved
from .models import (
    CampusAnnouncement,
    CampusClass,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
    CampusLeave,
    CampusScore,
    CampusScoreAudit,
    CampusStudent,
    CampusTeacher,
    CampusTerm,
    SysDictData,
    SysDictType,
)
from .views import ScheduleConflictError, _check_schedule_conflict


@admin.register(SysDictType)
class SysDictTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "dict_name", "dict_type", "status", "create_time")
    search_fields = ("dict_name", "dict_type")
    list_filter = ("status",)


@admin.register(SysDictData)
class SysDictDataAdmin(admin.ModelAdmin):
    list_display = ("id", "dict_type", "dict_sort", "dict_label", "dict_value",
                    "is_default", "status")
    search_fields = ("dict_label", "dict_value", "dict_type")
    list_filter = ("dict_type", "status")
    list_editable = ("dict_sort",)


@admin.register(CampusDepartment)
class CampusDepartmentAdmin(admin.ModelAdmin):
    """院系管理（T2-1）。"""
    list_display = ("id", "dept_name", "dept_code", "create_time")
    search_fields = ("dept_name", "dept_code")


@admin.register(CampusClass)
class CampusClassAdmin(admin.ModelAdmin):
    """班级管理（T2-1）：指定辅导员/年级/专业/院系（B-12：v1 无班主任）。"""
    list_display = ("id", "class_name", "class_code", "grade", "major",
                    "department", "counselor")
    list_filter = ("grade", "department")
    search_fields = ("class_name", "class_code", "major")
    autocomplete_fields = ("department", "counselor")


@admin.register(CampusCourse)
class CampusCourseAdmin(admin.ModelAdmin):
    """课程管理（T2-1）。"""
    list_display = ("id", "course_name", "course_code", "credit", "hours", "department")
    list_filter = ("department",)
    search_fields = ("course_name", "course_code")
    autocomplete_fields = ("department",)


@admin.register(CampusTerm)
class CampusTermAdmin(admin.ModelAdmin):
    """学期管理（T2-1）：is_current 切换（5.1：任意时刻仅一个）。"""
    list_display = ("id", "term_name", "start_date", "end_date", "total_weeks", "is_current")
    list_editable = ("is_current",)
    search_fields = ("term_name",)

    def save_model(self, request, obj, form, change):
        """学期保存：事务内保证任意时刻仅一个 is_current=1（5.1/P1-04）。"""
        with transaction.atomic():
            if obj.is_current == "1":
                CampusTerm.objects.filter(is_current="1").exclude(pk=obj.pk).update(is_current="0")
            obj.update_by = request.user.id if request.user.is_authenticated else None
            obj.save()


@admin.register(CampusCourseOffering)
class CampusCourseOfferingAdmin(admin.ModelAdmin):
    """教学班管理（T2-2）：课程+学期+班级+教师（唯一约束 (term, class, course)）。"""
    list_display = ("id", "course", "term", "class_field", "teacher")
    list_filter = ("term",)
    search_fields = ("course__course_name", "course__course_code",
                     "class_field__class_name", "teacher__nick_name")
    autocomplete_fields = ("course", "term", "class_field", "teacher")


@admin.register(CampusCourseSchedule)
class CampusCourseScheduleAdmin(admin.ModelAdmin):
    """排课管理（T2-3）：保存时校验班级/教师冲突（4.1 P0-06）。"""
    list_display = ("id", "offering", "day_of_week", "period_start", "period_end",
                    "week_start", "week_end", "location")
    list_filter = ("day_of_week",)
    search_fields = ("offering__course__course_name",
                     "offering__class_field__class_name",
                     "offering__teacher__nick_name")
    autocomplete_fields = ("offering",)

    def _run_conflict_check(self, obj) -> None:
        """Admin 保存前执行排课冲突校验（复用 DRF 接口校验逻辑，4.1 P0-06）。"""
        offering = CampusCourseOffering.objects.select_related("class_field").get(pk=obj.offering_id)
        _check_schedule_conflict(
            term_id=offering.term_id,
            class_id=offering.class_field_id,
            teacher_id=offering.teacher_id,
            day_of_week=obj.day_of_week,
            period_start=obj.period_start,
            period_end=obj.period_end,
            exclude_id=obj.pk,
        )

    def save_model(self, request, obj, form, change):
        """排课保存：冲突校验 + 写入同一事务，冲突转 Django ValidationError 提示。"""
        try:
            with transaction.atomic():
                self._run_conflict_check(obj)
                obj.update_by = request.user.id if request.user.is_authenticated else None
                obj.save()
        except ScheduleConflictError as exc:
            # Admin 页面友好提示（DRF 接口由 api_exception_handler 转 4091）
            raise DjangoValidationError(str(exc))
        except IntegrityError:
            raise


@admin.register(CampusAnnouncement)
class CampusAnnouncementAdmin(admin.ModelAdmin):
    """公告管理（T3-1，唯一发布方）：类型/置顶/状态流转（草稿→发布→下架，4.2）。"""
    list_display = ("id", "title", "ann_type_label", "target_label", "is_top",
                    "status_label", "publisher", "publish_time", "create_time")
    list_filter = ("ann_type", "status", "is_top")
    search_fields = ("title", "content")
    list_editable = ("is_top",)
    autocomplete_fields = ("target_class", "target_department", "publisher")
    date_hierarchy = "publish_time"

    @admin.display(description="类型")
    def ann_type_label(self, obj) -> str:
        """公告类型展示（1校园 2院系 3班级）。"""
        return {"1": "校园", "2": "院系", "3": "班级"}.get(obj.ann_type, obj.ann_type)

    @admin.display(description="状态")
    def status_label(self, obj) -> str:
        """状态展示（0草稿 1发布 2下架）。"""
        return {"0": "草稿", "1": "发布", "2": "下架"}.get(obj.status, obj.status)

    @admin.display(description="目标")
    def target_label(self, obj) -> str:
        """单目标展示（班级公告→班级名，院系公告→院系名）。"""
        if obj.ann_type == "3":
            return obj.target_class.class_name if obj.target_class else "-"
        if obj.ann_type == "2":
            return obj.target_department.dept_name if obj.target_department else "-"
        return "-"

    def save_model(self, request, obj, form, change):
        """公告保存：状态流转联动（发布记录时间、写 RAG 任务、缓存失效，8.3/T3-3）。

        与 DRF 接口共用 on_announcement_saved（P0-2：同一状态机唯一实现）。
        """
        old_status = None
        if change:
            old_status = CampusAnnouncement.objects.filter(pk=obj.pk).values_list(
                "status", flat=True
            ).first()
        uid = request.user.id if request.user.is_authenticated else None
        with transaction.atomic():
            obj.update_by = uid
            if obj.publisher_id is None:
                obj.publisher_id = uid
            obj.save()
            on_announcement_saved(obj, old_status=old_status, operator_id=uid, is_create=not change)


@admin.register(CampusScore)
class CampusScoreAdmin(admin.ModelAdmin):
    """成绩管理（T4-1）：管理前端为主入口；Admin 只读展示（发布/撤销走 DRF 接口）。"""
    list_display = ("id", "student", "offering", "usual_score", "exam_score",
                    "total_score", "is_published", "update_time")
    list_filter = ("is_published", "offering__term")
    search_fields = ("student__student_no", "student__user__nick_name",
                     "offering__course__course_name")
    autocomplete_fields = ("student", "offering")
    has_add_permission = lambda self, request: False  # noqa: E731
    has_delete_permission = lambda self, request, obj=None: False  # noqa: E731


@admin.register(CampusScoreAudit)
class CampusScoreAuditAdmin(admin.ModelAdmin):
    """成绩审计（T4-1）：只读追溯（B-11 明细快照）。"""
    list_display = ("id", "student", "offering", "old_score", "new_score",
                    "operation", "operator_id", "operation_time")
    list_filter = ("operation",)
    search_fields = ("student__student_no",)
    has_add_permission = lambda self, request: False  # noqa: E731
    has_change_permission = lambda self, request, obj=None: False  # noqa: E731
    has_delete_permission = lambda self, request, obj=None: False  # noqa: E731


@admin.register(CampusLeave)
class CampusLeaveAdmin(admin.ModelAdmin):
    """请假管理（T5-6）：管理前端为主入口；状态变更必须走干预接口（P1-15）。"""
    list_display = ("id", "student", "leave_type", "reason", "start_time", "end_time",
                    "status", "approve_comment", "create_time")
    list_filter = ("status", "leave_type")
    search_fields = ("student__student_no", "student__user__nick_name", "reason")
    autocomplete_fields = ("student",)
    has_add_permission = lambda self, request: False  # noqa: E731
    has_delete_permission = lambda self, request, obj=None: False  # noqa: E731

    def has_change_permission(self, request, obj=None):
        """禁止直接改 status（P1-15：只能走干预接口），其余字段只读。"""
        return False


@admin.register(CampusStudent)
class CampusStudentAdmin(admin.ModelAdmin):
    """学生档案管理（T2-8）：档案与 sys_user 账号联动由 DRF 接口承担（方案 B）。

    管理前端（admin-web）为主入口；Admin 仅提供只读查看，避免双写账号。
    """

    list_display = ("id", "student_no", "user", "class_field", "enroll_year", "del_flag")
    list_filter = ("del_flag",)
    search_fields = ("student_no", "user__nick_name", "class_field__class_name")
    autocomplete_fields = ("class_field",)
    readonly_fields = ("user",)
    has_add_permission = lambda self, request: False  # noqa: E731 — 账号联动由 DRF 接口负责

    def has_delete_permission(self, request, obj=None):
        """删除走 DRF 接口（需联动停用账号），Admin 不提供。"""
        return False


@admin.register(CampusTeacher)
class CampusTeacherAdmin(admin.ModelAdmin):
    """教师档案管理（T2-9）：联动逻辑同学生（方案 B）。"""

    list_display = ("id", "teacher_no", "user", "title", "department", "del_flag")
    list_filter = ("del_flag",)
    search_fields = ("teacher_no", "user__nick_name", "department__dept_name")
    autocomplete_fields = ("department",)
    readonly_fields = ("user",)
    has_add_permission = lambda self, request: False  # noqa: E731 — 账号联动由 DRF 接口负责

    def has_delete_permission(self, request, obj=None):
        """删除走 DRF 接口（需联动停用账号），Admin 不提供。"""
        return False
