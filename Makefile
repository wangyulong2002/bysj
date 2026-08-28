# ============================================================
# 智慧校园信息管理系统（bysj）— 一键命令（精简版）
#   常用命令已置顶；完整说明见 make help
#   统一地址源：根 .env 的 PUBLIC_BASE_URL（改一处 → make 构建全端生效）
# ============================================================

# 让 make 用 ">" 代替 TAB 作为命令前缀（防止复制时缩进出错）
.RECIPEPREFIX = >

# ---------- 路径配置（一般不需要修改） ----------
ROOT := $(HOME)/vibocoding/bysj
LOG_DIR := $(ROOT)/logs
VENV_PY := $(ROOT)/server/venv_wsl/bin/python
DJANGO_DIR := $(ROOT)/manage
SERVER_DIR := $(ROOT)/server
WX_CLI := C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat
MP_WIN_DIR := D:\bysj-mp-weixin
PUBLIC_BASE := $(shell grep -E '^PUBLIC_BASE_URL=' $(ROOT)/.env | head -1 | cut -d= -f2-)

.PHONY: help doctor all django fastapi h5 admin-web \
        stop status logs init-db seed-demo \
        h5-build mp-build mp-dev mp-sync-watch mp-open admin-web-build

# ============================================================
# 常用命令（置顶速查）
# ============================================================
help:
> @echo "=============================================================="
> @echo "  智慧校园信息管理系统 — 常用命令"
> @echo "=============================================================="
> @echo "  环境/启动/停止："
> @echo "    make doctor          环境自检（推荐第一步）"
> @echo "    make all             一键启动（Django 管理端 :8001 + FastAPI :8000）"
> @echo "    make django          启动 Django 管理端"
> @echo "    make fastapi         启动 FastAPI"
> @echo "    make h5              启动 H5（FastAPI + dev server :8080）"
> @echo "    make admin-web       启动管理前端（Vue3 admin-web :8081）"
> @echo "    make mp-dev          编译小程序（热更新，配微信开发者工具）"
> @echo "    make stop            停止全部服务（8000/8001/8081）"
> @echo ""
> @echo "  状态/日志/数据库："
> @echo "    make status          端口 + Docker 容器状态"
> @echo "    make logs            查看日志（最后 10 行）"
> @echo "    make init-db         数据库初始化（幂等）"
> @echo "    make seed-demo       灌入演示数据（幂等）"
> @echo ""
> @echo "  构建（读根 .env PUBLIC_BASE_URL 注入统一地址）："
> @echo "    make h5-build        H5 构建产物（dist/dev/h5）"
> @echo "    make mp-build        小程序构建产物（dist/dev/mp-weixin）"
> @echo "    make mp-sync-watch   监听并自动同步小程序产物（配合 mp-dev）"
> @echo "    make mp-open         同步 + 打开微信开发者工具"
> @echo "    make admin-web-build 构建管理前端（admin-web）"
> @echo ""
> @echo "  访问：管理后台 http://127.0.0.1:8001/admin | FastAPI http://127.0.0.1:8000/docs"
> @echo "=============================================================="

# ============================================================
# 环境自检
# ============================================================
doctor:
> @echo "========== 环境自检 =========="
> @if [ -x $(VENV_PY) ]; then echo "  通过：Python venv_wsl"; else echo "  失败：缺少 server/venv_wsl"; fi
> @if [ -d $(DJANGO_DIR) ] && $(VENV_PY) -c "import django" 2>/dev/null; then echo "  通过：Django $$($(VENV_PY) -c 'import django; print(django.get_version())')"; else echo "  失败：Django 未就绪"; fi
> @if command -v node >/dev/null 2>&1; then echo "  通过：Node $$(node -v)"; else echo "  失败：未安装 Node.js"; fi
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$$'; then echo "  通过：campus-mysql（3307）"; else echo "  失败：campus-mysql 未运行（docker start campus-mysql）"; fi
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-stack$$'; then echo "  通过：redis-stack（6379）"; else echo "  失败：redis-stack 未运行（docker start redis-stack）"; fi
> @echo "自检完成。全部通过可 make all 启动。"

# ============================================================
# 启动 / 停止
# ============================================================
all: django fastapi
> @echo ""
> @echo "全部服务已启动：管理后台 http://127.0.0.1:8001/admin | FastAPI http://127.0.0.1:8000/docs"

django:
> @echo "===== 启动 Django 管理端（:8001）====="
> @if [ ! -d $(DJANGO_DIR) ]; then echo "  缺少 manage/ 工程"; exit 1; fi
> @if [ ! -f $(ROOT)/.env ]; then echo "  缺少统一配置 $(ROOT)/.env（cp .env.example .env）"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8001 '; then echo "  8001 已被占用，先 make stop"; exit 1; fi
> @mkdir -p $(LOG_DIR)
> @cd $(DJANGO_DIR) && setsid $(VENV_PY) manage.py runserver 0.0.0.0:8001 > $(LOG_DIR)/django.log 2>&1 &
> @sleep 5
> @if ss -tlnp 2>/dev/null | grep -q ':8001 '; then echo "  成功：http://127.0.0.1:8001/admin"; else echo "  启动中，查看 make logs"; fi

