# ============================================================
# bysj 后端镜像（P0-6：此前无容器化，"环境不就绪"永远是新人第一天的主题）
# ------------------------------------------------------------
# 同一镜像内含两栈（FastAPI 应用端 + Django 管理端），由 compose/运行命令决定入口：
#   FastAPI : python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
#   Django  : gunicorn config.wsgi:application --bind 0.0.0.0:8001   （生产禁用 runserver）
#
# 构建： docker build -t bysj-backend .
# 运行： 见 docker-compose.yml
# ============================================================
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 运行期依赖：tzdata（时区，全栈 Asia/Shanghai）、curl（健康检查）
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单，利用镜像层缓存
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# 复制源码
COPY server /app/server
COPY manage /app/manage
COPY sql /app/sql
COPY scripts /app/scripts

# 上传目录（生产建议挂载卷）
RUN mkdir -p /app/uploads

WORKDIR /app/server

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
