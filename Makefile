# ============================================================
# 智慧校园信息管理系统（bysj）— 一键启动/停止/日志（新手友好版）
# ============================================================
#
# ============================================================
# 常用命令速查（完整说明见底部 make help）
# ============================================================
#   环境自检   make doctor
#   一键启动   make all             （Django 管理端 + FastAPI）
#   单服务     make django / make fastapi
#   管理前端   make admin-web       （Vue3 自建管理端 :8081，方案 2）
#   小程序     make mp-dev          （编译）  make mp-sync（同步产物）
#              make mp-open         （打开微信开发者工具）
#   停止       make stop
#   状态日志   make status / make logs
#   数据库     make db-status / make init-db / make seed-demo
#   常用流程   make doctor → make all → make admin-web
#              make mp-dev + make mp-sync-watch + make mp-open
# ============================================================
#
# 【这是什么】
#   本文件是项目的"启动遥控器"。你不需要记任何命令，
#   只要在项目文件夹里输入  make 目标名  就能操作。
#
# 【三分钟上手】
#   1. 打开终端，进入项目（WSL 环境）：
#        cd ~/vibocoding/bysj
#   2. 先检查环境是否就绪（强烈建议第一步）：
#        make doctor
#   3. 一键启动全部服务：
#        make all
#   4. 打开浏览器访问：
#        Django 管理后台  http://127.0.0.1:8001/admin   （账号 admin / 设置密码）
#        FastAPI 文档     http://127.0.0.1:8000/docs
#   5. 用完一键停止：
#        make stop
#
# 【本机有哪些服务】
#   fastapi   应用后端（Python FastAPI）         端口 8000
#   django    管理后端（Python Django + DRF）    端口 8001
#   h5        应用前端（uni-app H5 dev server）  端口 8080
#   mp        应用前端（uni-app 小程序，微信开发者工具加载）
#
# 【依赖环境（WSL 内）】
#   Python 3.11+（venv: server/venv_wsl）
#   MySQL（Docker 容器 campus-mysql，端口 3307）、Redis（Docker 容器 redis-stack）
#
# 【常见问题】
#   Q: 提示 command not found: make
#   A: 请先在 WSL 安装：  sudo apt install make
#   Q: 提示 端口被占用 / 启动失败
#   A: 先 make status 查看端口，再 make stop，或重启 WSL 后重试
#   Q: 想查看启动报错
#   A: make logs 查看各服务日志；日志文件在 logs/ 目录
#   Q: 修改了 Django 代码
#   A: 开发模式 make django 即可热重载；无需重新打包
# ============================================================

# 让 make 用 ">" 代替 TAB 作为命令前缀（防止复制时缩进出错）
.RECIPEPREFIX = >

# ---------- 路径配置（一般不需要修改） ----------
ROOT := $(HOME)/vibocoding/bysj
LOG_DIR := $(ROOT)/logs
VENV_PY := $(ROOT)/server/venv_wsl/bin/python
DJANGO_DIR := $(ROOT)/manage
SERVER_DIR := $(ROOT)/server
# 微信开发者工具 CLI（Windows 侧）
WX_CLI := C:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat
# 小程序产物同步到 Windows 侧的项目目录
MP_WIN_DIR := D:\bysj-mp-weixin

# 声明所有目标名（make 会忽略与文件同名的目录，避免歧义）
.PHONY: help doctor all django fastapi \
        stop stop-django stop-fastapi \
        status logs log-django log-fastapi db-status init-db seed-demo \
        h5 h5-build mp-dev mp-build mp-sync mp-sync-watch mp-open \
        admin-web admin-web-build admin-web-stop

