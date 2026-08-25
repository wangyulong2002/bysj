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

from .models import (
    CampusClass,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
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
