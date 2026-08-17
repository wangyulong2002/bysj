# ============================================================
# 智慧校园信息管理系统（bysj）— 一键启动/停止/日志（新手友好版）
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
#        若依后台管理  http://127.0.0.1:8081   （账号 admin / admin123）
#        若依后端      http://127.0.0.1:8080
#        FastAPI 文档  http://127.0.0.1:8000/docs
#   5. 用完一键停止：
#        make stop
#
# 【本机有哪些服务】
#   fastapi      应用后端（Python FastAPI）    端口 8000
#   ruoyi-admin  若依管理后端（Java SpringBoot）端口 8080
#   ruoyi-ui     若依管理前端（Vue）           端口 8081
#
# 【依赖环境（WSL 内）】
#   JDK 1.8、Node 16+、Python 3.11+（venv: server/venv_wsl）
#   MySQL（Docker 容器 campus-mysql，端口 3307）、Redis（Docker 容器 redis-stack）
#
# 【常见问题】
#   Q: 提示 command not found: make
#   A: 请先在 WSL 安装：  sudo apt install make
#   Q: 提示 端口被占用 / 启动失败
#   A: 先 make status 查看端口，再 make stop，或重启 WSL 后重试
#   Q: 想查看启动报错
#   A: make logs 查看各服务日志；日志文件在 logs/ 目录
#   Q: 修改了若依后端代码
#   A: 先 make build-ruoyi 重新打包，再 make ruoyi-admin 启动
# ============================================================

# 让 make 用 ">" 代替 TAB 作为命令前缀（防止复制时缩进出错）
.RECIPEPREFIX = >

# ---------- 路径配置（一般不需要修改） ----------
ROOT := $(HOME)/vibocoding/bysj
LOG_DIR := $(ROOT)/logs
JAVA_HOME_DIR := /usr/lib/jvm/java-8-openjdk-amd64
VENV_PY := $(ROOT)/server/venv_wsl/bin/python
RUIYI_ADMIN_DIR := $(ROOT)/RuoYi-Vue/ruoyi-admin
RUIYI_UI_DIR := $(ROOT)/RuoYi-Vue/ruoyi-ui
SERVER_DIR := $(ROOT)/server
JAR_FILE := $(RUIYI_ADMIN_DIR)/target/ruoyi-admin.jar

# 声明所有目标名（make 会忽略与文件同名的目录，避免歧义）
.PHONY: help doctor all ruoyi-admin ruoyi-ui fastapi build-ruoyi \
        stop stop-ruoyi-admin stop-ruoyi-ui stop-fastapi \
        status logs log-ruoyi-admin log-ruoyi-ui log-fastapi db-status init-db

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
> @echo "    make all              一键启动全部服务（后端+前端+FastAPI）"
> @echo "    make ruoyi-admin      启动若依后端   (Java, 端口 8080)"
> @echo "    make ruoyi-ui         启动若依前端   (Vue,  端口 8081)"
> @echo "    make fastapi          启动应用后端   (Python, 端口 8000)"
> @echo ""
> @echo "  停止服务："
> @echo "    make stop             停止全部服务"
> @echo "    make stop-ruoyi-admin 只停止若依后端"
> @echo "    make stop-ruoyi-ui    只停止若依前端"
> @echo "    make stop-fastapi     只停止 FastAPI"
> @echo ""
> @echo "  查看状态 / 日志："
> @echo "    make status           查看 8000/8080/8081 端口监听情况"
> @echo "    make logs             查看三个服务日志（各最后 10 行）"
> @echo "    make log-ruoyi-admin  实时查看若依后端日志（Ctrl+C 退出）"
> @echo "    make log-ruoyi-ui     实时查看若依前端日志（Ctrl+C 退出）"
> @echo "    make log-fastapi      实时查看 FastAPI 日志（Ctrl+C 退出）"
> @echo ""
> @echo "  环境 / 构建 / 数据库："
> @echo "    make doctor           环境自检（推荐第一步）"
> @echo "    make build-ruoyi      重新打包若依后端（改代码后使用）"
> @echo "    make db-status        查看 MySQL/Redis 容器运行状态"
> @echo ""
> @echo "  访问地址："
> @echo "    若依后台  http://127.0.0.1:8081   （admin / admin123）"
> @echo "    若依后端  http://127.0.0.1:8080"
> @echo "    FastAPI   http://127.0.0.1:8000/docs"
> @echo "=============================================================="

