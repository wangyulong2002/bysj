"""管理端认证视图（P1-1）：refresh token 走 httpOnly Cookie + 可吊销。

审核报告 P1-1：
- refresh token 存 localStorage → 任意 XSS（后台富文本公告是天然注入面）即可完整
  窃取长期凭证；
- 未启用 token_blacklist → refresh 泄露即 7 天可控。

实现：
- 登录/刷新：refresh token 只写入 **httpOnly + SameSite=Lax** Cookie（生产带 Secure），
  响应体只返回 access token；
- 刷新：配合 settings 的 `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`，
  每次刷新即轮换并拉黑旧 refresh；
- 登出：把 refresh 加入黑名单并清除 Cookie。

注：本模块（而非 users/jwt.py）才允许导入 `rest_framework.views`/`response`，
避免 DRF 初始化期的导入环，详见 users/jwt.py 的模块说明。
"""
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.jwt import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    AdminTokenObtainPairSerializer,
)


def _set_refresh_cookie(response: Response, refresh: str | None) -> None:
    """把 refresh token 写入 httpOnly Cookie（P1-1）。"""
    if not refresh:
        return
    lifetime = settings.SIMPLE_JWT.get("REFRESH_TOKEN_LIFETIME")
    max_age = int(lifetime.total_seconds()) if lifetime else 7 * 24 * 3600
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh,
        max_age=max_age,
        httponly=True,            # 关键：JS 不可读，规避 XSS 窃取
        secure=not settings.DEBUG,
        samesite="Lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


class AdminTokenObtainPairView(TokenObtainPairView):
    """登录：access token 走响应体，refresh token 走 httpOnly Cookie（P1-1）。"""

    serializer_class = AdminTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        response = Response({"access": data.get("access")})
        _set_refresh_cookie(response, data.get("refresh"))
        return response


class AdminTokenRefreshView(TokenRefreshView):
    """刷新：优先从 httpOnly Cookie 读取 refresh（兼容请求体），并轮换（P1-1）。"""

    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        payload = dict(getattr(request, "data", {}) or {})
        if not payload.get("refresh"):
            payload["refresh"] = request.COOKIES.get(REFRESH_COOKIE_NAME, "")
        if not payload.get("refresh"):
            return Response(
                {"detail": "缺少 refresh token", "code": 4011},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = self.get_serializer(data=payload)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            # 无效/已拉黑的 refresh → 清 Cookie，提示前端重新登录
            resp = Response(
                {"detail": str(exc), "code": 4011},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(resp)
            return resp
        data = dict(serializer.validated_data)
        response = Response({"access": data.get("access")})
        # ROTATE_REFRESH_TOKENS=True 时会返回新的 refresh → 写回 Cookie
        _set_refresh_cookie(response, data.get("refresh"))
        return response


class AdminLogoutView(APIView):
    """登出：把 refresh token 加入黑名单并清除 Cookie（P1-1）。"""

    authentication_classes: list = []

    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE_NAME, "") or (
            dict(getattr(request, "data", {}) or {}).get("refresh", "")
        )
        if raw:
            try:
                RefreshToken(raw).blacklist()   # 依赖 token_blacklist app（P1-1）
            except TokenError:
                pass                            # 已过期/已拉黑：幂等处理
        response = Response({"code": 0, "message": "已退出登录", "data": None})
        _clear_refresh_cookie(response)
        return response
