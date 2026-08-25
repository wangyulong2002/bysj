"""
Django settings for config project.

管理端（T0-2）：Django 5.2 LTS + DRF，共享 campus 库。
设计基线：《智慧校园信息管理系统 设计报告》v2.2
- DDL 权威：Django migrations（P0-1/B-05），sql/ 仅导出产物
- 时区：Asia/Shanghai、USE_TZ=False（B-10）
- 认证：Admin 用 Session+CSRF；/admin/api/** 用 JWT（P1-9）
- 用户：CustomUser(AbstractBaseUser, PermissionsMixin)，db_table='sys_user'（P1-8）
"""
import os
from pathlib import Path

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

SECRET_KEY = _ENV.get("DJANGO_SECRET_KEY", "django-insecure-4h&86@))7zui729*f7tg(=)%gggv(jta84&9z0&_t3s@")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _ENV.get("DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = _ENV.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
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
