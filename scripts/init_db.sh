#!/usr/bin/env bash
# ============================================================
# init_db.sh  数据库一键初始化（合并版，T0-4）
# 依据《智慧校园信息管理系统 设计报告》第 5 章 / 子任务 T0-4
#
# 功能：执行一次完成全部初始化（幂等，可重复执行）：
#  1. Django migrations：创建 sys_user + Django 系统表 + 全部业务表
#     （DDL 权威 P0-1：users.CustomUser → sys_user；apps → 19 业务表 + 2 字典表）
#  2. 执行 sql/init_all.sql（合并脚本，含 00/01/02/03/04）：
#     - 建库 campus（IF NOT EXISTS，utf8mb4_0900_ai_ci）
#     - 业务表 19 张（DROP+CREATE 重建，结构兼容 Django）
#     - 字典数据（sys_dict_type/sys_dict_data 重建 + DELETE+INSERT）
#     - campus_score/campus_leave 乐观锁 version 列（幂等增量）
#
# 用法：
#  ../../scripts/init_db.sh                 # 使用默认连接（Docker MySQL 3307）
#  MYSQL_HOST=x MYSQL_PORT=3307 MYSQL_PASS=y ../../scripts/init_db.sh
#
# 注意（P0-1）：DDL 权威为 Django migrations；init_all.sql 中业务表
#       先 DROP 再重建（清空业务数据），仅用于初始化/开发环境，勿在生产重复执行。
# ============================================================
set -euo pipefail

# ---- 配置（可用环境变量覆盖）----
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3307}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-123456}"

# 脚本所在目录（便于从任意 cwd 调用）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$(cd "$SCRIPT_DIR/../sql" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$ROOT/server/venv_wsl/bin/python"
DJANGO_DIR="$ROOT/manage"

# MySQL 客户端连接参数
MYSQL_ARGS=(-h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASS")
# 若密码为空，去掉 -p 参数
if [ -z "$MYSQL_PASS" ]; then
  MYSQL_ARGS=(-h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER")
fi

# 优先使用 docker 内 mysql，否则用本机 mysql
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^campus-mysql$'; then
  # 容器内 MySQL 监听默认端口（3306）与 unix socket，不再传 -h/-P/-u
  MYSQL_CMD=(docker exec -i campus-mysql mysql -uroot -p"$MYSQL_PASS")
else
  MYSQL_CMD=(mysql "${MYSQL_ARGS[@]}")
fi

echo "======================================================"
echo " 智慧校园 数据库一键初始化（执行一次完成）"
echo " 连接: $MYSQL_USER@$MYSQL_HOST:$MYSQL_PORT"
echo " SQL : $SQL_DIR/init_all.sql"
echo "======================================================"

# ---- 1/3 Django migrations（sys_user + 全部表，DDL 权威 P0-1，幂等）----
echo ""
echo "[1/3] Django migrations（创建 sys_user 与系统表）"
if [ -x "$VENV_PY" ] && [ -d "$DJANGO_DIR" ]; then
  echo "  执行: python manage.py migrate"
  (cd "$DJANGO_DIR" && "$VENV_PY" manage.py migrate) || {
    echo "  [警告] Django migrate 失败，请检查 manage/.env 与 MySQL 连接；"
    echo "         sys_user 需另行处理（P0-1 DDL 权威）。"
    exit 1
  }
else
  echo "  [跳过] 缺少 manage/ 或 venv_wsl，sys_user 需另行执行 manage.py migrate"
fi

# ---- 2/3 执行合并初始化脚本（建库 + 业务表 + 字典 + version）----
echo ""
echo "[2/3] 执行 init_all.sql（建库 + 19 业务表 + 字典 + version 列）"
"${MYSQL_CMD[@]}" --default-character-set=utf8mb4 < "$SQL_DIR/init_all.sql"
echo "  完成: init_all.sql"

# ---- 3/3 完成提示 ----
echo ""
echo "======================================================"
echo " 数据库初始化完成。"
echo " 校验："
echo "   USE campus; SHOW TABLES;                    # 业务表 + sys_user"
echo "   SELECT dict_type, dict_label, dict_value FROM sys_dict_data"
echo "     WHERE dict_type LIKE 'campus_%' LIMIT 5;  # 字典数据"
echo " 创建管理员账号（如需要）："
echo "   cd bysj/manage && ../server/venv_wsl/bin/python manage.py createsuperuser"
echo "======================================================"
