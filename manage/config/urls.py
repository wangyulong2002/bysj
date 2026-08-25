"""URL 配置（T0-2）。

- Django Admin：Session+CSRF（P1-9）
- /admin/api/auth/*：DRF JWT 登录/刷新（simplejwt）
- /admin/api/**：后续业务 App 管理接口（T2+ 挂载）
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

admin.site.site_header = "智慧校园 管理后台"
admin.site.site_title = "智慧校园 管理后台"
admin.site.index_title = "后台管理"

urlpatterns = [
    # /admin/api/**（P1-9：JWT 认证；Django Admin 仍用 Session+CSRF）
    # 注意：必须放在 admin.site.urls 之前，否则被 Admin 的 catch_all_view 吞掉
    path("admin/api/auth/login", TokenObtainPairView.as_view(), name="admin_api_token_obtain"),
    path("admin/api/auth/refresh", TokenRefreshView.as_view(), name="admin_api_token_refresh"),
    # 业务管理接口（T2-1/T2-2/T2-3：院系/班级/课程/学期/教学班/排课）
    path("admin/api/", include("apps.urls")),
    path("admin/", admin.site.urls),
]
