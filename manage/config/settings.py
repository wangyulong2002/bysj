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

pymysql.install_as_MySQLdb()  # Django MySQL 后端兼容（Python 3.14 无 mysqlclient 预编译包）

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # bysj/

# 从项目根 .env 读取（与 FastAPI 统一配置，见设计 9.3）
def _load_dotenv():
    """从项目根 .env 读取键值对（与 FastAPI 统一配置，见设计 9.3）。"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return {}
    data = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip()
    return data

_ENV = _load_dotenv()

# ===== 统一对外地址（唯一地址源：与 FastAPI / 前端构建共用根 .env，见设计 9.3/9.4）=====
PUBLIC_BASE_URL = _ENV.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _ENV.get("DJANGO_DEBUG", _ENV.get("DEBUG", "true")).lower() == "true"

# SECRET_KEY：生产（DEBUG=false）必须显式配置 DJANGO_SECRET_KEY，杜绝默认密钥上线（9.3）
DJANGO_SECRET_KEY = _ENV.get("DJANGO_SECRET_KEY", "").strip()
if DJANGO_SECRET_KEY:
    SECRET_KEY = DJANGO_SECRET_KEY
else:
    SECRET_KEY = "django-insecure-4h&86@))7zui729*f7tg(=)%gggv(jta84&9z0&_t3s@)"
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "生产环境（DEBUG=false）必须配置 DJANGO_SECRET_KEY（bysj/.env，参考 .env.example）"
        )

# ALLOWED_HOSTS：优先 DJANGO_ALLOWED_HOSTS（逗号分隔）；缺省从 PUBLIC_BASE_URL 推导 host；再缺省 *
_allowed_hosts = _ENV.get("DJANGO_ALLOWED_HOSTS", "").strip()
if _allowed_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(",") if h.strip()]
else:
    _public_host = urlparse(PUBLIC_BASE_URL).hostname
    ALLOWED_HOSTS = [_public_host] if _public_host else ["*"]

# CSRF 信任来源（P1-9 收敛后 /admin/api/** 走 JWT，此处主要覆盖 Session/模板页场景）：
# 生产 HTTPS 反代（Nginx 443 → Django http）必须正确，否则 POST 返回 403。
_trusted_origins = _ENV.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
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
DJANGO_BASE_URL = _ENV.get("DJANGO_BASE_URL", "").rstrip("/")

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
        "NAME": _ENV.get("MYSQL_DB_CAMPUS", "campus"),
        "USER": _ENV.get("MYSQL_USER", "root"),
        "PASSWORD": _ENV.get("MYSQL_PASS", "123456"),
        "HOST": _ENV.get("MYSQL_HOST", "127.0.0.1"),
        "PORT": _ENV.get("MYSQL_PORT", "3307"),
        "OPTIONS": {
            "charset": "utf8mb4",
            # B-10：collation 统一 utf8mb4_0900_ai_ci（与 00_create_database.sql 一致）
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES', collation_connection = 'utf8mb4_0900_ai_ci'",
        },
        "CONN_MAX_AGE": int(_ENV.get("DJANGO_CONN_MAX_AGE", "60")),  # C-05
    }
}

# Redis（T3-3：公告缓存版本失效 ann:version 用，与 FastAPI 统一配置 9.3）
REDIS_URL = _ENV.get("REDIS_URL", "redis://127.0.0.1:6379/0")

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
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
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
}