# ============================================================
# 环境自检：检查 JDK / Node / Python venv / Docker 容器 / 构建产物
# ============================================================
doctor:
> @echo "========== 环境自检（doctor）=========="
> @echo ""
> @echo "【1/6】JDK 1.8"
> @if java -version 2>&1 | grep -q '1\.8'; then echo "  通过：$(shell java -version 2>&1 | head -n1)"; else echo "  失败：未找到 JDK 1.8，请检查 JAVA_HOME 或安装 OpenJDK 8"; fi
> @echo "【2/6】Node.js"
> @if command -v node >/dev/null 2>&1; then echo "  通过：Node $$(node -v)"; else echo "  失败：未安装 Node.js（nvm 安装或 sudo apt install nodejs）"; fi
> @echo "【3/6】Python 虚拟环境（server/venv_wsl）"
> @if [ -x $(VENV_PY) ]; then echo "  通过：venv_wsl 存在，Python $$($(VENV_PY) -V 2>&1)"; else echo "  失败：缺少 server/venv_wsl，请按环境版本清单创建"; fi
> @echo "【4/6】MySQL 容器（campus-mysql）"
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$$'; then echo "  通过：campus-mysql 运行中（端口 3307）"; else echo "  失败：campus-mysql 未运行，请执行 docker start campus-mysql"; fi
> @echo "【5/6】Redis 容器（redis-stack）"
> @if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^redis-stack$$'; then echo "  通过：redis-stack 运行中（端口 6379）"; else echo "  失败：redis-stack 未运行，请执行 docker start redis-stack"; fi
> @echo "【6/6】若依后端构建产物"
> @if [ -f $(JAR_FILE) ]; then echo "  通过：$(JAR_FILE)"; else echo "  未找到：首次使用请先执行 make build-ruoyi 打包（约 3~5 分钟）"; fi
> @echo ""
> @echo "自检完成。如全部通过，现在可以 make all 启动全部服务。"

# ============================================================
# 一键启动全部服务（后端 → 前端 → FastAPI）
# ============================================================
all: ruoyi-admin ruoyi-ui fastapi
> @echo ""
> @echo "=============================================================="
> @echo "  全部服务已启动。浏览器访问："
> @echo "    若依后台  http://127.0.0.1:8081   （admin / admin123）"
> @echo "    FastAPI   http://127.0.0.1:8000/docs"
> @echo "  如需查看日志或停止：make logs / make stop"
> @echo "=============================================================="

# ============================================================
# 若依后端（ruoyi-admin）：Spring Boot，端口 8080
# ============================================================
ruoyi-admin:
> @echo "===== 启动若依后端（端口 8080）====="
> @if [ ! -f $(JAR_FILE) ]; then echo "  未找到构建产物 $(JAR_FILE)"; echo "  请先执行: make build-ruoyi"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8080 '; then echo "  8080 已被占用，先执行 make stop 或检查其他程序"; exit 1; fi
> mkdir -p $(LOG_DIR)
> cd $(RUIYI_ADMIN_DIR) && setsid env JAVA_HOME=$(JAVA_HOME_DIR) PATH="$(JAVA_HOME_DIR)/bin:$$PATH" java -jar target/ruoyi-admin.jar > $(LOG_DIR)/ruoyi-admin.log 2>&1 &
> @echo "  启动命令已执行，等待后端就绪（约 10 秒）..."
> @sleep 10
> @if ss -tlnp 2>/dev/null | grep -q ':8080 '; then echo "  成功：后端已监听 8080"; echo "  验证接口: http://127.0.0.1:8080/captchaImage"; else echo "  可能还在启动，请执行 make log-ruoyi-admin 查看日志"; fi

# ============================================================
# 若依前端（ruoyi-ui）：Vue dev server，端口 8081
# ============================================================
ruoyi-ui:
> @echo "===== 启动若依前端（端口 8081）====="
> @if [ ! -d $(RUIYI_UI_DIR)/node_modules ]; then echo "  缺少 node_modules，请先在 $(RUIYI_UI_DIR) 执行 npm install"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8081 '; then echo "  8081 已被占用，先执行 make stop 或检查其他程序"; exit 1; fi
> mkdir -p $(LOG_DIR)
> cd $(RUIYI_UI_DIR) && setsid env port=8081 npm run dev > $(LOG_DIR)/ruoyi-ui.log 2>&1 &
> @echo "  前端编译中（首次较慢，约 30~60 秒），等待就绪..."
> @sleep 15
> @if ss -tlnp 2>/dev/null | grep -q ':8081 '; then echo "  成功：前端已监听 8081"; echo "  访问: http://127.0.0.1:8081  （admin / admin123）"; else echo "  可能还在编译，请执行 make log-ruoyi-ui 查看日志"; fi

