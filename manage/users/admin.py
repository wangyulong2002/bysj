"""Django Admin 注册（T0-2）：sys_user 管理。"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """CustomUser 管理（映射 sys_user）。

    - 管理端认证用 Session+CSRF（P1-9），Admin 登录基于本模型。
    - 展示扩展字段（student_no/teacher_no/role_code/password_version 等）。
    """

    list_display = ("id", "username", "nick_name", "role_code", "status",
                    "student_no", "teacher_no", "wechat_openid", "create_time")
    list_filter = ("role_code", "status", "del_flag")
    search_fields = ("username", "nick_name", "student_no", "teacher_no", "phone")
    ordering = ("id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("基本信息", {"fields": ("nick_name", "gender", "phone", "email", "avatar")}),
        ("扩展字段（5.2）", {"fields": ("student_no", "teacher_no", "wechat_openid",
                                      "role_code", "password_version")}),
        ("状态", {"fields": ("status", "del_flag", "is_superuser", "groups", "user_permissions")}),
        ("审计", {"fields": ("create_by", "update_by", "create_time", "update_time")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "password1", "password2")}),
    )

    readonly_fields = ("create_time", "update_time")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(del_flag="0")