fastapi:
> @echo "===== 启动 FastAPI（:8000）====="
> @if [ ! -x $(VENV_PY) ]; then echo "  缺少虚拟环境 server/venv_wsl"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  8000 已被占用，先 make stop"; exit 1; fi
> @mkdir -p $(LOG_DIR)
> @cd $(SERVER_DIR) && setsid $(VENV_PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > $(LOG_DIR)/fastapi.log 2>&1 &
> @sleep 5
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  成功：http://127.0.0.1:8000/docs"; else echo "  启动中，查看 make logs"; fi

stop:
> @echo "===== 停止全部服务（8000/8001/8081）====="
> @for p in 8000 8001 8081; do if fuser -k $$p/tcp 2>/dev/null; then echo "  已停止端口 $$p"; else echo "  端口 $$p 未监听"; fi; done
> @echo "完成。"

# ============================================================
# 状态 / 日志
# ============================================================
status:
> @echo "===== 端口监听 ====="
> @ss -tlnp 2>/dev/null | grep -E ':8000|:8001|:8081' || echo "  8000/8001/8081 均未监听"
> @echo "===== Docker 容器 ====="
> @docker ps --filter "name=campus-mysql" --format "MySQL : {{.Status}} (3307)" 2>/dev/null || echo "MySQL 容器未运行"
> @docker ps --filter "name=redis-stack" --format "Redis : {{.Status}} (6379)" 2>/dev/null || echo "Redis 容器未运行"

logs:
> @echo "--- Django 管理端（logs/django.log）---"
> @tail -n 10 $(LOG_DIR)/django.log 2>/dev/null || echo "(暂无日志，先 make django)"
> @echo ""
> @echo "--- FastAPI（logs/fastapi.log）---"
> @tail -n 10 $(LOG_DIR)/fastapi.log 2>/dev/null || echo "(暂无日志，先 make fastapi)"

# ============================================================
# 前端
# ============================================================
h5:
> @bash $(ROOT)/scripts/run-h5.sh

admin-web:
> @echo "===== 启动管理前端（admin-web :8081）====="
> @if [ ! -d $(ROOT)/admin-web/node_modules ]; then echo "  首次先 cd admin-web && npm install"; exit 1; fi
> @cd $(ROOT)/admin-web && npm run dev
> @echo "  访问: http://127.0.0.1:8081 （proxy /admin/api → Django 8001）"

# 构建（统一注入根 .env 的 PUBLIC_BASE_URL，一次部署全端通用）
h5-build:
> @echo "===== 构建 H5（API: $(PUBLIC_BASE)）====="
> @cd $(ROOT)/uniapp && VUE_APP_API_BASE=$(PUBLIC_BASE) NODE_OPTIONS=--openssl-legacy-provider npm run build:h5

mp-build:
> @echo "===== 构建小程序（API: $(PUBLIC_BASE)）====="
> @cd $(ROOT)/uniapp && VUE_APP_API_BASE=$(PUBLIC_BASE) NODE_OPTIONS=--openssl-legacy-provider npm run build:mp-weixin

admin-web-build:
> @echo "===== 构建管理前端（admin-web）====="
> @cd $(ROOT)/admin-web && npm run build

mp-dev:
> @echo "===== 编译小程序（dev:mp-weixin，配微信开发者工具）====="
> @cd $(ROOT)/uniapp && VUE_APP_API_BASE=$(PUBLIC_BASE) NODE_OPTIONS=--openssl-legacy-provider npm run dev:mp-weixin

mp-sync-watch:
> @bash $(ROOT)/scripts/sync-mp.sh --watch

mp-open:
> @echo "===== 同步 + 打开微信开发者工具（D:/bysj-mp-weixin）====="
> @bash $(ROOT)/scripts/sync-mp.sh
> @powershell.exe -NoProfile -Command "Set-Location 'C:\'; & '$(WX_CLI)' open --project '$(MP_WIN_DIR)'"

# ============================================================
# 数据库
# ============================================================
init-db:
> @echo "===== 数据库初始化（T0-4，幂等）====="
> @bash $(ROOT)/scripts/init_db.sh

seed-demo:
> @echo "===== 灌入演示数据（幂等）====="
> @if [ ! -f $(ROOT)/sql/seed_demo_data.sql ]; then echo "  缺少 sql/seed_demo_data.sql，先执行: python3 scripts/gen_seed_demo.py"; exit 1; fi
> @if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$$'; then \
    docker exec -i campus-mysql mysql -uroot -p123456 --default-character-set=utf8mb4 < $(ROOT)/sql/seed_demo_data.sql; \
  else \
    mysql -h127.0.0.1 -P3307 -uroot -p123456 --default-character-set=utf8mb4 < $(ROOT)/sql/seed_demo_data.sql; \
  fi
> @echo "  完成。演示账号（密码 123456）：demo_s01~10 / demo_t01~10 / demo_c01~10"