# ============================================================
# 默认目标：直接输入 make 就会显示这份帮助
# ============================================================
help:
> @echo "=============================================================="
> @echo "  智慧校园信息管理系统 — 命令速查"
> @echo "=============================================================="
> @echo ""
> @echo "  【推荐步骤】先 make doctor 检查环境 → make all 启动全部"
> @echo ""
> @echo "  启动服务："
> @echo "    make all              一键启动全部服务（Django 管理端 + FastAPI）"
> @echo "    make django           启动 Django 管理端 (端口 8001)"
> @echo "    make fastapi          启动应用后端   (Python, 端口 8000)"
> @echo ""
> @echo "  前端："
> @echo "    make admin-web        启动自建管理前端（Vue3 admin-web，:8081，方案 2）"
> @echo "    make h5               一键启动 H5（FastAPI + dev server，:8080）"
> @echo "    make mp-dev           编译小程序（dev 模式，配合微信开发者工具）"
> @echo "    make mp-sync          同步小程序产物 → D:/bysj-mp-weixin"
> @echo "    make mp-sync-watch    监听并自动同步小程序产物（配合 mp-dev）"
> @echo "    make mp-open          同步 + 打开微信开发者工具（需已扫码登录）"
> @echo "    make h5-build         构建 H5 产物（dist/dev/h5）"
> @echo "    make mp-build         构建小程序产物（dist/dev/mp-weixin）"
> @echo ""
> @echo "  停止服务："
> @echo "    make stop             停止全部服务"
> @echo "    make stop-django      只停止 Django 管理端"
> @echo "    make stop-fastapi     只停止 FastAPI"
> @echo ""
> @echo "  查看状态 / 日志："
> @echo "    make status           查看 8000/8001 端口监听情况"
> @echo "    make logs             查看两个服务日志（各最后 10 行）"
> @echo "    make log-django       实时查看 Django 日志（Ctrl+C 退出）"
> @echo "    make log-fastapi      实时查看 FastAPI 日志（Ctrl+C 退出）"
> @echo ""
> @echo "  环境 / 数据库："
> @echo "    make doctor           环境自检（推荐第一步）"
> @echo "    make db-status        查看 MySQL/Redis 容器运行状态"
> @echo "    make init-db          数据库初始化（建库建表 + 字典 + Django migrate）"
> @echo "    make seed-demo        灌入演示数据（每张表 >=10 条，幂等）"
> @echo ""
> @echo "  访问地址："
> @echo "    Django 管理后台  http://127.0.0.1:8001/admin"
> @echo "    FastAPI         http://127.0.0.1:8000/docs"
> @echo "=============================================================="

# ============================================================
# 环境自检：检查 Python venv / Django / Node / Docker 容器
# ============================================================
doctor:
> @echo "========== 环境自检（doctor）=========="
> @echo ""
> @echo "【1/5】Python 虚拟环境（server/venv_wsl）"
> @if [ -x $(VENV_PY) ]; then echo "  通过：venv_wsl 存在，Python $$($(VENV_PY) -V 2>&1)"; else echo "  失败：缺少 server/venv_wsl，请按环境版本清单创建"; fi
> @echo "【2/5】Django 管理端（manage/）"
> @if [ -d $(DJANGO_DIR) ] && $(VENV_PY) -c "import django" 2>/dev/null; then echo "  通过：Django $$($(VENV_PY) -c 'import django; print(django.get_version())' 2>/dev/null)"; else echo "  失败：manage/ 或 Django 未就绪，请先创建 manage 工程并安装依赖"; fi
> @echo "【3/5】Node.js"
> @if command -v node >/dev/null 2>&1; then echo "  通过：Node $$(node -v)"; else echo "  失败：未安装 Node.js（nvm 安装或 sudo apt install nodejs）"; fi
> @echo "【4/5】MySQL 容器（campus-mysql）"
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$$'; then echo "  通过：campus-mysql 运行中（端口 3307）"; else echo "  失败：campus-mysql 未运行，请执行 docker start campus-mysql"; fi
> @echo "【5/5】Redis 容器（redis-stack）"
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-stack$$'; then echo "  通过：redis-stack 运行中（端口 6379）"; else echo "  失败：redis-stack 未运行，请执行 docker start redis-stack"; fi
> @echo ""
> @echo "自检完成。如全部通过，现在可以 make all 启动全部服务。"

# ============================================================
# 一键启动全部服务（Django 管理端 → FastAPI）
# ============================================================
all: django fastapi
> @echo ""
> @echo "=============================================================="
> @echo "  全部服务已启动。浏览器访问："
> @echo "    Django 管理后台  http://127.0.0.1:8001/admin"
> @echo "    FastAPI         http://127.0.0.1:8000/docs"
> @echo "  如需查看日志或停止：make logs / make stop"
> @echo "=============================================================="

# ============================================================
# Django 管理后端（manage/）：Django + DRF，端口 8001
# ============================================================
django:
> @echo "===== 启动 Django 管理端（端口 8001）====="
> @if [ ! -d $(DJANGO_DIR) ]; then echo "  缺少 manage/ 工程，请先创建 Django 工程"; exit 1; fi
> @if [ ! -f $(ROOT)/.env ]; then echo "  缺少统一配置 $(ROOT)/.env，请先执行: cp .env.example .env"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8001 '; then echo "  8001 已被占用，先执行 make stop 或检查其他程序"; exit 1; fi
> @mkdir -p $(LOG_DIR)
> @cd $(DJANGO_DIR) && setsid $(VENV_PY) manage.py runserver 0.0.0.0:8001 > $(LOG_DIR)/django.log 2>&1 &
> @echo "  启动命令已执行，等待就绪（约 5 秒）..."
> @sleep 5
> @if ss -tlnp 2>/dev/null | grep -q ':8001 '; then echo "  成功：Django 已监听 8001"; echo "  访问: http://127.0.0.1:8001/admin"; else echo "  可能还在启动，请执行 make log-django 查看日志"; fi

