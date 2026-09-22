"""管理端 JWT 认证增强（P1-1）：令牌可撤销。

审核报告 P1-1 指出的问题：
1. **access token 不可撤销**：管理端改密/停用账号后，已签发的 access token 依然
   有效 —— simplejwt 只验签 + 查 `is_active`，不做版本比对（对比 FastAPI 侧有
   `password_version` 机制，两边能力不对齐）。
2. **refresh token 不可吊销**：未启用 `token_blacklist` app，refresh 泄露即 7 天可控。
3. **refresh token 存 localStorage**：任意 XSS（后台富文本公告是天然注入面）即可
   完整窃取长期凭证。

本模块负责 (1)：把 `password_version` 写进 token 并在每次请求时比对；
(2)/(3) 由 `users/views.py`（Cookie 化登录/刷新/登出）+ settings 的
`ROTATE_REFRESH_TOKENS` / `BLACKLIST_AFTER_ROTATION` / `token_blacklist` 共同实现。

⚠️ 模块边界（重要）：本模块被 `settings.REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`
引用，会在 **DRF 自身初始化期间被导入**。因此这里**禁止**导入 `rest_framework.views`
/ `rest_framework.response` 等会回溯读取 DRF settings 的模块，否则形成导入环
（settings → api_settings → users.jwt → rest_framework.views → rest_framework.schemas
→ api_settings → users.jwt 未初始化完成 → ImportError）。
视图类一律放在 `users/views.py`。
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

#: refresh token 的 Cookie 名与作用域（限定到认证接口路径，避免随全站请求发送）
REFRESH_COOKIE_NAME = "bysj_admin_refresh"
REFRESH_COOKIE_PATH = "/admin/api/auth"


class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    """登录签发：把 `password_version` / `role_code` 写入 token（P1-1）。"""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["password_version"] = int(getattr(user, "password_version", 0) or 0)
        token["role_code"] = getattr(user, "role_code", "") or ""
        return token


class PasswordVersionJWTAuthentication(JWTAuthentication):
    """在 simplejwt 默认验签之上，增加 `password_version` 校验（P1-1）。

    与 FastAPI 侧 `app/core/deps.py` 的版本比对语义保持一致：
    用户改密 / 管理员重置密码 → `password_version` 自增 → 旧 access token 立即失效。
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_version = validated_token.get("password_version")
        if token_version is None or int(token_version) != int(
            getattr(user, "password_version", 0) or 0
        ):
            raise AuthenticationFailed(
                "登录状态已失效，请重新登录（密码已变更）",
                code="password_version_changed",
            )
        return user