# ============================================================
# FastAPI 应用后端：uvicorn，端口 8000
# ============================================================
fastapi:
> @echo "===== 启动 FastAPI（端口 8000）====="
> @if [ ! -x $(VENV_PY) ]; then echo "  缺少虚拟环境 server/venv_wsl，请按环境版本清单创建"; exit 1; fi
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  8000 已被占用，先执行 make stop 或检查其他程序"; exit 1; fi
> mkdir -p $(LOG_DIR)
> cd $(SERVER_DIR) && setsid $(VENV_PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > $(LOG_DIR)/fastapi.log 2>&1 &
> @echo "  启动命令已执行，等待就绪（约 5 秒）..."
> @sleep 5
> @if ss -tlnp 2>/dev/null | grep -q ':8000 '; then echo "  成功：FastAPI 已监听 8000"; echo "  文档: http://127.0.0.1:8000/docs  /  健康检查: http://127.0.0.1:8000/health"; else echo "  可能还在启动，请执行 make log-fastapi 查看日志"; fi

# ============================================================
# 重新打包若依后端（修改 Java 代码 / 首次使用）
# ============================================================
build-ruoyi:
> @echo "===== 重新打包若依后端 ====="
> @echo "  将清空各模块 target 并用 Maven 重新打包，约需 3~5 分钟"
> @echo "  日志见 logs/build-ruoyi.log，请耐心等待..."
> @bash $(ROOT)/scripts/build-ruoyi.sh
> @echo "  打包完成。现在可以 make ruoyi-admin 启动后端。"

# ============================================================
# 停止服务（支持全部停止 / 单个停止）
# 原理：用 fuser -k 按端口强制杀占用进程（Linux 标准工具，WSL 自带）
#       fuser -k <port>/tcp 精确匹配 TCP 端口，不会误杀 make 自身。
# ============================================================
stop:
> @echo "===== 强制停止全部服务（按端口 8000/8080/8081）====="
> @echo "  处理端口 8080（若依后端）..."
> @if fuser -k 8080/tcp 2>/dev/null; then echo "  已强制停止：若依后端"; else echo "  8080 未监听，无需停止"; fi
> @echo "  处理端口 8081（若依前端）..."
> @if fuser -k 8081/tcp 2>/dev/null; then echo "  已强制停止：若依前端"; else echo "  8081 未监听，无需停止"; fi
> @echo "  处理端口 8000（FastAPI）..."
> @if fuser -k 8000/tcp 2>/dev/null; then echo "  已强制停止：FastAPI"; else echo "  8000 未监听，无需停止"; fi
> @echo "完成。可用 make status 确认 8000/8080/8081 是否全部释放。"

stop-ruoyi-admin:
> @echo "===== 停止若依后端（端口 8080）====="
> @if fuser -k 8080/tcp 2>/dev/null; then echo "  已强制停止：若依后端"; else echo "  8080 未监听，无需停止"; fi

stop-ruoyi-ui:
> @echo "===== 停止若依前端（端口 8081）====="
> @if fuser -k 8081/tcp 2>/dev/null; then echo "  已强制停止：若依前端"; else echo "  8081 未监听，无需停止"; fi

stop-fastapi:
> @echo "===== 停止 FastAPI（端口 8000）====="
> @if fuser -k 8000/tcp 2>/dev/null; then echo "  已强制停止：FastAPI"; else echo "  8000 未监听，无需停止"; fi

# ============================================================
# 查看状态 / 日志
# ============================================================
status:
> @echo "===== 端口监听状态（8000/8080/8081）====="
> @ss -tlnp 2>/dev/null | grep -E ':8000|:8080|:8081' || echo "  三个端口均未监听，服务未启动"

logs:
> @echo "===== 各服务日志（最后 10 行）====="
> @echo ""
> @echo "--- 若依后端 logs/ruoyi-admin.log ---"
> @tail -n 10 $(LOG_DIR)/ruoyi-admin.log 2>/dev/null || echo "(暂无日志，先执行 make ruoyi-admin)"
> @echo ""
> @echo "--- 若依前端 logs/ruoyi-ui.log ---"
> @tail -n 10 $(LOG_DIR)/ruoyi-ui.log 2>/dev/null || echo "(暂无日志，先执行 make ruoyi-ui)"
> @echo ""
> @echo "--- FastAPI logs/fastapi.log ---"
> @tail -n 10 $(LOG_DIR)/fastapi.log 2>/dev/null || echo "(暂无日志，先执行 make fastapi)"

log-ruoyi-admin:
> @echo "实时查看若依后端日志（按 Ctrl+C 退出）"
> @tail -f $(LOG_DIR)/ruoyi-admin.log 2>/dev/null || echo "(暂无日志，先执行 make ruoyi-admin)"

log-ruoyi-ui:
> @echo "实时查看若依前端日志（按 Ctrl+C 退出）"
> @tail -f $(LOG_DIR)/ruoyi-ui.log 2>/dev/null || echo "(暂无日志，先执行 make ruoyi-ui)"

log-fastapi:
> @echo "实时查看 FastAPI 日志（按 Ctrl+C 退出）"
> @tail -f $(LOG_DIR)/fastapi.log 2>/dev/null || echo "(暂无日志，先执行 make fastapi)"

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
# ============================================================
init-db:
> @echo "===== 数据库初始化（T0-4）====="
> @bash $(ROOT)/scripts/init_db.sh
