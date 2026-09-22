"""
Django settings for config project.

管理端（T0-2）：Django 5.2 LTS + DRF，共享 campus 库。
设计基线：《智慧校园信息管理系统 设计报告》v2.2
- DDL 权威：Django migrations（P0-1/B-05），sql/ 仅导出产物
- 时区：Asia/Shanghai、USE_TZ=False（B-10）
- 认证：管理端统一自建前端（admin-web）+ /admin/api/** JWT（P1-9）；内置 Django Admin 已移除
- 用户：CustomUser(AbstractBaseUser, PermissionsMixin)，db_table='sys_user'（P1-8）
"""
import os
from pathlib import Path
from urllib.parse import urlparse

import pymysql  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

pymysql.install_as_MySQLdb()  # Django MySQL 后端兼容（Python 3.14 无 mysqlclient 预编译包）

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # bysj/

# 统一从项目根 .env 读取（与 FastAPI 共用同一份配置，见设计 9.3）
# P1-18：改用 python-dotenv 解析。原手写解析器不处理引号 / export / 转义 / 多行值，
# 与 FastAPI 侧 pydantic-settings 的解析结果可能不同（如 MYSQL_PASS="p@ss word"）。
# load_dotenv 默认不覆盖已存在的真实环境变量（优先级：环境变量 > .env）。
load_dotenv(PROJECT_ROOT / ".env")

# ===== 统一对外地址（唯一地址源：与 FastAPI / 前端构建共用根 .env，见设计 9.3/9.4）=====
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# SECURITY WARNING: don't run with debug turned on in production!
# P1-3：默认 False（fail-safe）；本地开发在 .env 显式 DEBUG=true 打开。
DEBUG = (os.getenv("DJANGO_DEBUG") or os.getenv("DEBUG") or "false").strip().lower() == "true"

# SECRET_KEY（P1-3）：**必须显式配置**，源码内不保留任何默认密钥。
# 原实现「DEBUG=false 才校验」与「缺省 DEBUG=true」互相抵消：.env 缺失/未同步时，
# 会用源码中公开的 django-insecure-* 密钥以 DEBUG 模式启动
#（可伪造会话与 JWT、触发调试页泄露配置与 SQL、ALLOWED_HOSTS 回退 *）。
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "必须配置 DJANGO_SECRET_KEY（bysj/.env，参考 .env.example）；"
        '生成：python -c "import secrets;print(secrets.token_urlsafe(64))"'
    )

# ALLOWED_HOSTS：优先 DJANGO_ALLOWED_HOSTS（逗号分隔）；缺省从 PUBLIC_BASE_URL 推导 host；再缺省 *
_allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "").strip()
if _allowed_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(",") if h.strip()]
else:
    _public_host = urlparse(PUBLIC_BASE_URL).hostname
    ALLOWED_HOSTS = [_public_host] if _public_host else ["*"]

# P1-3/P2-12：生产环境禁止 ALLOWED_HOSTS 为 *（须由 DJANGO_ALLOWED_HOSTS 白名单化）
if not DEBUG and "*" in ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "生产环境（DEBUG=false）禁止 ALLOWED_HOSTS 为 *，请配置 DJANGO_ALLOWED_HOSTS"
    )

# CSRF 信任来源（P1-9 收敛后 /admin/api/** 走 JWT，此处主要覆盖 Session/模板页场景）：
# 生产 HTTPS 反代（Nginx 443 → Django http）必须正确，否则 POST 返回 403。
_trusted_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
if _trusted_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _trusted_origins.split(",") if o.strip()]
else:
    _public = urlparse(PUBLIC_BASE_URL)
    CSRF_TRUSTED_ORIGINS = (
        [f"{_public.scheme}://{_public.netloc}"]
        if _public.scheme in ("http", "https") and _public.netloc
        else []
    )

# HTTPS 反代支持（设计 9.4：Nginx 443 终止 TLS → http 转发给 Django）：
# PUBLIC_BASE_URL 为 https 时自动启用，保证 request.is_secure() 与绝对 URL 正确。
if PUBLIC_BASE_URL.startswith("https://"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

# Django 对外地址（预留：Django 端生成绝对 URL 时使用；缺省留空）
DJANGO_BASE_URL = os.getenv("DJANGO_BASE_URL", "").rstrip("/")

# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 第三方
    "rest_framework",
    "rest_framework_simplejwt",
    # P1-1：启用 refresh token 黑名单（可吊销），需 migrate 建表
    "rest_framework_simplejwt.token_blacklist",
    # 业务 App
    "users",
    "apps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database（共享 MySQL campus 库，端口 3307，见设计 9.1）
# 生产建议从 .env 注入；DDL 权威为 Django migrations（P0-1）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DB_CAMPUS", "campus"),
        "USER": os.getenv("MYSQL_USER", "root"),
        "PASSWORD": os.getenv("MYSQL_PASS", "123456"),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        # P1-18：默认端口与设计约定 / FastAPI 侧统一为 3307（原 FastAPI 侧默认 3306 → 漏配时一端连得上、一端连不上）
        "PORT": os.getenv("MYSQL_PORT", "3307"),
        "OPTIONS": {
            "charset": "utf8mb4",
            # B-10 / P1-18：collation 统一 utf8mb4_0900_ai_ci，且 sql_mode 与 FastAPI 侧
            # 显式设置**完全相同**。原实现只设 STRICT_TRANS_TABLES，丢掉了 MySQL 8 默认的
            # ONLY_FULL_GROUP_BY / NO_ZERO_DATE 等 → 同一句 SQL 两端行为可能不一致。
            # P1-13：会话时区固定 +08:00（MySQL 容器默认 UTC），与全栈 Asia/Shanghai、
            # FastAPI 侧时间源同基准，避免 create_time/update_time 相差 8 小时。
            "init_command": (
                "SET time_zone = '+08:00', "
                "sql_mode='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,"
                "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,"
                "NO_ENGINE_SUBSTITUTION', collation_connection = 'utf8mb4_0900_ai_ci'"
            ),
        },
        "CONN_MAX_AGE": int(os.getenv("DJANGO_CONN_MAX_AGE", "60")),  # C-05
    }
}

# Redis（T3-3：公告缓存版本失效 ann:version 用，与 FastAPI 统一配置 9.3）
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# 用户模型（P1-8）：CustomUser 映射 sys_user，首次迁移前写死
AUTH_USER_MODEL = "users.CustomUser"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization（B-10：全栈统一 Asia/Shanghai，USE_TZ=False）
LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
# 自建管理前端（方案 2，admin-web）构建产物：/admin/ 入口由 AdminWebView 提供，
# 静态资源（/static/assets/*）由 staticfiles 直接服务（runserver 自动）
ADMIN_WEB_DIST = PROJECT_ROOT / "admin-web" / "dist"
STATICFILES_DIRS = [str(ADMIN_WEB_DIST)]

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ===== DRF（P1-9：/admin/api/** 用 JWT）=====
REST_FRAMEWORK = {
    # P1-1：在 simplejwt 验签之上叠加 password_version 校验（改密即全端失效）
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "users.jwt.PasswordVersionJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": ("apps.renderers.ApiJSONRenderer",),
    "EXCEPTION_HANDLER": "apps.views.api_exception_handler",
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # P1-1：刷新即轮换，并把旧 refresh 加入黑名单（需 token_blacklist app）
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ===== 传输与响应安全（P1-2，生产 DEBUG=false 时生效）=====
# Nginx 侧同样配置 HSTS / 安全响应头（scripts/nginx/bysj.conf），
# 此处为 Django 应用层兜底（防绕过反代直连）。
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