# ============================================================
# FastAPI 应用后端：uvicorn，端口 8000
# ============================================================
fastapi:
> @echo "===== 启动 FastAPI（端口 8000）====="
> @if [ ! -x $(VENV_PY) ]; then echo "  缺少虚拟环境 server/venv_wsl，请按环境版本清单创建"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  8000 已被占用，先执行 make stop 或检查其他程序"; exit 1; fi
> @mkdir -p $(LOG_DIR)
> @cd $(SERVER_DIR) && setsid $(VENV_PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > $(LOG_DIR)/fastapi.log 2>&1 &
> @echo "  启动命令已执行，等待就绪（约 5 秒）..."
> @sleep 5
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  成功：FastAPI 已监听 8000"; echo "  文档: http://127.0.0.1:8000/docs  /  健康检查: http://127.0.0.1:8000/health"; else echo "  可能还在启动，请执行 make log-fastapi 查看日志"; fi

# ============================================================
# 停止服务（支持全部停止 / 单个停止）
# 原理：用 fuser -k 按端口强制杀占用进程（Linux 标准工具，WSL 自带）
#       fuser -k <port>/tcp 精确匹配 TCP 端口，不会误杀 make 自身。
# ============================================================
stop:
> @echo "===== 强制停止全部服务（按端口 8000/8001）====="
> @echo "  处理端口 8001（Django 管理端）..."
> @if fuser -k 8001/tcp 2>/dev/null; then echo "  已强制停止：Django"; else echo "  8001 未监听，无需停止"; fi
> @echo "  处理端口 8000（FastAPI）..."
> @if fuser -k 8000/tcp 2>/dev/null; then echo "  已强制停止：FastAPI"; else echo "  8000 未监听，无需停止"; fi
> @echo "完成。可用 make status 确认 8000/8001 是否全部释放。"

stop-django:
> @echo "===== 停止 Django 管理端（端口 8001）====="
> @if fuser -k 8001/tcp 2>/dev/null; then echo "  已强制停止：Django"; else echo "  8001 未监听，无需停止"; fi

stop-fastapi:
> @echo "===== 停止 FastAPI（端口 8000）====="
> @if fuser -k 8000/tcp 2>/dev/null; then echo "  已强制停止：FastAPI"; else echo "  8000 未监听，无需停止"; fi

# ============================================================
# 查看状态 / 日志
# ============================================================
status:
> @echo "===== 端口监听状态（8000/8001）====="
> @ss -tlnp 2>/dev/null | grep -E ':8000|:8001' || echo "  两个端口均未监听，服务未启动"

logs:
> @echo "===== 各服务日志（最后 10 行）====="
> @echo ""
> @echo "--- Django 管理端 logs/django.log ---"
> @tail -n 10 $(LOG_DIR)/django.log 2>/dev/null || echo "(暂无日志，先执行 make django)"
> @echo ""
> @echo "--- FastAPI logs/fastapi.log ---"
> @tail -n 10 $(LOG_DIR)/fastapi.log 2>/dev/null || echo "(暂无日志，先执行 make fastapi)"

log-django:
> @echo "实时查看 Django 日志（按 Ctrl+C 退出）"
> @tail -f $(LOG_DIR)/django.log 2>/dev/null || echo "(暂无日志，先执行 make django)"

log-fastapi:
> @echo "实时查看 FastAPI 日志（按 Ctrl+C 退出）"
> @tail -f $(LOG_DIR)/fastapi.log 2>/dev/null || echo "(暂无日志，先执行 make fastapi)"

# ============================================================
# 前端（uni-app CLI 工程，方案 A）
# 依赖：uniapp/ 为 CLI 工程（src/ + package.json），Node 24 + webpack5
# ============================================================

# H5 一键启动：起 FastAPI + npm run dev:h5（脚本 scripts/run-h5.sh）
h5:
> @bash $(ROOT)/scripts/run-h5.sh

# H5 构建产物（dist/dev/h5）
h5-build:
> @echo "===== 构建 H5（build:h5）====="
> @cd $(ROOT)/uniapp && NODE_OPTIONS=--openssl-legacy-provider npm run build:h5

# 小程序 dev 编译（热更新，配合微信开发者工具加载 D:\bysj-mp-weixin）
mp-dev:
> @echo "===== 编译小程序（dev:mp-weixin，产物 dist/dev/mp-weixin）====="
> @cd $(ROOT)/uniapp && NODE_OPTIONS=--openssl-legacy-provider npm run dev:mp-weixin

# 小程序构建产物（dist/dev/mp-weixin）
mp-build:
> @echo "===== 构建小程序（build:mp-weixin）====="
> @cd $(ROOT)/uniapp && NODE_OPTIONS=--openssl-legacy-provider npm run build:mp-weixin

# 小程序产物同步一次 → Windows（微信开发者工具项目目录）
mp-sync:
> @bash $(ROOT)/scripts/sync-mp.sh

# 监听并自动同步小程序产物（配合 mp-dev 使用，Ctrl+C 退出）
mp-sync-watch:
> @bash $(ROOT)/scripts/sync-mp.sh --watch

# 同步产物 + 打开微信开发者工具（需先扫码登录工具；未登录会提示 code 10）
mp-open:
> @echo "===== 打开微信开发者工具（D:/bysj-mp-weixin）====="
> @bash $(ROOT)/scripts/sync-mp.sh
> @powershell.exe -NoProfile -Command "Set-Location 'C:\'; & '$(WX_CLI)' open --project '$(MP_WIN_DIR)'"

# ============================================================
# 自建管理前端（方案 2：Django 接口 + Vue3 admin-web，端口 8081）
# 依赖：admin-web/（Vue3 + Vite + Element Plus，青岚校园主题）
# ============================================================
admin-web:
> @echo "===== 启动自建管理前端（admin-web，端口 8081）====="
> @if [ ! -d $(ROOT)/admin-web/node_modules ]; then echo "  首次使用先安装依赖：cd admin-web && npm install"; exit 1; fi
> @cd $(ROOT)/admin-web && npm run dev
> @echo "  访问: http://127.0.0.1:8081 （proxy /admin/api → Django 8001）"

# 构建管理前端产物（dist/，可部署到 nginx 反代 /admin/api）
admin-web-build:
> @echo "===== 构建管理前端（admin-web）====="
> @cd $(ROOT)/admin-web && npm run build

# 停止管理前端（按 8081 端口）
admin-web-stop:
> @echo "===== 停止管理前端（端口 8081）====="
> @if fuser -k 8081/tcp 2>/dev/null; then echo "  已停止 admin-web"; else echo "  8081 未监听，无需停止"; fi

# ============================================================
# 数据库 / 缓存容器状态
# ============================================================
db-status:
> @echo "===== Docker 容器状态 ====="
> @docker ps --filter "name=campus-mysql" --format "MySQL : {{.Names}}  {{.Status}}  (端口 3307)" 2>/dev/null || echo "MySQL 容器未运行"
> @docker ps --filter "name=redis-stack" --format "Redis : {{.Names}}  {{.Status}}  (端口 6379)" 2>/dev/null || echo "Redis 容器未运行"

# ============================================================
# 数据库初始化（T0-4）：一键建库建表 + 字典数据（可重复执行/幂等）
# 依赖 MySQL 容器运行（make db-status 确认）
# 注意（P0-1）：DDL 权威为 Django migrations；scripts/init_db.sh 仅作
# 演示/兼容初始化，业务表结构变更一律走 manage/ 的 makemigrations/migrate
# ============================================================
init-db:
> @echo "===== 数据库初始化（T0-4）====="
> @bash $(ROOT)/scripts/init_db.sh

# ============================================================
# 演示数据（seed-demo）：每张业务表 >= 10 条，幂等可重复执行
# 依赖：先 make init-db（表结构）；生成器 scripts/gen_seed_demo.py
# 演示账号：demo_s01~10（学生）/ demo_t01~10（教师）/ demo_c01~10（辅导员），密码 123456
# ============================================================
seed-demo:
> @echo "===== 灌入演示数据（seed_demo_data.sql，幂等）====="
> @if [ ! -f $(ROOT)/sql/seed_demo_data.sql ]; then echo "  缺少 sql/seed_demo_data.sql，先执行: python3 scripts/gen_seed_demo.py"; exit 1; fi
> @if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$$'; then \
    docker exec -i campus-mysql mysql -uroot -p123456 --default-character-set=utf8mb4 < $(ROOT)/sql/seed_demo_data.sql; \
  else \
    mysql -h127.0.0.1 -P3307 -uroot -p123456 --default-character-set=utf8mb4 < $(ROOT)/sql/seed_demo_data.sql; \
  fi
> @echo "  完成。演示账号（密码 123456）：demo_s01~10 / demo_t01~10 / demo_c01~10"
