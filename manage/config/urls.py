"""URL 配置（T0-2 / 方案 2 管理前端自建）。

- /admin/          自建管理前端入口（SPA：admin-web 构建产物，AdminWebView）
- /admin/api/**    DRF 管理接口（simplejwt JWT，P1-9）
- /django-admin/   Django 内置 Admin（保留作后备，不再占 /admin 路径）
"""
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views import View
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

admin.site.site_header = "智慧校园 管理后台"
admin.site.site_title = "智慧校园 管理后台"
admin.site.index_title = "后台管理"


class AdminWebView(View):
    """自建管理前端（Vue3 admin-web）SPA 入口。

    /admin/ 与 /admin/<path> 均返回构建产物 index.html；
    静态资源（/static/assets/*）由 django.contrib.staticfiles 提供（runserver 自动）。
    未构建时返回引导提示（先 cd admin-web && npm run build）。
    """

    def get(self, request, *args, **kwargs):
        index_file = Path(settings.ADMIN_WEB_DIST) / "index.html"
        try:
            content = index_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return HttpResponse(
                "管理前端未构建，请先执行: cd bysj/admin-web && npm run build，然后重启 Django。",
                status=404,
            )
        return HttpResponse(content, content_type="text/html; charset=utf-8")


urlpatterns = [
    # /admin/api/**（P1-9：JWT 认证）
    path("admin/api/auth/login", TokenObtainPairView.as_view(), name="admin_api_token_obtain"),
    path("admin/api/auth/refresh", TokenRefreshView.as_view(), name="admin_api_token_refresh"),
    # 业务管理接口（院系/班级/学生/教师/课程/学期/教学班/排课/公告）
    path("admin/api/", include("apps.urls")),
    # 自建管理前端 SPA（方案 2）：/admin/ 与子路径均返回 index.html
    path("admin/", AdminWebView.as_view(), name="admin_web"),
    path("admin/<path:path>", AdminWebView.as_view(), name="admin_web_spa"),
    # Django 内置 Admin 保留在 /django-admin/（不占 /admin）
    path("django-admin/", admin.site.urls),
]
