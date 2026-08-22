"""Django Admin 注册（T0-4/T2+）：业务模型 + 字典。

说明：19 张 campus_* 业务表的模型由 inspectdb 生成（apps/models.py），
DDL 权威为 Django migrations（P0-1/B-05）。此处注册基础字典便于后台维护；
业务表（班级/课程/教学班等）管理页在 T2-1~T2-3 落地。
"""
from django.contrib import admin

from .models import CampusDepartment, CampusTerm, SysDictData, SysDictType


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
    """院系管理（T2-1 前置注册，便于初始数据维护）。"""
    list_display = ("id", "dept_name", "dept_code", "create_time")
    search_fields = ("dept_name", "dept_code")


@admin.register(CampusTerm)
class CampusTermAdmin(admin.ModelAdmin):
    """学期管理（T2-1 前置注册）。"""
    list_display = ("id", "term_name", "start_date", "end_date", "total_weeks", "is_current")
    list_editable = ("is_current",)
